"""
update_market_data.py
台股盤後資料抓取主程式 — 全面使用 twstock
每日由 GitHub Actions 觸發執行
"""

import json
import os
import time
from datetime import datetime, date

# ─────────────────────────────────────────
# 族群定義（純數字代號）
# ─────────────────────────────────────────
SECTORS = {
    "玻璃基板": ["3522", "3486", "6504", "4935", "6146", "5443"],
    "CoWoS先進封裝": ["3583", "3131", "6187", "6640", "6223"],
    "CPO光通訊": ["3363", "3081", "4979", "3163", "6442"],
    "AI Server": ["3231", "2382", "2356", "3706", "2376"],
    "電源BBU": ["6703", "6728", "2301", "2308"],
    "散熱": ["3017", "3324", "3653"],
    "PCB高階載板": ["3037", "8046", "3189", "8358", "2383"],
}

ALL_CODES = list(set([c for codes in SECTORS.values() for c in codes]))


def get_all_names():
    import twstock
    print("  正在更新 twstock 代號資料庫...")
    twstock.__update_codes()
    print(f"  ✓ 載入完成，共 {len(twstock.codes)} 筆")
    name_map = {}
    for code in ALL_CODES:
        if code in twstock.codes:
            info = twstock.codes[code]
            name_map[code] = info.name
            print(f"  ✓ {code} → {info.name} ({info.market})")
        else:
            name_map[code] = code
            print(f"  ✗ {code} → 代號不存在！")
    return name_map


def fetch_stock_history(code, name):
    from twstock import Stock
    try:
        stock = Stock(code)
        today = date.today()
        stock.fetch_from(today.year, max(1, today.month - 2))
        time.sleep(0.8)
        if not stock.price or len(stock.price) < 5:
            print(f"  ✗ {code} ({name}) 資料不足")
            return None
        print(f"  ✓ {code} ({name}) 共 {len(stock.price)} 筆")
        return {
            "code": code,
            "name": name,
            "prices": stock.price,
            "volumes": stock.capacity,
            "dates": [str(d.date()) if hasattr(d, 'date') else str(d) for d in stock.date],
        }
    except Exception as e:
        print(f"  ✗ {code} ({name}) 錯誤: {e}")
        return None


def ma(data, period):
    result = [None] * len(data)
    for i in range(period - 1, len(data)):
        window = data[i - period + 1:i + 1]
        if all(v is not None for v in window):
            result[i] = sum(window) / period
    return result


def ema_calc(data, span):
    k = 2 / (span + 1)
    result = [None] * len(data)
    for i, v in enumerate(data):
        if v is None:
            continue
        prev = next((result[j] for j in range(i - 1, -1, -1) if result[j] is not None), None)
        result[i] = v if prev is None else v * k + prev * (1 - k)
    return result


def calculate_indicators(hist):
    prices  = hist["prices"]
    volumes = hist["volumes"]
    ma5_list  = ma(prices, 5)
    ma20_list = ma(prices, 20)
    ma60_list = ma(prices, 60)
    vol5_list = ma(volumes, 5)
    ema12 = ema_calc(prices, 12)
    ema26 = ema_calc(prices, 26)
    macd_line = [
        (a - b) if a is not None and b is not None else None
        for a, b in zip(ema12, ema26)
    ]
    signal_line = ema_calc(macd_line, 9)
    macd_hist_list = [
        (m - s) if m is not None and s is not None else None
        for m, s in zip(macd_line, signal_line)
    ]
    return {
        "ma5": ma5_list, "ma20": ma20_list, "ma60": ma60_list,
        "vol5": vol5_list, "macd_hist": macd_hist_list,
    }


