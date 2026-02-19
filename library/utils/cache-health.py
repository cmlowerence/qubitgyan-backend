from django.core.cache import cache

def check_cache():
    try:
        cache.set("health_check", "ok", timeout=10)
        return cache.get("health_check") == "ok"
    except Exception:
        return False