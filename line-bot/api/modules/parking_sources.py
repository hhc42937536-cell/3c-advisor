"""Parking data source fetchers and aggregators."""

from __future__ import annotations

import threading
from modules.parking_city_sources import get_hsinchu_parking
from modules.parking_city_sources import get_ntpc_lot_parking
from modules.parking_city_sources import get_ntpc_street_parking
from modules.parking_city_sources import get_tainan_parking
from modules.parking_city_sources import get_taoyuan_parking
from modules.parking_tdx_sources import get_tdx_parking
from modules.parking_tdx_sources import get_yilan_parking


def get_nearby_parking(
    lat: float,
    lon: float,
    radius: int = 1500,
    *,
    coords_to_tdx_city,
    get_yilan_parking,
    get_ntpc_street_parking,
    get_ntpc_lot_parking,
    get_taoyuan_parking,
    get_hsinchu_parking,
    get_tainan_parking,
    get_tdx_parking,
) -> dict:
    """多來源停車資料整合，回傳 {'street': [...], 'lot': [...], 'city': str}"""
    city = coords_to_tdx_city(lat, lon)
    street_result: list = []
    lot_result:    list = []

    def _run_parallel(fn1, fn2, timeout=5):
        """並行執行兩個函式，各自 timeout 秒，超時只記 log 不崩潰"""
        t1 = threading.Thread(target=fn1, daemon=True)
        t2 = threading.Thread(target=fn2, daemon=True)
        t1.start(); t2.start()
        t1.join(timeout=timeout); t2.join(timeout=timeout)
        if t1.is_alive(): print(f"[parking] thread1 超時仍在執行")
        if t2.is_alive(): print(f"[parking] thread2 超時仍在執行")

    if city == "YilanCounty":
        lot_result = get_yilan_parking(lat, lon, radius)
    elif city == "NewTaipei":
        def fetch_street(): street_result.extend(get_ntpc_street_parking(lat, lon, radius))
        def fetch_lot():
            try:
                lot_result.extend(get_ntpc_lot_parking(lat, lon, radius))
            except Exception as e:
                print(f"[NTPC lot] thread 異常: {e}")
        _run_parallel(fetch_street, fetch_lot)
    elif city == "Taoyuan":
        def fetch_tycg(): lot_result.extend(get_taoyuan_parking(lat, lon, radius))
        def fetch_tdx_ty():
            tdx = get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_tycg, fetch_tdx_ty)
    elif city == "Hsinchu":
        def fetch_hsinchu(): lot_result.extend(get_hsinchu_parking(lat, lon, radius))
        def fetch_tdx_hc():
            tdx = get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_hsinchu, fetch_tdx_hc)
    elif city == "Tainan":
        def fetch_tainan(): lot_result.extend(get_tainan_parking(lat, lon, radius))
        def fetch_tdx():
            tdx = get_tdx_parking(lat, lon, radius)
            existing = {p["name"] for p in lot_result}
            lot_result.extend(p for p in tdx if p["name"] not in existing)
        _run_parallel(fetch_tainan, fetch_tdx)
    else:
        lot_result = get_tdx_parking(lat, lon, radius)

    return {
        "street": street_result[:8] if isinstance(street_result, list) else [],
        "lot":    lot_result[:6]    if isinstance(lot_result,    list) else [],
        "city":   city or "Unknown",
    }
