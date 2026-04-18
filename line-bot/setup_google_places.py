"""
一鍵設定 Google Places API + 建 Supabase 表 + 部署
======================================================
執行：python setup_google_places.py
"""

import os, sys, json, time
import urllib.request, urllib.error

sys.stdout = __import__('io').TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ── 從 deploy_vercel.py 讀取 Vercel 設定 ──────────────────────
VERCEL_TOKEN      = os.environ.get("VERCEL_TOKEN", "")
VERCEL_PROJECT_ID = os.environ.get("VERCEL_PROJECT_ID", "")
VERCEL_TEAM_ID    = ""

def vercel_api(method, path, body=None):
    url = f"https://api.vercel.com{path}"
    if VERCEL_TEAM_ID:
        url += ("&" if "?" in url else "?") + f"teamId={VERCEL_TEAM_ID}"
    headers = {"Authorization": f"Bearer {VERCEL_TOKEN}", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        raise RuntimeError(f"{e.code}: {err.get('error',{}).get('message', str(err))}")


def get_vercel_env(key_name):
    """從 Vercel 專案取得環境變數明文值"""
    try:
        resp = vercel_api("GET", f"/v9/projects/{VERCEL_PROJECT_ID}/env")
        envs = resp.get("envs", [])
        for e in envs:
            if e.get("key") == key_name:
                env_id = e["id"]
                detail = vercel_api("GET", f"/v1/projects/{VERCEL_PROJECT_ID}/env/{env_id}")
                return detail.get("value", "")
    except Exception as ex:
        print(f"  ⚠️  無法從 Vercel 取得 {key_name}: {ex}")
    return ""


def set_vercel_env(key_name, value):
    """新增或更新 Vercel 環境變數"""
    # 先取得現有 ID（若已存在要用 PATCH）
    try:
        resp = vercel_api("GET", f"/v9/projects/{VERCEL_PROJECT_ID}/env")
        existing = {e["key"]: e["id"] for e in resp.get("envs", [])}
    except:
        existing = {}

    body = {"key": key_name, "value": value, "type": "encrypted",
            "target": ["production", "preview", "development"]}
    if key_name in existing:
        vercel_api("PATCH", f"/v9/projects/{VERCEL_PROJECT_ID}/env/{existing[key_name]}", body)
    else:
        vercel_api("POST", f"/v9/projects/{VERCEL_PROJECT_ID}/env", body)


def create_supabase_table(supabase_url, supabase_key):
    """用 Supabase REST API + RPC 建立 user_eaten_restaurants 表"""
    sql = """
    create table if not exists user_eaten_restaurants (
        id bigserial primary key,
        uid_hash text not null,
        restaurant_name text not null,
        city text default '',
        created_at timestamptz default now()
    );
    create index if not exists idx_eaten_uid_time
        on user_eaten_restaurants (uid_hash, created_at desc);
    """
    # 用 Supabase SQL endpoint（Management API 不需要，用 rpc 也可以）
    # 先試 /rest/v1/rpc/exec_sql（需要 pg_net 或自訂函數，不一定有）
    # 改用 Management API
    # 從 SUPABASE_URL 提取 project ref（格式：https://{ref}.supabase.co）
    import re
    m = re.search(r'https://([^.]+)\.supabase\.co', supabase_url)
    if not m:
        print("  ⚠️  無法解析 Supabase project ref，請手動建表")
        return False
    project_ref = m.group(1)

    # 用 Supabase Management API 執行 SQL
    # service_role key 有這個權限
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    body = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {supabase_key}",
                 "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            result = json.loads(r.read())
            print(f"  ✅ Supabase 建表成功")
            return True
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        # 若 Management API 不支援，改用 Supabase REST + SQL Editor
        print(f"  ⚠️  Management API 建表失敗（{e.code}），改用備用方法...")
        return _create_table_fallback(supabase_url, supabase_key)
    except Exception as ex:
        print(f"  ⚠️  建表失敗: {ex}")
        return _create_table_fallback(supabase_url, supabase_key)


def _create_table_fallback(supabase_url, supabase_key):
    """嘗試用 Supabase SQL function 建表（fallback）"""
    # 嘗試插一筆測試資料，若表不存在會報 42P01
    url = f"{supabase_url}/rest/v1/user_eaten_restaurants"
    test_body = json.dumps({"uid_hash": "__test__", "restaurant_name": "__ping__"}).encode()
    req = urllib.request.Request(
        url, data=test_body,
        headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}",
                 "Content-Type": "application/json", "Prefer": "return=minimal"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            # 表已存在，清掉測試資料
            del_url = f"{supabase_url}/rest/v1/user_eaten_restaurants?uid_hash=eq.__test__"
            del_req = urllib.request.Request(
                del_url,
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                method="DELETE",
            )
            try: urllib.request.urlopen(del_req, timeout=5)
            except: pass
            print("  ✅ user_eaten_restaurants 表已存在，無需建立")
            return True
    except urllib.error.HTTPError as e:
        if e.code in (404, 400):
            print(f"\n{'='*55}")
            print("  ❗ 需要手動在 Supabase 建表，執行以下 SQL：")
            print(f"{'='*55}")
            print("""
  create table user_eaten_restaurants (
    id bigserial primary key,
    uid_hash text not null,
    restaurant_name text not null,
    city text default '',
    created_at timestamptz default now()
  );
  create index on user_eaten_restaurants (uid_hash, created_at desc);
""")
            print(f"{'='*55}")
            print("  路徑：Supabase → SQL Editor → New Query → 貼上 → Run")
            return False
        return False


def deploy():
    print("\n🚀 開始部署到 Vercel...")
    import subprocess
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "deploy_vercel.py")],
        capture_output=True, text=True, encoding='utf-8', errors='replace'
    )
    if result.returncode == 0:
        lines = result.stdout.strip().splitlines()
        for line in lines[-5:]:
            if line.strip():
                print(f"  {line}")
        print("✅ 部署完成！")
    else:
        print("❌ 部署失敗")
        print(result.stderr[-300:] or result.stdout[-300:])


