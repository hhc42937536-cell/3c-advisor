import json
import os
import urllib.parse
import urllib.request

UPSTASH_REDIS_URL   = os.environ.get("UPSTASH_REDIS_URL",   "")
UPSTASH_REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_TOKEN", "")


def redis_get(key: str):
    """從 Upstash Redis 取值；失敗或未設定回傳 None"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        req = urllib.request.Request(
            f"{UPSTASH_REDIS_URL}/get/{urllib.parse.quote(key, safe='')}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            result = json.loads(r.read()).get("result")
            return json.loads(result) if result else None
    except Exception as e:
        print(f"[Redis] GET {key} 失敗: {e}")
        return None


def redis_set(key: str, value, ttl: int = 300):
    """存值到 Upstash Redis（JSON），ttl 秒後過期"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    try:
        payload = json.dumps(
            ["SET", key, json.dumps(value, ensure_ascii=False), "EX", ttl]
        ).encode()
        req = urllib.request.Request(
            UPSTASH_REDIS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2):
            pass
    except Exception as e:
        print(f"[Redis] SET {key} 失敗: {e}")
