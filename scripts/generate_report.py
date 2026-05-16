\
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# 可自行調整族群與股票
THEMES: Dict[str, List[Dict[str, Any]]] = {
    "玻璃基板": [
        {"id": "6207", "name": "雷科", "role": "leader"},
        {"id": "8064", "name": "東捷", "role": "core"},
        {"id": "6667", "name": "信紘科", "role": "core"},
        {"id": "6274", "name": "台燿", "role": "core"},
        {"id": "3455", "name": "由田", "role": "core"},
        {"id": "5443", "name": "均豪", "role": "core"},
    ],
    "CoWoS / 先進封裝": [
        {"id": "3583", "name": "辛耘", "role": "core"},
        {"id": "3131", "name": "弘塑", "role": "leader"},
        {"id": "6187", "name": "萬潤", "role": "core"},
        {"id": "6640", "name": "均華", "role": "core"},
        {"id": "6223", "name": "旺矽", "role": "core"},
    ],
    "CPO / 光通訊": [
        {"id": "3363", "name": "上詮", "role": "core"},
        {"id": "3081", "name": "聯亞", "role": "core"},
        {"id": "4979", "name": "華星光", "role": "core"},
        {"id": "3163", "name": "波若威", "role": "core"},
        {"id": "6442", "name": "光聖", "role": "leader"},
    ],
    "AI Server": [
        {"id": "3231", "name": "緯創", "role": "core"},
        {"id": "2382", "name": "廣達", "role": "leader"},
        {"id": "2356", "name": "英業達", "role": "core"},
        {"id": "3706", "name": "神達", "role": "core"},
        {"id": "2376", "name": "技嘉", "role": "core"},
    ],
    "電源 / BBU": [
        {"id": "4931", "name": "新盛力", "role": "core"},
        {"id": "6781", "name": "AES-KY", "role": "leader"},
        {"id": "2301", "name": "光寶科", "role": "core"},
        {"id": "2308", "name": "台達電", "role": "leader"},
    ],
    "散熱": [
        {"id": "3017", "name": "奇鋐", "role": "leader"},
        {"id": "3324", "name": "雙鴻", "role": "core"},
        {"id": "3653", "name": "健策", "role": "core"},
    ],
    "PCB / 高階載板": [
        {"id": "3037", "name": "欣興", "role": "core"},
        {"id": "8046", "name": "南電", "role": "core"},
        {"id": "3189", "name": "景碩", "role": "core"},
        {"id": "8358", "name": "金居", "role": "core"},
        {"id": "2383", "name": "台光電", "role": "leader"},
    ],
}


def tw_suffix(stock_id: str) -> str:
    # 以常見代號粗略判斷上市/上櫃；若抓不到會自動嘗試另一個市場
    otc_ids = {
        "8064", "6667", "3455", "5443", "3583", "3131", "6187", "6640", "6223",
        "3363", "3081", "4979", "3163", "6442", "4931", "6781", "3324", "8358"
    }
    return "TWO" if stock_id in otc_ids else "TW"


def fetch_stooq(stock_id: str) -> pd.DataFrame:
    # stooq 免費日線 CSV。台股格式常見：2330.tw 或 8064.two
    markets = [tw_suffix(stock_id), "TW", "TWO"]
    last_error = None

    for market in markets:
        symbol = f"{stock_id}.{market.lower()}"
        url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            text = r.text.strip()
            if "No data" in text or len(text.splitlines()) <= 2:
                continue
            from io import StringIO
            df = pd.read_csv(StringIO(text))
            if df.empty or "Close" not in df.columns:
                continue
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date").tail(260)
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["Close"])
            if len(df) >= 30:
                return df
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"無法抓取 {stock_id} 日線資料: {last_error}")


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA5"] = df["Close"].rolling(5).mean()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA60"] = df["Close"].rolling(60).mean()
    df["VOL5"] = df["Volume"].rolling(5).mean()

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_SIGNAL"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_HIST"] = df["MACD"] - df["MACD_SIGNAL"]

    df["RET_PCT"] = df["Close"].pct_change() * 100
    df["DIST_MA20_PCT"] = (df["Close"] - df["MA20"]) / df["MA20"] * 100
    df["HIGH20"] = df["High"].rolling(20).max()
    return df


