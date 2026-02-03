"""Safe file system tools for local workspace operations.

All tools enforce path sandboxing to prevent access outside the configured
workspace root directory. Tools return structured dict responses with `ok`
status for success/failure rather than raising exceptions.

Safety Guards (Section E):
- Repo-root allowlist: ALLOWED_REPO_ROOTS env var, checked on every operation
- Max file size: 1MB read, 500KB write
- Binary detection: Check magic bytes, reject if binary
- Path traversal: Resolve symlinks, reject if outside allowlist
- Backup on write: Create .bak before overwrite

Tool Signature Pattern:
    All tools follow the pattern: func(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]
    where `args` contains the tool parameters and `tool_context` provides ADK context.
"""

from typing import Dict, Any, List, Optional
import os
import stat
import subprocess
import tempfile
import fnmatch
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from spendmend_adk.settings import settings


# =============================================================================
# Constants and Configuration
# =============================================================================

DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (general)
MAX_READ_FILE_SIZE = 1 * 1024 * 1024  # 1 MB (Section E safety guard)
MAX_WRITE_FILE_SIZE = 500 * 1024  # 500 KB (Section E safety guard)
DEFAULT_ENCODING = "utf-8"
MAX_DIRECTORY_ENTRIES = 10000
MAX_RECURSION_DEPTH = 20

# Binary file detection: common binary file magic bytes
BINARY_MAGIC_BYTES = [
    b'\x7fELF',      # ELF executables
    b'MZ',          # DOS/Windows executables
    b'\x89PNG',     # PNG images
    b'\xff\xd8',    # JPEG images
    b'GIF8',        # GIF images
    b'PK\x03\x04',  # ZIP archives
    b'\x1f\x8b',    # Gzip compressed
    b'BZh',         # Bzip2 compressed
    b'\x00\x00\x01\x00',  # ICO files
    b'%PDF',        # PDF files
]


# =============================================================================
# PatchResult Schema (Section E2)
# =============================================================================


class PatchResult(BaseModel):
    """Structured result from patch application.

    Provides detailed information about patch application success/failure,
    including backup paths for recovery and diff preview.
    """

    success: bool = Field(description="Whether the patch was applied successfully")
    target_file: str = Field(description="Path to the file that was patched")
    hunks_applied: int = Field(default=0, description="Number of hunks successfully applied")
    hunks_failed: int = Field(default=0, description="Number of hunks that failed to apply")
    backup_path: Optional[str] = Field(
        default=None, description="Path to backup file (.bak) if created"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if patch failed"
    )
    diff_preview: Optional[str] = Field(
        default=None, description="First 500 chars of resulting diff"
    )


def _get_workspace_root() -> Path:
    """Get the resolved workspace root path."""
    return Path(settings.workspace_root).resolve()


def _get_allowed_repo_roots() -> List[Path]:
    """Get the list of allowed repository roots from environment.

    The ALLOWED_REPO_ROOTS environment variable should contain a colon-separated
    list of absolute paths. If not set, defaults to workspace root only.

    Returns:
        List of resolved allowed root paths
    """
    allowed_roots_str = os.environ.get("ALLOWED_REPO_ROOTS", "")
    if allowed_roots_str:
        roots = [Path(p.strip()).resolve() for p in allowed_roots_str.split(":") if p.strip()]
        return roots
    # Default to workspace root only
    return [_get_workspace_root()]


def _is_binary_file(path: Path, check_bytes: int = 8192) -> bool:
    """Check if a file appears to be binary.

    Uses magic bytes detection and null byte scanning to identify binary files.

    Args:
        path: Path to the file to check
        check_bytes: Number of bytes to read for checking

    Returns:
        True if the file appears to be binary
    """
    try:
        with open(path, "rb") as f:
            header = f.read(min(check_bytes, 8))

            # Check magic bytes
            for magic in BINARY_MAGIC_BYTES:
                if header.startswith(magic):
                    return True

            # Read more content and check for null bytes
            f.seek(0)
            chunk = f.read(check_bytes)
            if b'\x00' in chunk:
                return True

            # Try to decode as UTF-8
            try:
                chunk.decode("utf-8")
                return False
            except UnicodeDecodeError:
                # Contains non-UTF-8 bytes, likely binary
                return True

    except Exception:
        # On error, assume binary for safety
        return True


