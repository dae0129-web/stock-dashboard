"""
update_market_data.py
台股盤後資料抓取主程式
每日由 GitHub Actions 觸發執行
"""

import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import requests
from datetime import datetime, timedelta
import time

# ─────────────────────────────────────────
# 族群定義（只需維護代號，名稱自動從官方查詢）
# ─────────────────────────────────────────
SECTORS = {
    "玻璃基板": ["3522.TW", "3486.TW", "6504.TW", "4935.TW", "6146.TW", "5443.TW"],
    "CoWoS先進封裝": ["3583.TW", "3131.TW", "6187.TW", "6640.TW", "6223.TW"],
    "CPO光通訊": ["3363.TW", "3081.TW", "4979.TW", "3163.TW", "6442.TW"],
    "AI Server": ["3231.TW", "2382.TW", "2356.TW", "3706.TW", "2376.TW"],
    "電源BBU": ["6703.TW", "6728.TW", "2301.TW", "2308.TW"],
    "散熱": ["3017.TW", "3324.TW", "3653.TW"],
    "PCB高階載板": ["3037.TW", "8046.TW", "3189.TW", "8358.TW", "2383.TW"],
}

# 所有股票代號
ALL_TICKERS = list(set([t for tickers in SECTORS.values() for t in tickers]))


