"""OpenAPI toolsets (ADK) for Jira, GitHub, and Databricks.

These toolsets generate `RestApiTool` instances from OpenAPI specs so agents can
call REST APIs without writing a bespoke tool per endpoint.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from google.adk.tools.openapi_tool.auth.auth_helpers import token_to_scheme_credential
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

from spendmend_adk.settings import settings

_JIRA_SPEC_URL = "https://developer.atlassian.com/cloud/jira/platform/swagger-v3.v3.json"
_GITHUB_SPEC_URL = (
    "https://raw.githubusercontent.com/github/rest-api-description/main/"
    "descriptions/api.github.com/api.github.com.json"
)


def _cache_dir() -> Path:
    default_dir = Path(__file__).resolve().parents[3] / ".openapi_cache"
    return Path(os.getenv("OPENAPI_SPEC_CACHE_DIR", str(default_dir)))


def _cache_path_for_url(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    safe_name = url.split("/")[-1] or "spec"
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in safe_name)
    return _cache_dir() / f"{safe_name}.{digest}.json"


def _load_spec_json_from_url(url: str, *, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    cache_path = _cache_path_for_url(url)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()

    _cache_dir().mkdir(parents=True, exist_ok=True)
    cache_path.write_text(resp.text, encoding="utf-8")
    return resp.json()


def _jira_basic_auth_header_value(email: str, api_token: str) -> str:
    # Jira Cloud uses HTTP Basic with email:api_token
    token_bytes = f"{email}:{api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(token_bytes).decode("ascii")


def _normalize_host(url: str) -> str:
    return url.rstrip("/")


def _resolve_databricks_host_and_token() -> Tuple[str, str]:
    """Resolve Databricks host+token.

    Preference order:
      1) WorkspaceClient(profile=...) if databricks-sdk is installed
      2) Explicit env token (DATABRICKS_TOKEN/DBX_TOKEN)
    """

    host = settings.databricks_host
    if not host:
        raise ValueError("Missing Databricks host (set DATABRICKS_HOST).")
    host = _normalize_host(host)

    profile = settings.databricks_profile
    if profile:
        try:
            from databricks.sdk import WorkspaceClient  # type: ignore

            client = WorkspaceClient(profile=profile)
            token = getattr(getattr(client, "config", None), "token", None)
            if token:
                return host, token
        except Exception:
            pass

    token = settings.databricks_token
    if not token:
        raise ValueError(
            "Missing Databricks token (set DATABRICKS_TOKEN) and unable to resolve from profile."
        )
    return host, token


def _databricks_sql_minimal_spec(host: str) -> Dict[str, Any]:
    # Minimal OpenAPI 3 spec for the Databricks SQL Statement Execution API.
    # Keeps schemas permissive (`type: object`) so it stays resilient to API evolution.
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Databricks SQL Statement Execution API (minimal)",
            "version": "0.1",
        },
        "servers": [{"url": host}],
        "paths": {
            "/api/2.0/sql/statements": {
                "post": {
                    "operationId": "executeStatement",
                    "summary": "Execute a SQL statement",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "statement": {"type": "string"},
                                        "warehouse_id": {"type": "string"},
                                        "catalog": {"type": "string"},
                                        "schema": {"type": "string"},
                                        "wait_timeout": {"type": "string"},
                                        "on_wait_timeout": {"type": "string"},
                                        "disposition": {"type": "string"},
                                        "format": {"type": "string"},
                                    },
                                    "required": ["statement", "warehouse_id"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Statement executed (sync or async)",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/2.0/sql/statements/{statement_id}": {
                "get": {
                    "operationId": "getStatement",
                    "summary": "Get statement execution status/result metadata",
                    "parameters": [
                        {
                            "name": "statement_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Statement status/result",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
            "/api/2.0/sql/statements/{statement_id}/result/chunks/{chunk_index}": {
                "get": {
                    "operationId": "getStatementChunk",
                    "summary": "Get a result chunk",
                    "parameters": [
                        {
                            "name": "statement_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "chunk_index",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Chunk payload",
                            "content": {"application/json": {"schema": {"type": "object"}}},
                        }
                    },
                    "security": [{"bearerAuth": []}],
                }
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }
        },
    }


@lru_cache(maxsize=1)
def jira_openapi_toolset() -> OpenAPIToolset:
    if not settings.jira_email or not settings.jira_api_token:
        raise ValueError("Missing Jira credentials (set JIRA_EMAIL and JIRA_API_KEY).")

    spec = _load_spec_json_from_url(_JIRA_SPEC_URL)
    spec["servers"] = [{"url": _normalize_host(settings.jira_url)}]

    auth_value = _jira_basic_auth_header_value(settings.jira_email, settings.jira_api_token)
    auth_scheme, auth_credential = token_to_scheme_credential(
        "apikey", "header", "Authorization", auth_value
    )

    # tool_filter expects *unprefixed* tool names; ADK applies tool_name_prefix at runtime.
    tool_filter = ["get_issue", "add_comment", "search_for_issues_using_jql", "get_remote_issue_links"]
    return OpenAPIToolset(
        spec_dict=spec,
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
        tool_name_prefix="jira_api",
        tool_filter=tool_filter,
    )


@lru_cache(maxsize=1)
def github_openapi_toolset() -> OpenAPIToolset:
    if not settings.github_token:
        raise ValueError("Missing GitHub token (set GITHUB_TOKEN).")

    spec = _load_spec_json_from_url(_GITHUB_SPEC_URL)

    auth_scheme, auth_credential = token_to_scheme_credential(
        "oauth2Token", "header", "Authorization", settings.github_token
    )

    tool_filter = [
        "pulls_get",
        "pulls_list_files",
        "pulls_list_reviews",
        "pulls_list_review_comments",
        "repos_get_content",
        "git_get_tree",
        "repos_get_commit",
        "repos_compare_commits",
    ]
    return OpenAPIToolset(
        spec_dict=spec,
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
        tool_name_prefix="gh_api",
        tool_filter=tool_filter,
    )


@lru_cache(maxsize=1)
def databricks_sql_openapi_toolset() -> OpenAPIToolset:
    host, token = _resolve_databricks_host_and_token()
    spec = _databricks_sql_minimal_spec(host)

    auth_scheme, auth_credential = token_to_scheme_credential(
        "oauth2Token", "header", "Authorization", token
    )

    tool_filter = ["execute_statement", "get_statement", "get_statement_chunk"]
    return OpenAPIToolset(
        spec_dict=spec,
        auth_scheme=auth_scheme,
        auth_credential=auth_credential,
        tool_name_prefix="dbx_api",
        tool_filter=tool_filter,
    )


def openapi_toolsets_for_agents() -> List[OpenAPIToolset]:
    """Convenience: OpenAPIToolset instances to expose to agents.

    ADK will call `await toolset.get_tools(...)` at runtime.
    """
    toolsets: List[OpenAPIToolset] = []
    for builder in (jira_openapi_toolset, github_openapi_toolset, databricks_sql_openapi_toolset):
        try:
            toolsets.append(builder())
        except Exception:
            # Keep agent importable even if an API isn't configured in the environment.
            continue
    return toolsets
