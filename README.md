# 台股盤後市場結構觀測系統

每日盤後自動更新的台股市場結構 Dashboard，架設於 GitHub Pages，資料由 GitHub Actions 自動排程抓取與計算。

## 功能

- 主流族群排行
- 各族群強勢股 Top 5
- 第二波觀察池
- 平台突破候選
- 過熱與風險警示
- 全部觀測股票清單

## 專案結構

```text
stock-dashboard/
├─ index.html
├─ styles/style.css
├─ js/dashboard.js
├─ data/
│  ├─ market_report.json
│  ├─ sector_ranking.json
│  ├─ stock_signals.json
│  └─ hot_alerts.json
├─ scripts/generate_report.py
├─ requirements.txt
└─ .github/workflows/daily_update.yml
```

## 本機測試

```bash
pip install -r requirements.txt
python scripts/generate_report.py
```

接著用瀏覽器開啟 `index.html`。

## GitHub Pages 設定

1. 進入 GitHub repo
2. 點選 Settings
3. 點選 Pages
4. Source 選擇 `Deploy from a branch`
5. Branch 選擇 `main`
6. Folder 選擇 `/root`
7. 儲存

網站網址通常會是：

```text
https://你的帳號.github.io/stock-dashboard/
```

## GitHub Actions 設定

workflow 檔案位於：

```text
.github/workflows/daily_update.yml
```

預設每日台灣時間 19:30 自動更新。

也可以到 GitHub：

```text
Actions → Daily Stock Dashboard Update → Run workflow
```

手動執行一次。

## 調整觀測股票

請修改：

```text
scripts/generate_report.py
```

裡面的 `THEMES` 區塊。

## 注意

本系統僅供盤後市場結構觀測，不構成投資建議。