def _create_backup(path: Path) -> Optional[str]:
    """Create a backup of a file before modification.

    Creates a .bak copy of the file in the same directory.

    Args:
        path: Path to the file to back up

    Returns:
        Path to the backup file, or None if backup failed
    """
    if not path.exists():
        return None

    backup_path = path.with_suffix(path.suffix + ".bak")

    # If backup already exists, add timestamp
    if backup_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = path.with_suffix(f"{path.suffix}.{timestamp}.bak")

    try:
        shutil.copy2(path, backup_path)
        return str(backup_path)
    except Exception as e:
        # Log but don't fail - backup is a safety measure
        import logging
        logging.getLogger(__name__).warning(f"Failed to create backup: {e}")
        return None


def _check_in_allowed_roots(path: Path) -> tuple[bool, str]:
    """Check if a path is within any allowed repository root.

    Args:
        path: Resolved absolute path to check

    Returns:
        Tuple of (is_allowed, error_message)
    """
    allowed_roots = _get_allowed_repo_roots()

    for root in allowed_roots:
        try:
            path.relative_to(root)
            return (True, "")
        except ValueError:
            continue

    return (
        False,
        f"Path '{path}' is not within allowed repo roots: {[str(r) for r in allowed_roots]}",
    )


def _validate_path_in_sandbox(path: str) -> tuple[bool, str, Optional[Path]]:
    """
    Validate that a path is within the workspace sandbox.

    Args:
        path: The path to validate (absolute or relative to workspace)

    Returns:
        Tuple of (is_valid, error_message, resolved_path)
    """
    workspace_root = _get_workspace_root()

    # Ensure workspace root exists
    if not workspace_root.exists():
        try:
            workspace_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"Cannot create workspace root: {e}", None

    # Handle relative and absolute paths
    input_path = Path(path)
    if input_path.is_absolute():
        resolved = input_path.resolve()
    else:
        resolved = (workspace_root / path).resolve()

    # Check if resolved path is within workspace
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        return False, f"Path '{path}' is outside workspace sandbox '{workspace_root}'", None

    return True, "", resolved


