# 台股盤後市場結構觀測系統

每日盤後自動更新的台股市場結構 Dashboard，架設於 GitHub Pages，資料由 GitHub Actions 自動排程抓取。

**成本：$0 / 月**

---

## 系統功能

- ⚡ **主流族群排行**：7 大族群強度評分與狀態
- 🚀 **平台突破候選**：量價俱揚的突破訊號
- 🔄 **第二波觀察池**：回測月線後的低風險再攻訊號
- ⚠️ **過熱與風險警示**：過熱股、爆量長黑提醒
- 📊 **族群強勢股明細**：位階、距月線、評分、技術標籤

---

## 快速部署步驟

### 第一步：建立 GitHub Repo

1. 登入 [GitHub](https://github.com)
2. 點選右上角 **+** → **New repository**
3. Repository name 填入：`stock-dashboard`
4. 選擇 **Public**（GitHub Pages 免費版需為公開）
5. 點選 **Create repository**

---

### 第二步：上傳所有檔案

將本專案所有檔案上傳至 Repo：

```bash
git clone https://github.com/你的帳號/stock-dashboard.git
cd stock-dashboard

# 複製所有專案檔案進來
# 然後：
git add .
git commit -m "初始化台股觀測系統"
git push
```

或直接在 GitHub 網頁上傳。

---

### 第三步：啟用 GitHub Pages

1. 進入 Repo → **Settings** → **Pages**
2. Source 選擇：**Deploy from a branch**
3. Branch 選擇：**main**，資料夾選 **/ (root)**
4. 點選 **Save**
5. 等待約 1 分鐘，系統會顯示你的 Dashboard 網址

**網址格式**：`https://你的帳號.github.io/stock-dashboard`

---

### 第四步：設定 GitHub Actions 權限

1. 進入 Repo → **Settings** → **Actions** → **General**
2. 找到 **Workflow permissions**
3. 選擇 **Read and write permissions**
4. 點選 **Save**

這個設定讓 GitHub Actions 可以自動 commit 更新後的 JSON 資料。

---

### 第五步：手動測試資料更新

1. 進入 Repo → **Actions**
2. 點選左側 **每日盤後資料更新**
3. 點選右側 **Run workflow** → **Run workflow**
4. 等待約 2-3 分鐘執行完成
5. 回到 Pages 網址確認資料已更新

---

## 自動排程說明

系統設定為：

- **每週一至五**（台灣時間）**18:00** 自動執行
- 若當日非交易日，yfinance 會抓到最近一個交易日資料

排程設定在：`.github/workflows/daily_update.yml`

---

## 專案結構

```
stock-dashboard/
│
├─ index.html                     # Dashboard 首頁
├─ js/
│   └─ dashboard.js               # 前端顯示邏輯
│
├─ data/
│   ├─ market_report.json         # 每日市場摘要
│   ├─ sector_ranking.json        # 族群排行
│   └─ stock_signals.json         # 股票訊號
│
├─ scripts/
│   └─ update_market_data.py      # Python 資料處理主程式
│
└─ .github/
    └─ workflows/
        └─ daily_update.yml       # GitHub Actions 排程
```

---

## 族群設定說明

族群與成員股定義在 `scripts/update_market_data.py` 的 `SECTORS` 字典中：

```python
SECTORS = {
    "玻璃基板": ["3522.TW", "3486.TW", "6504.TW", ...],
    "CoWoS先進封裝": ["3511.TW", "6770.TW", ...],
    ...
}
```

若要新增或修改族群，直接編輯此處即可。

---

## 指標計算邏輯

### 族群強度（最高 10 分）

| 條件 | 分數 |
|---|---|
| ≥3 檔漲幅 >3% | +2 |
| ≥2 檔成交量 >5日均量 1.5 倍 | +2 |
| 族群內有漲停股 | +2 |
| 多數個股站上月線 | +1 |
| MACD 正向比例高 | +1 |

### 個股評分（0–100）

| 條件 | 分數 |
|---|---|
| 站上月線 | +10 |
| MA20 > MA60 | +10 |
| MACD 翻正 | +10 |
| 短均線向上 | +5 |
| 成交量放大 | +15 |
| 距月線 >25% | -20 |
| 爆量長黑 | -25 |

---

## 注意事項

- 本系統為**盤後觀測工具**，不提供買賣建議
- 資料來源為 Yahoo Finance（yfinance），偶爾可能有延遲
- GitHub Actions 免費版每月提供 2,000 分鐘，每日執行約需 2–3 分鐘，一個月約 60–90 分鐘，完全在免費額度內

---

## 後續升級方向

- [ ] 加入 FinMind API（更穩定的台股資料）
- [ ] 加入 Telegram / LINE 推播
- [ ] 加入歷史資料回顧
- [ ] AI 每日市場摘要
