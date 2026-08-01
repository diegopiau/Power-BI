"""Pull ad-level insights and store them in SQLite.

Meant to run 3x/day via cron:
    0 8,14,20 * * * cd .../meta-ads-automation && .venv/bin/python -m collector.fetch_insights
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow "python -m collector.fetch_insights" from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meta_client import MetaClient, MetaError  # noqa: E402

DB_PATH = Path(os.getenv("DB_PATH", "data/meta_ads.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS insights (
    fetched_at    TEXT    NOT NULL,
    ad_id         TEXT    NOT NULL,
    ad_name       TEXT,
    adset_id      TEXT,
    campaign_id   TEXT,
    campaign_name TEXT,
    date_preset   TEXT    NOT NULL,
    impressions   INTEGER,
    clicks        INTEGER,
    spend         REAL,
    ctr           REAL,
    cpc           REAL,
    cpm           REAL,
    frequency     REAL,
    purchases     INTEGER,
    purchase_value REAL,
    cost_per_purchase REAL,
    raw_actions   TEXT,
    PRIMARY KEY (ad_id, date_preset, fetched_at)
);
CREATE INDEX IF NOT EXISTS ix_insights_fetched ON insights(fetched_at DESC);
CREATE INDEX IF NOT EXISTS ix_insights_ad ON insights(ad_id);
"""


def db_connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def _sum_action(actions: list[dict] | None, action_type: str) -> float:
    if not actions:
        return 0.0
    return sum(float(a.get("value", 0)) for a in actions if a.get("action_type") == action_type)


def _cost_per(actions: list[dict] | None, action_type: str) -> float | None:
    if not actions:
        return None
    for a in actions:
        if a.get("action_type") == action_type:
            v = a.get("value")
            return float(v) if v is not None else None
    return None


def normalize(row: dict, fetched_at: str, date_preset: str) -> tuple:
    actions = row.get("actions") or []
    action_values = row.get("action_values") or []
    cost_per_action = row.get("cost_per_action_type") or []

    purchases = int(_sum_action(actions, "purchase") or _sum_action(actions, "omni_purchase"))
    purchase_value = float(
        _sum_action(action_values, "purchase") or _sum_action(action_values, "omni_purchase")
    )
    cost_per_purchase = _cost_per(cost_per_action, "purchase") or _cost_per(cost_per_action, "omni_purchase")

    return (
        fetched_at,
        row.get("ad_id"),
        row.get("ad_name"),
        row.get("adset_id"),
        row.get("campaign_id"),
        row.get("campaign_name"),
        date_preset,
        int(row.get("impressions") or 0),
        int(row.get("clicks") or 0),
        float(row.get("spend") or 0),
        float(row.get("ctr") or 0),
        float(row.get("cpc") or 0),
        float(row.get("cpm") or 0),
        float(row.get("frequency") or 0),
        purchases,
        purchase_value,
        cost_per_purchase,
        json.dumps(actions),
    )


def run(date_preset: str = "last_7d", dry_run: bool = False) -> int:
    client = MetaClient.from_env()
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = client.get_ad_insights(date_preset=date_preset)

    if dry_run:
        print(f"[dry-run] would insert {len(rows)} rows fetched at {fetched_at}")
        return len(rows)

    conn = db_connect()
    with conn:
        conn.executemany(
            """INSERT OR REPLACE INTO insights VALUES
               (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            [normalize(r, fetched_at, date_preset) for r in rows],
        )
    print(f"[collector] inserted {len(rows)} rows at {fetched_at}")
    return len(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true", help="just create tables and exit")
    p.add_argument("--date-preset", default="last_7d")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    if args.init:
        db_connect().close()
        print(f"[collector] initialized {DB_PATH}")
        return 0

    try:
        run(date_preset=args.date_preset, dry_run=args.dry_run)
    except MetaError as e:
        print(f"[collector] Meta API error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
