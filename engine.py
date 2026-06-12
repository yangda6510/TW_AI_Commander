import pandas as pd

# =========================
# 台股生命爆發 AI 操盤總司令
# V1.8 操盤實戰版：S/A 評級校正版
# =========================


def _to_bool(v):
    if isinstance(v, bool):
        return v
    if pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in ["true", "1", "yes", "y", "v", "✓", "✅", "是"]


def _to_num(v, default=0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def compute_indicators(hist):
    if hist is None or hist.empty or len(hist) < 20:
        return {}

    h = hist.sort_values("日期").copy()
    close = h["收盤價"]
    volume = h["成交股數"] if "成交股數" in h.columns else pd.Series([0] * len(h))

    last_close = float(close.iloc[-1])
    ma5 = float(close.rolling(5).mean().iloc[-1]) if len(h) >= 5 else 0
    ma10 = float(close.rolling(10).mean().iloc[-1]) if len(h) >= 10 else 0
    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(h) >= 20 else 0
    ma60 = float(close.rolling(60).mean().iloc[-1]) if len(h) >= 60 else 0

    ma20_prev = float(close.rolling(20).mean().iloc[-2]) if len(h) >= 21 else ma20
    ma60_prev = float(close.rolling(60).mean().iloc[-2]) if len(h) >= 61 else ma60

    high20 = float(close.iloc[-21:-1].max()) if len(h) >= 21 else float(close.max())
    vol20 = float(volume.rolling(20).mean().iloc[-1]) if len(h) >= 20 else 0
    last_vol = float(volume.iloc[-1]) if len(h) else 0
    volume_ratio = round(last_vol / vol20, 2) if vol20 > 0 else 0

    day_low = bool(len(h) >= 21 and last_close > float(close.iloc[-20]))
    week_low = bool(len(h) >= 61 and last_close > float(close.iloc[-60]))
    month_low = bool(len(h) >= 121 and last_close > float(close.iloc[-120]))

    day_low_prev = bool(len(h) >= 22 and float(close.iloc[-2]) > float(close.iloc[-21]))
    week_low_prev = bool(len(h) >= 62 and float(close.iloc[-2]) > float(close.iloc[-61]))
    month_low_prev = bool(len(h) >= 122 and float(close.iloc[-2]) > float(close.iloc[-121]))

    day_turn = day_low and not day_low_prev
    week_turn = week_low and not week_low_prev
    month_turn = month_low and not month_low_prev

    deduct_count = sum([day_low, week_low, month_low])
    breakout20 = bool(last_close > high20)
    true_breakout = bool(breakout20 and volume_ratio >= 1.2)
    dev20 = round((last_close / ma20 - 1) * 100, 2) if ma20 > 0 else 0

    return {
        "5MA": round(ma5, 2),
        "10MA": round(ma10, 2),
        "20MA": round(ma20, 2),
        "60MA": round(ma60, 2),
        "20日高點": round(high20, 2),
        "量比": volume_ratio,
        "20MA乖離%": dev20,
        "日扣低": day_low,
        "週扣低": week_low,
        "月扣低": month_low,
        "日剛轉扣低": day_turn,
        "週剛轉扣低": week_turn,
        "月剛轉扣低": month_turn,
        "扣低共振": deduct_count,
        "突破20日高": breakout20,
        "真突破": true_breakout,
        "20MA上揚": ma20 > ma20_prev,
        "60MA上揚": ma60 > ma60_prev,
        "多頭排列": ma5 > ma10 > ma20 if ma20 > 0 else False,
        "站上20MA": last_close > ma20 if ma20 > 0 else False,
        "20MA大於60MA": ma20 > ma60 if ma60 > 0 else False,
    }


def calc_life(row):
    score = 0

    if _to_bool(row.get("站上20MA", False)):
        score += 5
    if _to_bool(row.get("20MA大於60MA", False)):
        score += 5
    if _to_bool(row.get("多頭排列", False)):
        score += 5
    if _to_bool(row.get("20MA上揚", False)):
        score += 5
    if _to_bool(row.get("60MA上揚", False)):
        score += 5

    if _to_bool(row.get("日扣低", False)):
        score += 5
    if _to_bool(row.get("週扣低", False)):
        score += 8
    if _to_bool(row.get("月扣低", False)):
        score += 12

    if _to_bool(row.get("日剛轉扣低", False)):
        score += 2
    if _to_bool(row.get("週剛轉扣低", False)):
        score += 4
    if _to_bool(row.get("月剛轉扣低", False)):
        score += 6

    if _to_bool(row.get("突破20日高", False)):
        score += 5
    if _to_bool(row.get("真突破", False)):
        score += 10

    vr = _to_num(row.get("量比", 0))
    if vr >= 1.2:
        score += 3
    if vr >= 1.5:
        score += 5
    if vr >= 2:
        score += 5

    dev = _to_num(row.get("20MA乖離%", 999), 999)
    if dev <= 5:
        score += 10
    elif dev <= 10:
        score += 5

    return max(0, min(100, round(score, 0)))


def calc_power(row):
    power = 0

    if _to_bool(row.get("月扣低", False)):
        power += 25
    if _to_bool(row.get("週扣低", False)):
        power += 15
    if _to_bool(row.get("日扣低", False)):
        power += 10

    if _to_bool(row.get("月剛轉扣低", False)):
        power += 10
    if _to_bool(row.get("週剛轉扣低", False)):
        power += 6
    if _to_bool(row.get("日剛轉扣低", False)):
        power += 4

    if _to_bool(row.get("突破20日高", False)):
        power += 5
    if _to_bool(row.get("真突破", False)):
        power += 15

    vr = _to_num(row.get("量比", 0))
    if vr >= 1.2:
        power += 5
    if vr >= 1.5:
        power += 5
    if vr >= 2:
        power += 10

    if _to_bool(row.get("20MA上揚", False)):
        power += 5
    if _to_bool(row.get("60MA上揚", False)):
        power += 5

    return max(0, min(100, round(power, 0)))


def calc_grade(row):
    life = _to_num(row.get("生命值", 0))
    power = _to_num(row.get("馬力", 0))
    deduct = _to_num(row.get("扣低共振", 0))
    vr = _to_num(row.get("量比", 0))
    dev = _to_num(row.get("20MA乖離%", 999), 999)

    true_breakout = _to_bool(row.get("真突破", False))
    breakout20 = _to_bool(row.get("突破20日高", False))
    stand20 = _to_bool(row.get("站上20MA", False))
    ma20_up = _to_bool(row.get("20MA上揚", False))
    ma60_up = _to_bool(row.get("60MA上揚", False))
    bull = _to_bool(row.get("多頭排列", False))
    ma20_gt_ma60 = _to_bool(row.get("20MA大於60MA", False))

    safe_not_hot = dev <= 12
    not_too_cold = stand20 or ma20_up

    if (
        life >= 82
        and power >= 85
        and deduct >= 2
        and true_breakout
        and safe_not_hot
        and not_too_cold
    ):
        return "S"

    strong_setup = (
        life >= 75
        and power >= 70
        and deduct >= 2
        and safe_not_hot
        and not_too_cold
    )

    breakout_setup = (
        life >= 70
        and power >= 75
        and deduct >= 2
        and (breakout20 or true_breakout or vr >= 1.5)
        and safe_not_hot
        and not_too_cold
    )

    trend_setup = (
        life >= 72
        and power >= 65
        and deduct >= 2
        and ma20_up
        and (ma60_up or ma20_gt_ma60 or bull)
        and safe_not_hot
    )

    if strong_setup or breakout_setup or trend_setup:
        return "A"

    if (
        life >= 60
        and power >= 55
        and (deduct >= 2 or stand20 or ma20_up)
    ):
        return "B"

    return "X"


def calc_status(row):
    grade = row.get("等級", "X")
    life = _to_num(row.get("生命值", 0))
    power = _to_num(row.get("馬力", 0))
    deduct = _to_num(row.get("扣低共振", 0))
    true_breakout = _to_bool(row.get("真突破", False))
    dev = _to_num(row.get("20MA乖離%", 999), 999)

    if grade == "S":
        return "🚀 主升攻擊"

    if grade == "A":
        if true_breakout:
            return "🔥 真突破"
        if deduct >= 3 and power >= 75:
            return "🔥 強勢整理"
        return "🟢 可布局"

    if grade == "B":
        if deduct >= 2:
            return "🌱 準備發動"
        return "👀 觀察整理"

    if dev > 15:
        return "⚠️ 乖離過大"

    if life < 45 or power < 45:
        return "🔴 轉弱"

    return "🔴 暫不看"
