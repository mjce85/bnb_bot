#!/usr/bin/env python
"""Diagnostic: what does the free CMC key reach? (Throwaway probe, not committed.)

Reads CMC_PRO_API_KEY from .env, prints the plan tier and, for each endpoint we'd
need for a *live* CMC-powered signal, the HTTP status + a few response field names
or the API's error message. NEVER prints the key.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

BASE = "https://pro-api.coinmarketcap.com"


def _load_key() -> str:
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line.startswith("CMC_PRO_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("CMC_PRO_API_KEY not found in .env")


def _get(key: str, path: str, params: dict | None = None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-CMC_PRO_API_KEY": key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body[:200]}
    except Exception as e:  # network etc.
        return None, {"error": str(e)}


def _summ(status, body) -> str:
    if (
        isinstance(body, dict)
        and "status" in body
        and body["status"].get("error_message")
    ):
        return f"HTTP {status} — error: {body['status']['error_message']}"
    if isinstance(body, dict) and "data" in body:
        data = body["data"]
        if isinstance(data, dict):
            keys = list(data.keys())[:6]
        elif isinstance(data, list) and data:
            keys = list(data[0].keys())[:6] if isinstance(data[0], dict) else ["<list>"]
        else:
            keys = ["<empty>"]
        return f"HTTP {status} OK — data fields: {keys}"
    return f"HTTP {status} — {str(body)[:160]}"


def main() -> int:
    key = _load_key()
    print(f"(key loaded, {len(key)} chars — not shown)\n")

    s, b = _get(key, "/v1/key/info")
    if isinstance(b, dict) and "data" in b:
        plan = b["data"].get("plan", {})
        usage = b["data"].get("usage", {})
        print("PLAN INFO:")
        print(f"  plan: {json.dumps(plan)[:300]}")
        print(f"  usage: {json.dumps(usage)[:300]}\n")
    else:
        print(f"key/info: {_summ(s, b)}\n")

    tests = [
        ("Live quote (BNB)", "/v2/cryptocurrency/quotes/latest", {"symbol": "BNB"}),
        ("Global metrics (BTC dom, etc.)", "/v1/global-metrics/quotes/latest", None),
        ("Fear & Greed (latest)", "/v3/fear-and-greed/latest", None),
        ("Latest OHLCV (BNB)", "/v2/cryptocurrency/ohlcv/latest", {"symbol": "BNB"}),
        (
            "Historical OHLCV (BNB, daily)",
            "/v2/cryptocurrency/ohlcv/historical",
            {"symbol": "BNB", "count": "10", "interval": "daily"},
        ),
        (
            "Historical quotes (BTC)",
            "/v3/cryptocurrency/quotes/historical",
            {"symbol": "BTC", "count": "10", "interval": "daily"},
        ),
        (
            "Price-performance stats",
            "/v2/cryptocurrency/price-performance-stats/latest",
            {"symbol": "BNB"},
        ),
        ("Trending latest", "/v1/cryptocurrency/trending/latest", None),
    ]
    print("ENDPOINT PROBES (for a live signal path):")
    for label, path, params in tests:
        s, b = _get(key, path, params)
        print(f"  [{label}]\n     {_summ(s, b)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
