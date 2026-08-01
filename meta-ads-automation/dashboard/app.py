"""Local Streamlit dashboard.

Run: streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rules.engine import Config, classify  # noqa: E402

DB_PATH = Path(os.getenv("DB_PATH", "data/meta_ads.db"))

st.set_page_config(page_title="Meta Ads — Automatizado", layout="wide")
st.title("Tráfego Pago — visão local")

if not DB_PATH.exists():
    st.warning(f"Banco não encontrado em `{DB_PATH}`. Rode `python -m collector.fetch_insights` primeiro.")
    st.stop()


@st.cache_data(ttl=60)
def load_latest() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    latest = conn.execute("SELECT MAX(fetched_at) FROM insights").fetchone()[0]
    if not latest:
        return pd.DataFrame()
    df = pd.read_sql(
        "SELECT * FROM insights WHERE fetched_at = ?", conn, params=(latest,)
    )
    df.attrs["fetched_at"] = latest
    return df


@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    return pd.read_sql(
        "SELECT fetched_at, SUM(spend) spend, SUM(purchases) purchases, "
        "SUM(purchase_value) revenue FROM insights GROUP BY fetched_at "
        "ORDER BY fetched_at",
        conn,
    )


df = load_latest()
if df.empty:
    st.info("Sem dados ainda.")
    st.stop()

cfg = Config.load()

verdicts, reasons = [], []
for _, row in df.iterrows():
    v, r = classify(row.to_dict(), cfg)
    verdicts.append(v)
    reasons.append("; ".join(r))
df["verdict"] = verdicts
df["reasons"] = reasons
df["roas"] = df.apply(lambda r: (r["purchase_value"] / r["spend"]) if r["spend"] else 0, axis=1)
df["cpa"] = df.apply(lambda r: (r["spend"] / r["purchases"]) if r["purchases"] else None, axis=1)

# KPIs
total_spend = df["spend"].sum()
total_rev = df["purchase_value"].sum()
total_purch = df["purchases"].sum()
avg_ctr = (df["clicks"].sum() / df["impressions"].sum() * 100) if df["impressions"].sum() else 0
avg_cpm = (df["spend"].sum() / df["impressions"].sum() * 1000) if df["impressions"].sum() else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("CPA médio", f"R$ {(total_spend/total_purch):.2f}" if total_purch else "—")
c2.metric("CTR médio", f"{avg_ctr:.2f}%")
c3.metric("CPM médio", f"R$ {avg_cpm:.2f}")
c4.metric("ROAS", f"{(total_rev/total_spend):.2f}" if total_spend else "—")

st.caption(f"Última coleta: {df.attrs['fetched_at']} • {len(df)} anúncios")

# Verdict summary
st.subheader("Recomendações")
counts = df["verdict"].value_counts().to_dict()
color_map = {"ESCALAR": "🟢", "MANTER": "🟡", "MATAR": "🔴", "APRENDENDO": "⚪"}
cols = st.columns(4)
for i, v in enumerate(["ESCALAR", "MANTER", "MATAR", "APRENDENDO"]):
    cols[i].metric(f"{color_map[v]} {v}", counts.get(v, 0))

# Table
st.subheader("Anúncios")
show = df[["ad_name", "campaign_name", "spend", "roas", "cpa", "ctr",
           "frequency", "purchases", "verdict", "reasons"]].copy()
show = show.sort_values(
    "verdict",
    key=lambda s: s.map({"MATAR": 0, "ESCALAR": 1, "MANTER": 2, "APRENDENDO": 3}),
)
st.dataframe(show, use_container_width=True, hide_index=True)

# History
st.subheader("Histórico (agregado por coleta)")
hist = load_history()
if not hist.empty:
    hist["roas"] = hist.apply(lambda r: (r["revenue"] / r["spend"]) if r["spend"] else 0, axis=1)
    st.line_chart(hist.set_index("fetched_at")[["spend", "revenue"]])
    st.line_chart(hist.set_index("fetched_at")[["roas"]])
