"""Live exchange rates (European Central Bank data, via the free frankfurter.dev service).

No account or key needed. A rate is kept for one hour so we do not ask again for every click.
"""
import time

import httpx

SUPPORTED = {"INR": "Indian rupee", "GBP": "British pound", "USD": "US dollar", "EUR": "Euro"}
CACHE_SECONDS = 3600
URL = "https://api.frankfurter.dev/v1/latest"

_cache = {}     # (from, to) -> (time saved, rate, date)


class RatesUnavailable(Exception):
    pass


def get_rate(base: str, target: str):
    """Return (rate, date): 1 unit of `base` is `rate` units of `target`."""
    if base == target:
        return 1.0, None
    saved = _cache.get((base, target))
    if saved and time.time() - saved[0] < CACHE_SECONDS:
        return saved[1], saved[2]
    try:
        response = httpx.get(URL, params={"base": base, "symbols": target}, timeout=6)
        response.raise_for_status()
        data = response.json()
        rate = float(data["rates"][target])
        day = data.get("date")
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        if saved:                       # an old rate is better than no rate
            return saved[1], saved[2]
        raise RatesUnavailable()
    _cache[(base, target)] = (time.time(), rate, day)
    return rate, day