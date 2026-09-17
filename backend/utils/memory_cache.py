from cachetools import TTLCache

# Create a RAM cache that holds up to 100 items, with a 1-hour expiration (3600 seconds)
_board_cache = TTLCache(maxsize=100, ttl=3600)

def get_cached_json(key: str):
    """Fetches data from the local RAM cache."""
    return _board_cache.get(key)

def set_cached_json(key: str, value: dict, ttl: int = 3600):
    """Stores data in the local RAM cache. (TTL is fixed by the cache setup)."""
    _board_cache[key] = value

def invalidate_board_cache():
    """Wipes the entire board cache from RAM."""
    _board_cache.clear()
    print("[CACHE] Invalidated all in-memory board cache keys.")