"""
DatabaseTool - Unified database management and SQL execution tool for Jarvis.
Supports SQLite, MySQL, and PostgreSQL operations (queries, tables listing, schema inspection, and CSV export).
"""

import csv
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class DatabaseTool:
    """Unified database operations for SQLite, MySQL, and PostgreSQL."""

    def __init__(self, workspace: Optional[str] = None):
        self.workspace = Path(workspace).resolve() if workspace else None

    def _resolve_sqlite_path(self, db_path: str) -> Path:
        p = Path(db_path).expanduser().resolve()
        if self.workspace and not str(p).startswith(str(self.workspace)):
            # If not explicitly under workspace, allow relative to cwd
            pass
        return p

    def _get_connection(
        self,
        db_type: str = "sqlite",
        db_name: str = "database.db",
        host: str = "localhost",
        port: Optional[int] = None,
        user: str = "root",
        password: str = "",
    ):
        db_type = (db_type or "sqlite").lower()

        if db_type == "sqlite":
            path = self._resolve_sqlite_path(db_name)
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            return conn, db_type

        elif db_type in ("mysql", "mariadb"):
            try:
                import pymysql
                conn = pymysql.connect(
                    host=host,
                    port=port or 3306,
                    user=user,
                    password=password,
                    database=db_name,
                    cursorclass=pymysql.cursors.DictCursor,
                )
                return conn, db_type
            except ImportError:
                raise ImportError("MySQL driver 'pymysql' is not installed. Please install it with 'pip install pymysql'.")

        elif db_type in ("postgres", "postgresql"):
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(
                    host=host,
                    port=port or 5432,
                    user=user,
                    password=password,
                    dbname=db_name,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
                return conn, db_type
            except ImportError:
                raise ImportError("PostgreSQL driver 'psycopg2' is not installed. Please install it with 'pip install psycopg2-binary'.")

        else:
            raise ValueError(f"Unsupported database type: '{db_type}'. Supported: sqlite, mysql, postgresql.")

    def query(
        self,
        query: str,
        db_type: str = "sqlite",
        db_name: str = "database.db",
        host: str = "localhost",
        port: Optional[int] = None,
        user: str = "root",
        password: str = "",
        max_rows: int = 100,
    ) -> Dict[str, Any]:
        """
        Execute an arbitrary SQL query and return results or execution status.
        """
        try:
            conn, resolved_type = self._get_connection(
                db_type=db_type,
                db_name=db_name,
                host=host,
                port=port,
                user=user,
                password=password,
            )
            cursor = conn.cursor()
            cursor.execute(query)

            clean_q = query.strip().lower()
            is_select = clean_q.startswith(("select", "show", "pragma", "describe", "explain"))

            if is_select:
                rows_data = cursor.fetchmany(max_rows)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = []
                for row in rows_data:
                    if isinstance(row, dict):
                        rows.append(row)
                    elif hasattr(row, "keys"):
                        rows.append(dict(row))
                    else:
                        rows.append(dict(zip(columns, row)))

                conn.close()
                return {
                    "success": True,
                    "db_type": resolved_type,
                    "db_name": db_name,
                    "columns": columns,
                    "rows": rows,
                    "row_count": len(rows),
                    "message": f"Retrieved {len(rows)} row(s).",
                }
            else:
                conn.commit()
                rowcount = cursor.rowcount
                conn.close()
                return {
                    "success": True,
                    "db_type": resolved_type,
                    "db_name": db_name,
                    "affected_rows": rowcount,
                    "message": f"Query executed successfully. {rowcount} row(s) affected.",
                }
        except Exception as e:
            return {"success": False, "error": str(e), "query": query}

    def list_tables(
        self,
        db_type: str = "sqlite",
        db_name: str = "database.db",
        host: str = "localhost",
        port: Optional[int] = None,
        user: str = "root",
        password: str = "",
    ) -> Dict[str, Any]:
        """List all tables in the specified database."""
        try:
            db_type_lower = (db_type or "sqlite").lower()
            if db_type_lower == "sqlite":
                q = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
            elif db_type_lower in ("mysql", "mariadb"):
                q = "SHOW TABLES;"
            elif db_type_lower in ("postgres", "postgresql"):
                q = "SELECT table_name FROM information_schema.tables WHERE table_schema='public';"
            else:
                q = "SHOW TABLES;"

            res = self.query(
                query=q,
                db_type=db_type,
                db_name=db_name,
                host=host,
                port=port,
                user=user,
                password=password,
            )
            if not res.get("success"):
                return res

            tables = []
            for r in res.get("rows", []):
                val = list(r.values())[0] if r else None
                if val:
                    tables.append(val)

            return {
                "success": True,
                "db_type": db_type,
                "db_name": db_name,
                "tables": tables,
                "count": len(tables),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_csv(
        self,
        query: str,
        output_path: str,
        db_type: str = "sqlite",
        db_name: str = "database.db",
        host: str = "localhost",
        port: Optional[int] = None,
        user: str = "root",
        password: str = "",
    ) -> Dict[str, Any]:
        """Execute a query and export all result rows to a CSV file."""
        try:
            res = self.query(
                query=query,
                db_type=db_type,
                db_name=db_name,
                host=host,
                port=port,
                user=user,
                password=password,
                max_rows=100000,
            )
            if not res.get("success"):
                return res

            out = Path(output_path).expanduser().resolve()
            out.parent.mkdir(parents=True, exist_ok=True)

            columns = res.get("columns", [])
            rows = res.get("rows", [])

            with open(out, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)

            return {
                "success": True,
                "output_path": str(out),
                "row_count": len(rows),
                "message": f"Exported {len(rows)} row(s) to {out}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
