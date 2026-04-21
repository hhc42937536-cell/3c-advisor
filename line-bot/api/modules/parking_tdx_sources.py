"""Parking source fetchers split from parking_sources.py."""

from __future__ import annotations

import json
import ssl as _ssl
import threading
import time as _time
import urllib.request


def get_tdx_parking(
    lat: float,
    lon: float,
    radius: int = 1500,
    *,
    get_tdx_token,
    coords_to_tdx_city,
    tdx_get,
    haversine,
    redis_get,
    redis_set,
    tdx_lots_cache: dict,
    tdx_avail_cache: dict,
    tdx_cache_ttl: int,
) -> list:
    """TDX 路外停車場（城市路徑）+ 即時車位，type='lot'；城市資料快取 90 秒
    兩個 API 並行呼叫，避免超過 Vercel 10s 限制"""
    token = get_tdx_token()
    if not token:
        return []

    city = coords_to_tdx_city(lat, lon)
    now  = _time.time()
    print(f"[TDX] 查詢城市: {city}，座標: ({lat}, {lon})")

    # ── Redis 持久快取（跨 instance）優先，再 in-memory，最後才打 TDX ──
    lots     = redis_get(f"tdx_lots_{city}")
    avail_map = redis_get(f"tdx_avail_{city}")

    if lots is not None:
        print(f"[TDX] lots Redis命中 ({len(lots)} 筆)")
    elif city in tdx_lots_cache and now - tdx_lots_cache[city][0] < tdx_cache_ttl:
        lots = tdx_lots_cache[city][1]
        print(f"[TDX] lots 記憶體命中 ({len(lots)} 筆)")

    if avail_map is not None:
        print(f"[TDX] avail Redis命中 ({len(avail_map)} 筆)")
    elif city in tdx_avail_cache and now - tdx_avail_cache[city][0] < 60:
        avail_map = tdx_avail_cache[city][1]
        print(f"[TDX] avail 記憶體命中")

    lots_buf:  list = []
    avail_buf: list = []

    def _fetch_lots():
        try:
            data = tdx_get(f"Parking/OffStreet/CarPark/City/{city}?$format=JSON", token, timeout=4)
            lots_buf.extend(data)
        except Exception as e:
            print(f"[TDX] lots 失敗: {e}")

    def _fetch_avail():
        try:
            data = tdx_get(f"Parking/OffStreet/ParkingAvailability/City/{city}?$format=JSON", token, timeout=4)
            avail_buf.extend(data)
        except Exception as e:
            print(f"[TDX] avail 失敗: {e}")

    threads = []
    if lots is None:
        t1 = threading.Thread(target=_fetch_lots, daemon=True)
        threads.append(t1); t1.start()
    if avail_map is None:
        t2 = threading.Thread(target=_fetch_avail, daemon=True)
        threads.append(t2); t2.start()

    for t in threads:
        t.join(timeout=4)

    if lots is None:
        lots = lots_buf
        tdx_lots_cache[city] = (now, lots)
        if lots:  # 只有非空才存 Redis，避免暫時失敗把空結果快取 24h
            redis_set(f"tdx_lots_{city}", lots, ttl=86400)
    if avail_map is None:
        avail_map = {a.get("CarParkID", ""): a for a in avail_buf}
        tdx_avail_cache[city] = (now, avail_map)
        if avail_map:  # 空結果不快取
            redis_set(f"tdx_avail_{city}", avail_map, ttl=180)

    print(f"[TDX] CarParks: {len(lots)}, Availabilities: {len(avail_map)}")

    result = []
    for lot in lots:
        pos   = lot.get("CarParkPosition") or lot.get("ParkingPosition") or {}
        p_lat = pos.get("PositionLat") or lot.get("PositionLat")
        p_lon = pos.get("PositionLon") or lot.get("PositionLon")
        if not p_lat or not p_lon:
            continue
        dist = haversine(lat, lon, float(p_lat), float(p_lon))
        if dist > radius:
            continue

        pid = lot.get("CarParkID", "")
        av  = avail_map.get(pid, {})

        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        name      = _zh(lot.get("CarParkName") or lot.get("ParkingName") or {}) or "停車場"
        addr      = _zh(lot.get("Address") or {})
        fare      = str(_zh(lot.get("FareDescription") or lot.get("PricingNote") or {}))[:30]
        total     = int(av.get("TotalSpaces") or lot.get("TotalCapacity") or 0)
        available = int(av.get("AvailableSpaces", -1))

        result.append({
            "name": name, "addr": addr, "fare": fare,
            "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
            "total": total, "available": available, "type": "lot",
        })

    result.sort(key=lambda x: x["dist"])
    return result