def read_local_file(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Safely read a file from the local workspace.

    Safety guards enforced:
    - Path must be within allowed repo roots
    - Maximum file size: 1MB (configurable)
    - Binary files are rejected

    Args:
        args: Dictionary containing:
            - path: str - File path (absolute or relative to workspace root)
            - encoding: Optional[str] - File encoding (default: "utf-8")
            - max_size: Optional[int] - Maximum file size in bytes (default: 1MB)
            - max_lines: Optional[int] - Maximum lines to read (default: 1000)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - content: str - File contents (on success)
            - path: str - Resolved file path
            - size: int - File size in bytes (on success)
            - error: str - Error message (on failure)
    """
    path = args.get("path", "")
    encoding = args.get("encoding", DEFAULT_ENCODING)
    max_size = args.get("max_size", MAX_READ_FILE_SIZE)  # Default 1MB per Section E
    max_lines = args.get("max_lines", 1000)

    if not path:
        return {"ok": False, "error": "path is required", "path": ""}

    # Validate path is within sandbox
    valid, error, resolved_path = _validate_path_in_sandbox(path)
    if not valid:
        return {"ok": False, "error": error, "path": path}

    # Additional check: path must be within allowed repo roots
    allowed, error = _check_in_allowed_roots(resolved_path)
    if not allowed:
        return {"ok": False, "error": error, "path": str(resolved_path)}

    # Check if file exists
    if not resolved_path.exists():
        return {"ok": False, "error": f"File not found: {resolved_path}", "path": str(resolved_path)}

    if not resolved_path.is_file():
        return {"ok": False, "error": f"Path is not a file: {resolved_path}", "path": str(resolved_path)}

    # Check file size
    try:
        file_size = resolved_path.stat().st_size
    except OSError as e:
        return {"ok": False, "error": f"Cannot stat file: {e}", "path": str(resolved_path)}

    if file_size > max_size:
        return {
            "ok": False,
            "error": f"File size ({file_size} bytes) exceeds maximum ({max_size} bytes)",
            "path": str(resolved_path),
            "size": file_size,
        }

    # Safety guard: Reject binary files
    if _is_binary_file(resolved_path):
        return {
            "ok": False,
            "error": "Binary file detected - cannot read binary files",
            "path": str(resolved_path),
            "size": file_size,
        }

    # Read the file
    try:
        content = resolved_path.read_text(encoding=encoding)

        # Optionally limit lines
        if max_lines and max_lines > 0:
            lines = content.split("\n")
            if len(lines) > max_lines:
                content = "\n".join(lines[:max_lines])
                content += f"\n... (truncated, showing {max_lines} of {len(lines)} lines)"

        return {
            "ok": True,
            "content": content,
            "path": str(resolved_path),
            "size": file_size,
        }
    except UnicodeDecodeError as e:
        return {"ok": False, "error": f"Encoding error: {e}", "path": str(resolved_path)}
    except OSError as e:
        return {"ok": False, "error": f"Read error: {e}", "path": str(resolved_path)}


def write_local_file(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Safely write a file to the local workspace.

    Safety guards enforced:
    - Path must be within allowed repo roots
    - Maximum content size: 500KB
    - Creates backup (.bak) before overwriting existing files

    Args:
        args: Dictionary containing:
            - path: str - File path (absolute or relative to workspace root)
            - content: str - File contents to write
            - encoding: Optional[str] - File encoding (default: "utf-8")
            - create_dirs: Optional[bool] - Create parent directories (default: True)
            - create_backup: Optional[bool] - Create .bak backup before overwrite (default: True)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - path: str - Resolved file path
            - size: int - Written file size in bytes (on success)
            - message: str - Status message
            - backup_path: str - Path to backup file if created
            - error: str - Error message (on failure)
    """
    path = args.get("path", "")
    content = args.get("content", "")
    encoding = args.get("encoding", DEFAULT_ENCODING)
    create_dirs = args.get("create_dirs", True)
    create_backup = args.get("create_backup", True)

    if not path:
        return {"ok": False, "error": "path is required", "path": ""}

    # Safety guard: Check content size
    content_size = len(content.encode(encoding) if isinstance(content, str) else content)
    if content_size > MAX_WRITE_FILE_SIZE:
        return {
            "ok": False,
            "error": f"Content size ({content_size} bytes) exceeds maximum ({MAX_WRITE_FILE_SIZE} bytes)",
            "path": path,
        }

    # Validate path is within sandbox
    valid, error, resolved_path = _validate_path_in_sandbox(path)
    if not valid:
        return {"ok": False, "error": error, "path": path}

    # Additional check: path must be within allowed repo roots
    allowed, error = _check_in_allowed_roots(resolved_path)
    if not allowed:
        return {"ok": False, "error": error, "path": str(resolved_path)}

    # Create parent directories if needed
    parent_dir = resolved_path.parent
    if not parent_dir.exists():
        if create_dirs:
            try:
                parent_dir.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                return {"ok": False, "error": f"Cannot create parent directory: {e}", "path": str(resolved_path)}
        else:
            return {"ok": False, "error": f"Parent directory does not exist: {parent_dir}", "path": str(resolved_path)}

    # Safety guard: Create backup before overwriting
    backup_path = None
    if create_backup and resolved_path.exists():
        backup_path = _create_backup(resolved_path)

    # Write the file
    try:
        resolved_path.write_text(content, encoding=encoding)
        file_size = resolved_path.stat().st_size
        result = {
            "ok": True,
            "path": str(resolved_path),
            "size": file_size,
            "message": f"Successfully wrote {file_size} bytes to {resolved_path}",
        }
        if backup_path:
            result["backup_path"] = backup_path
        return result
    except UnicodeEncodeError as e:
        return {"ok": False, "error": f"Encoding error: {e}", "path": str(resolved_path)}
    except OSError as e:
        return {"ok": False, "error": f"Write error: {e}", "path": str(resolved_path)}


def apply_patch_locally(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Apply a unified diff patch to the local workspace.

    Uses `git apply` if in a git repository, otherwise falls back to `patch` command.

    Safety guards enforced:
    - Target directory must be within allowed repo roots
    - Creates backups of modified files before patching
    - Returns structured PatchResult with recovery information

    Args:
        args: Dictionary containing:
            - patch_content: str - Unified diff/patch content
            - target_dir: str - Target directory to apply patch (must be within workspace)
            - target_file: str - Optional specific file to patch (for single-file patches)
            - dry_run: Optional[bool] - Test patch without applying (default: False)
            - strip: Optional[int] - Number of leading path components to strip (default: 1)
            - create_backup: Optional[bool] - Create .bak backups before patching (default: True)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing PatchResult fields:
            - ok: bool - Success status (alias for success)
            - success: bool - Whether patch was applied successfully
            - target_file: str - Path to patched file
            - hunks_applied: int - Number of hunks successfully applied
            - hunks_failed: int - Number of hunks that failed
            - backup_path: str - Path to backup file if created
            - error_message: str - Error message if failed
            - diff_preview: str - First 500 chars of resulting diff
            - files_modified: List[str] - List of modified files
            - files_created: List[str] - List of created files
            - files_deleted: List[str] - List of deleted files
            - conflicts: List[str] - List of conflicts if any
    """
    patch_content = args.get("patch_content", "")
    target_dir = args.get("target_dir", "")
    target_file = args.get("target_file", "")
    dry_run = args.get("dry_run", False)
    strip = args.get("strip", 1)
    create_backup = args.get("create_backup", True)

    if not patch_content:
        return {"ok": False, "success": False, "error": "patch_content is required", "error_message": "patch_content is required", "target_file": target_file}

    if not target_dir:
        return {"ok": False, "success": False, "error": "target_dir is required", "error_message": "target_dir is required", "target_file": ""}

    # Validate target directory is within sandbox
    valid, error, resolved_target = _validate_path_in_sandbox(target_dir)
    if not valid:
        return {"ok": False, "success": False, "error": error, "error_message": error, "target_file": target_file}

    # Additional check: path must be within allowed repo roots
    allowed, error = _check_in_allowed_roots(resolved_target)
    if not allowed:
        return {"ok": False, "success": False, "error": error, "error_message": error, "target_file": target_file}

    # Ensure target directory exists
    if not resolved_target.exists():
        return {"ok": False, "success": False, "error": f"Target directory does not exist: {resolved_target}", "error_message": f"Target directory does not exist: {resolved_target}", "target_file": str(resolved_target)}

    if not resolved_target.is_dir():
        return {"ok": False, "success": False, "error": f"Target path is not a directory: {resolved_target}", "error_message": f"Target path is not a directory: {resolved_target}", "target_file": str(resolved_target)}

    # Write patch to temporary file
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8') as patch_file:
            patch_file.write(patch_content)
            patch_path = patch_file.name
    except OSError as e:
        return {"ok": False, "error": f"Cannot create temporary patch file: {e}", "target_dir": str(resolved_target)}

    result = {
        "ok": False,
        "success": False,
        "target_file": target_file or str(resolved_target),
        "hunks_applied": 0,
        "hunks_failed": 0,
        "backup_path": None,
        "error_message": None,
        "diff_preview": None,
        "files_modified": [],
        "files_created": [],
        "files_deleted": [],
        "message": "",
        "conflicts": [],
        "target_dir": str(resolved_target),
    }

    # Parse patch to find files that will be modified
    files_to_patch = _extract_files_from_patch(patch_content)

    # FIX 5: Validate each file path for safety before proceeding
    is_valid, validation_error, validated_files = _validate_patch_file_paths(
        files_to_patch, resolved_target
    )
    if not is_valid:
        # Clean up temp file
        try:
            os.unlink(patch_path)
        except OSError:
            pass
        return {
            "ok": False,
            "success": False,
            "error": validation_error,
            "error_message": validation_error,
            "target_file": target_file,
            "target_dir": str(resolved_target),
        }

    # Create backups of files that will be modified (if not dry_run)
    backup_paths = {}
    if create_backup and not dry_run:
        for file_path in validated_files:
            full_path = resolved_target / file_path
            if full_path.exists():
                backup = _create_backup(full_path)
                if backup:
                    backup_paths[file_path] = backup

    try:
        # Check if we're in a git repository
        is_git_repo = (resolved_target / ".git").exists() or _is_inside_git_repo(resolved_target)

        if is_git_repo:
            # Use git apply
            apply_result = _apply_with_git(patch_path, resolved_target, dry_run, strip)
        else:
            # Use patch command
            apply_result = _apply_with_patch(patch_path, resolved_target, dry_run, strip)

        # Merge apply_result into result
        result.update(apply_result)
        result["target_dir"] = str(resolved_target)
        result["target_file"] = target_file or str(resolved_target)
        result["success"] = apply_result.get("ok", False)

        # Add backup information
        if backup_paths:
            result["backup_path"] = list(backup_paths.values())[0] if len(backup_paths) == 1 else str(backup_paths)

        # Generate diff preview for successful patches
        if result["success"] and not dry_run and result.get("files_modified"):
            diff_preview = _generate_diff_preview(resolved_target, result["files_modified"][:1])
            result["diff_preview"] = diff_preview

        return result

    finally:
        # Clean up temporary file
        try:
            os.unlink(patch_path)
        except OSError:
            pass


def _is_inside_git_repo(path: Path) -> bool:
    """Check if a path is inside a git repository."""
    current = path
    while current != current.parent:
        if (current / ".git").exists():
            return True
        current = current.parent
    return False


def _extract_files_from_patch(patch_content: str) -> List[str]:
    """Extract file paths from a unified diff patch.

    Args:
        patch_content: The patch content to parse

    Returns:
        List of file paths that will be modified by the patch
    """
    import re
    files = []

    # Match "--- a/path/to/file" or "+++ b/path/to/file" patterns
    for line in patch_content.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            # Extract path, removing the a/ or b/ prefix
            path = line[6:].split("\t")[0].strip()
            if path and path not in files and path != "/dev/null":
                files.append(path)

    return files


def _validate_patch_file_paths(
    files: List[str], target_dir: Path
) -> tuple[bool, str, List[str]]:
    """Validate each file path extracted from a patch for safety.

    FIX 5: This function validates that each file path in a patch:
    1. Does not contain absolute paths
    2. Does not contain path traversal sequences (..)
    3. Resolves to a location within allowed repo roots

    Args:
        files: List of file paths extracted from the patch
        target_dir: The resolved target directory for patch application

    Returns:
        Tuple of (is_valid, error_message, validated_files)
    """
    validated_files = []

    for file_path in files:
        # FIX 5: Reject absolute paths in patch content
        if file_path.startswith("/"):
            return (
                False,
                f"Absolute path detected in patch: {file_path}",
                [],
            )

        # FIX 5: Reject path traversal sequences
        if ".." in file_path:
            return (
                False,
                f"Path traversal detected in patch: {file_path}",
                [],
            )

        # FIX 5: Resolve full path and verify it's within allowed roots
        full_path = (target_dir / file_path).resolve()

        # Check that resolved path is still under target_dir (handles symlink attacks)
        try:
            full_path.relative_to(target_dir)
        except ValueError:
            return (
                False,
                f"Path escapes target directory after resolution: {file_path}",
                [],
            )

        # Check against allowed repo roots
        allowed, error = _check_in_allowed_roots(full_path)
        if not allowed:
            return (False, f"Patch file path {file_path}: {error}", [])

        validated_files.append(file_path)

    return (True, "", validated_files)


def _generate_diff_preview(target_dir: Path, files: List[str], max_chars: int = 500) -> Optional[str]:
    """Generate a preview of the diff after patch application.

    Args:
        target_dir: Directory where patch was applied
        files: List of modified files
        max_chars: Maximum characters for preview

    Returns:
        Diff preview string or None if unavailable
    """
    if not files:
        return None

    try:
        # Try to get git diff for the first file
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", files[0]],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout:
            preview = result.stdout[:max_chars]
            if len(result.stdout) > max_chars:
                preview += "\n... (truncated)"
            return preview

    except Exception:
        pass

    return None


def _apply_with_git(patch_path: str, target_dir: Path, dry_run: bool, strip: int) -> Dict[str, Any]:
    """Apply patch using git apply command."""
    cmd = ["git", "apply", f"-p{strip}"]

    if dry_run:
        cmd.append("--check")

    # Add verbose to get file list
    cmd.append("-v")
    cmd.append(patch_path)

    try:
        result = subprocess.run(
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            # Parse output for modified files
            files_modified = []
            files_created = []
            files_deleted = []

            for line in result.stderr.split('\n'):
                if line.startswith('Applied patch '):
                    # Extract filename from "Applied patch path/to/file cleanly."
                    parts = line.split()
                    if len(parts) >= 3:
                        files_modified.append(parts[2])

            message = "Patch applied successfully" if not dry_run else "Dry run: patch can be applied"
            return {
                "ok": True,
                "files_modified": files_modified,
                "files_created": files_created,
                "files_deleted": files_deleted,
                "message": message,
                "conflicts": [],
            }
        else:
            # Parse error output for conflicts
            conflicts = []
            error_lines = []
            for line in result.stderr.split('\n'):
                if 'error:' in line.lower() or 'conflict' in line.lower():
                    conflicts.append(line.strip())
                if line.strip():
                    error_lines.append(line.strip())

            return {
                "ok": False,
                "files_modified": [],
                "files_created": [],
                "files_deleted": [],
                "message": "Patch application failed",
                "conflicts": conflicts,
                "error": "\n".join(error_lines) or "git apply failed",
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "files_modified": [],
            "files_created": [],
            "files_deleted": [],
            "message": "Patch application timed out",
            "conflicts": [],
            "error": "git apply timed out after 60 seconds",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "files_modified": [],
            "files_created": [],
            "files_deleted": [],
            "message": "git command not found",
            "conflicts": [],
            "error": "git command not found - is git installed?",
        }


def _apply_with_patch(patch_path: str, target_dir: Path, dry_run: bool, strip: int) -> Dict[str, Any]:
    """Apply patch using patch command."""
    cmd = ["patch", f"-p{strip}", "-i", patch_path]

    if dry_run:
        cmd.append("--dry-run")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            # Parse output for modified files
            files_modified = []

            for line in result.stdout.split('\n'):
                if 'patching file' in line.lower():
                    # Extract filename from "patching file path/to/file"
                    parts = line.split()
                    if len(parts) >= 3:
                        files_modified.append(parts[2])

            message = "Patch applied successfully" if not dry_run else "Dry run: patch can be applied"
            return {
                "ok": True,
                "files_modified": files_modified,
                "files_created": [],
                "files_deleted": [],
                "message": message,
                "conflicts": [],
            }
        else:
            # Parse output for conflicts/rejections
            conflicts = []
            for line in (result.stdout + result.stderr).split('\n'):
                if 'reject' in line.lower() or 'failed' in line.lower() or 'hunk' in line.lower():
                    conflicts.append(line.strip())

            return {
                "ok": False,
                "files_modified": [],
                "files_created": [],
                "files_deleted": [],
                "message": "Patch application failed",
                "conflicts": conflicts,
                "error": result.stderr or result.stdout or "patch command failed",
            }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "files_modified": [],
            "files_created": [],
            "files_deleted": [],
            "message": "Patch application timed out",
            "conflicts": [],
            "error": "patch command timed out after 60 seconds",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "files_modified": [],
            "files_created": [],
            "files_deleted": [],
            "message": "patch command not found",
            "conflicts": [],
            "error": "patch command not found - is patch installed?",
        }


def list_directory(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    List files and directories in the local workspace.

    Args:
        args: Dictionary containing:
            - path: str - Directory path (absolute or relative to workspace root)
            - recursive: Optional[bool] - List recursively (default: False)
            - pattern: Optional[str] - Glob pattern to filter entries (e.g., "*.py")
            - max_depth: Optional[int] - Maximum recursion depth (default: 20)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - entries: List[Dict] - List of files/dirs with path, name, type, size
            - count: int - Number of entries
            - truncated: bool - Whether results were truncated
            - error: str - Error message (on failure)
    """
    path = args.get("path", "")
    recursive = args.get("recursive", False)
    pattern = args.get("pattern")
    max_depth = args.get("max_depth")

    if not path:
        return {"ok": False, "error": "path is required", "path": ""}

    # Validate path is within sandbox
    valid, error, resolved_path = _validate_path_in_sandbox(path)
    if not valid:
        return {"ok": False, "error": error, "path": path}

    # Check if directory exists
    if not resolved_path.exists():
        return {"ok": False, "error": f"Directory not found: {resolved_path}", "path": str(resolved_path)}

    if not resolved_path.is_dir():
        return {"ok": False, "error": f"Path is not a directory: {resolved_path}", "path": str(resolved_path)}

    # Set depth limit
    effective_max_depth = min(max_depth or MAX_RECURSION_DEPTH, MAX_RECURSION_DEPTH)

    entries = []
    truncated = False

    try:
        if recursive:
            entries, truncated = _list_recursive(resolved_path, pattern, effective_max_depth, 0)
        else:
            entries, truncated = _list_single_level(resolved_path, pattern)

        return {
            "ok": True,
            "entries": entries,
            "count": len(entries),
            "truncated": truncated,
            "path": str(resolved_path),
        }

    except OSError as e:
        return {"ok": False, "error": f"Directory listing error: {e}", "path": str(resolved_path)}


def _list_single_level(dir_path: Path, pattern: Optional[str]) -> tuple[List[Dict[str, Any]], bool]:
    """List entries in a single directory level."""
    entries = []
    truncated = False

    for entry in dir_path.iterdir():
        if len(entries) >= MAX_DIRECTORY_ENTRIES:
            truncated = True
            break

        # Apply pattern filter
        if pattern and not fnmatch.fnmatch(entry.name, pattern):
            continue

        entry_info = _get_entry_info(entry)
        if entry_info:
            entries.append(entry_info)

    return entries, truncated


def _list_recursive(
    dir_path: Path,
    pattern: Optional[str],
    max_depth: int,
    current_depth: int
) -> tuple[List[Dict[str, Any]], bool]:
    """Recursively list directory entries."""
    entries = []
    truncated = False

    if current_depth > max_depth:
        return entries, False

    try:
        for entry in dir_path.iterdir():
            if len(entries) >= MAX_DIRECTORY_ENTRIES:
                truncated = True
                break

            # Apply pattern filter
            if pattern and not fnmatch.fnmatch(entry.name, pattern):
                # Still recurse into directories even if they don't match pattern
                if entry.is_dir():
                    sub_entries, sub_truncated = _list_recursive(
                        entry, pattern, max_depth, current_depth + 1
                    )
                    entries.extend(sub_entries)
                    if sub_truncated:
                        truncated = True
                continue

            entry_info = _get_entry_info(entry)
            if entry_info:
                entries.append(entry_info)

            # Recurse into directories
            if entry.is_dir():
                sub_entries, sub_truncated = _list_recursive(
                    entry, pattern, max_depth, current_depth + 1
                )
                entries.extend(sub_entries)
                if sub_truncated:
                    truncated = True

    except PermissionError:
        pass  # Skip directories we can't access

    return entries, truncated


def _get_entry_info(entry: Path) -> Optional[Dict[str, Any]]:
    """Get information about a directory entry."""
    try:
        stat_info = entry.stat()
        return {
            "path": str(entry),
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "size": stat_info.st_size if entry.is_file() else 0,
        }
    except OSError:
        return None


def get_file_info(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Get information about a file or directory.

    Args:
        args: Dictionary containing:
            - path: str - File or directory path (absolute or relative to workspace root)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - path: str - Resolved path
            - name: str - File/directory name
            - type: str - "file", "directory", "symlink", or "other"
            - size: int - Size in bytes
            - modified: str - Last modified timestamp (ISO format)
            - created: str - Creation timestamp (ISO format, if available)
            - readable: bool - Whether file is readable
            - writable: bool - Whether file is writable
            - executable: bool - Whether file is executable
            - mode: str - File mode string (e.g., "-rw-r--r--")
            - error: str - Error message (on failure)
    """
    path = args.get("path", "")

    if not path:
        return {"ok": False, "error": "path is required", "path": ""}

    # Validate path is within sandbox
    valid, error, resolved_path = _validate_path_in_sandbox(path)
    if not valid:
        return {"ok": False, "error": error, "path": path}

    # Check if path exists
    if not resolved_path.exists():
        return {"ok": False, "error": f"Path not found: {resolved_path}", "path": str(resolved_path)}

    try:
        stat_info = resolved_path.stat()

        # Determine type
        if resolved_path.is_file():
            path_type = "file"
        elif resolved_path.is_dir():
            path_type = "directory"
        elif resolved_path.is_symlink():
            path_type = "symlink"
        else:
            path_type = "other"

        # Get timestamps
        modified = datetime.fromtimestamp(stat_info.st_mtime).isoformat()

        # st_birthtime may not be available on all systems
        try:
            created = datetime.fromtimestamp(stat_info.st_birthtime).isoformat()
        except AttributeError:
            created = datetime.fromtimestamp(stat_info.st_ctime).isoformat()

        # Check permissions
        readable = os.access(resolved_path, os.R_OK)
        writable = os.access(resolved_path, os.W_OK)
        executable = os.access(resolved_path, os.X_OK)

        return {
            "ok": True,
            "path": str(resolved_path),
            "name": resolved_path.name,
            "type": path_type,
            "size": stat_info.st_size,
            "modified": modified,
            "created": created,
            "readable": readable,
            "writable": writable,
            "executable": executable,
            "mode": stat.filemode(stat_info.st_mode),
        }

    except OSError as e:
        return {"ok": False, "error": f"Cannot get file info: {e}", "path": str(resolved_path)}


def create_directory(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Create a directory in the local workspace.

    Args:
        args: Dictionary containing:
            - path: str - Directory path (absolute or relative to workspace root)
            - parents: Optional[bool] - Create parent directories (default: True)
            - exist_ok: Optional[bool] - Don't error if exists (default: True)
        tool_context: ADK tool context (unused but required for signature)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - path: str - Resolved directory path
            - message: str - Status message
            - created: bool - Whether directory was actually created (vs already existed)
            - error: str - Error message (on failure)
    """
    path = args.get("path", "")
    parents = args.get("parents", True)
    exist_ok = args.get("exist_ok", True)

    if not path:
        return {"ok": False, "error": "path is required", "path": ""}

    # Validate path is within sandbox
    valid, error, resolved_path = _validate_path_in_sandbox(path)
    if not valid:
        return {"ok": False, "error": error, "path": path}

    # Check if already exists
    if resolved_path.exists():
        if resolved_path.is_dir():
            if exist_ok:
                return {
                    "ok": True,
                    "path": str(resolved_path),
                    "message": f"Directory already exists: {resolved_path}",
                    "created": False,
                }
            else:
                return {
                    "ok": False,
                    "error": f"Directory already exists: {resolved_path}",
                    "path": str(resolved_path),
                }
        else:
            return {
                "ok": False,
                "error": f"Path exists but is not a directory: {resolved_path}",
                "path": str(resolved_path),
            }

    # Create the directory
    try:
        resolved_path.mkdir(parents=parents, exist_ok=exist_ok)
        return {
            "ok": True,
            "path": str(resolved_path),
            "message": f"Successfully created directory: {resolved_path}",
            "created": True,
        }
    except OSError as e:
        return {"ok": False, "error": f"Cannot create directory: {e}", "path": str(resolved_path)}


__all__ = [
    # Schema
    "PatchResult",
    # Tool functions
    "read_local_file",
    "write_local_file",
    "apply_patch_locally",
    "list_directory",
    "get_file_info",
    "create_directory",
    # Safety helpers (exported for testing)
    "MAX_READ_FILE_SIZE",
    "MAX_WRITE_FILE_SIZE",
]
