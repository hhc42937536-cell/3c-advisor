"""New Taipei parking source fetchers."""

from __future__ import annotations

import json
import math
import threading
import urllib.request
from collections import defaultdict


def get_ntpc_lot_parking(
    lat: float,
    lon: float,
    radius: int = 1500,
    *,
    ntpc_lot_static: dict,
    redis_get,
    redis_set,
    haversine,
    twd97tm2_to_wgs84,
) -> list:
    """新北市路外公有停車場（靜態資料 + 即時車位合併）
    靜態 dataset: B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68（含 TWD97 座標）
    即時 dataset: e09b35a5-a738-48cc-b0f5-570b67ad9c78（每 3 分鐘更新）
    """
    # ── 1. 靜態資料（記憶體 > Redis 24h > API）──
    static_data = ntpc_lot_static or redis_get("ntpc_lot_static") or {}
    if not static_data:
        try:
            req = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "B1464EF0-9C7C-4A6F-ABF7-6BDF32847E68/json?size=500",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                lots_raw = json.loads(r.read())
            for lot in lots_raw:
                lid = lot.get("ID", "")
                try:
                    tw_x = float(lot.get("TW97X", 0) or 0)
                    tw_y = float(lot.get("TW97Y", 0) or 0)
                    if not lid or tw_x < 100000:
                        continue
                    p_lat, p_lon = twd97tm2_to_wgs84(tw_x, tw_y)
                    static_data[lid] = {
                        "name": lot.get("NAME", "停車場"),
                        "addr": lot.get("ADDRESS", ""),
                        "fare": str(lot.get("PAYEX", ""))[:30],
                        "total": int(lot.get("TOTALCAR", 0) or 0),
                        "lat": p_lat, "lon": p_lon,
                    }
                except Exception:
                    pass
            ntpc_lot_static = static_data
            if static_data:  # 空結果不快取
                redis_set("ntpc_lot_static", static_data, ttl=86400)
            print(f"[NTPC lot] 靜態資料 {len(static_data)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 靜態資料失敗: {e}")
            return []
    else:
        ntpc_lot_static = static_data  # 同步記憶體
        print(f"[NTPC lot] 靜態快取命中 {len(static_data)} 筆")

    # ── 2. 即時車位（Redis 3min > API）──
    avail_map: dict = redis_get("ntpc_lot_avail") or {}
    if not avail_map:
        try:
            req2 = urllib.request.Request(
                "https://data.ntpc.gov.tw/api/datasets/"
                "e09b35a5-a738-48cc-b0f5-570b67ad9c78/json",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req2, timeout=5) as r:
                avail_list = json.loads(r.read())
            for av in avail_list:
                lid = av.get("ID", "")
                if lid:
                    try:
                        v = int(av.get("AVAILABLECAR", -1))
                        avail_map[lid] = max(v, -1)  # -9 表示未提供，統一設 -1
                    except (ValueError, TypeError):
                        avail_map[lid] = -1
            if avail_map:  # 空結果不快取
                redis_set("ntpc_lot_avail", avail_map, ttl=180)
            print(f"[NTPC lot] 即時車位 {len(avail_map)} 筆")
        except Exception as e:
            print(f"[NTPC lot] 即時車位失敗: {e}")

    # ── 3. 過濾半徑內的停車場 ──
    result = []
    for lid, info in static_data.items():
        d = haversine(lat, lon, info["lat"], info["lon"])
        if d > radius:
            continue
        available = avail_map.get(lid, -1)
        result.append({
            "name":      info["name"],
            "addr":      info["addr"],
            "fare":      info["fare"],
            "lat":       info["lat"], "lon": info["lon"],
            "dist":      d,
            "total":     info["total"],
            "available": available,
            "type":      "lot",
        })
    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC lot] 半徑 {radius}m 內 {len(result)} 個停車場")
    return result


def get_ntpc_street_parking(lat: float, lon: float, radius: int = 1500, *, haversine) -> list:
    """新北市路邊停車格即時狀態（NTPC open data）
    API 不支援空間過濾，採 5 頁並行下載後本地過濾，按路名分組回傳
    dataset: 54A507C4-C038-41B5-BF60-BBECB9D052C6
    cellstatus: Y=空位, N=有車
    """

    lat_delta = radius / 111000
    lon_delta = radius / (111000 * math.cos(math.radians(lat)))
    lat_min, lat_max = lat - lat_delta, lat + lat_delta
    lon_min, lon_max = lon - lon_delta, lon + lon_delta

    DATASET_ID = "54A507C4-C038-41B5-BF60-BBECB9D052C6"
    PAGE_SIZE  = 1000
    MAX_PAGES  = 5
    pages_data = [[] for _ in range(MAX_PAGES)]

    def fetch_page(i):
        url = (f"https://data.ntpc.gov.tw/api/datasets/{DATASET_ID}/json"
               f"?size={PAGE_SIZE}&page={i}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                pages_data[i] = json.loads(r.read()) or []
        except Exception as e:
            print(f"[NTPC] 第{i}頁失敗: {e}")

    threads = [threading.Thread(target=fetch_page, args=(i,)) for i in range(MAX_PAGES)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=4)

    # 按路名分組
    road_map: dict = defaultdict(lambda: {"spots": [], "lat": 0.0, "lon": 0.0, "fare": ""})

    for page_records in pages_data:
        for rec in page_records:
            try:
                p_lat = float(rec.get("latitude", 0))
                p_lon = float(rec.get("longitude", 0))
            except (ValueError, TypeError):
                continue
            if not (lat_min <= p_lat <= lat_max and lon_min <= p_lon <= lon_max):
                continue
            dist = haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue

            road = rec.get("roadname") or "路邊停車格"
            status = rec.get("cellstatus", "")
            entry = road_map[road]
            entry["spots"].append({"status": status, "dist": dist, "lat": p_lat, "lon": p_lon})
            if not entry["lat"] or dist < haversine(lat, lon, entry["lat"], entry["lon"]):
                entry["lat"] = p_lat
                entry["lon"] = p_lon
            if not entry["fare"] and rec.get("paycash"):
                entry["fare"] = rec["paycash"]

    if not road_map:
        print("[NTPC] 範圍內無路邊格資料（可能在這5頁內）")
        return []

    result = []
    for road, info in road_map.items():
        spots   = info["spots"]
        total   = len(spots)
        avail   = sum(1 for s in spots if s["status"] == "Y")
        nearest = min(spots, key=lambda s: s["dist"])
        result.append({
            "name":      road,
            "addr":      road,
            "fare":      info["fare"],
            "lat":       nearest["lat"],
            "lon":       nearest["lon"],
            "dist":      nearest["dist"],
            "total":     total,
            "available": avail,
            "type":      "street",
        })

    result.sort(key=lambda x: x["dist"])
    print(f"[NTPC] 找到 {len(result)} 條路段，共 {sum(r['total'] for r in result)} 格")
    return result