def get_yilan_parking(
    lat: float,
    lon: float,
    radius: int = 1500,
    *,
    get_tdx_token,
    tdx_get,
    redis_get,
    redis_set,
    haversine,
) -> list:
    """宜蘭縣停車場即時空位（opendataap2.e-land.gov.tw + TDX 座標）
    e-land API 有即時剩餘數但無座標；TDX YilanCounty 有座標但無即時空位。
    策略：TDX 取座標/名稱，e-land 補即時空位（按停車場名稱 fuzzy match）
    """
    try:
        # ── 1. TDX 取宜蘭縣停車場（有座標）──
        token = get_tdx_token()
        tdx_lots = redis_get("tdx_lots_YilanCounty")
        if tdx_lots is None:
            try:
                tdx_lots = tdx_get("Parking/OffStreet/CarPark/City/YilanCounty?$format=JSON", token, timeout=5)
                if tdx_lots:  # 空結果不快取，避免 24h 鎖死
                    redis_set("tdx_lots_YilanCounty", tdx_lots, ttl=86400)
            except Exception as e:
                print(f"[Yilan] TDX lots 失敗: {e}")
                tdx_lots = []

        # ── 2. e-land 即時空位（有剩餘數但無座標）──
        eland_map: dict = {}  # 名稱 → 剩餘數
        try:
            cached_avail = redis_get("yilan_avail")
            if cached_avail:
                eland_map = cached_avail
            else:
                ctx = _ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = _ssl.CERT_NONE
                url = ("https://opendataap2.e-land.gov.tw/./resource/files/"
                       "2023-02-12/62f4d78b604ba16b8cc1e856dd28d2c3.json")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    raw_data = json.loads(r.read())
                for item in (raw_data if isinstance(raw_data, list) else []):
                    name = item.get("名稱", "")
                    try:
                        avail = int(item.get("小車位剩餘數") or -1)
                    except Exception:
                        avail = -1
                    try:
                        total = int(item.get("小車位總數") or 0)
                    except Exception:
                        total = 0
                    if name:
                        eland_map[name] = {"available": avail, "total": total}
                if eland_map:  # 空結果不快取
                    redis_set("yilan_avail", eland_map, ttl=180)
                print(f"[Yilan] e-land 即時空位 {len(eland_map)} 筆")
        except Exception as e:
            print(f"[Yilan] e-land avail 失敗: {e}")

        # ── 3. 合併：TDX 座標 + e-land 空位 ──
        def _zh(obj):
            if isinstance(obj, dict):
                return obj.get("Zh_tw") or next(iter(obj.values()), "") if obj else ""
            return str(obj) if obj else ""

        result = []
        for lot in (tdx_lots or []):
            pos   = lot.get("CarParkPosition") or {}
            p_lat = pos.get("PositionLat")
            p_lon = pos.get("PositionLon")
            if not p_lat or not p_lon:
                continue
            dist = haversine(lat, lon, float(p_lat), float(p_lon))
            if dist > radius:
                continue
            name = _zh(lot.get("CarParkName") or {}) or "停車場"
            addr = _zh(lot.get("Address") or {})
            fare = str(_zh(lot.get("FareDescription") or {}))[:30]
            # fuzzy match：找 e-land 裡名稱包含 TDX 名稱的項目
            av_data = eland_map.get(name, {})
            if not av_data:
                for ename, edata in eland_map.items():
                    if name[:4] in ename or ename[:4] in name:
                        av_data = edata
                        break
            available = av_data.get("available", -1)
            total     = av_data.get("total", int(lot.get("TotalCapacity") or 0))
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": float(p_lat), "lon": float(p_lon), "dist": dist,
                "total": total, "available": available, "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Yilan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Yilan] 失敗: {e}")
        return []
