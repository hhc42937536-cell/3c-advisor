import base64
import hashlib
import hmac
import json
import os
import urllib.request

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET", "")
LINE_BOT_ID          = os.environ.get("LINE_BOT_ID", "")


def reply_message(reply_token: str, messages: list):
    """回覆使用者訊息（最多 5 則）"""
    if not messages:
        print("[reply] SKIPPED: messages is None/empty")
        return
    print(f"[reply] token={reply_token[:20]}... msgs={len(messages)}")
    if not CHANNEL_ACCESS_TOKEN or not reply_token:
        return
    data = json.dumps({"replyToken": reply_token, "messages": messages[:5]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/reply",
        data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[reply] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[reply] ERROR: {e}")
        if hasattr(e, "read"):
            print(f"[reply] BODY: {e.read().decode('utf-8', 'ignore')}")


def push_message(user_id: str, messages: list):
    """主動推送訊息（最多 5 則）"""
    if not messages or not user_id or not CHANNEL_ACCESS_TOKEN:
        return
    data = json.dumps({"to": user_id, "messages": messages[:5]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[push] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[push] ERROR: {e}")
        if hasattr(e, "read"):
            print(f"[push] BODY: {e.read().decode('utf-8', 'ignore')}")


def broadcast_message(text: str):
    """廣播文字訊息給所有好友"""
    if not CHANNEL_ACCESS_TOKEN:
        return
    data = json.dumps({"messages": [{"type": "text", "text": text}]}).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/broadcast",
        data=data,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        print(f"[broadcast] SUCCESS: {resp.status}")
    except Exception as e:
        print(f"[broadcast] ERROR: {e}")
        if hasattr(e, "read"):
            print(f"[broadcast] BODY: {e.read().decode('utf-8', 'ignore')}")


def verify_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook 簽名"""
    if not CHANNEL_SECRET:
        return True  # 開發模式跳過驗證
    mac = hmac.new(CHANNEL_SECRET.encode("utf-8"), body, hashlib.sha256)
    return hmac.compare_digest(
        base64.b64encode(mac.digest()).decode("utf-8"), signature
    )


def bot_invite_text() -> str:
    """生成 Bot 邀請文字"""
    if LINE_BOT_ID:
        return f"\n\n➡️ 加「生活優轉」\nhttps://line.me/ti/p/{LINE_BOT_ID}"
    return "\n\n👉 搜尋「生活優轉」加好友一起用！"
