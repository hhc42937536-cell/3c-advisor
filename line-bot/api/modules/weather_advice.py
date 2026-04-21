"""Pure weather presentation and advice helpers."""

from __future__ import annotations

import datetime as _dt


def wx_icon(wx: str) -> str:
    if "晴" in wx and "雲" not in wx:
        return "☀️"
    if "晴" in wx:
        return "🌤️"
    if "雷" in wx:
        return "⛈️"
    if "雨" in wx:
        return "🌧️"
    if "陰" in wx:
        return "☁️"
    if "多雲" in wx:
        return "⛅"
    if "雪" in wx:
        return "❄️"
    return "🌤️"


def outfit_advice(max_t: int, min_t: int, pop: int) -> tuple:
    """Return outfit advice, supporting note, and umbrella hint."""
    if max_t >= 32:
        clothes, note = "輕薄短袖＋透氣材質", "防曬乳必備，帽子加分，小心中暑"
    elif max_t >= 28:
        clothes, note = "短袖為主，薄外套備著", "室內冷氣強，包包放一件薄外套"
    elif max_t >= 24:
        clothes, note = "薄長袖或短袖＋輕便外套", "早晚涼，外套放包包最方便"
    elif max_t >= 20:
        clothes, note = "輕便外套或薄夾克", "早晚溫差大，多一層最安全"
    elif max_t >= 16:
        clothes, note = "毛衣＋外套", "圍巾帶著，隨時可以拿出來用"
    elif max_t >= 12:
        clothes, note = "厚外套＋衛衣", "手套、圍巾都考慮帶上"
    else:
        clothes, note = "羽絨衣＋多層次穿搭", "室內室外差很多，穿脫方便最重要"

    umbrella = ""
    if pop >= 70:
        umbrella = "☂️ 雨傘必帶！降雨機率很高"
    elif pop >= 40:
        umbrella = "🌂 建議帶折疊傘備用"
    elif pop >= 20:
        umbrella = "☁️ 零星降雨可能，輕便傘備著"
    return clothes, note, umbrella


def estimate_uvi(wx: str, max_t: int) -> dict:
    """Estimate UV level from weather text and temperature without external APIs."""
    hour = (_dt.datetime.utcnow() + _dt.timedelta(hours=8)).hour

    if hour < 7 or hour > 17:
        return {"ok": True, "label": "☀️ 紫外線：低（日落後）", "emoji": "🟢"}

    if max_t >= 33:
        base = 10
    elif max_t >= 30:
        base = 8
    elif max_t >= 27:
        base = 6
    elif max_t >= 23:
        base = 4
    else:
        base = 3

    if "雨" in wx:
        base = max(1, base - 4)
    elif "陰" in wx:
        base = max(2, base - 3)
    elif "雲" in wx:
        base = max(3, base - 1)

    if 10 <= hour <= 14:
        uvi = base
    elif 9 <= hour <= 15:
        uvi = max(2, base - 1)
    elif 7 <= hour <= 17:
        uvi = max(1, base - 2)
    else:
        uvi = max(1, base - 3)

    if uvi <= 2:
        level = "低量"
    elif uvi <= 5:
        level = "中量"
    elif uvi <= 7:
        level = "高量"
    elif uvi <= 10:
        level = "過量"
    else:
        level = "危險"

    advice = ""
    if uvi >= 6:
        advice = "建議擦防曬、戴帽子"
    elif uvi >= 3:
        advice = "外出建議擦防曬"

    label = f"☀️ 紫外線 {level}（UV {uvi}）"
    if advice:
        label += f"　{advice}"
    return {"ok": True, "label": label}
