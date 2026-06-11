import pandas as pd

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

    # 扣低：現在價格 > N日前價格，視為未來扣低較有利
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

    # =====================
    # 趨勢引擎 25
    # =====================

    if row.get("站上20MA", False):
        score += 5

    if row.get("20MA大於60MA", False):
        score += 5

    if row.get("多頭排列", False):
        score += 5

    if row.get("20MA上揚", False):
        score += 5

    if row.get("60MA上揚", False):
        score += 5


    # =====================
    # 扣低引擎 37
    # =====================

    if row.get("日扣低", False):
        score += 5

    if row.get("週扣低", False):
        score += 8

    if row.get("月扣低", False):
        score += 12


    if row.get("日剛轉扣低", False):
        score += 2

    if row.get("週剛轉扣低", False):
        score += 4

    if row.get("月剛轉扣低", False):
        score += 6


    # =====================
    # 真突破引擎 15
    # =====================

    if row.get("突破20日高", False):
        score += 5

    if row.get("真突破", False):
        score += 10


    # =====================
    # 量能引擎 13
    # =====================

    vr = row.get("量比", 0)

    if vr >= 1.2:
        score += 3

    if vr >= 1.5:
        score += 5

    if vr >= 2:
        score += 5


    # =====================
    # 安全分 10
    # =====================

    dev = row.get("20MA乖離%", 999)

    if dev <= 5:
        score += 10

    elif dev <= 10:
        score += 5


    return max(0, min(100, round(score, 0)))

    return max(0, min(100, round(score, 0)))

def calc_power(row):

    power = 0


    # =====================
    # 扣低強度 50
    # =====================

    if row.get("月扣低", False):
        power += 25

    if row.get("週扣低", False):
        power += 15

    if row.get("日扣低", False):
        power += 10


    if row.get("月剛轉扣低", False):
        power += 10

    if row.get("週剛轉扣低", False):
        power += 6

    if row.get("日剛轉扣低", False):
        power += 4


    # =====================
    # 突破 20
    # =====================

    if row.get("突破20日高", False):
        power += 5

    if row.get("真突破", False):
        power += 15


    # =====================
    # 量能 20
    # =====================

    vr = row.get("量比", 0)

    if vr >= 1.2:
        power += 5

    if vr >= 1.5:
        power += 5

    if vr >= 2:
        power += 10


    # =====================
    # 趨勢加速 10
    # =====================

    if row.get("20MA上揚", False):
        power += 5

    if row.get("60MA上揚", False):
        power += 5


    return max(0, min(100, round(power, 0)))

def calc_grade(row):

    life = row.get("生命值", 0)
    power = row.get("馬力", 0)
    deduct = row.get("扣低共振", 0)

    if (
        life >= 90
        and power >= 85
        and deduct >= 2
        and row.get("真突破", False)
    ):
        return "S"

    elif (
        life >= 80
        and power >= 70
    ):
        return "A"

    elif (
        life >= 70
        and power >= 60
    ):
        return "B"

    return "X"

def calc_status(row):
    grade = row.get("等級", "X")
    deduct = row.get("扣低共振", 0)

    if grade == "S":
        return "🚀 主升攻擊"
    if grade == "A":
        return "🔥 強勢整理"
    if grade == "B" and deduct >= 2:
        return "🌱 準備發動"
    if grade == "B":
        return "👀 觀察整理"
    return "🔴 轉弱"
