"""Minimal wrapper around Meta Marketing Graph API.

Only the calls we actually use are here. No SDK dependency — plain requests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH = "https://graph.facebook.com"


class MetaError(RuntimeError):
    pass


@dataclass
class MetaClient:
    access_token: str
    ad_account_id: str
    api_version: str = "v21.0"
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "MetaClient":
        token = os.getenv("META_ACCESS_TOKEN")
        acct = os.getenv("META_AD_ACCOUNT_ID")
        if not token or not acct:
            raise MetaError("META_ACCESS_TOKEN and META_AD_ACCOUNT_ID must be set")
        return cls(
            access_token=token,
            ad_account_id=acct,
            api_version=os.getenv("META_API_VERSION", "v21.0"),
        )

    def _url(self, path: str) -> str:
        return f"{GRAPH}/{self.api_version}/{path.lstrip('/')}"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {**(params or {}), "access_token": self.access_token}
        r = requests.get(self._url(path), params=params, timeout=self.timeout)
        if not r.ok:
            raise MetaError(f"GET {path} -> {r.status_code}: {r.text}")
        return r.json()

    def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        data = {**data, "access_token": self.access_token}
        r = requests.post(self._url(path), data=data, timeout=self.timeout)
        if not r.ok:
            raise MetaError(f"POST {path} -> {r.status_code}: {r.text}")
        return r.json()

    def _paginate(self, path: str, params: dict[str, Any]) -> Iterable[dict[str, Any]]:
        url = self._url(path)
        p = {**params, "access_token": self.access_token}
        while url:
            r = requests.get(url, params=p, timeout=self.timeout)
            if not r.ok:
                raise MetaError(f"GET {url} -> {r.status_code}: {r.text}")
            body = r.json()
            yield from body.get("data", [])
            url = body.get("paging", {}).get("next")
            p = None  # next URL already has query string

    # ---- reads ----

    def list_campaigns(self, status: str = "ACTIVE") -> list[dict]:
        return list(self._paginate(
            f"{self.ad_account_id}/campaigns",
            {"fields": "id,name,status,objective,daily_budget,lifetime_budget",
             "effective_status": f'["{status}"]', "limit": 200},
        ))

    def list_ads(self, status: str = "ACTIVE") -> list[dict]:
        return list(self._paginate(
            f"{self.ad_account_id}/ads",
            {"fields": "id,name,status,adset_id,campaign_id,creative",
             "effective_status": f'["{status}"]', "limit": 200},
        ))

    def get_ad_insights(self, date_preset: str = "last_7d") -> list[dict]:
        fields = ",".join([
            "ad_id", "ad_name", "adset_id", "campaign_id", "campaign_name",
            "impressions", "clicks", "spend", "ctr", "cpc", "cpm", "frequency",
            "actions", "action_values", "cost_per_action_type",
        ])
        return list(self._paginate(
            f"{self.ad_account_id}/insights",
            {"level": "ad", "date_preset": date_preset, "fields": fields, "limit": 200},
        ))

    # ---- writes ----

    def pause_ad(self, ad_id: str) -> dict:
        return self._post(ad_id, {"status": "PAUSED"})

    def resume_ad(self, ad_id: str) -> dict:
        return self._post(ad_id, {"status": "ACTIVE"})

    def update_adset_daily_budget(self, adset_id: str, budget_cents: int) -> dict:
        return self._post(adset_id, {"daily_budget": budget_cents})