def get_latest(hist, ind):
    prices  = hist["prices"]
    volumes = hist["volumes"]
    if len(prices) < 2:
        return None
    close  = prices[-1]
    prev   = prices[-2]
    vol    = volumes[-1]
    ma5    = ind["ma5"][-1]
    ma20   = ind["ma20"][-1]
    ma60   = ind["ma60"][-1]
    vol5   = ind["vol5"][-1]
    macd_h = ind["macd_hist"][-1]
    prev_macd_h = ind["macd_hist"][-2]
    if ma20 is None or ma20 == 0:
        return None
    change_pct  = round((close - prev) / prev * 100, 2) if prev else 0
    dist_ma20   = round((close - ma20) / ma20 * 100, 2)
    vol_ratio   = round(vol / vol5, 2) if vol5 and vol5 > 0 else 1.0
    is_red      = close >= prev
    is_limit_up = change_pct >= 9.5
    macd_positive = macd_h is not None and macd_h > 0
    macd_cross_up = (macd_h is not None and prev_macd_h is not None
                     and macd_h > 0 and prev_macd_h <= 0)
    if dist_ma20 < -3:
        recent_p  = prices[-5:]
        recent_m  = ind["ma20"][-5:]
        below_days = sum(1 for p, m in zip(recent_p, recent_m) if m and p < m)
        position = "轉弱區" if below_days >= 3 else "月線下方"
    elif dist_ma20 <= 5:
        position = "主升初期"
    elif dist_ma20 <= 15:
        position = "回檔再攻" if change_pct < 0 else "主升中段"
    elif dist_ma20 <= 25:
        position = "主升中段"
    else:
        position = "過熱區"
    return {
        "code": hist["code"], "name": hist["name"],
        "close": round(close, 2), "change_pct": change_pct,
        "volume": int(vol), "vol5": int(vol5) if vol5 else 0,
        "vol_ratio": vol_ratio,
        "ma5": round(ma5, 2) if ma5 else None,
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2) if ma60 else None,
        "dist_ma20": dist_ma20,
        "macd_positive": macd_positive, "macd_cross_up": macd_cross_up,
        "is_red": is_red, "is_limit_up": is_limit_up,
        "position": position,
        "trade_date": hist["dates"][-1] if hist["dates"] else "",
    }


def calc_sector_score(stocks):
    score, details = 0, []
    if not stocks:
        return 0, "非主流", []
    up3 = sum(1 for s in stocks if s["change_pct"] >= 3)
    if up3 >= 3: score += 2; details.append(f"{up3} 檔漲幅 >3%")
    vol_surge = sum(1 for s in stocks if s["vol_ratio"] >= 1.5)
    if vol_surge >= 2: score += 2; details.append(f"{vol_surge} 檔爆量")
    limit_up = sum(1 for s in stocks if s["is_limit_up"])
    if limit_up > 0: score += 2; details.append(f"{limit_up} 檔漲停")
    above = sum(1 for s in stocks if s["dist_ma20"] > 0)
    if above >= len(stocks) * 0.6: score += 1; details.append(f"{above}/{len(stocks)} 站月線")
    macd_pos = sum(1 for s in stocks if s["macd_positive"])
    if macd_pos >= len(stocks) * 0.5: score += 1; details.append(f"{macd_pos} 檔 MACD 正")
    status = "主流啟動" if score >= 8 else "資金回流" if score >= 6 else "觀察中" if score >= 4 else "非主流"
    return score, status, details


def calc_stock_score(s):
    score = 0
    if s["dist_ma20"] > 0: score += 10
    if s["ma5"] and s["ma20"] and s["ma5"] > s["ma20"]: score += 5
    if s["ma20"] and s["ma60"] and s["ma20"] > s["ma60"]: score += 10
    if s["macd_positive"]: score += 10
    if s["vol_ratio"] >= 1.5: score += 15
    if s["dist_ma20"] > 25: score -= 20
    if s["change_pct"] <= -5 and s["vol_ratio"] >= 2: score -= 25
    return max(0, min(100, score))


def score_label(score):
    if score >= 85: return "強勢核心"
    if score >= 70: return "強勢觀察"
    if score >= 55: return "中性"
    if score >= 40: return "偏弱"
    return "避免觀察"


