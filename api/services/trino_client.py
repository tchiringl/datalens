"""
Trino query client — synchronous wrapper around the trino-python-client.
All public methods are synchronous (trino's DB-API 2.0 driver is blocking),
so callers that live inside async route handlers should run them with
asyncio.to_thread() or FastAPI's BackgroundTasks if latency is a concern.
"""

import os
from typing import Any, Dict, List, Optional

import trino
from trino.exceptions import TrinoQueryError


def _quote_id(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


class TrinoClient:
    """Thin wrapper around the trino DB-API 2.0 driver."""

    def __init__(self) -> None:
        self.host: str = os.getenv("TRINO_HOST", "trino")
        self.port: int = int(os.getenv("TRINO_PORT", "8080"))
        self.user: str = os.getenv("TRINO_USER", "admin")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self, catalog: Optional[str] = None, schema: Optional[str] = None):
        """Return a new DB-API connection, optionally scoped to catalog/schema."""
        kwargs: Dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
        }
        if catalog:
            kwargs["catalog"] = catalog
        if schema:
            kwargs["schema"] = schema
        return trino.dbapi.connect(**kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, query: str, catalog: Optional[str] = None, schema: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute *query* and return results as a list of dicts.

        Column names are taken from the cursor description so callers never
        need to handle raw tuples.
        """
        conn = self._connect(catalog=catalog, schema=schema)
        try:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            if not cur.description:
                return []
            columns = [desc[0] for desc in cur.description]
            return [dict(zip(columns, row)) for row in rows]
        except TrinoQueryError as exc:
            raise RuntimeError(f"Trino query failed: {exc}") from exc
        finally:
            conn.close()

    def get_table_row_count(self, catalog: str, schema: str, table: str) -> int:
        """Return the approximate row count for *catalog.schema.table*."""
        query = f"SELECT count(*) AS cnt FROM {_quote_id(catalog)}.{_quote_id(schema)}.{_quote_id(table)}"
        try:
            results = self.execute(query)
            return int(results[0]["cnt"]) if results else 0
        except (RuntimeError, KeyError, IndexError):
            return -1

    def test_connection(self, catalog: str) -> bool:
        """Return True if Trino is reachable and *catalog* is accessible."""
        try:
            results = self.execute(f"SHOW SCHEMAS FROM \"{catalog}\"")
            return isinstance(results, list)
        except Exception:
            return False

    def list_schemas(self, catalog: str) -> List[str]:
        """Return a list of schema names in *catalog*."""
        rows = self.execute(f'SHOW SCHEMAS FROM "{catalog}"')
        # The column name varies between Trino versions ("Schema" or "schema")
        key = list(rows[0].keys())[0] if rows else "Schema"
        return [row[key] for row in rows]

    def list_tables(self, catalog: str, schema: str) -> List[str]:
        """Return a list of table names in *catalog.schema*."""
        rows = self.execute(f'SHOW TABLES FROM "{catalog}"."{schema}"')
        key = list(rows[0].keys())[0] if rows else "Table"
        return [row[key] for row in rows]

    def get_table_columns(self, catalog: str, schema: str, table: str) -> List[Dict[str, str]]:
        """Return column metadata for *catalog.schema.table*.

        Each dict has keys: ``name``, ``type``, ``nullable``, ``comment``.
        """
        rows = self.execute(f'DESCRIBE "{catalog}"."{schema}"."{table}"')
        columns = []
        for row in rows:
            # Trino DESCRIBE returns: Column, Type, Extra, Comment
            columns.append(
                {
                    "name": row.get("Column", row.get("column", "")),
                    "type": row.get("Type", row.get("type", "")),
                    "nullable": True,  # Trino does not surface nullability here
                    "comment": row.get("Comment", row.get("comment", "")),
                }
            )
        return columns

    def get_stats(self) -> Dict[str, Any]:
        """Return basic cluster info (Trino /v1/info equivalent via SQL)."""
        try:
            rows = self.execute("SELECT node_id, node_version, active FROM system.runtime.nodes")
            return {"nodes": rows}
        except Exception as exc:
            return {"error": str(exc)}
