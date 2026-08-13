"""
Rate limiter zdieľaný medzi viacerými workermi cez Redis.

Chráni citlivé endpointy (login, reset hesla) pred hrubou silou / spamom.
Na rozdiel od in-memory riešenia funguje správne aj pri viacerých gunicorn
workeroch, lebo počítadlo pokusov je centrálne v Redise.

Ak Redis nie je nakonfigurovaný alebo je nedostupný, limiter automaticky
prepne na in-memory režim (fallback), aby aplikácia fungovala aj bez Redisu
(napr. pri lokálnom vývoji). V tomto režime platí obmedzenie len v rámci
jedného procesu.

Použitie:
    from services.rate_limiter import rate_limited
    if rate_limited("login:1.2.3.4:jozko", max_attempts=10, window_seconds=300):
        # zamietni požiadavku
"""

import os
import time
from collections import defaultdict

# --- Redis klient (voliteľný) ---
# REDIS_URL napr. "redis://redis:6379/0". Ak nie je nastavený, používa sa fallback.
_redis_client = None
_redis_checked = False


def _get_redis():
    """Vráti Redis klienta (alebo None, ak nie je dostupný). Skúša sa len raz."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client

    _redis_checked = True
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        _redis_client = None
        return None

    try:
        import redis  # importuje sa len ak je REDIS_URL nastavený
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
        client.ping()  # overí spojenie
        _redis_client = client
        print("[rate_limiter] Používa sa Redis:", redis_url)
    except Exception as e:
        print(f"[rate_limiter] Redis nedostupný ({e}) - fallback na in-memory")
        _redis_client = None

    return _redis_client


# --- Fallback: in-memory (len v rámci jedného procesu) ---
_attempts = defaultdict(list)


def _rate_limited_memory(key: str, max_attempts: int, window_seconds: int) -> bool:
    now = time.time()
    window_start = now - window_seconds
    _attempts[key] = [t for t in _attempts[key] if t > window_start]
    if len(_attempts[key]) >= max_attempts:
        return True
    _attempts[key].append(now)
    return False


def _rate_limited_redis(client, key: str, max_attempts: int, window_seconds: int) -> bool:
    """
    Počítadlo v Redise so skĺzavým oknom (sliding window) cez sorted set.
    Kľúč obsahuje časové značky pokusov; staré sa odstránia, nové pridá.
    """
    redis_key = f"ratelimit:{key}"
    now = time.time()
    window_start = now - window_seconds
    try:
        pipe = client.pipeline()
        # odstráň pokusy staršie než okno
        pipe.zremrangebyscore(redis_key, 0, window_start)
        # spočítaj aktuálne pokusy v okne
        pipe.zcard(redis_key)
        _, count = pipe.execute()

        if count >= max_attempts:
            return True

        # zaznamenaj tento pokus a nastav expiráciu kľúča
        pipe = client.pipeline()
        pipe.zadd(redis_key, {f"{now}": now})
        pipe.expire(redis_key, window_seconds)
        pipe.execute()
        return False
    except Exception as e:
        # ak Redis počas behu zlyhá, radšej pusti požiadavku ďalej
        # (bezpečnosť neohrozíme - fallback na in-memory)
        print(f"[rate_limiter] Redis chyba ({e}) - fallback na in-memory pre tento pokus")
        return _rate_limited_memory(key, max_attempts, window_seconds)


def rate_limited(key: str, max_attempts: int, window_seconds: int) -> bool:
    """
    Vráti True, ak sa má požiadavka zamietnuť (prekročený limit).

    key             - jedinečný identifikátor (napr. "login:IP:login")
    max_attempts    - koľko pokusov je povolených v okne
    window_seconds  - dĺžka časového okna v sekundách
    """
    client = _get_redis()
    if client is not None:
        return _rate_limited_redis(client, key, max_attempts, window_seconds)
    return _rate_limited_memory(key, max_attempts, window_seconds)


def retry_after(key: str, window_seconds: int) -> int:
    """
    Vráti počet sekúnd, koľko ešte ostáva do odblokovania (do vypršania
    najstaršieho pokusu v okne). Slúži na zobrazenie časovača používateľovi.
    Ak nie sú žiadne pokusy, vráti 0.
    """
    now = time.time()
    oldest = None

    client = _get_redis()
    if client is not None:
        try:
            redis_key = f"ratelimit:{key}"
            # najstarší záznam (najmenšie skóre) v sorted sete
            items = client.zrange(redis_key, 0, 0, withscores=True)
            if items:
                oldest = items[0][1]
        except Exception:
            oldest = None

    if oldest is None:
        # in-memory fallback
        attempts = _attempts.get(key, [])
        if attempts:
            oldest = min(attempts)

    if oldest is None:
        return 0

    remaining = int(oldest + window_seconds - now) + 1
    return max(0, remaining)
