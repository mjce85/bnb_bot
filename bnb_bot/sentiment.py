"""Historical Fear & Greed sentiment — loading, caching, and causal lookup.

Two free sources, same concept (a 0-100 crypto Fear & Greed index, daily):

* ``"cmc"`` — CoinMarketCap's own index via the Agent Hub / Data API
  (``/v3/fear-and-greed/historical``). Needs ``CMC_PRO_API_KEY`` (free Basic tier
  reaches this endpoint). History begins **2023-06-29**. This is the *sponsor*
  signal we deploy live.
* ``"alternative"`` — alternative.me's index (free, no key). History begins
  **2018-02-01**, so it covers our full 2021-start backtest window. A different
  methodology than CMC's but the same idea — used to *extend* the backtest before
  CMC's data exists, with the proxy gap measured (see :func:`overlap_correlation`).

The credibility guard here is **no-lookahead**: :meth:`FearGreedSeries.value_asof`
returns the most recent reading *strictly before* a bar's timestamp, so a signal
at bar ``t`` can never see the sentiment reading stamped at ``t`` itself. We fail
loud on a missing API key rather than silently degrading.
"""

from __future__ import annotations

import bisect
import json
import os
import statistics
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import polars as pl

from bnb_bot import config

_CMC_BASE = "https://pro-api.coinmarketcap.com"
_CMC_FNG_PATH = "/v3/fear-and-greed/historical"
_ALT_URL = "https://api.alternative.me/fng/?limit=0&format=json"
_DAY_MS = 24 * 60 * 60 * 1000
SOURCES = ("cmc", "alternative")


class FearGreedError(Exception):
    """Raised when sentiment data can't be loaded honestly (missing key, etc.)."""


# --- the causal series -------------------------------------------------


@dataclass(frozen=True)
class FearGreedReading:
    ts: int  # epoch milliseconds, midnight UTC
    value: int  # 0-100
    classification: str  # e.g. "Extreme Fear", "Greed"


class FearGreedSeries:
    """A daily Fear & Greed series with a no-lookahead ``value_asof`` lookup."""

    def __init__(self, readings: list[FearGreedReading], *, source: str):
        if not readings:
            raise FearGreedError(f"empty Fear & Greed series for source {source!r}")
        self._readings = sorted(readings, key=lambda r: r.ts)
        self._ts = [r.ts for r in self._readings]
        self.source = source

    def __len__(self) -> int:
        return len(self._readings)

    @property
    def readings(self) -> list[FearGreedReading]:
        return list(self._readings)

    def range(self) -> tuple[int, int]:
        """(earliest_ts, latest_ts) in epoch ms."""
        return self._ts[0], self._ts[-1]

    def value_asof(self, bar_ts: int) -> int | None:
        """Most recent F&G value with ts **strictly before** ``bar_ts``.

        Strictly-before is the no-lookahead guarantee: the reading stamped on the
        decision bar's own day is not used, so the signal leans only on sentiment
        that was already published. Returns ``None`` before the series begins
        (an honest "no reading yet", not a guessed default).
        """
        i = bisect.bisect_left(self._ts, bar_ts)
        if i == 0:
            return None
        return self._readings[i - 1].value


# --- parsing (pure; unit-tested without network) -----------------------


def parse_cmc(payload: dict) -> list[FearGreedReading]:
    """Parse a CMC ``/v3/fear-and-greed/historical`` JSON payload."""
    out = []
    for row in payload.get("data", []):
        out.append(
            FearGreedReading(
                ts=int(row["timestamp"]) * 1000,
                value=int(row["value"]),
                classification=str(row.get("value_classification", "")),
            )
        )
    return out


def parse_alternative(payload: dict) -> list[FearGreedReading]:
    """Parse an alternative.me ``/fng/`` JSON payload."""
    out = []
    for row in payload.get("data", []):
        out.append(
            FearGreedReading(
                ts=int(row["timestamp"]) * 1000,
                value=int(row["value"]),
                classification=str(row.get("value_classification", "")),
            )
        )
    return out


