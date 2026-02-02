"""Databricks SQL tools for querying Unity Catalog."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from databricks import sql as dbsql

from spendmend_adk.settings import settings


def _normalize_databricks_host(host: str) -> str:
    return host.rstrip("/")


def _server_hostname_from_host(host: str) -> str:
    host = _normalize_databricks_host(host)
    if host.startswith("https://"):
        return host[len("https://") :]
    if host.startswith("http://"):
        return host[len("http://") :]
    return host


def _resolve_databricks_token() -> str:
    profile = settings.databricks_profile
    if profile:
        try:
            from databricks.sdk import WorkspaceClient  # type: ignore

            client = WorkspaceClient(profile=profile)
            token = getattr(getattr(client, "config", None), "token", None)
            if token:
                return token
        except Exception:
            pass

    if settings.databricks_token:
        return settings.databricks_token
    raise ValueError("Missing Databricks token (set DATABRICKS_TOKEN).")


def _connect_sql_warehouse(http_path: str):
    if not settings.databricks_host:
        raise ValueError("Missing Databricks host (set DATABRICKS_HOST).")
    token = _resolve_databricks_token()
    return dbsql.connect(
        server_hostname=_server_hostname_from_host(settings.databricks_host),
        http_path=http_path,
        access_token=token,
    )


def _quote_ident(ident: str) -> str:
    # Databricks SQL uses backticks for identifiers.
    return "`" + ident.replace("`", "``") + "`"


def _rows_to_dicts(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append({col: row[idx] for idx, col in enumerate(columns)})
    return out


def _execute_query(
    *,
    query: str,
    http_path: str,
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
    max_rows: int = 1000,
) -> Tuple[List[Dict[str, Any]], List[str], bool, int]:
    start = time.time()
    with _connect_sql_warehouse(http_path) as conn:
        with conn.cursor() as cursor:
            if catalog:
                cursor.execute(f"USE CATALOG {_quote_ident(catalog)}")
            if schema:
                cursor.execute(f"USE SCHEMA {_quote_ident(schema)}")

            cursor.execute(query)
            description = cursor.description or []
            columns = [d[0] for d in description]

            rows = cursor.fetchmany(max_rows + 1)
            truncated = len(rows) > max_rows
            if truncated:
                rows = rows[:max_rows]

    elapsed_ms = int((time.time() - start) * 1000)
    return _rows_to_dicts(columns, rows), columns, truncated, elapsed_ms


def dbx_sql_query(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Execute a SQL query against Databricks SQL warehouse.

    Args:
        args: Dictionary containing:
            - query: str - SQL query to execute
            - warehouse_id: str - Databricks SQL warehouse ID
            - catalog: Optional[str] - Unity Catalog to use (default: session catalog)
            - schema: Optional[str] - Schema to use (default: session schema)
            - max_rows: Optional[int] - Maximum rows to return (default: 1000)
            - timeout: Optional[int] - Query timeout in seconds (default: 300)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - rows: List[Dict] - Query results as list of dictionaries
            - columns: List[str] - Column names
            - row_count: int - Number of rows returned
            - execution_time_ms: int - Query execution time
            - truncated: bool - Whether results were truncated
    """
    try:
        query = args["query"]
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        if not http_path:
            raise ValueError("Missing warehouse_id (set DATABRICKS_WAREHOUSE_ID or pass warehouse_id).")

        max_rows = int(args.get("max_rows", 1000))
        catalog = args.get("catalog")
        schema = args.get("schema")

        rows, columns, truncated, elapsed_ms = _execute_query(
            query=query,
            http_path=http_path,
            catalog=catalog,
            schema=schema,
            max_rows=max_rows,
        )
        return {
            "ok": True,
            "rows": rows,
            "columns": columns,
            "row_count": len(rows),
            "execution_time_ms": elapsed_ms,
            "truncated": truncated,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dbx_list_catalogs(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    List available Unity Catalogs.

    Args:
        args: Dictionary containing:
            - warehouse_id: str - Databricks SQL warehouse ID

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - catalogs: List[str] - List of catalog names
            - count: int - Number of catalogs
    """
    try:
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        if not http_path:
            raise ValueError("Missing warehouse_id (set DATABRICKS_WAREHOUSE_ID or pass warehouse_id).")

        rows, _, _, _ = _execute_query(query="SHOW CATALOGS", http_path=http_path, max_rows=5000)
        catalogs = []
        for row in rows:
            # Databricks returns either {"catalog": "..."} or {"catalog_name": "..."}
            name = row.get("catalog") or row.get("catalog_name") or next(iter(row.values()), None)
            if name:
                catalogs.append(str(name))
        return {"ok": True, "catalogs": catalogs, "count": len(catalogs)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dbx_list_schemas(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    List schemas in a Unity Catalog.

    Args:
        args: Dictionary containing:
            - warehouse_id: str - Databricks SQL warehouse ID
            - catalog: str - Catalog name

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - schemas: List[str] - List of schema names
            - count: int - Number of schemas
    """
    try:
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        catalog = args["catalog"]
        rows, _, _, _ = _execute_query(
            query=f"SHOW SCHEMAS IN {_quote_ident(catalog)}",
            http_path=http_path,
            max_rows=5000,
        )
        schemas = []
        for row in rows:
            name = (
                row.get("databaseName")
                or row.get("schema_name")
                or row.get("schema")
                or next(iter(row.values()), None)
            )
            if name:
                schemas.append(str(name))
        return {"ok": True, "schemas": schemas, "count": len(schemas)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dbx_list_tables(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    List tables in a schema.

    Args:
        args: Dictionary containing:
            - warehouse_id: str - Databricks SQL warehouse ID
            - catalog: str - Catalog name
            - schema: str - Schema name

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - tables: List[Dict] - List of tables with name, type, and location
            - count: int - Number of tables
    """
    try:
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        if not http_path:
            raise ValueError("Missing warehouse_id (set DATABRICKS_WAREHOUSE_ID or pass warehouse_id).")
        catalog = args["catalog"]
        schema = args["schema"]

        rows, _, _, _ = _execute_query(
            query=f"SHOW TABLES IN {_quote_ident(catalog)}.{_quote_ident(schema)}",
            http_path=http_path,
            max_rows=5000,
        )
        tables: List[Dict[str, Any]] = []
        for row in rows:
            tables.append(
                {
                    "name": row.get("tableName") or row.get("table_name") or row.get("name"),
                    "database": row.get("database") or row.get("databaseName") or row.get("schema"),
                    "is_temporary": row.get("isTemporary"),
                }
            )
        return {"ok": True, "tables": tables, "count": len(tables)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dbx_describe_table(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Describe the schema of a table.

    Args:
        args: Dictionary containing:
            - warehouse_id: str - Databricks SQL warehouse ID
            - catalog: str - Catalog name
            - schema: str - Schema name
            - table: str - Table name

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - columns: List[Dict] - Column definitions (name, type, nullable, comment)
            - partitions: List[str] - Partition columns if any
            - table_type: str - Table type (MANAGED, EXTERNAL, VIEW)
    """
    try:
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        if not http_path:
            raise ValueError("Missing warehouse_id (set DATABRICKS_WAREHOUSE_ID or pass warehouse_id).")
        catalog = args["catalog"]
        schema = args["schema"]
        table = args["table"]

        fqtn = f"{_quote_ident(catalog)}.{_quote_ident(schema)}.{_quote_ident(table)}"
        rows, _, _, _ = _execute_query(query=f"DESCRIBE {fqtn}", http_path=http_path, max_rows=5000)

        columns: List[Dict[str, Any]] = []
        for row in rows:
            col_name = row.get("col_name") or row.get("col_name ") or row.get("col_name\t")
            data_type = row.get("data_type")
            comment = row.get("comment")
            if not col_name or str(col_name).startswith("#"):
                continue
            if str(col_name).strip() == "":
                break
            columns.append(
                {
                    "name": str(col_name).strip(),
                    "type": str(data_type).strip() if data_type is not None else None,
                    "nullable": None,
                    "comment": comment,
                }
            )

        return {"ok": True, "columns": columns, "partitions": [], "table_type": "UNKNOWN"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def dbx_get_table_sample(args: Dict[str, Any], tool_context: Any) -> Dict[str, Any]:
    """
    Get a sample of rows from a table.

    Args:
        args: Dictionary containing:
            - warehouse_id: str - Databricks SQL warehouse ID
            - catalog: str - Catalog name
            - schema: str - Schema name
            - table: str - Table name
            - limit: Optional[int] - Number of rows to sample (default: 10)

    Returns:
        Dictionary containing:
            - ok: bool - Success status
            - rows: List[Dict] - Sample rows
            - columns: List[str] - Column names
            - row_count: int - Number of rows returned
    """
    try:
        http_path = args.get("warehouse_id") or settings.databricks_warehouse_id
        if not http_path:
            raise ValueError("Missing warehouse_id (set DATABRICKS_WAREHOUSE_ID or pass warehouse_id).")
        catalog = args["catalog"]
        schema = args["schema"]
        table = args["table"]
        limit = int(args.get("limit", 10))

        fqtn = f"{_quote_ident(catalog)}.{_quote_ident(schema)}.{_quote_ident(table)}"
        rows, columns, truncated, _ = _execute_query(
            query=f"SELECT * FROM {fqtn} LIMIT {limit}",
            http_path=http_path,
            max_rows=limit,
        )
        return {"ok": True, "rows": rows, "columns": columns, "row_count": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
