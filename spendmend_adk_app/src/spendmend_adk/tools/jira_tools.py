"""Jira integration tools for searching, getting, and updating issues."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from spendmend_adk.settings import settings


def _jira_headers() -> Dict[str, str]:
    if not settings.jira_email or not settings.jira_api_token:
        raise ValueError("Missing Jira credentials (set JIRA_EMAIL and JIRA_API_KEY).")
    if not settings.jira_url:
        raise ValueError("Missing Jira URL (set JIRA_URL).")
    return {"Accept": "application/json"}


def _jira_auth() -> tuple[str, str]:
    if not settings.jira_email or not settings.jira_api_token:
        raise ValueError("Missing Jira credentials (set JIRA_EMAIL and JIRA_API_KEY).")
    return (settings.jira_email, settings.jira_api_token)


def _jira_url(path: str) -> str:
    base = settings.jira_url.rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _text_to_adf_doc(text: str) -> Dict[str, Any]:
    # Atlassian Document Format (ADF) minimal "doc" with one paragraph.
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def jira_search_assigned(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Search for Jira issues assigned to a specific user.

    Args:
        args: Dictionary containing:
            - assignee: str - Username to search for
            - status: Optional[str] - Filter by status (e.g., "In Progress", "Open")
            - project: Optional[str] - Filter by project key
            - max_results: Optional[int] - Maximum number of results to return (default: 50)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - issues: List[Dict] - List of matching issues
            - count: int - Total number of results
    """
    try:
        assignee = args["assignee"]
        status = args.get("status")
        project = args.get("project")
        max_results = int(args.get("max_results", 50))

        jql_parts = [f'assignee = "{assignee}"']
        if project:
            jql_parts.append(f'project = "{project}"')
        if status:
            jql_parts.append(f'status = "{status}"')
        jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"

        resp = requests.get(
            _jira_url("/rest/api/3/search"),
            headers=_jira_headers(),
            auth=_jira_auth(),
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,assignee,updated,created,issuetype,project",
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        issues = []
        for issue in data.get("issues", []):
            fields = issue.get("fields") or {}
            issues.append(
                {
                    "key": issue.get("key"),
                    "summary": (fields.get("summary") or ""),
                    "status": ((fields.get("status") or {}).get("name")),
                    "assignee": ((fields.get("assignee") or {}).get("displayName")),
                    "updated": fields.get("updated"),
                    "created": fields.get("created"),
                    "issue_type": ((fields.get("issuetype") or {}).get("name")),
                    "project": ((fields.get("project") or {}).get("key")),
                }
            )
        return {"ok": True, "issues": issues, "count": data.get("total", len(issues))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def jira_get_issue(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Get detailed information about a specific Jira issue.

    Args:
        args: Dictionary containing:
            - issue_key: str - Jira issue key (e.g., "SPEND-123")
            - include_comments: Optional[bool] - Include comments (default: False)
            - include_attachments: Optional[bool] - Include attachments (default: False)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - issue: Dict - Issue details (key, summary, description, status, assignee, etc.)
            - comments: Optional[List[Dict]] - Comments if requested
            - attachments: Optional[List[Dict]] - Attachments if requested
    """
    try:
        issue_key = args["issue_key"]
        include_comments = bool(args.get("include_comments", False))
        include_attachments = bool(args.get("include_attachments", False))

        resp = requests.get(
            _jira_url(f"/rest/api/3/issue/{issue_key}"),
            headers=_jira_headers(),
            auth=_jira_auth(),
            params={"fields": "*all"},
            timeout=60,
        )
        resp.raise_for_status()
        issue = resp.json()

        fields = issue.get("fields") or {}
        out: Dict[str, Any] = {
            "ok": True,
            "issue": {
                "key": issue.get("key"),
                "id": issue.get("id"),
                "summary": fields.get("summary"),
                "description": fields.get("description"),
                "status": ((fields.get("status") or {}).get("name")),
                "assignee": ((fields.get("assignee") or {}).get("displayName")),
                "reporter": ((fields.get("reporter") or {}).get("displayName")),
                "labels": fields.get("labels"),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "project": ((fields.get("project") or {}).get("key")),
                "issue_type": ((fields.get("issuetype") or {}).get("name")),
            },
        }

        if include_comments:
            c = requests.get(
                _jira_url(f"/rest/api/3/issue/{issue_key}/comment"),
                headers=_jira_headers(),
                auth=_jira_auth(),
                timeout=60,
            )
            c.raise_for_status()
            comments = []
            for com in (c.json().get("comments") or []):
                comments.append(
                    {
                        "id": com.get("id"),
                        "author": ((com.get("author") or {}).get("displayName")),
                        "created": com.get("created"),
                        "updated": com.get("updated"),
                        "body": com.get("body"),
                    }
                )
            out["comments"] = comments

        if include_attachments:
            attachments = []
            for att in (fields.get("attachment") or []):
                attachments.append(
                    {
                        "id": att.get("id"),
                        "filename": att.get("filename"),
                        "size": att.get("size"),
                        "mime_type": att.get("mimeType"),
                        "created": att.get("created"),
                        "author": ((att.get("author") or {}).get("displayName")),
                        "content": att.get("content"),
                    }
                )
            out["attachments"] = attachments

        return out
    except Exception as e:
        return {"ok": False, "error": str(e)}


def jira_add_comment(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Add a comment to a Jira issue.

    Args:
        args: Dictionary containing:
            - issue_key: str - Jira issue key
            - comment: str - Comment text (supports Jira markdown)
            - visibility: Optional[str] - Visibility restriction (e.g., "Developers")

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - comment_id: str - ID of the created comment
            - message: str - Status message
    """
    try:
        issue_key = args["issue_key"]
        comment = args["comment"]

        payload: Dict[str, Any] = {"body": _text_to_adf_doc(comment)}
        # NOTE: Jira Cloud supports comment visibility restrictions, but the exact shape depends on
        # instance permissions; leave unconfigured unless explicitly requested.

        resp = requests.post(
            _jira_url(f"/rest/api/3/issue/{issue_key}/comment"),
            headers={**_jira_headers(), "Content-Type": "application/json"},
            auth=_jira_auth(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"ok": True, "comment_id": data.get("id"), "message": "Comment added."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def jira_assign_issue(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Assign a Jira issue to a user.

    Args:
        args: Dictionary containing:
            - issue_key: str - Jira issue key
            - assignee: str - Username to assign to (or null to unassign)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - message: str - Status message
    """
    try:
        issue_key = args["issue_key"]
        assignee = args.get("assignee")
        # Jira Cloud expects accountId for assignee. This tool accepts a raw string and passes it through.
        payload = {"accountId": assignee} if assignee else {"accountId": None}
        resp = requests.put(
            _jira_url(f"/rest/api/3/issue/{issue_key}/assignee"),
            headers={**_jira_headers(), "Content-Type": "application/json"},
            auth=_jira_auth(),
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        return {"ok": True, "message": "Assignee updated."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def jira_transition_issue(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Transition a Jira issue to a different status.

    Args:
        args: Dictionary containing:
            - issue_key: str - Jira issue key
            - transition: str - Transition name or ID (e.g., "In Progress", "Done")
            - comment: Optional[str] - Optional comment to add with transition

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - message: str - Status message
    """
    try:
        issue_key = args["issue_key"]
        transition = args["transition"]
        comment = args.get("comment")

        # Get available transitions
        tr = requests.get(
            _jira_url(f"/rest/api/3/issue/{issue_key}/transitions"),
            headers=_jira_headers(),
            auth=_jira_auth(),
            timeout=60,
        )
        tr.raise_for_status()
        transitions = tr.json().get("transitions") or []
        chosen = None
        for t in transitions:
            if str(t.get("id")) == str(transition) or (t.get("name") or "").lower() == str(transition).lower():
                chosen = t
                break
        if not chosen:
            names = [t.get("name") for t in transitions]
            raise ValueError(f"Transition '{transition}' not found. Available: {names}")

        payload: Dict[str, Any] = {"transition": {"id": chosen.get("id")}}
        if comment:
            payload["update"] = {"comment": [{"add": {"body": _text_to_adf_doc(comment)}}]}

        do = requests.post(
            _jira_url(f"/rest/api/3/issue/{issue_key}/transitions"),
            headers={**_jira_headers(), "Content-Type": "application/json"},
            auth=_jira_auth(),
            json=payload,
            timeout=60,
        )
        do.raise_for_status()
        return {"ok": True, "message": f"Transitioned via '{chosen.get('name')}'."}
    except Exception as e:
        return {"ok": False, "error": str(e)}
