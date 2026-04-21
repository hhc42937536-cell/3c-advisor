"""
Vercel 自動部署腳本
====================
用 Vercel API 直接上傳檔案並部署，不需要 git 或 Vercel CLI。

使用方式：
  python deploy_vercel.py

環境變數（或直接填在下方）：
  VERCEL_TOKEN=你的_Vercel_Token
  VERCEL_PROJECT_ID=你的_Project_ID
  VERCEL_TEAM_ID=你的_Team_ID（個人帳號不需要）

如何取得 Vercel Token：
  Vercel 網站 → Account Settings → Tokens → Create Token

如何取得 Project ID：
  Vercel 專案頁面 → Settings → General → Project ID
"""

import os, sys, json, hashlib, time
import urllib.request, urllib.error
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Token 自動讀取（env var → 共用 token 檔 → 手動輸入）──
def _load_tokens() -> dict:
    data = {}
    token_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".tokens.json",
    )
    if os.path.exists(token_file):
        try:
            data = json.loads(open(token_file, encoding="utf-8").read())
        except Exception:
            pass
    return data

_tk = _load_tokens()
VERCEL_TOKEN      = os.environ.get("VERCEL_TOKEN", _tk.get("VERCEL_TOKEN", ""))
VERCEL_PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", _tk.get("VERCEL_PROJECT_ID_生活優轉", ""))
VERCEL_TEAM_ID    = os.environ.get("VERCEL_TEAM_ID", _tk.get("VERCEL_TEAM_ID", ""))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 要上傳的檔案清單（相對於 line-bot 目錄）
DEPLOY_FILES = [
    "api/webhook.py",
    "requirements.txt",
    "vercel.json",
    "pyproject.toml",
    "accupass_cache.json",
    "restaurant_cache.json",
    "liff/index.html",
    "liff/images/ramen.jpg",
    "liff/images/calendar.jpg",
    "liff/images/coin.jpg",
    "liff/images/dumbbell.jpg",
    "liff/images/car.jpg",
    "liff/images/wrench.jpg",
]


def api_request(method: str, path: str, body=None) -> dict:
    """呼叫 Vercel API"""
    url = f"https://api.vercel.com{path}"
    if VERCEL_TEAM_ID:
        sep = "&" if "?" in url else "?"
        url += f"{sep}teamId={VERCEL_TEAM_ID}"

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        raise RuntimeError(f"Vercel API {e.code}: {err.get('error', {}).get('message', str(e))}")


def upload_file(file_path: str) -> str:
    """上傳單一檔案到 Vercel，回傳 sha1"""
    with open(os.path.join(BASE_DIR, file_path), "rb") as f:
        content = f.read()

    sha1 = hashlib.sha1(content).hexdigest()
    size = len(content)

    url = "https://api.vercel.com/v2/files"
    if VERCEL_TEAM_ID:
        url += f"?teamId={VERCEL_TEAM_ID}"

    headers = {
        "Authorization": f"Bearer {VERCEL_TOKEN}",
        "Content-Type": "application/octet-stream",
        "x-vercel-digest": sha1,
        "Content-Length": str(size),
    }
    req = urllib.request.Request(url, data=content, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            pass  # 200 or 409 (already exists) both OK
    except urllib.error.HTTPError as e:
        if e.code != 409:  # 409 = 已存在，OK
            raise
    return sha1


def deploy():
    print("=" * 50)
    print("Vercel 自動部署")
    print("=" * 50)

    if not VERCEL_TOKEN:
        print("\n[ERROR] 缺少 VERCEL_TOKEN！")
        print("請到 Vercel → Account Settings → Tokens → Create Token")
        print("然後把 token 填入 deploy_vercel.py 的 VERCEL_TOKEN 變數")
        print("\n或設定環境變數：")
        print("  set VERCEL_TOKEN=你的token")
        print("  python deploy_vercel.py")
        return False

    if not VERCEL_PROJECT_ID:
        print("\n[ERROR] 缺少 VERCEL_PROJECT_ID！")
        print("請到 Vercel 專案頁 → Settings → General → Project ID")
        return False

    # 1. 上傳所有檔案
    print("\n[1/3] 上傳檔案...")
    file_meta = []
    for rel_path in DEPLOY_FILES:
        full_path = os.path.join(BASE_DIR, rel_path)
        if not os.path.exists(full_path):
            print(f"  跳過（不存在）: {rel_path}")
            continue
        try:
            sha1 = upload_file(rel_path)
            size = os.path.getsize(full_path)
            # Vercel 專案 rootDirectory = "line-bot"，上傳時需加前綴
            file_meta.append({"file": f"line-bot/{rel_path}", "sha": sha1, "size": size})
            print(f"  ✅ {rel_path} ({size:,} bytes)")
        except Exception as e:
            print(f"  ❌ {rel_path}: {e}")
            return False

    # 2. 建立 deployment
    print("\n[2/3] 建立部署...")
    deploy_body = {
        "name": VERCEL_PROJECT_ID,
        "files": file_meta,
        "projectSettings": {
            "framework": None,
            "buildCommand": None,
            "outputDirectory": None,
            "rootDirectory": None,
        },
        "target": "production",
    }
    try:
        result = api_request("POST", f"/v13/deployments?projectId={VERCEL_PROJECT_ID}", deploy_body)
        deploy_id = result.get("id", "")
        deploy_url = result.get("url", "")
        print(f"  部署 ID: {deploy_id}")
        print(f"  URL: https://{deploy_url}")
    except Exception as e:
        print(f"  ❌ 建立部署失敗: {e}")
        return False

    # 3. 等待部署完成
    print("\n[3/3] 等待部署完成...")
    for attempt in range(20):
        time.sleep(10)
        try:
            status_result = api_request("GET", f"/v13/deployments/{deploy_id}")
            state = status_result.get("readyState", "UNKNOWN")
            print(f"  狀態: {state} ({attempt+1}/20)...")
            if state == "READY":
                print(f"\n✅ 部署成功！")
                print(f"   網址: https://{deploy_url}")
                return True
            elif state in ("ERROR", "CANCELED"):
                print(f"\n❌ 部署失敗: {state}")
                return False
        except Exception as e:
            print(f"  查詢狀態失敗: {e}")

    print("\n⚠️ 部署超時，請到 Vercel 網站確認")
    return False


if __name__ == "__main__":
    success = deploy()
    sys.exit(0 if success else 1)