# --- network fetch (kept out of unit tests) ----------------------------


def cmc_api_key() -> str:
    """Read CMC_PRO_API_KEY from the environment or a local .env. Fail loud."""
    key = os.environ.get("CMC_PRO_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(".env"):
        for line in open(".env"):
            line = line.strip()
            if line.startswith("CMC_PRO_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise FearGreedError(
        "CMC_PRO_API_KEY not set. Put it in the environment or a .env file "
        "(CMC_PRO_API_KEY=...) to load CMC Fear & Greed history."
    )


def _http_get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        raise FearGreedError(f"HTTP {e.code} from {url.split('?')[0]}: {body}")
    except Exception as e:  # noqa: BLE001 — surface the cause loudly
        raise FearGreedError(f"request to {url.split('?')[0]} failed: {e}")


def _fetch_cmc() -> list[FearGreedReading]:
    key = cmc_api_key()
    headers = {"X-CMC_PRO_API_KEY": key}
    readings: list[FearGreedReading] = []
    start, limit = 1, 500
    while True:
        url = f"{_CMC_BASE}{_CMC_FNG_PATH}?" + urllib.parse.urlencode(
            {"start": start, "limit": limit}
        )
        page = parse_cmc(_http_get_json(url, headers))
        if not page:
            break
        readings.extend(page)
        if len(page) < limit:
            break
        start += limit
    return readings


def _fetch_alternative() -> list[FearGreedReading]:
    return parse_alternative(_http_get_json(_ALT_URL))


# --- parquet cache -----------------------------------------------------


def _cache_path(source: str) -> str:
    return os.path.join(config.DATA_DIR, f"fng_{source}.parquet")


def _save(readings: list[FearGreedReading], source: str) -> str:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    path = _cache_path(source)
    pl.DataFrame(
        {
            "ts": [r.ts for r in readings],
            "value": [r.value for r in readings],
            "classification": [r.classification for r in readings],
        }
    ).write_parquet(path)
    return path


def _load_cached(source: str) -> list[FearGreedReading] | None:
    path = _cache_path(source)
    if not os.path.exists(path):
        return None
    df = pl.read_parquet(path)
    return [
        FearGreedReading(
            ts=int(r["ts"]), value=int(r["value"]), classification=r["classification"]
        )
        for r in df.iter_rows(named=True)
    ]


def load_fear_greed(source: str, *, use_cache: bool = True) -> FearGreedSeries:
    """Return a :class:`FearGreedSeries` for ``source`` ('cmc' | 'alternative').

    Tries the parquet cache, else fetches from the network and caches. Sentiment
    history is append-only and small, so a full re-fetch on a cache miss is fine.
    """
    if source not in SOURCES:
        raise FearGreedError(f"unknown source {source!r}; known: {SOURCES}")
    if use_cache:
        cached = _load_cached(source)
        if cached:
            return FearGreedSeries(cached, source=source)
    readings = _fetch_cmc() if source == "cmc" else _fetch_alternative()
    _save(readings, source)
    return FearGreedSeries(readings, source=source)


# --- proxy quality: how well does alternative.me track CMC? ------------


def overlap_correlation(a: FearGreedSeries, b: FearGreedSeries) -> tuple[float, int]:
    """Pearson correlation of two F&G series on the days they both cover.

    Returns ``(correlation, n_overlap_days)``. This quantifies how good a proxy
    one index is for the other — the honest justification for using
    alternative.me to extend the backtest before CMC's data begins.
    """
    by_day_a = {r.ts // _DAY_MS: r.value for r in a.readings}
    by_day_b = {r.ts // _DAY_MS: r.value for r in b.readings}
    common = sorted(set(by_day_a) & set(by_day_b))
    if len(common) < 2:
        raise FearGreedError("series overlap is too small to correlate (<2 days)")
    xs = [by_day_a[d] for d in common]
    ys = [by_day_b[d] for d in common]
    return statistics.correlation(xs, ys), len(common)
