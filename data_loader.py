import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

import pandas as pd
import requests

HEADERS = {"User-Agent": "Mozilla/5.0"}
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

TWSE_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_ALL_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"


def read_pool_from_csv_file(path="stock_pool.csv"):
    p = Path(path)
    if p.exists():
        return pd.read_csv(p, dtype=str)
    return pd.DataFrame(columns=["代號", "名稱", "族群", "市場"])


def to_number(x):
    if pd.isna(x):
        return 0.0
    s = (
        str(x)
        .replace(",", "")
        .replace("--", "")
        .replace("X", "")
        .replace("+", "")
        .replace('"', "")
        .strip()
    )
    if s in ["", "-", "----", "nan", "None", "除權息", "N/A", "null"]:
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def pick_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def fetch_json(url, timeout=20):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def normalize_quote_df(raw, market_name):
    df = pd.DataFrame(raw)
    if df.empty:
        return df

    code_col = pick_col(df, ["Code", "SecuritiesCompanyCode", "股票代號", "證券代號", "代號", "公司代號"])
    name_col = pick_col(df, ["Name", "CompanyName", "SecuritiesCompanyName", "股票名稱", "證券名稱", "名稱", "公司名稱"])
    close_col = pick_col(df, ["ClosingPrice", "Close", "收盤價", "收盤", "最新價"])
    vol_col = pick_col(df, ["TradeVolume", "Volume", "成交股數", "成交量"])
    val_col = pick_col(df, ["TradeValue", "成交金額", "成交值"])
    high_col = pick_col(df, ["HighestPrice", "High", "最高價", "最高"])
    low_col = pick_col(df, ["LowestPrice", "Low", "最低價", "最低"])
    open_col = pick_col(df, ["OpeningPrice", "Open", "開盤價", "開盤"])
    pct_col = pick_col(df, ["ChangeRate", "漲跌幅", "漲跌百分比", "漲跌幅(%)"])
    change_col = pick_col(df, ["Change", "漲跌價差", "漲跌"])

    out = pd.DataFrame()
    out["代號"] = df[code_col].astype(str).str.extract(r"(\d+)")[0] if code_col else ""
    out["名稱"] = df[name_col].astype(str) if name_col else ""
    out["市場來源"] = market_name
    out["收盤價"] = df[close_col].map(to_number) if close_col else 0
    out["成交股數"] = df[vol_col].map(to_number) if vol_col else 0
    out["成交金額"] = df[val_col].map(to_number) if val_col else 0
    out["最高價"] = df[high_col].map(to_number) if high_col else 0
    out["最低價"] = df[low_col].map(to_number) if low_col else 0
    out["開盤價"] = df[open_col].map(to_number) if open_col else 0
    out["漲跌幅"] = df[pct_col].map(to_number) if pct_col else 0
    out["漲跌"] = df[change_col].map(to_number) if change_col else 0

    missing_value = out["成交金額"].eq(0) & out["成交股數"].gt(0) & out["收盤價"].gt(0)
    out.loc[missing_value, "成交金額"] = out.loc[missing_value, "收盤價"] * out.loc[missing_value, "成交股數"]
    return out[out["代號"].notna() & (out["代號"] != "")]


def fetch_official_quotes():
    frames = []
    errors = []
    for url, market in [(TWSE_ALL_URL, "上市"), (TPEX_ALL_URL, "上櫃")]:
        try:
            frames.append(normalize_quote_df(fetch_json(url), market))
        except Exception as e:
            errors.append(f"{market}行情失敗：{e}")
    if not frames:
        return pd.DataFrame(), errors
    return pd.concat(frames, ignore_index=True).drop_duplicates("代號"), errors


def twse_date_str(dt):
    return dt.strftime("%Y%m%d")


def fetch_twse_month(code, yyyymmdd):
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={yyyymmdd}&stockNo={code}"
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    j = r.json()
    data = j.get("data", [])
    fields = j.get("fields", [])
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data, columns=fields)

    def parse_twse_date(s):
        parts = str(s).split("/")
        if len(parts) == 3:
            return pd.to_datetime(f"{int(parts[0]) + 1911}/{parts[1]}/{parts[2]}", errors="coerce")
        return pd.NaT

    return pd.DataFrame({
        "日期": df["日期"].apply(parse_twse_date),
        "開盤價": df["開盤價"].map(to_number),
        "最高價": df["最高價"].map(to_number),
        "最低價": df["最低價"].map(to_number),
        "收盤價": df["收盤價"].map(to_number),
        "成交股數": df["成交股數"].map(to_number),
    })


