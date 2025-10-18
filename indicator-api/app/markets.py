import asyncio
from os import getenv
from dotenv import load_dotenv
import requests
from logger import logger
from typing import Dict

load_dotenv()
log = logger(__name__)

DB_ACCESSOR_API_HOST = getenv("DB_ACCESSOR_API_HOST", "database-accessor-api")
DB_ACCESSOR_API_PORT = getenv("DB_ACCESSOR_API_PORT", 8000)

SYMBOL_MAPPING: Dict[str, int] = {}
_SYMBOLS_LOCK = asyncio.Lock()


async def load_symbols() -> Dict[str, int]:
    """Populate SYMBOL_MAPPING once (idempotent) and return it.

    Uses a lock to avoid overlapping population if multiple coroutines call
    this concurrently at startup. The dictionary is mutated in-place so any
    modules that imported the object keep seeing updated contents.
    """
    if SYMBOL_MAPPING:
        return SYMBOL_MAPPING
    async with _SYMBOLS_LOCK:
        if not SYMBOL_MAPPING:  # double-checked locking
            markets = await get_markets()
            SYMBOL_MAPPING.clear()
            SYMBOL_MAPPING.update({m['symbol']: m['symbol_id'] for m in markets})
    return SYMBOL_MAPPING


async def get_markets() -> list[dict]:
    """Fetch all markets from the database accessor API without blocking the loop.

    Runs the blocking requests.get call in a thread via asyncio.to_thread.
    """
    base_url = f"http://{DB_ACCESSOR_API_HOST}:{DB_ACCESSOR_API_PORT}/markets"

    def _fetch():
        try:
            resp = requests.get(base_url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # network boundary
            log.warning("Error fetching markets: %s", e)
            return []

    return await asyncio.to_thread(_fetch)


def get_symbol_mapping(symbols: list[str]) -> Dict[str, int]:
    """Return the current SYMBOL_MAPPING dictionary (may be empty if not loaded)."""
    missing_symbols = [s for s in symbols if s not in SYMBOL_MAPPING]

    if missing_symbols:
        log.info("Symbols not found in cache: %s", missing_symbols)
        missing_symbols_mapping = get_symbol_id_sync(missing_symbols)

        if missing_symbols_mapping:
            SYMBOL_MAPPING.update(missing_symbols_mapping)
            log.info("Updated SYMBOL_MAPPING with %d new entries", len(missing_symbols_mapping))
        else:
            log.info("No new symbols found to update SYMBOL_MAPPING")

    return {s: SYMBOL_MAPPING[s] for s in symbols if s in SYMBOL_MAPPING}


def get_symbol_id_sync(symbols: list[str]) -> dict[str, int]:
    """Blocking fetch for multiple symbols' IDs. Returns {symbol: symbol_id|None} mapping.
    Runs multiple requests in parallel using asyncio and threads.
    """
    mapping: dict[str, int] = {}
    missing: list[str] = []
    for sym in symbols:
        _, sid = _fetch_symbol_id_sync(sym)
        if sid is not None:
            mapping[sym] = sid
        else:
            missing.append(sym)
    if missing:
        log.info("Symbols not found (skipped): %s", missing)
    return mapping


def _fetch_symbol_id_sync(symbol: str) -> tuple[str, int | None]:
    """Blocking fetch for a single symbol's ID. Returns (symbol, symbol_id|None)."""
    base_url = f"http://{DB_ACCESSOR_API_HOST}:{DB_ACCESSOR_API_PORT}/markets"

    try:
        params = {"symbol": symbol}
        resp = requests.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        markets = resp.json()
        if markets:
            symbol_id = markets[0]["symbol_id"]
            log.debug("Found ID %s for symbol %s", symbol_id, symbol)
            return symbol, symbol_id
        else:
            log.debug("No market found for symbol: %s", symbol)
            return symbol, None
    except Exception as e:  # broad catch acceptable for I/O boundary
        log.warning("Error fetching symbol ID for %s: %s", symbol, e)
        return symbol, None
