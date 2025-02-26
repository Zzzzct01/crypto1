import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# 初始化應用
st.set_page_config(page_title="虛擬貨幣交易管理系統", layout="wide")
st.title("📊 虛擬貨幣交易管理系統")

# 上傳 CSV
uploaded_file = st.file_uploader("上傳交易紀錄 CSV", type=["csv"])

if uploaded_file:
    # 讀取 CSV 並處理 BOM（Byte Order Mark）
    df = pd.read_csv(uploaded_file, encoding="utf-8")

    # 修正欄位名稱，去除隱藏字元 (BOM) 與多餘空格
    df.columns = df.columns.str.replace(r'\ufeff', '', regex=True).str.strip()

    # 確保必要欄位存在
    # 移除 "Direction" 欄位，因為 CSV 檔案中沒有這個欄位
    required_columns = ["Symbol", "Trade Time", "Filled Amount", "Filled Price", "Trading Volume", "Fee"]
    if not all(col in df.columns for col in required_columns):
        st.error("CSV 欄位缺失，請確認格式。")
        st.stop()  # **停止執行，避免報錯**

    # 轉換數據格式
    df["Trade Time"] = pd.to_datetime(df["Trade Time"])
    df = df.sort_values(by="Trade Time")

    # 填補 'taker/maker' 欄位的空值，避免後續計算出錯
    # 這裡使用 'unknown' 填補，您可以根據實際情況選擇其他填補方式
    df['taker/maker'] = df['taker/maker'].fillna('unknown')

    # 計算交易方向 (買入/賣出)
    # 這裡假設 'taker/maker' 為 'maker' 時為買入，'taker' 時為賣出
    # 您可能需要根據實際情況調整判斷邏輯
    df['Direction'] = df['taker/maker'].apply(lambda x: 'buy' if x == 'maker' else 'sell')

    # 計算持倉量與成本
    df["Total Cost"] = df["Filled Amount"] * df["Filled Price"] + df["Fee"]
    position_summary = df.groupby("Symbol").agg({
        "Filled Amount": "sum",
        "Total Cost": "sum",
        "Fee": "sum"
    }).reset_index()

    # 計算持倉均價
    position_summary["Average Price"] = position_summary["Total Cost"] / position_summary["Filled Amount"]

    # OKX API 取得即時價格
    def get_latest_price(symbol):
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}-USDT"
        response = requests.get(url).json()
        if "data" in response and len(response["data"]) > 0:
            return float(response["data"][0]["last"])
        return None

    # 修改 Symbol 格式，移除 "-SWAP"
    position_summary["Symbol"] = position_summary["Symbol"].str.replace("-SWAP", "")

    position_summary["Latest Price"] = position_summary["Symbol"].apply(get_latest_price)

    # 計算即時持倉價值與盈虧
    position_summary["Current Value"] = position_summary["Filled Amount"] * position_summary["Latest Price"]
    position_summary["PnL"] = position_summary["Current Value"] - position_summary["Total Cost"]

    # 視覺化圖表
    fig_pie = px.pie(position_summary, values="Current Value", names="Symbol", title="各幣種持倉比例")
    st.plotly_chart(fig_pie)

    fig_line = px.line(df, x="Trade Time", y="Total Cost", title="累計持倉市值變化")
    st.plotly_chart(fig_line)

    # 顯示數據表格
    st.dataframe(position_summary.style.applymap(lambda x: "color: red" if x < 0 else "color: green", subset=["PnL"]))

    # Excel 匯出
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        position_summary.to_excel(writer, sheet_name="持倉分析", index=False)
        writer.close()
    st.download_button(label="📥 下載 Excel", data=output.getvalue(), file_name="crypto_portfolio.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
