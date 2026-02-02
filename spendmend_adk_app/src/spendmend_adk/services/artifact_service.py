"""Artifact service configuration for filesystem-backed artifact storage.

ADK Docs:
- https://google.github.io/adk-docs/api-reference/python/google-adk.html#google.adk.artifacts.FileArtifactService
"""

from google.adk.artifacts import FileArtifactService


def create_artifact_service(root_dir: str = "./artifacts") -> FileArtifactService:
    """
    Create a FileArtifactService instance.

    Args:
        root_dir: Root directory for artifact storage (default: "./artifacts")

    Returns:
        Configured FileArtifactService instance

    Note:
        FileArtifactService stores artifacts under root_dir and supports:
        - Versioning (each save creates a new revision starting at 0)
        - Session-scoped storage when session_id is set
        - Custom metadata
        - Multiple MIME types

        Directory structure:
        {root_dir}/
          {app_name}/
            {user_id}/
              {session_id}/
                {filename}
                {filename}.1
                {filename}.2
                ...
    """
    return FileArtifactService(root_dir=root_dir)