def fetch_official_stock_names():
    """
    從 TWSE + TPEx 官方 API 取得股票中文名稱對照表。
    上市股票用 TWSE，上櫃股票用 TPEx。
    回傳格式：{"2330.TW": "台積電", "3037.TW": "欣興", ...}
    """
    name_map = {}

    # ── 上市股票（TWSE）──
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        resp = requests.get(url_twse, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                code = item.get("Code", "").strip()
                name = item.get("Name", "").strip()
                if code and name:
                    name_map[f"{code}.TW"] = name
            print(f"  ✓ TWSE 取得 {len(name_map)} 筆上市股票名稱")
    except Exception as e:
        print(f"  ✗ TWSE 查詢失敗: {e}")

    # ── 上櫃股票（TPEx）──
    try:
        url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        resp = requests.get(url_tpex, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            before = len(name_map)
            for item in data:
                code = item.get("SecuritiesCompanyCode", "").strip()
                name = item.get("CompanyName", "").strip()
                if code and name:
                    name_map[f"{code}.TW"] = name
            print(f"  ✓ TPEx 取得 {len(name_map) - before} 筆上櫃股票名稱")
    except Exception as e:
        print(f"  ✗ TPEx 查詢失敗: {e}")

    return name_map


def get_stock_name(ticker, official_names):
    """
    取得股票中文名稱。
    優先使用官方名稱，若查不到才用代號本身作為備用。
    """
    name = official_names.get(ticker, "")
    if name:
        return name
    # 備用：只顯示代號（去掉 .TW）
    return ticker.replace(".TW", "")


def fetch_stock_data(tickers, official_names, period="60d"):
    """抓取股票歷史資料"""
    print(f"[INFO] 抓取 {len(tickers)} 檔股票資料...")
    data = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if not hist.empty:
                data[ticker] = hist
                name = get_stock_name(ticker, official_names)
                print(f"  ✓ {ticker} ({name})")
            else:
                print(f"  ✗ {ticker} 無資料")
            time.sleep(0.3)  # 避免請求過快
        except Exception as e:
            print(f"  ✗ {ticker} 錯誤: {e}")
    return data


def calculate_indicators(hist_df):
    """計算技術指標"""
    df = hist_df.copy()

    # 均線
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()

    # 5日均量
    df["Vol5"] = df["Volume"].rolling(5).mean()

    # MACD
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["Signal"]

    return df


def get_latest_data(ticker, df, official_names):
    """取得最新一日的分析資料"""
    if df is None or len(df) < 21:
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    close = latest["Close"]
    ma20 = latest["MA20"]
    ma5 = latest["MA5"]
    ma60 = latest["MA60"]
    vol = latest["Volume"]
    vol5 = latest["Vol5"]
    macd_hist = latest["MACD_Hist"]
    prev_macd_hist = prev["MACD_Hist"]

    # 漲跌幅
    change_pct = ((close - prev["Close"]) / prev["Close"] * 100) if prev["Close"] > 0 else 0

    # 距月線%
    dist_ma20 = ((close - ma20) / ma20 * 100) if ma20 > 0 else 0

    # 量比（今日量 / 5日均量）
    vol_ratio = (vol / vol5) if vol5 > 0 else 1

    # 是否收紅
    is_red = close > prev["Close"]

    # MACD 翻正
    macd_positive = macd_hist > 0
    macd_cross_up = macd_hist > 0 and prev_macd_hist <= 0

    # 位階判斷
    def get_position_level(dist):
        if dist < -3:
            # 檢查是否連續跌破月線 3 日
            recent = df.tail(5)
            below_ma20_days = sum(recent["Close"] < recent["MA20"])
            if below_ma20_days >= 3:
                return "轉弱區"
            return "月線下方"
        elif dist <= 5:
            return "主升初期"
        elif dist <= 15:
            return "回檔再攻" if change_pct < 0 else "主升中段"
        elif dist <= 25:
            return "主升中段"
        else:
            return "過熱區"

    position = get_position_level(dist_ma20)

    # 漲停判斷（台股漲停 ≈ +10%）
    is_limit_up = change_pct >= 9.5

    return {
        "ticker": ticker,
        "name": get_stock_name(ticker, official_names),
        "close": round(close, 2),
        "change_pct": round(change_pct, 2),
        "volume": int(vol),
        "vol5": int(vol5) if not np.isnan(vol5) else 0,
        "vol_ratio": round(vol_ratio, 2),
        "ma5": round(ma5, 2) if not np.isnan(ma5) else None,
        "ma20": round(ma20, 2) if not np.isnan(ma20) else None,
        "ma60": round(ma60, 2) if not np.isnan(ma60) else None,
        "dist_ma20": round(dist_ma20, 2),
        "macd_positive": bool(macd_positive),
        "macd_cross_up": bool(macd_cross_up),
        "is_red": bool(is_red),
        "is_limit_up": bool(is_limit_up),
        "position": position,
    }


def calculate_sector_score(sector_name, tickers, stock_data_map):
    """計算族群強度分數"""
    score = 0
    details = []

    valid_stocks = []
    for ticker in tickers:
        d = stock_data_map.get(ticker)
        if d:
            valid_stocks.append(d)

    if not valid_stocks:
        return 0, "非主流", []

    # 條件1：≥3 檔上漲超過 3%
    up3 = sum(1 for s in valid_stocks if s["change_pct"] >= 3)
    if up3 >= 3:
        score += 2
        details.append(f"{up3} 檔漲幅 >3%")

    # 條件2：≥2 檔成交量 > 5日均量 1.5 倍
    vol_surge = sum(1 for s in valid_stocks if s["vol_ratio"] >= 1.5)
    if vol_surge >= 2:
        score += 2
        details.append(f"{vol_surge} 檔爆量")

    # 條件3：族群龍頭創 20 日新高（用第一檔作為龍頭代理）
    leader_ticker = tickers[0]
    leader_hist = None
    for ticker in tickers:
        if ticker in stock_data_map and stock_data_map[ticker]:
            leader_hist = ticker
            break

    # 條件4：族群內有漲停股
    limit_up = sum(1 for s in valid_stocks if s["is_limit_up"])
    if limit_up > 0:
        score += 2
        details.append(f"{limit_up} 檔漲停")

    # 條件5：多數個股站上月線
    above_ma20 = sum(1 for s in valid_stocks if s["dist_ma20"] > 0)
    if above_ma20 >= len(valid_stocks) * 0.6:
        score += 1
        details.append(f"{above_ma20}/{len(valid_stocks)} 站月線")

    # 條件6：MACD 翻正個股數
    macd_pos = sum(1 for s in valid_stocks if s["macd_positive"])
    if macd_pos >= len(valid_stocks) * 0.5:
        score += 1
        details.append(f"{macd_pos} 檔 MACD 正")

    # 族群狀態
    if score >= 8:
        status = "主流啟動"
    elif score >= 6:
        status = "資金回流"
    elif score >= 4:
        status = "觀察中"
    else:
        status = "非主流"

    return score, status, details


def calculate_stock_score(stock):
    """計算個股強勢評分"""
    score = 0

    if stock["dist_ma20"] > 0:
        score += 10  # 站上月線
    if stock.get("ma5") and stock.get("ma20") and stock["ma5"] > stock["ma20"]:
        score += 5   # 短均線向上
    if stock.get("ma20") and stock.get("ma60") and stock["ma20"] > stock["ma60"]:
        score += 10  # MA20 > MA60
    if stock["macd_positive"]:
        score += 10  # MACD 翻正
    if stock["vol_ratio"] >= 1.5:
        score += 15  # 成交量放大
    if stock["dist_ma20"] > 25:
        score -= 20  # 距月線過遠
    if stock["change_pct"] <= -5 and stock["vol_ratio"] >= 2:
        score -= 25  # 爆量長黑

    return max(0, min(100, score))


def get_signal_labels(stock, sector_score, all_stocks_in_sector):
    """判斷進場訊號標籤"""
    labels = []

    # 風險警示優先
    if stock["dist_ma20"] > 30:
        labels.append("過熱勿追")
    if stock["position"] == "轉弱區":
        labels.append("趨勢轉弱")
    if stock["change_pct"] <= -5 and stock["vol_ratio"] >= 2:
        labels.append("爆量長黑")

    if labels:
        return labels

    # 正向訊號
    if (stock["vol_ratio"] >= 1.5 and stock["is_red"] and
            stock["dist_ma20"] > 0 and sector_score >= 6):
        labels.append("平台突破")

    if (stock["dist_ma20"] >= -5 and stock["dist_ma20"] <= 5 and
            stock["is_red"] and stock["vol_ratio"] < 1.2):
        labels.append("回月線轉強")

    # 補漲候選（同族群有龍頭創高，個股尚未創高但站月線）
    sector_leaders_high = any(
        s["change_pct"] >= 5 for s in all_stocks_in_sector
        if s["ticker"] != stock["ticker"]
    )
    if (sector_leaders_high and stock["dist_ma20"] > 0 and
            stock["dist_ma20"] < 15 and stock["vol_ratio"] >= 1.2):
        labels.append("補漲候選")

    if not labels:
        labels.append("觀察中")

    return labels


def get_score_label(score):
    if score >= 85:
        return "強勢核心"
    elif score >= 70:
        return "強勢觀察"
    elif score >= 55:
        return "中性"
    elif score >= 40:
        return "偏弱"
    else:
        return "避免觀察"


def main():
    print("=" * 50)
    print(f"台股盤後觀測系統 — 資料更新")
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # 從官方 API 取得正確股票名稱
    print("\n[INFO] 從 TWSE/TPEx 官方 API 取得股票名稱...")
    official_names = fetch_official_stock_names()
    print(f"  共取得 {len(official_names)} 筆官方股票名稱")

    # 抓取資料
    raw_data = fetch_stock_data(ALL_TICKERS, official_names)

    # 計算技術指標
    print("\n[INFO] 計算技術指標...")
    processed = {}
    for ticker, hist in raw_data.items():
        df = calculate_indicators(hist)
        stock_info = get_latest_data(ticker, df, official_names)
        if stock_info:
            processed[ticker] = stock_info

    # 計算族群強度
    print("\n[INFO] 計算族群強度...")
    sector_results = []
    sector_score_map = {}

    for sector_name, tickers in SECTORS.items():
        score, status, details = calculate_sector_score(
            sector_name, tickers, processed
        )
        sector_score_map[sector_name] = score
        sector_results.append({
            "name": sector_name,
            "score": score,
            "status": status,
            "details": details,
            "tickers": tickers,
        })
        print(f"  {sector_name}: {score}分 ({status})")

    sector_results.sort(key=lambda x: x["score"], reverse=True)

    # 計算個股評分與訊號
    print("\n[INFO] 計算個股評分與訊號...")
    stock_results = []

    for sector in sector_results:
        sector_name = sector["name"]
        sector_score = sector["score"]
        sector_stocks = [processed[t] for t in sector["tickers"] if t in processed]

        for stock in sector_stocks:
            score = calculate_stock_score(stock)
            labels = get_signal_labels(stock, sector_score, sector_stocks)
            stock["sector"] = sector_name
            stock["score"] = score
            stock["score_label"] = get_score_label(score)
            stock["labels"] = labels
            stock["sector_score"] = sector_score
            stock_results.append(stock)

    # 分類整理
    second_wave = [s for s in stock_results if "回月線轉強" in s["labels"] or "補漲候選" in s["labels"]]
    breakout = [s for s in stock_results if "平台突破" in s["labels"]]
    risk_alerts = [s for s in stock_results if any(l in s["labels"] for l in ["過熱勿追", "趨勢轉弱", "爆量長黑"])]

    # 產生 JSON
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    trade_date = datetime.now().strftime("%Y-%m-%d")

    # market_report.json
    market_report = {
        "update_time": update_time,
        "trade_date": trade_date,
        "summary": {
            "top_sector": sector_results[0]["name"] if sector_results else "-",
            "top_sector_score": sector_results[0]["score"] if sector_results else 0,
            "total_stocks": len(stock_results),
            "strong_stocks": len([s for s in stock_results if s["score"] >= 70]),
            "breakout_count": len(breakout),
            "risk_count": len(risk_alerts),
        }
    }

    # sector_ranking.json
    sector_ranking = {
        "update_time": update_time,
        "sectors": sector_results
    }

    # stock_signals.json
    stock_signals = {
        "update_time": update_time,
        "all_stocks": stock_results,
        "second_wave": second_wave,
        "breakout": breakout,
        "risk_alerts": risk_alerts,
    }

    # 寫入檔案
    os.makedirs("data", exist_ok=True)

    with open("data/market_report.json", "w", encoding="utf-8") as f:
        json.dump(market_report, f, ensure_ascii=False, indent=2)

    with open("data/sector_ranking.json", "w", encoding="utf-8") as f:
        json.dump(sector_ranking, f, ensure_ascii=False, indent=2)

    with open("data/stock_signals.json", "w", encoding="utf-8") as f:
        json.dump(stock_signals, f, ensure_ascii=False, indent=2)

    print("\n✅ 資料更新完成！")
    print(f"  市場報告: data/market_report.json")
    print(f"  族群排行: data/sector_ranking.json")
    print(f"  股票訊號: data/stock_signals.json")


if __name__ == "__main__":
    main()