def classify_stock(df: pd.DataFrame, theme_score: int) -> Dict[str, Any]:
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last

    close = float(last["Close"])
    open_ = float(last["Open"])
    ma20 = float(last["MA20"]) if not math.isnan(last["MA20"]) else None
    ma60 = float(last["MA60"]) if not math.isnan(last["MA60"]) else None
    vol = float(last["Volume"]) if not math.isnan(last["Volume"]) else 0
    vol5 = float(last["VOL5"]) if not math.isnan(last["VOL5"]) else None
    dist = float(last["DIST_MA20_PCT"]) if not math.isnan(last["DIST_MA20_PCT"]) else None
    ret = float(last["RET_PCT"]) if not math.isnan(last["RET_PCT"]) else 0
    macd = float(last["MACD"]) if not math.isnan(last["MACD"]) else None
    macd_signal = float(last["MACD_SIGNAL"]) if not math.isnan(last["MACD_SIGNAL"]) else None
    macd_hist = float(last["MACD_HIST"]) if not math.isnan(last["MACD_HIST"]) else None

    recent = df.tail(30)
    above_ma20_days = int((recent.tail(3)["Close"] > recent.tail(3)["MA20"]).sum()) if ma20 else 0
    below_ma20_3days = bool((recent.tail(3)["Close"] < recent.tail(3)["MA20"]).all()) if ma20 else False
    red_k = close > open_
    black_long = close < open_ and abs(close - open_) / open_ > 0.04
    volume_expand = bool(vol5 and vol > vol5 * 1.5)
    volume_shrink = bool(vol5 and vol < vol5 * 0.8)

    prev_20_high = float(df.iloc[-21:-1]["High"].max()) if len(df) >= 22 else float(last["HIGH20"])
    platform_break = bool(
        len(df) >= 22 and close > prev_20_high and volume_expand and red_k and theme_score >= 6
    )

    # 前 30 日低點到近高點漲幅
    low_30 = float(recent["Low"].min())
    high_30 = float(recent["High"].max())
    advance_30 = (high_30 - low_30) / low_30 * 100 if low_30 > 0 else 0

    near_ma20 = bool(dist is not None and abs(dist) <= 5)
    pullback_rebound = bool(advance_30 >= 20 and near_ma20 and red_k and not below_ma20_3days)

    overheated = bool(dist is not None and dist > 25)
    risk_hot = bool(dist is not None and dist > 30)
    macd_bull = bool(macd is not None and macd_signal is not None and macd > macd_signal and macd > 0)
    macd_bear = bool(macd is not None and macd_signal is not None and macd < macd_signal)

    score = 50
    if ma20 and close > ma20:
        score += 10
    if len(df) >= 25 and not math.isnan(df.iloc[-1]["MA20"]) and not math.isnan(df.iloc[-5]["MA20"]) and df.iloc[-1]["MA20"] > df.iloc[-5]["MA20"]:
        score += 10
    if ma20 and ma60 and ma20 > ma60:
        score += 10
    if macd_bull:
        score += 10
    if volume_expand:
        score += 15
    if theme_score >= 6:
        score += 20
    if overheated:
        score -= 20
    if black_long and volume_expand:
        score -= 25
    if below_ma20_3days:
        score -= 25
    score = max(0, min(100, int(score)))

    if below_ma20_3days:
        phase = "轉弱區"
        suggestion = "減碼或移除"
    elif overheated:
        phase = "過熱區"
        suggestion = "避免追高"
    elif pullback_rebound:
        phase = "回檔再攻"
        suggestion = "第二波觀察"
    elif ma20 and ma60 and close > ma20 and ma20 > ma60 and volume_expand and macd_bull and (dist is not None and dist < 15):
        phase = "主升初期"
        suggestion = "優先觀察"
    elif dist is not None and 15 <= dist <= 25:
        phase = "主升中段"
        suggestion = "降低部位"
    else:
        phase = "觀察中"
        suggestion = "持續觀察"

    tags = []
    if platform_break:
        tags.append("平台突破")
    if pullback_rebound:
        tags.append("回月線轉強")
    if risk_hot:
        tags.append("過熱勿追")
    if black_long and volume_expand:
        tags.append("爆量長黑")
    if macd_bear:
        tags.append("MACD轉弱")
    if below_ma20_3days:
        tags.append("趨勢轉弱")
    if not tags:
        tags.append(phase)

    return {
        "trade_date": str(last["Date"].date()),
        "close": round(close, 2),
        "change_pct": round(ret, 2),
        "volume": int(vol),
        "ma5": round(float(last["MA5"]), 2) if not math.isnan(last["MA5"]) else None,
        "ma20": round(float(last["MA20"]), 2) if ma20 else None,
        "ma60": round(float(last["MA60"]), 2) if ma60 else None,
        "vol5": int(vol5) if vol5 else None,
        "distance_ma20_pct": round(dist, 2) if dist is not None else None,
        "macd": round(macd, 3) if macd is not None else None,
        "macd_signal": round(macd_signal, 3) if macd_signal is not None else None,
        "macd_hist": round(macd_hist, 3) if macd_hist is not None else None,
        "phase": phase,
        "score": score,
        "suggestion": suggestion,
        "tags": tags,
        "platform_break": platform_break,
        "pullback_rebound": pullback_rebound,
        "overheated": overheated,
        "trend_weak": below_ma20_3days,
        "volume_expand": volume_expand,
    }


