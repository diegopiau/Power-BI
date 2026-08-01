"""Classify each ad as ESCALAR / MANTER / MATAR / APRENDENDO.

Reads the latest snapshot from SQLite, applies thresholds in config.yaml,
prints a table. Optionally writes the verdict back to a `verdicts` table.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

DB_PATH = Path(os.getenv("DB_PATH", "data/meta_ads.db"))
CONFIG_PATH = Path(__file__).parent / "config.yaml"

VERDICTS = ("ESCALAR", "MANTER", "MATAR", "APRENDENDO")


@dataclass
class Config:
    min_spend_to_judge: float
    target_cpa: float
    roas_escalar: float
    roas_matar: float
    cpa_ratio_escalar: float
    cpa_ratio_matar: float
    ctr_escalar: float
    ctr_matar: float
    frequency_escalar_max: float
    frequency_matar_min: float

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Config":
        y = yaml.safe_load(path.read_text())
        return cls(
            min_spend_to_judge=y["min_spend_to_judge"],
            target_cpa=y["target_cpa"],
            roas_escalar=y["roas"]["escalar"],
            roas_matar=y["roas"]["matar"],
            cpa_ratio_escalar=y["cpa_ratio"]["escalar"],
            cpa_ratio_matar=y["cpa_ratio"]["matar"],
            ctr_escalar=y["ctr"]["escalar"],
            ctr_matar=y["ctr"]["matar"],
            frequency_escalar_max=y["frequency"]["escalar_max"],
            frequency_matar_min=y["frequency"]["matar_min"],
        )


def classify(row: dict, cfg: Config) -> tuple[str, list[str]]:
    """Return (verdict, reasons). Simple vote-based classifier.

    A signal casts one of: +escalar / -matar / neutral. Verdict is the
    strongest side that has ≥2 signals; otherwise MANTER. MATAR wins ties.
    """
    reasons: list[str] = []
    spend = row["spend"] or 0
    if spend < cfg.min_spend_to_judge:
        return "APRENDENDO", [f"spend {spend:.2f} < {cfg.min_spend_to_judge:.2f}"]

    escalar_votes = 0
    matar_votes = 0

    purchases = row["purchases"] or 0
    purchase_value = row["purchase_value"] or 0
    roas = (purchase_value / spend) if spend > 0 else 0
    cpa = (spend / purchases) if purchases > 0 else float("inf")
    cpa_ratio = cpa / cfg.target_cpa if cfg.target_cpa > 0 else float("inf")

    ctr = row["ctr"] or 0
    freq = row["frequency"] or 0

    if roas >= cfg.roas_escalar:
        escalar_votes += 1
        reasons.append(f"ROAS {roas:.2f} ≥ {cfg.roas_escalar}")
    elif roas < cfg.roas_matar:
        matar_votes += 1
        reasons.append(f"ROAS {roas:.2f} < {cfg.roas_matar}")

    if cpa_ratio <= cfg.cpa_ratio_escalar:
        escalar_votes += 1
        reasons.append(f"CPA {cpa:.2f} ≤ {cfg.cpa_ratio_escalar*cfg.target_cpa:.2f}")
    elif cpa_ratio > cfg.cpa_ratio_matar:
        matar_votes += 1
        reasons.append(f"CPA {cpa:.2f} > {cfg.cpa_ratio_matar*cfg.target_cpa:.2f}")

    if ctr >= cfg.ctr_escalar:
        escalar_votes += 1
        reasons.append(f"CTR {ctr:.2f}% ≥ {cfg.ctr_escalar}%")
    elif ctr < cfg.ctr_matar:
        matar_votes += 1
        reasons.append(f"CTR {ctr:.2f}% < {cfg.ctr_matar}%")

    if freq and freq < cfg.frequency_escalar_max:
        escalar_votes += 1
        reasons.append(f"freq {freq:.2f} < {cfg.frequency_escalar_max}")
    elif freq > cfg.frequency_matar_min:
        matar_votes += 1
        reasons.append(f"freq {freq:.2f} > {cfg.frequency_matar_min}")

    if matar_votes >= 2 and matar_votes >= escalar_votes:
        return "MATAR", reasons
    if escalar_votes >= 2 and escalar_votes > matar_votes:
        return "ESCALAR", reasons
    return "MANTER", reasons


def latest_snapshot(conn: sqlite3.Connection) -> list[dict]:
    row = conn.execute("SELECT MAX(fetched_at) FROM insights").fetchone()
    if not row or not row[0]:
        return []
    latest = row[0]
    cur = conn.execute(
        "SELECT ad_id, ad_name, campaign_name, spend, ctr, frequency, "
        "purchases, purchase_value FROM insights WHERE fetched_at = ?",
        (latest,),
    )
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def ensure_verdicts_table(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS verdicts (
            evaluated_at TEXT NOT NULL,
            ad_id        TEXT NOT NULL,
            verdict      TEXT NOT NULL,
            reasons      TEXT,
            PRIMARY KEY (ad_id, evaluated_at)
        );
    """)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--persist", action="store_true", help="save verdicts to DB")
    args = p.parse_args()

    cfg = Config.load()
    if not DB_PATH.exists():
        print(f"no db at {DB_PATH} — run collector first", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    rows = latest_snapshot(conn)
    if not rows:
        print("no snapshot in db", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    for r in rows:
        verdict, reasons = classify(r, cfg)
        results.append((r, verdict, reasons))

    print(f"{'AD':<40} {'CAMPANHA':<25} {'SPEND':>8} {'ROAS':>6} {'CTR':>6} {'VERDICT':<12} REASONS")
    for r, v, reasons in results:
        spend = r["spend"] or 0
        roas = (r["purchase_value"] / spend) if spend else 0
        print(f"{(r['ad_name'] or r['ad_id'])[:40]:<40} "
              f"{(r['campaign_name'] or '')[:25]:<25} "
              f"{spend:>8.2f} {roas:>6.2f} {(r['ctr'] or 0):>6.2f} "
              f"{v:<12} {'; '.join(reasons)}")

    if args.persist:
        ensure_verdicts_table(conn)
        with conn:
            conn.executemany(
                "INSERT OR REPLACE INTO verdicts VALUES (?,?,?,?)",
                [(now, r["ad_id"], v, "; ".join(reasons)) for r, v, reasons in results],
            )
        print(f"\npersisted {len(results)} verdicts at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
