"""Tainan, Hsinchu, and Taoyuan parking source fetchers."""

from __future__ import annotations

import json
import ssl as _ssl
import urllib.request


def get_tainan_parking(lat: float, lon: float, radius: int = 1500, *, haversine) -> list:
    """台南市公有停車場即時車位（parkweb.tainan.gov.tw）"""
    try:
        url = "https://parkweb.tainan.gov.tw/api/parking.php"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read()
            data = json.loads(raw.decode("utf-8"))
        if isinstance(data, dict):
            # 可能包在 data key 內
            for k, v in data.items():
                if isinstance(v, list):
                    data = v
                    break
        result = []
        for lot in (data if isinstance(data, list) else []):
            lnglat = lot.get("lnglat", "")
            if not lnglat:
                continue
            try:
                # 格式: "lat,lng"（中文逗號或英文逗號）
                parts = lnglat.replace("，", ",").split(",")
                p_lat, p_lon = float(parts[0].strip()), float(parts[1].strip())
            except Exception:
                continue
            dist = haversine(lat, lon, p_lat, p_lon)
            if dist > radius:
                continue
            name      = lot.get("name", "停車場")
            addr      = lot.get("address", "")
            fare      = str(lot.get("chargeFee") or lot.get("chargeTime") or "")[:30]
            total     = int(lot.get("car_total") or 0)
            available = int(lot.get("car") if lot.get("car") is not None else -1)
            result.append({
                "name": name, "addr": addr, "fare": fare,
                "lat": p_lat, "lon": p_lon, "dist": dist,
                "total": total, "available": available,
                "type": "lot",
            })
        result.sort(key=lambda x: x["dist"])
        print(f"[Tainan] 找到 {len(result)} 個停車場（半徑 {radius}m）")
        return result
    except Exception as e:
        print(f"[Tainan] API 失敗: {e}")
        return []


def get_hsinchu_parking(lat: float, lon: float, radius: int = 1500, *, redis_get, redis_set, haversine) -> list:
    """新竹市路外停車場即時車位（hispark.hccg.gov.tw，即時更新）
    欄位：PARKINGNAME, ADDRESS, WEEKDAYS(費率), FREEQUANTITY(剩餘), TOTALQUANTITY(總),
          LONGITUDE, LATITUDE, UPDATETIME
    """
    try:
        cached = redis_get("hsinchu_lots")
        if cached:
            data = cached
        else:
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = _ssl.CERT_NONE
            req = urllib.request.Request(
                "https://hispark.hccg.gov.tw/OpenData/GetParkInfo",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6, context=ctx) as r:
                raw = r.read()
            data = json.loads(raw)
            if isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        data = v
                        break
            if data:  # 空結果不快取
                redis_set("hsinchu_lots", data, ttl=180)
            print(f"[Hsinchu] API 取得 {len(data)} 筆")

        result = []
        for lot in (data if isinstance(data, list) else []):
            try:
                p_lat = float(lot.get("LATITUDE") or 0)
                p_lon = float(lot.get("LONGITUDE") or 0)
                if not p_lat or not p_lon:
                    continue
                dist = haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("FREEQUANTITY") or -1)
                total     = int(lot.get("TOTALQUANTITY") or 0)
                fare      = str(lot.get("WEEKDAYS") or "")
                # 費率欄位可能很長，只取第一行
                fare = fare.split("\n")[0].split("\r")[0][:30]
                result.append({
                    "name":      lot.get("PARKINGNAME", "停車場"),
                    "addr":      lot.get("ADDRESS", ""),
                    "fare":      fare,
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Hsinchu] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Hsinchu] API 失敗: {e}")
        return []


def get_taoyuan_parking(lat: float, lon: float, radius: int = 1500, *, redis_get, redis_set, haversine) -> list:
    """桃園市路外停車場即時車位（桃園開放資料，每分鐘更新）
    API: opendata.tycg.gov.tw  wgsX=緯度, wgsY=經度（命名相反，請注意）
    """
    try:
        # Redis 2分鐘快取（此API每分鐘更新，2分鐘夠用）
        cached = redis_get("taoyuan_lots")
        if cached:
            data = cached
        else:
            req = urllib.request.Request(
                "https://opendata.tycg.gov.tw/api/dataset/"
                "f4cc0b12-86ac-40f9-8745-885bddc18f79/resource/"
                "0381e141-f7ee-450e-99da-2240208d1773/download",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                raw = r.read().decode("utf-8", "ignore")
            # 防止 Extra data（有時回傳非標準 JSON）
            start, end = raw.find("["), raw.rfind("]")
            data = json.loads(raw[start:end+1]) if start >= 0 else []
            if data:  # 空結果不快取
                redis_set("taoyuan_lots", data, ttl=120)
            print(f"[Taoyuan] API 取得 {len(data)} 筆")

        result = []
        for lot in data:
            try:
                # API 命名相反：wgsX=緯度, wgsY=經度
                p_lat = float(lot.get("wgsX", 0) or 0)
                p_lon = float(lot.get("wgsY", 0) or 0)
                if not p_lat or not p_lon:
                    continue
                dist = haversine(lat, lon, p_lat, p_lon)
                if dist > radius:
                    continue
                available = int(lot.get("surplusSpace", -1) or -1)
                total     = int(lot.get("totalSpace", 0)    or 0)
                result.append({
                    "name":      lot.get("parkName", "停車場"),
                    "addr":      lot.get("address", ""),
                    "fare":      str(lot.get("payGuide", ""))[:30],
                    "lat": p_lat, "lon": p_lon, "dist": dist,
                    "total":     total,
                    "available": available,
                    "type":      "lot",
                })
            except Exception:
                pass
        result.sort(key=lambda x: x["dist"])
        print(f"[Taoyuan] 半徑 {radius}m 內 {len(result)} 個停車場")
        return result
    except Exception as e:
        print(f"[Taoyuan] API 失敗: {e}")
        return []