def get_labels(s, sector_score, sector_stocks):
    labels = []
    if s["dist_ma20"] > 30: labels.append("過熱勿追")
    if s["position"] == "轉弱區": labels.append("趨勢轉弱")
    if s["change_pct"] <= -5 and s["vol_ratio"] >= 2: labels.append("爆量長黑")
    if labels: return labels
    if s["vol_ratio"] >= 1.5 and s["is_red"] and s["dist_ma20"] > 0 and sector_score >= 6:
        labels.append("平台突破")
    if s["dist_ma20"] >= -5 and s["dist_ma20"] <= 5 and s["is_red"] and s["vol_ratio"] < 1.2:
        labels.append("回月線轉強")
    leader_high = any(x["change_pct"] >= 5 for x in sector_stocks if x["code"] != s["code"])
    if leader_high and s["dist_ma20"] > 0 and s["dist_ma20"] < 15 and s["vol_ratio"] >= 1.2:
        labels.append("補漲候選")
    if not labels: labels.append("觀察中")
    return labels


def main():
    print("=" * 50)
    print(f"台股盤後觀測系統 — 資料更新")
    print(f"執行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    print("\n[INFO] 從 twstock 取得股票名稱...")
    name_map = get_all_names()

    print(f"\n[INFO] 抓取 {len(ALL_CODES)} 檔股票資料...")
    histories = {}
    for code in ALL_CODES:
        hist = fetch_stock_history(code, name_map.get(code, code))
        if hist:
            histories[code] = hist

    print("\n[INFO] 計算技術指標...")
    processed = {}
    for code, hist in histories.items():
        ind = calculate_indicators(hist)
        latest = get_latest(hist, ind)
        if latest:
            processed[code] = latest

    print("\n[INFO] 計算族群強度...")
    sector_results = []
    for sector_name, codes in SECTORS.items():
        sector_stocks = [processed[c] for c in codes if c in processed]
        score, status, details = calc_sector_score(sector_stocks)
        sector_results.append({
            "name": sector_name, "score": score,
            "status": status, "details": details, "codes": codes,
        })
        print(f"  {sector_name}: {score}分 ({status})")
    sector_results.sort(key=lambda x: x["score"], reverse=True)

    print("\n[INFO] 計算個股評分與訊號...")
    stock_results = []
    for sector in sector_results:
        sector_stocks = [processed[c] for c in sector["codes"] if c in processed]
        for s in sector_stocks:
            s["sector"] = sector["name"]
            s["sector_score"] = sector["score"]
            s["score"] = calc_stock_score(s)
            s["score_label"] = score_label(s["score"])
            s["labels"] = get_labels(s, sector["score"], sector_stocks)
            stock_results.append(s)

    second_wave = [s for s in stock_results if any(l in s["labels"] for l in ["回月線轉強", "補漲候選"])]
    breakout    = [s for s in stock_results if "平台突破" in s["labels"]]
    risk_alerts = [s for s in stock_results if any(l in s["labels"] for l in ["過熱勿追", "趨勢轉弱", "爆量長黑"])]

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    trade_date  = datetime.now().strftime("%Y-%m-%d")

    os.makedirs("data", exist_ok=True)
    with open("data/market_report.json", "w", encoding="utf-8") as f:
        json.dump({"update_time": update_time, "trade_date": trade_date,
                   "summary": {"top_sector": sector_results[0]["name"] if sector_results else "-",
                                "top_sector_score": sector_results[0]["score"] if sector_results else 0,
                                "total_stocks": len(stock_results),
                                "strong_stocks": len([s for s in stock_results if s["score"] >= 70]),
                                "breakout_count": len(breakout),
                                "risk_count": len(risk_alerts)}}, f, ensure_ascii=False, indent=2)
    with open("data/sector_ranking.json", "w", encoding="utf-8") as f:
        json.dump({"update_time": update_time, "sectors": sector_results}, f, ensure_ascii=False, indent=2)
    with open("data/stock_signals.json", "w", encoding="utf-8") as f:
        json.dump({"update_time": update_time, "all_stocks": stock_results,
                   "second_wave": second_wave, "breakout": breakout,
                   "risk_alerts": risk_alerts}, f, ensure_ascii=False, indent=2)

    print("\n✅ 資料更新完成！")


if __name__ == "__main__":
    main()
