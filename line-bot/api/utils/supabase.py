import hashlib
import json
import os
import time
import urllib.request

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_HEADERS = lambda: {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def log_usage(user_id: str, feature: str, sub_action: str = None,
              city: str = None, is_success: bool = True):
    """記錄匿名使用統計（失敗不中斷主流程）"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        data = {"uid_hash": uid_hash, "feature": feature, "is_success": is_success}
        if sub_action:
            data["sub_action"] = sub_action
        if city:
            data["city"] = city
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/linebot_usage_logs",
            data=json.dumps(data).encode("utf-8"),
            headers=_HEADERS(),
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"[log] {e}")


def record_eaten(user_id: str, restaurant_name: str, city: str = ""):
    """記錄用戶吃過的餐廳"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        body = json.dumps({
            "uid_hash": uid_hash,
            "restaurant_name": restaurant_name[:80],
            "city": city[:10],
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/user_eaten_restaurants",
            data=body,
            headers=_HEADERS(),
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
    except Exception as e:
        print(f"[eaten] record error: {e}")


def get_eaten(user_id: str) -> set:
    """取得用戶近 7 天吃過的餐廳名稱集合"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return set()
    try:
        uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:16]
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                               time.gmtime(time.time() - 7 * 86400))
        url = (
            f"{SUPABASE_URL}/rest/v1/user_eaten_restaurants"
            f"?select=restaurant_name&uid_hash=eq.{uid_hash}&created_at=gte.{cutoff}"
        )
        req = urllib.request.Request(
            url,
            headers={"apikey": SUPABASE_KEY,
                     "Authorization": f"Bearer {SUPABASE_KEY}"},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            rows = json.loads(r.read().decode("utf-8"))
        return {row["restaurant_name"] for row in rows}
    except Exception as e:
        print(f"[eaten] fetch error: {e}")
        return set()