def main():
    print("=" * 55)
    print("  生活優轉 Google Places 一鍵設定")
    print("=" * 55)

    # ── Step 1: 取得 Supabase 憑證 ──
    print("\n[1/4] 從 Vercel 取得 Supabase 憑證...")
    supabase_url = get_vercel_env("SUPABASE_URL")
    supabase_key = get_vercel_env("SUPABASE_KEY")
    if supabase_url and supabase_key:
        print(f"  ✅ SUPABASE_URL: {supabase_url[:30]}...")
        print(f"  ✅ SUPABASE_KEY: {supabase_key[:15]}...")
    else:
        print("  ⚠️  找不到 Supabase 憑證，跳過建表步驟")

    # ── Step 2: 建 Supabase 表 ──
    if supabase_url and supabase_key:
        print("\n[2/4] 建立 user_eaten_restaurants 表...")
        create_supabase_table(supabase_url, supabase_key)
    else:
        print("\n[2/4] 跳過（無 Supabase 憑證）")

    # ── Step 3: 設定 Google Places API Key ──
    print("\n[3/4] 設定 Google Places API Key")
    existing_key = get_vercel_env("GOOGLE_PLACES_API_KEY")
    if existing_key:
        print(f"  目前已設定：{existing_key[:10]}...")
        ans = input("  要更新嗎？(y/N) ").strip().lower()
        if ans != "y":
            print("  保留原有金鑰")
            need_set = False
        else:
            need_set = True
    else:
        print("  尚未設定 GOOGLE_PLACES_API_KEY")
        need_set = True

    if need_set:
        print()
        print("  取得方式：")
        print("  1. 前往 https://console.cloud.google.com/apis/credentials")
        print("  2. 建立 API Key")
        print("  3. 開啟 'Places API' + 'Maps JavaScript API'")
        print()
        api_key = input("  請貼上你的 Google Places API Key：").strip()
        if api_key:
            print("  正在寫入 Vercel 環境變數...")
            try:
                set_vercel_env("GOOGLE_PLACES_API_KEY", api_key)
                print("  ✅ Google Places API Key 設定完成")
            except Exception as e:
                print(f"  ❌ 設定失敗: {e}")
        else:
            print("  ⚠️  跳過（未輸入）— 功能會 fallback 到靜態資料庫")

    # ── Step 4: 部署 ──
    print("\n[4/4] 部署最新 webhook.py 到 Vercel")
    ans = input("  現在部署？(Y/n) ").strip().lower()
    if ans != "n":
        deploy()
    else:
        print("  跳過部署，稍後執行 python deploy_vercel.py")

    print("\n" + "=" * 55)
    print("  完成！功能摘要：")
    print("  ✅ Google Places 即時搜尋（有 API key 時）")
    print("  ✅ 照片卡片 Carousel")
    print("  ✅ 吃過了按鈕（Supabase 記憶）")
    print("  ✅ 半徑 fallback 500m→1→2→3km")
    print("=" * 55)


if __name__ == "__main__":
    main()
