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
        with urllib.request.urlopen(req, timeout=1) as r:
            result = json.loads(r.read()).get("result")
            return json.loads(result) if result else None
    except Exception as e:
        print(f"[Redis] GET {key} 失敗: {e}")
        return None


def redis_set(key: str, value, ttl: int = 300):
    """存值到 Upstash Redis（JSON），ttl=0 表示永不過期"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    try:
        v = json.dumps(value, ensure_ascii=False)
        cmd = ["SET", key, v] if ttl == 0 else ["SET", key, v, "EX", ttl]
        payload = json.dumps(cmd).encode()
        req = urllib.request.Request(
            UPSTASH_REDIS_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1):
            pass
    except Exception as e:
        print(f"[Redis] SET {key} 失敗: {e}")


def redis_lpush(key: str, value, max_len: int = 200):
    """LPUSH + LTRIM，保留最新 max_len 筆（不設 TTL，永久保留）"""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    headers = {
        "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        v = json.dumps(value, ensure_ascii=False)
        for cmd in (["LPUSH", key, v], ["LTRIM", key, 0, max_len - 1]):
            req = urllib.request.Request(
                UPSTASH_REDIS_URL,
                data=json.dumps(cmd).encode(),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=2):
                pass
    except Exception as e:
        print(f"[Redis] LPUSH {key} 失敗: {e}")


def get_user_pref(user_id: str) -> dict:
    """取使用者個人偏好（streak、visited_count 等）"""
    return redis_get(f"user_pref:{user_id}") or {}


def update_user_pref(user_id: str, **kwargs) -> None:
    """Merge 更新使用者偏好，TTL 90 天"""
    key = f"user_pref:{user_id}"
    pref = redis_get(key) or {}
    pref.update(kwargs)
    redis_set(key, pref, ttl=0)  # 0 = Upstash 永不過期，成就資料不應隨非活躍消失
