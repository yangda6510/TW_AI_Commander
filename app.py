from zoneinfo import ZoneInfo
from datetime import datetime

now = datetime.now(ZoneInfo("Asia/Taipei"))

def in_trading_time():
    now = datetime.now(ZoneInfo("Asia/Taipei")).time()
    return time(8, 45) <= now <= time(13, 35)



import streamlit as st
import pandas as pd
from datetime import datetime, time
import streamlit.components.v1 as components

from data_loader import read_pool_from_csv_file, fetch_official_quotes, fetch_history
from engine import compute_indicators, calc_life, calc_power, calc_grade, calc_status

st.set_page_config( page_title="台股生命爆發 AI 操盤總司令 V2.0", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.title("🚀 台股生命爆發 AI 操盤總司令 V1.8")
st.caption("自動更新版：TWSE + TPEx + 歷史K快取 + 20MA/60MA/20日高 + 生命值/馬力")
taipei_now = datetime.now(ZoneInfo("Asia/Taipei"))

st.info( f"🇹🇼 台灣時間：{taipei_now.strftime('%Y-%m-%d %H:%M:%S')}")


with st.sidebar:
    st.header("設定")

    auto_refresh = st.checkbox("盤中自動更新", value=False)
    refresh_min = st.selectbox("更新頻率", [1, 3, 5, 10, 15], index=2)
    only_market = st.checkbox("只在 08:45~13:35 更新", value=True)

    if auto_refresh:
        allow_refresh = in_trading_time() if only_market else True
        if allow_refresh:
            st.success(f"自動更新中：每 {refresh_min} 分鐘")
            components.html(
                f"<script>setTimeout(function(){{window.parent.location.reload();}}, {refresh_min * 60 * 1000});</script>",
                height=0
            )
        else:
            st.info("非盤中時間，暫停自動更新。")

        pool = read_pool_from_csv_file("stock_pool.csv")

    DEFAULT_STOCKS = min(80, len(pool))

    max_stocks = st.slider(
        "本次計算檔數",
        20,
        len(pool),
        DEFAULT_STOCKS,
        step=10
    )

    force_reload = st.checkbox("強制重抓歷史K", value=False)
    st.info("第一次抓歷史K會比較慢。建議先跑80檔，確認成功後再拉到全部。")

    if st.button("🔄 重新計算"):
        st.cache_data.clear()
        st.rerun()

if pool.empty:
    st.error("找不到 stock_pool.csv")
    st.stop()

pool = pool.head(max_stocks).copy()
quote_df, quote_errors = fetch_official_quotes()

if quote_df.empty:
    st.error("官方行情抓取失敗")
    for e in quote_errors:
        st.write(e)
    st.stop()

df = pool.merge(quote_df, on="代號", how="left", suffixes=("_池", ""))
if "名稱池" in df.columns:
    df["名稱"] = df["名稱"].fillna(df["名稱池"]) if "名稱" in df.columns else df["名稱池"]

rows = []
progress = st.progress(0)
status_box = st.empty()

for i, row in df.iterrows():
    code = str(row["代號"])
    market = row.get("市場", row.get("市場來源", "上市"))
    name = row.get("名稱", "")
    status_box.caption(f"計算中：{code} {name} ({i+1}/{len(df)})")

    hist, err = fetch_history(code, market, months=5, force=force_reload)
    ind = compute_indicators(hist)

    data = row.to_dict()
    data.update(ind)
    data["歷史K狀態"] = "✅" if not hist.empty else f"❌ {err or ''}"

    data["生命值"] = calc_life(data)
    data["馬力"] = calc_power(data)
    data["等級"] = calc_grade(data)
    data["狀態"] = calc_status(data)
    rows.append(data)

    progress.progress((i + 1) / len(df))

status_box.empty()
progress.empty()

update_time = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%H:%M:%S")
result = pd.DataFrame(rows)

for c in ["收盤價", "成交金額", "漲跌幅", "生命值", "馬力", "量比", "20MA乖離%"]:
    if c in result.columns:
        result[c] = pd.to_numeric(result[c], errors="coerce").fillna(0)

valid = result[result.get("收盤價", 0) > 0]
avg_life = round(valid["生命值"].mean(), 1) if not valid.empty else 0
avg_power = round(valid["馬力"].mean(), 1) if not valid.empty else 0
s_count = int((result["等級"] == "S").sum())
a_count = int((result["等級"] == "A").sum())
deduct_count = int((result.get("扣低共振", pd.Series([0]*len(result))) >= 2).sum())

tabs = st.tabs(["📊 戰情總覽", "🏆 總排行", "📡 扣低雷達", "🚀 真突破雷達", "⚠️ 風險雷達", "📋 原始資料"])

with tabs[0]:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("本次檔數", len(result))
    c2.metric("市場生命值", avg_life)
    c3.metric("平均馬力", avg_power)
    c4.metric("S/A", f"{s_count}/{a_count}")
    c5.metric("扣低共振≥2", deduct_count)
    st.caption(f"📈 最後更新：{update_time}")

    if quote_errors:
        with st.expander("官方行情警告"):
            for e in quote_errors:
                st.write(e)

    st.subheader("🔥 今日 TOP 20")
    top = result.sort_values(["生命值","馬力","扣低共振"], ascending=False).head(30)
    cols = [c for c in ["代號", "名稱", "族群", "市場", "收盤價", "漲跌幅", "生命值", "馬力", "等級", "狀態", "扣低共振", "量比", "20MA乖離%"] if c in top.columns]
    st.dataframe(top[cols], use_container_width=True, hide_index=True)

with tabs[1]:
    st.subheader("🏆 AI + 泛AI 總排行")
    rank = result.sort_values(["馬力", "生命值"], ascending=False)
    cols = [c for c in ["代號", "名稱", "族群", "市場", "收盤價", "5MA", "10MA", "20MA", "60MA", "20日高點", "生命值", "馬力", "等級", "狀態"] if c in rank.columns]
    st.dataframe(rank[cols], use_container_width=True, hide_index=True)

with tabs[2]:
    st.subheader("📡 扣低雷達")
    radar = result[result.get("扣低共振", pd.Series([0]*len(result))) >= 2].sort_values(["扣低共振", "馬力"], ascending=False)
    cols = [c for c in ["代號", "名稱", "生命值", "馬力", "等級", "日扣低", "週扣低", "月扣低", "日剛轉扣低", "週剛轉扣低", "月剛轉扣低", "扣低共振", "狀態"] if c in radar.columns]
    st.dataframe(radar[cols], use_container_width=True, hide_index=True)

with tabs[3]:
    st.subheader("🚀 真突破雷達")
    brk = result[result.get("真突破", pd.Series([False]*len(result))) == True].sort_values(["馬力", "生命值"], ascending=False)
    cols = [c for c in ["代號", "名稱", "收盤價", "20日高點", "量比", "生命值", "馬力", "等級", "狀態"] if c in brk.columns]
    if brk.empty:
        st.info("目前沒有真突破股票。")
    else:
        st.dataframe(brk[cols], use_container_width=True, hide_index=True)

with tabs[4]:
    st.subheader("⚠️ 風險雷達")
    risk = result[(result["生命值"] < 60) | (result["馬力"] < 60) | (result.get("站上20MA", pd.Series([True]*len(result))) == False)]
    risk = risk.sort_values(["生命值", "馬力"], ascending=True)
    cols = [c for c in ["代號", "名稱", "收盤價", "20MA", "生命值", "馬力", "等級", "狀態", "歷史K狀態"] if c in risk.columns]
    st.dataframe(risk[cols], use_container_width=True, hide_index=True)

with tabs[5]:
    st.subheader("📋 原始資料")
    st.dataframe(result, use_container_width=True, hide_index=True)

st.caption("V2.0 正式版：第一波起漲 × 扣低共振 × 不追高。建議盤中每5分鐘更新；歷史K快取12小時。")