def _parse_roc_or_md_date(s, year_hint=None):
    s = str(s).replace('"', '').strip()
    parts = s.split("/")
    if len(parts) == 3:
        y = int(parts[0])
        if y < 1911:
            y += 1911
        return pd.to_datetime(f"{y}/{parts[1]}/{parts[2]}", errors="coerce")
    if len(parts) == 2 and year_hint is not None:
        return pd.to_datetime(f"{year_hint}/{parts[0]}/{parts[1]}", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def fetch_tpex_month_old_json(code, month_start):
    roc_ym = f"{month_start.year - 1911}/{month_start.month:02d}"

    urls = [
        f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?d={roc_ym}&stkno={code}",
        f"http://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?d={roc_ym}&stkno={code}",
        f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d={roc_ym}&stkno={code}",
    ]

    last_err = None
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            j = r.json()
            data = j.get("aaData", []) or j.get("data", [])
            if not data:
                continue

            rows = []
            for item in data:
                if not isinstance(item, (list, tuple)) or len(item) < 7:
                    continue
                dt = _parse_roc_or_md_date(item[0], year_hint=month_start.year)
                close = to_number(item[6])
                if pd.isna(dt) or close <= 0:
                    continue
                rows.append({
                    "日期": dt,
                    "成交股數": to_number(item[1]) * 1000,
                    "開盤價": to_number(item[3]),
                    "最高價": to_number(item[4]),
                    "最低價": to_number(item[5]),
                    "收盤價": close,
                })
            df = pd.DataFrame(rows)
            if not df.empty:
                return df
        except Exception as e:
            last_err = e
            continue

    return pd.DataFrame()


def fetch_tpex_month_new_csv(code, month_start):
    url = (
        "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock"
        f"?code={code}&date={month_start.strftime('%Y/%m/%d')}&response=csv"
    )
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    text = r.text.replace("\ufeff", "")
    lines = [line for line in text.splitlines() if "," in line]
    if not lines:
        return pd.DataFrame()

    header_i = None
    for i, line in enumerate(lines):
        if "日期" in line and ("收盤" in line or "收盤價" in line):
            header_i = i
            break
    if header_i is None:
        return pd.DataFrame()

    csv_text = "\n".join(lines[header_i:])
    try:
        raw = pd.read_csv(StringIO(csv_text))
    except Exception:
        return pd.DataFrame()

    raw.columns = [str(c).replace('"', '').strip() for c in raw.columns]
    date_col = pick_col(raw, ["日期", "Date"])
    open_col = pick_col(raw, ["開盤", "開盤價"])
    high_col = pick_col(raw, ["最高", "最高價"])
    low_col = pick_col(raw, ["最低", "最低價"])
    close_col = pick_col(raw, ["收盤", "收盤價"])
    vol_col = pick_col(raw, ["成交股數", "成交張數", "成交量"])

    if not date_col or not close_col:
        return pd.DataFrame()

    vol = raw[vol_col].map(to_number) if vol_col else 0
    if vol_col and "張" in vol_col:
        vol = vol * 1000

    return pd.DataFrame({
        "日期": raw[date_col].apply(lambda x: _parse_roc_or_md_date(x, year_hint=month_start.year)),
        "開盤價": raw[open_col].map(to_number) if open_col else 0,
        "最高價": raw[high_col].map(to_number) if high_col else 0,
        "最低價": raw[low_col].map(to_number) if low_col else 0,
        "收盤價": raw[close_col].map(to_number),
        "成交股數": vol,
    })


def fetch_yahoo_history(code, market):
    # 備援來源：上櫃用 .TWO，上市用 .TW
    suffixes = [".TWO", ".TW"] if market == "上櫃" else [".TW", ".TWO"]
    last_err = None

    for suffix in suffixes:
        symbol = f"{code}{suffix}"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=8mo&interval=1d&events=history"
        try:
            resp = requests.get(
                  url,
                  timeout=20,
                   verify=False
            )
            r.raise_for_status()
            j = r.json()
            result = j.get("chart", {}).get("result", [])
            if not result:
                continue

            data = result[0]
            ts = data.get("timestamp", [])
            q = data.get("indicators", {}).get("quote", [{}])[0]
            if not ts or not q:
                continue

            df = pd.DataFrame({
                "日期": pd.to_datetime(ts, unit="s").tz_localize("UTC").tz_convert("Asia/Taipei").tz_localize(None).normalize(),
                "開盤價": q.get("open", []),
                "最高價": q.get("high", []),
                "最低價": q.get("low", []),
                "收盤價": q.get("close", []),
                "成交股數": q.get("volume", []),
            })
            df = df.dropna(subset=["日期", "收盤價"])
            df = df[df["收盤價"] > 0]
            if len(df) >= 20:
                df["資料來源"] = f"Yahoo{suffix}"
                return df.sort_values("日期")
        except Exception as e:
            last_err = e
            continue

    return pd.DataFrame()


def fetch_tpex_month(code, month_start):
    df = fetch_tpex_month_old_json(code, month_start)
    if not df.empty:
        return df
    return fetch_tpex_month_new_csv(code, month_start)


def get_last_month_starts(months=5):
    today = datetime.now()
    starts = []
    for i in range(months):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        starts.append(datetime(y, m, 1))
    return list(reversed(starts))


def fetch_history(code, market, months=5, force=False):
    cache_file = CACHE_DIR / f"{code}_{market}_hist.csv"

    if cache_file.exists() and not force:
        try:
            df = pd.read_csv(cache_file, parse_dates=["日期"])
            if len(df) >= 20:
                return df.sort_values("日期").tail(180), None
        except Exception:
            pass

    frames = []
    err = None

    # 官方來源優先
    for start in get_last_month_starts(months):
        try:
            if market == "上市":
                part = fetch_twse_month(code, twse_date_str(start))
            else:
                part = fetch_tpex_month(code, start)
            if not part.empty:
                frames.append(part)
            time.sleep(0.05)
        except Exception as e:
            err = str(e)

    if frames:
        df = pd.concat(frames, ignore_index=True)
        df = df.dropna(subset=["日期"]).drop_duplicates("日期").sort_values("日期")
        df = df[df["收盤價"] > 0]
        if len(df) >= 20:
            try:
                df.to_csv(cache_file, index=False, encoding="utf-8-sig")
            except Exception:
                pass
            return df.tail(180), err

    # 上櫃官方歷史K若失敗，改用 Yahoo .TWO 備援
    ydf = fetch_yahoo_history(code, market)
    if not ydf.empty:
        try:
            ydf.to_csv(cache_file, index=False, encoding="utf-8-sig")
        except Exception:
            pass
        return ydf.tail(180), "Yahoo備援"

    return pd.DataFrame(), err or "無歷史資料"