def theme_status(score: int) -> str:
    if score >= 8:
        return "主流啟動"
    if score >= 6:
        return "資金回流"
    if score >= 4:
        return "觀察中"
    return "非主流"


def main() -> None:
    all_stock_results = []
    errors = []

    # 先抓資料與指標
    raw: Dict[str, Dict[str, Any]] = {}
    for theme, stocks in THEMES.items():
        for s in stocks:
            sid = s["id"]
            if sid in raw:
                continue
            try:
                df = add_indicators(fetch_stooq(sid))
                raw[sid] = {"df": df, "name": s["name"]}
                time.sleep(0.25)
            except Exception as e:
                errors.append({"stock_id": sid, "stock_name": s["name"], "error": str(e)})

    sector_ranking = []
    for theme, stocks in THEMES.items():
        valid = []
        for s in stocks:
            if s["id"] in raw:
                df = raw[s["id"]]["df"]
                last = df.iloc[-1]
                valid.append({"meta": s, "df": df, "last": last})

        score = 0
        if len([x for x in valid if x["last"]["RET_PCT"] > 3]) >= 3:
            score += 2
        if len([x for x in valid if not math.isnan(x["last"]["VOL5"]) and x["last"]["Volume"] > x["last"]["VOL5"] * 1.5]) >= 2:
            score += 2

        leaders = [x for x in valid if x["meta"].get("role") == "leader"] or valid[:1]
        if any(len(x["df"]) >= 22 and x["last"]["Close"] >= x["df"].iloc[-21:-1]["High"].max() for x in leaders):
            score += 2

        if any(x["last"]["RET_PCT"] >= 9.5 for x in valid):
            score += 2

        if valid and len([x for x in valid if not math.isnan(x["last"]["MA20"]) and x["last"]["Close"] > x["last"]["MA20"]]) >= max(1, len(valid) // 2 + 1):
            score += 1

        # 簡化版：三日平均漲幅 > 0 視為強於弱盤，之後可改成相對加權指數
        if valid:
            three_day = np.nanmean([x["df"].tail(3)["RET_PCT"].sum() for x in valid])
            if three_day > 2:
                score += 2

        score = min(score, 10)

        sector_ranking.append({
            "theme": theme,
            "score": score,
            "status": theme_status(score),
            "stocks_count": len(valid),
        })

    sector_score_map = {x["theme"]: x["score"] for x in sector_ranking}

    for theme, stocks in THEMES.items():
        for s in stocks:
            sid = s["id"]
            if sid not in raw:
                continue
            result = classify_stock(raw[sid]["df"], sector_score_map.get(theme, 0))
            result.update({
                "stock_id": sid,
                "stock_name": s["name"],
                "theme": theme,
                "role": s.get("role", "core"),
            })
            all_stock_results.append(result)

    sector_ranking = sorted(sector_ranking, key=lambda x: x["score"], reverse=True)

    second_wave = [
        s for s in all_stock_results
        if s["pullback_rebound"] or "回月線轉強" in s["tags"]
    ]
    platform = [
        s for s in all_stock_results
        if s["platform_break"]
    ]
    hot_alerts = [
        s for s in all_stock_results
        if s["overheated"] or s["trend_weak"] or "爆量長黑" in s["tags"]
    ]

    top_by_theme = {}
    for theme in THEMES:
        rows = [s for s in all_stock_results if s["theme"] == theme]
        top_by_theme[theme] = sorted(rows, key=lambda x: x["score"], reverse=True)[:5]

    report = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "stooq daily csv; TWSE/TPEx compatible symbol fallback",
        "sector_ranking": sector_ranking,
        "top_by_theme": top_by_theme,
        "second_wave": sorted(second_wave, key=lambda x: x["score"], reverse=True),
        "platform_breakouts": sorted(platform, key=lambda x: x["score"], reverse=True),
        "hot_alerts": sorted(hot_alerts, key=lambda x: x["score"]),
        "all_stocks": sorted(all_stock_results, key=lambda x: x["score"], reverse=True),
        "errors": errors,
        "disclaimer": "本資料僅供盤後市場結構觀測，不構成投資建議。"
    }

    (DATA_DIR / "market_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "sector_ranking.json").write_text(json.dumps(sector_ranking, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "stock_signals.json").write_text(json.dumps(report["all_stocks"], ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "hot_alerts.json").write_text(json.dumps(report["hot_alerts"], ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Done. Stocks: {len(all_stock_results)}, sectors: {len(sector_ranking)}, errors: {len(errors)}")


if __name__ == "__main__":
    main()
