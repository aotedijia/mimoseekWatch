from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    cached_tokens INTEGER NOT NULL DEFAULT 0,
                    uncached_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    cost REAL NOT NULL DEFAULT 0,
                    currency TEXT NOT NULL DEFAULT 'CNY',
                    priced INTEGER NOT NULL DEFAULT 1,
                    request_count INTEGER NOT NULL DEFAULT 1,
                    source_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_events(created_at);
                CREATE INDEX IF NOT EXISTS idx_usage_provider ON usage_events(provider);
                CREATE TABLE IF NOT EXISTS balance_snapshots (
                    provider TEXT PRIMARY KEY,
                    captured_at TEXT NOT NULL,
                    total_balance REAL,
                    granted_balance REAL,
                    topped_up_balance REAL,
                    currency TEXT NOT NULL DEFAULT 'CNY',
                    available INTEGER,
                    source TEXT NOT NULL,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(usage_events)")}
            if "request_count" not in columns:
                db.execute("ALTER TABLE usage_events ADD COLUMN request_count INTEGER NOT NULL DEFAULT 1")
            if "source_id" not in columns:
                db.execute("ALTER TABLE usage_events ADD COLUMN source_id TEXT")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usage_source ON usage_events(source_id)")
            db.execute("DELETE FROM balance_snapshots WHERE source != 'official_web_session'")
            db.execute("INSERT OR IGNORE INTO settings VALUES ('warning_balance', '10')")

    def record_usage(self, event: dict) -> int:
        fields = (
            "created_at", "provider", "model", "endpoint", "status_code", "latency_ms",
            "input_tokens", "cached_tokens", "uncached_tokens", "output_tokens",
            "total_tokens", "cost", "currency", "priced", "request_count", "source_id",
        )
        values = [event.get(field, 1 if field == "request_count" else None) for field in fields]
        with self.connect() as db:
            cursor = db.execute(
                f"INSERT OR REPLACE INTO usage_events ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                values,
            )
            return int(cursor.lastrowid)

    def replace_provider_usage(self, provider: str, events: list[dict]) -> None:
        """Replace one provider's official usage snapshot atomically."""
        fields = (
            "created_at", "provider", "model", "endpoint", "status_code", "latency_ms",
            "input_tokens", "cached_tokens", "uncached_tokens", "output_tokens",
            "total_tokens", "cost", "currency", "priced", "request_count", "source_id",
        )
        rows = [
            [event.get(field, 1 if field == "request_count" else None) for field in fields]
            for event in events
        ]
        with self.connect() as db:
            db.execute(
                "DELETE FROM usage_events WHERE provider = ? AND source_id IS NOT NULL",
                (provider,),
            )
            if rows:
                db.executemany(
                    f"INSERT INTO usage_events ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    rows,
                )

    def upsert_balance(self, snapshot: dict) -> None:
        fields = (
            "provider", "captured_at", "total_balance", "granted_balance",
            "topped_up_balance", "currency", "available", "source", "error",
        )
        with self.connect() as db:
            db.execute(
                f"""INSERT INTO balance_snapshots ({','.join(fields)})
                VALUES ({','.join('?' for _ in fields)})
                ON CONFLICT(provider) DO UPDATE SET
                {','.join(f'{field}=excluded.{field}' for field in fields[1:])}""",
                [snapshot.get(field) for field in fields],
            )

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_settings(self, values: dict[str, str]) -> None:
        with self.connect() as db:
            db.executemany(
                "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                values.items(),
            )

    def summary(self) -> dict:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%dT00:00:00")
        with self.connect() as db:
            totals = [dict(row) for row in db.execute(
                """SELECT provider, SUM(request_count) requests, SUM(total_tokens) total_tokens,
                SUM(input_tokens) input_tokens, SUM(output_tokens) output_tokens,
                SUM(cached_tokens) cached_tokens, SUM(cost) cost,
                SUM(CASE WHEN priced = 0 THEN 1 ELSE 0 END) unpriced
                FROM usage_events e
                WHERE e.source_id IS NOT NULL
                GROUP BY provider"""
            )]
            today_row = dict(db.execute(
                """SELECT COALESCE(SUM(request_count),0) requests, COALESCE(SUM(total_tokens),0) total_tokens,
                COALESCE(SUM(input_tokens),0) input_tokens,
                COALESCE(SUM(cached_tokens),0) cached_tokens,
                COALESCE(SUM(cost),0) cost FROM usage_events e WHERE created_at >= ?
                AND e.source_id IS NOT NULL""", (today,)
            ).fetchone())
            balances = [dict(row) for row in db.execute("SELECT * FROM balance_snapshots")]
            trend = [dict(row) for row in db.execute(
                """SELECT substr(created_at,1,10) day, provider, SUM(total_tokens) tokens, SUM(cost) cost
                FROM usage_events e WHERE created_at >= datetime('now','-13 days')
                AND e.source_id IS NOT NULL
                GROUP BY day, provider ORDER BY day"""
            )]
            history = [dict(row) for row in db.execute(
                """SELECT substr(created_at,1,7) month, provider,
                SUM(total_tokens) tokens, SUM(cost) cost
                FROM usage_events e
                WHERE created_at >= date('now','start of month','-11 months')
                AND e.source_id IS NOT NULL
                GROUP BY month, provider ORDER BY month"""
            )]
            recent = [dict(row) for row in db.execute(
                """SELECT id, created_at, provider, model, status_code, latency_ms,
                input_tokens, cached_tokens, output_tokens, total_tokens, cost, priced
                FROM usage_events WHERE source_id IS NOT NULL
                ORDER BY created_at DESC, provider ASC, model ASC LIMIT 50"""
            )]
        return {
            "today": today_row, "providers": totals, "balances": balances,
            "trend": trend, "history": history, "recent": recent,
        }

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
