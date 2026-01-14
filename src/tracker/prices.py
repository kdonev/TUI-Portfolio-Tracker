import json
import logging
from typing import List, Dict
import yfinance as yf

logger = logging.getLogger(__name__)

# Default mapping from Interactive Brokers market codes to common Yahoo ticker suffixes.
# This is best-effort and can be extended by configuring TRACKER_TICKER_MAP env var (JSON dict).
DEFAULT_MARKET_MAP = {
    "IBIS": [".MI", ".DE"],
    "IBIS2": [".DE", ".MI"],
    "AEB": [".AS"],
    "SBF": [".PA"],
    "XLON": [".L"],
    "XETRA": [".DE"],
}

# Explicit exact mappings from TICKER@MARKET to a preferred Yahoo symbol
# Add any one-off overrides here so common delisted/mismatched symbols resolve
DEFAULT_EXACT_MAP = {
    "NUKL@SBF": ["NUKL.DE"],
}

# Generic fallback suffixes to try when market is unknown
GENERIC_SUFFIXES = [".DE", ".PA", ".AS", ".MI", ".L"]


def _load_custom_map() -> Dict[str, List[str]]:
    import os
    raw = os.getenv("TRACKER_TICKER_MAP")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        # Support keys that are either market codes (e.g., "IBIS") or full ticker@market (e.g., "NUKL@SBF").
        return {k.upper(): v for k, v in data.items()}
    except Exception:
        logger.warning("Invalid TRACKER_TICKER_MAP; must be JSON mapping")
        return {}

CUSTOM_MAP = _load_custom_map()


def _candidates_for(t: str) -> List[str]:
    """Given an input like 'SXR8@IBIS2' or 'VOO', return candidate Yahoo tickers to try.

    The returned list is ordered by preference.
    Supports exact matches in CUSTOM_MAP keyed by 'TICKER@MARKET' for overrides.
    """
    t = t.strip()
    key = t.upper()

    # Exact mapping in DEFAULT_EXACT_MAP (built-in overrides) takes highest precedence
    if key in DEFAULT_EXACT_MAP:
        mapped = DEFAULT_EXACT_MAP[key]
        base = t.split("@", 1)[0].upper() if "@" in t else t.upper()
        candidates = []
        for item in mapped:
            item = item.strip().upper()
            if item.startswith(base) or "." in item:
                candidates.append(item)
            else:
                candidates.append(base + item)
        seen = set(); out = []
        for c in candidates:
            if c not in seen:
                seen.add(c); out.append(c)
        return out

    # If there's an exact mapping for the full input (e.g., 'NUKL@SBF'), use custom map if present
    if key in CUSTOM_MAP:
        mapped = CUSTOM_MAP[key]
        # If the mapping contains full tickers, return them directly; otherwise
        # treat them as suffixes to append to the base part.
        base = t.split("@", 1)[0].upper() if "@" in t else t.upper()
        candidates = []
        for item in mapped:
            item = item.strip().upper()
            if item.startswith(base):
                # full ticker provided
                candidates.append(item)
            elif item.startswith('.'):
                # suffix like '.DE' provided
                candidates.append(base + item)
            elif '.' in item:
                # dot appears somewhere else - treat as full symbol
                candidates.append(item)
            else:
                # assume it's a suffix without leading dot (e.g. 'DE')
                candidates.append(base + '.' + item)
        # ensure unique preserving order
        seen = set(); out = []
        for c in candidates:
            if c not in seen:
                seen.add(c); out.append(c)
        return out

    if "@" not in t:
        return [t.upper()]
    base, market = t.split("@", 1)
    base = base.strip().upper()
    market = market.strip().upper()

    # custom mapping by market next
    if market in CUSTOM_MAP:
        suffixes = CUSTOM_MAP[market]
        # allow mapping values to be full tickers or suffixes
        candidates = []
        for s in suffixes:
            s = s.strip().upper()
            if s.startswith(base):
                candidates.append(s)
            elif s.startswith('.'):
                candidates.append(base + s)
            elif '.' in s:
                candidates.append(s)
            else:
                candidates.append(base + '.' + s)
        candidates.append(base)
        # unique preserve order
        seen = set(); out = []
        for c in candidates:
            if c not in seen:
                seen.add(c); out.append(c)
        return out

    if market in DEFAULT_MARKET_MAP:
        suffixes = DEFAULT_MARKET_MAP[market]
        candidates = [base + s for s in suffixes]
    else:
        # try a raw dot-suffix using market (first two chars), then generic ones
        candidates = [base + "." + market, base + "." + market[:2]]
        candidates += [base + s for s in GENERIC_SUFFIXES]
    candidates.append(base)
    # ensure uppercase and unique, preserving order
    seen = set()
    out = []
    for c in candidates:
        cu = c.upper()
        if cu not in seen:
            seen.add(cu)
            out.append(cu)
    return out


def fetch_prices(tickers: List[str]) -> Dict[str, float]:
    """Fetch latest close price for each ticker using yfinance.Ticker.

    Accepts tickers optionally suffixed with @MARKET (e.g. SXR8@IBIS2) and will
    attempt several candidate Yahoo tickers until it finds one with data.
    Returns dict original_input -> price (float or None)
    """
    prices: Dict[str, float] = {}
    for inp in tickers:
        candidates = _candidates_for(inp)
        price = None
        for tk in candidates:
            try:
                info = yf.Ticker(tk)
                hist = info.history(period="1d")
                if hist is None or hist.empty:
                    # try next candidate
                    continue
                price = float(hist["Close"].iloc[-1])
                # log which candidate succeeded
                if tk != inp.upper():
                    logger.debug("Resolved %s -> %s", inp, tk)
                break
            except Exception as e:
                logger.debug("Error fetching %s: %s", tk, e)
                continue
        prices[inp] = price
    return prices


def fetch_prices_with_resolution(tickers: List[str]) -> Dict[str, tuple]:
    """Like fetch_prices but returns (price, resolved_ticker) for each input."""
    out: Dict[str, tuple] = {}
    for inp in tickers:
        candidates = _candidates_for(inp)
        price = None
        resolved = None
        for tk in candidates:
            try:
                info = yf.Ticker(tk)
                hist = info.history(period="1d")
                if hist is None or hist.empty:
                    continue
                price = float(hist["Close"].iloc[-1])
                resolved = tk
                if tk != inp.upper():
                    logger.debug("Resolved %s -> %s", inp, tk)
                break
            except Exception as e:
                logger.debug("Error fetching %s: %s", tk, e)
                continue
        out[inp] = (price, resolved)
    return out