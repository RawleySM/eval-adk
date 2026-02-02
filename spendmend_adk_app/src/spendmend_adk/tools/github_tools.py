"""GitHub integration tools for repository operations."""

from __future__ import annotations

import fnmatch
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from spendmend_adk.settings import settings


def _run_git(args: List[str], *, cwd: Optional[str] = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc.stdout.strip()


def _with_github_token_in_url(clone_url: str) -> str:
    token = settings.github_token
    if not token:
        return clone_url
    if clone_url.startswith("https://") and "@github.com" not in clone_url:
        # Use x-access-token format to avoid username prompts.
        return clone_url.replace("https://", f"https://x-access-token:{token}@", 1)
    return clone_url


def _parse_pr_url(pr_url: str) -> Tuple[str, str, int]:
    """
    Supports:
      - https://github.com/{owner}/{repo}/pull/{number}
      - https://api.github.com/repos/{owner}/{repo}/pulls/{number}
    """
    u = urlparse(pr_url)
    path = u.path.rstrip("/")
    m = re.match(r"^/([^/]+)/([^/]+)/pull/([0-9]+)$", path)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    m = re.match(r"^/repos/([^/]+)/([^/]+)/pulls/([0-9]+)$", path)
    if m:
        return m.group(1), m.group(2), int(m.group(3))
    raise ValueError(f"Unrecognized PR URL: {pr_url}")


def _gh_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"
    if extra:
        headers.update(extra)
    return headers


def gh_clone_at_ref(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Clone a repository at a specific ref (commit, branch, or tag).

    Args:
        args: Dictionary containing:
            - clone_url: str - Repository clone URL
            - ref: str - Git ref (commit SHA, branch name, or tag)
            - target_dir: str - Local directory to clone into
            - depth: Optional[int] - Clone depth for shallow clone (default: None for full clone)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - workdir: str - Local working directory path
            - commit_sha: str - Actual commit SHA checked out
            - message: str - Status message
    """
    try:
        clone_url = args["clone_url"]
        ref = args["ref"]
        target_dir = args["target_dir"]
        depth = args.get("depth")

        target_path = Path(target_dir)
        if target_path.exists() and any(target_path.iterdir()):
            raise ValueError(f"target_dir is not empty: {target_dir}")

        clone_url = _with_github_token_in_url(clone_url)
        clone_cmd = ["clone"]
        if depth:
            clone_cmd += ["--depth", str(int(depth))]
        clone_cmd += [clone_url, target_dir]
        _run_git(clone_cmd)

        try:
            _run_git(["-C", target_dir, "checkout", ref])
        except Exception:
            # Fetch the ref explicitly then retry.
            _run_git(["-C", target_dir, "fetch", "--all", "--tags"])
            _run_git(["-C", target_dir, "checkout", ref])

        commit_sha = _run_git(["-C", target_dir, "rev-parse", "HEAD"])
        return {
            "ok": True,
            "workdir": str(target_path),
            "commit_sha": commit_sha,
            "message": f"Cloned and checked out {ref}.",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def gh_read_file(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Read a file from a local git repository.

    Args:
        args: Dictionary containing:
            - workdir: str - Local repository working directory
            - file_path: str - Relative path to file within repository
            - encoding: Optional[str] - File encoding (default: "utf-8")

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - content: str - File contents
            - path: str - File path
            - size: int - File size in bytes
    """
    try:
        workdir = args["workdir"]
        file_path = args["file_path"]
        encoding = args.get("encoding", "utf-8")

        repo_root = Path(workdir).resolve()
        full_path = (repo_root / file_path).resolve()
        if repo_root not in full_path.parents and repo_root != full_path:
            raise ValueError("file_path escapes workdir")

        content = full_path.read_text(encoding=encoding)
        return {
            "ok": True,
            "content": content,
            "path": str(full_path),
            "size": full_path.stat().st_size,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def gh_list_tree(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    List files in a directory tree within a repository.

    Args:
        args: Dictionary containing:
            - workdir: str - Local repository working directory
            - path: str - Directory path to list (default: "." for root)
            - recursive: Optional[bool] - List recursively (default: False)
            - pattern: Optional[str] - Glob pattern to filter files (e.g., "*.py")

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - files: List[Dict] - List of files with path, type, and size
            - count: int - Total number of files
    """
    try:
        workdir = Path(args["workdir"]).resolve()
        path = args.get("path", ".")
        recursive = bool(args.get("recursive", False))
        pattern = args.get("pattern")

        start = (workdir / path).resolve()
        if workdir not in start.parents and workdir != start:
            raise ValueError("path escapes workdir")
        if not start.exists():
            raise FileNotFoundError(str(start))

        results: List[Dict[str, Any]] = []

        if start.is_file():
            rel = str(start.relative_to(workdir))
            if not pattern or fnmatch.fnmatch(rel, pattern):
                results.append({"path": rel, "type": "file", "size": start.stat().st_size})
            return {"ok": True, "files": results, "count": len(results)}

        if recursive:
            for root, dirs, files in os.walk(start):
                root_path = Path(root)
                for name in files:
                    fp = root_path / name
                    rel = str(fp.relative_to(workdir))
                    if pattern and not fnmatch.fnmatch(rel, pattern):
                        continue
                    results.append({"path": rel, "type": "file", "size": fp.stat().st_size})
                for name in dirs:
                    dp = root_path / name
                    rel = str(dp.relative_to(workdir))
                    results.append({"path": rel, "type": "dir", "size": 0})
        else:
            for entry in sorted(start.iterdir(), key=lambda p: p.name):
                rel = str(entry.relative_to(workdir))
                if pattern and entry.is_file() and not fnmatch.fnmatch(rel, pattern):
                    continue
                results.append(
                    {
                        "path": rel,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": 0 if entry.is_dir() else entry.stat().st_size,
                    }
                )
        return {"ok": True, "files": results, "count": len(results)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def gh_fetch_pr_patch(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Fetch the unified diff/patch for a merged pull request.

    Args:
        args: Dictionary containing:
            - pr_url: str - GitHub pull request URL
            - format: Optional[str] - "diff" or "patch" (default: "patch")

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - patch: str - Unified diff/patch content
            - pr_number: int - Pull request number
            - files_changed: int - Number of files changed
            - additions: int - Total line additions
            - deletions: int - Total line deletions
    """
    try:
        pr_url = args["pr_url"]
        fmt = args.get("format", "patch")
        if fmt not in ("diff", "patch"):
            raise ValueError('format must be "diff" or "patch"')

        owner, repo, number = _parse_pr_url(pr_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        accept = "application/vnd.github.v3.patch" if fmt == "patch" else "application/vnd.github.v3.diff"

        # Fetch metadata as JSON
        meta = requests.get(api_url, headers=_gh_headers(), timeout=60)
        meta.raise_for_status()
        meta_json = meta.json()

        # Fetch patch/diff
        txt = requests.get(api_url, headers=_gh_headers({"Accept": accept}), timeout=60)
        txt.raise_for_status()
        return {
            "ok": True,
            "patch": txt.text,
            "pr_number": number,
            "files_changed": meta_json.get("changed_files"),
            "additions": meta_json.get("additions"),
            "deletions": meta_json.get("deletions"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def gh_get_pr_details(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Get detailed information about a pull request.

    Args:
        args: Dictionary containing:
            - pr_url: str - GitHub pull request URL
            - include_comments: Optional[bool] - Include comments (default: False)
            - include_reviews: Optional[bool] - Include reviews (default: False)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - pr: Dict - PR details (number, title, description, state, author, etc.)
            - base_sha: str - Base commit SHA
            - head_sha: str - Head commit SHA
            - merged_sha: Optional[str] - Merge commit SHA if merged
            - comments: Optional[List[Dict]] - Comments if requested
            - reviews: Optional[List[Dict]] - Reviews if requested
    """
    try:
        pr_url = args["pr_url"]
        include_comments = bool(args.get("include_comments", False))
        include_reviews = bool(args.get("include_reviews", False))

        owner, repo, number = _parse_pr_url(pr_url)
        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        resp = requests.get(api_url, headers=_gh_headers(), timeout=60)
        resp.raise_for_status()
        pr = resp.json()

        out: Dict[str, Any] = {
            "ok": True,
            "pr": {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "body": pr.get("body"),
                "state": pr.get("state"),
                "html_url": pr.get("html_url"),
                "author": ((pr.get("user") or {}).get("login")),
                "merged": pr.get("merged"),
                "merged_at": pr.get("merged_at"),
            },
            "base_sha": ((pr.get("base") or {}).get("sha")),
            "head_sha": ((pr.get("head") or {}).get("sha")),
            "merged_sha": pr.get("merge_commit_sha"),
        }

        if include_comments:
            comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}/comments"
            comments = []
            page = 1
            while True:
                c = requests.get(
                    comments_url,
                    headers=_gh_headers(),
                    params={"per_page": 100, "page": page},
                    timeout=60,
                )
                c.raise_for_status()
                batch = c.json()
                comments.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            out["comments"] = comments

        if include_reviews:
            reviews_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews"
            reviews = []
            page = 1
            while True:
                r = requests.get(
                    reviews_url,
                    headers=_gh_headers(),
                    params={"per_page": 100, "page": page},
                    timeout=60,
                )
                r.raise_for_status()
                batch = r.json()
                reviews.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            out["reviews"] = reviews

        return out
    except Exception as e:
        return {"ok": False, "error": str(e)}


def gh_get_file_changes(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Get list of file changes in a pull request.

    Args:
        args: Dictionary containing:
            - pr_url: str - GitHub pull request URL

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - files: List[Dict] - List of changed files with path, status, additions, deletions
            - total_changes: int - Total number of file changes
    """
    try:
        pr_url = args["pr_url"]
        owner, repo, number = _parse_pr_url(pr_url)
        files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files"

        files: List[Dict[str, Any]] = []
        page = 1
        while True:
            resp = requests.get(
                files_url,
                headers=_gh_headers(),
                params={"per_page": 100, "page": page},
                timeout=60,
            )
            resp.raise_for_status()
            batch = resp.json()
            for f in batch:
                files.append(
                    {
                        "path": f.get("filename"),
                        "status": f.get("status"),
                        "additions": f.get("additions"),
                        "deletions": f.get("deletions"),
                        "changes": f.get("changes"),
                    }
                )
            if len(batch) < 100:
                break
            page += 1
        return {"ok": True, "files": files, "total_changes": len(files)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
