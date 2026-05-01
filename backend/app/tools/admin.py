from __future__ import annotations

import asyncio
from typing import Any

import asyncpg

from app.tools.config import ToolConfig


def db_check(config: ToolConfig) -> dict[str, Any]:
    return asyncio.run(_db_check(config))


def index_check(config: ToolConfig) -> dict[str, Any]:
    return asyncio.run(_index_check(config))


def processing_health(config: ToolConfig) -> dict[str, Any]:
    return asyncio.run(_processing_health(config))


async def _db_check(config: ToolConfig) -> dict[str, Any]:
    conn = await _readonly_connection(config)
    try:
        version = await conn.fetchval("SHOW server_version")
        database = await conn.fetchval("SELECT current_database()")
        return {"database": database, "server_version": version, "read_only": await _is_readonly(conn)}
    finally:
        await conn.close()


async def _index_check(config: ToolConfig) -> dict[str, Any]:
    conn = await _readonly_connection(config)
    try:
        rows = await conn.fetch(
            """
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename IN ('graph_node', 'graph_edge', 'chunk', 'document', 'entity', 'claim', 'cluster', 'processing_job')
            ORDER BY tablename, indexname
            """
        )
        return {"indexes": [dict(row) for row in rows], "read_only": await _is_readonly(conn)}
    finally:
        await conn.close()


async def _processing_health(config: ToolConfig) -> dict[str, Any]:
    conn = await _readonly_connection(config)
    try:
        rows = await conn.fetch(
            """
            SELECT status, count(*) AS count
            FROM processing_job
            GROUP BY status
            ORDER BY status
            """
        )
        return {"jobs_by_status": [dict(row) for row in rows], "read_only": await _is_readonly(conn)}
    finally:
        await conn.close()


async def _readonly_connection(config: ToolConfig) -> asyncpg.Connection:
    conn = await asyncpg.connect(config.require_admin_database_url())
    await conn.execute("SET default_transaction_read_only = on")
    return conn


async def _is_readonly(conn: asyncpg.Connection) -> bool:
    value = await conn.fetchval("SHOW default_transaction_read_only")
    return str(value).lower() == "on"
