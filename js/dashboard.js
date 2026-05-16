/**
 * dashboard.js
 * 台股盤後市場結構觀測系統 — 前端邏輯
 */

// ─────────────────────────────────────────
// 資料載入
// ─────────────────────────────────────────
async function loadJSON(path) {
  const res = await fetch(path + "?t=" + Date.now()); // 避免快取
  if (!res.ok) throw new Error(`無法載入 ${path}`);
  return res.json();
}

async function init() {
  try {
    const [report, sectors, signals] = await Promise.all([
      loadJSON("data/market_report.json"),
      loadJSON("data/sector_ranking.json"),
      loadJSON("data/stock_signals.json"),
    ]);

    renderSummaryBar(report);
    renderSectors(sectors.sectors, signals.all_stocks);
    renderBreakout(signals.breakout);
    renderSecondWave(signals.second_wave);
    renderRiskAlerts(signals.risk_alerts);
    renderStockDetails(sectors.sectors, signals.all_stocks);

    document.getElementById("update-time").textContent =
      "更新：" + report.update_time;
    document.getElementById("trade-date").textContent =
      report.trade_date;
  } catch (e) {
    console.error(e);
    showError("資料載入失敗，請稍後重試。");
  }
}

// ─────────────────────────────────────────
// Summary Bar
// ─────────────────────────────────────────
function renderSummaryBar(report) {
  const s = report.summary;
  document.getElementById("top-sector").textContent = s.top_sector || "—";
  document.getElementById("strong-count").textContent = s.strong_stocks || 0;
  document.getElementById("breakout-count").textContent = s.breakout_count || 0;
  document.getElementById("risk-count").textContent = s.risk_count || 0;
}

// ─────────────────────────────────────────
// 族群排行
// ─────────────────────────────────────────
function renderSectors(sectors, allStocks) {
  const el = document.getElementById("sector-list");
  el.innerHTML = sectors.map((sec, idx) => {
    const pct = Math.round((sec.score / 10) * 100);
    const statusColor = getStatusColor(sec.status);
    const barColor = getBarColor(sec.score);

    // 族群內個股摘要
    const secStocks = allStocks.filter((s) => s.sector === sec.name);
    const stockBadges = secStocks
      .slice(0, 4)
      .map((s) => {
        const cls = s.change_pct >= 0 ? "text-red-400" : "text-green-400";
        return `<span class="text-xs ${cls} mono">${s.name} ${s.change_pct >= 0 ? "+" : ""}${s.change_pct}%</span>`;
      })
      .join(" · ");

    return `
      <div class="flex items-center gap-4 py-2 border-b border-gray-800 last:border-0">
        <!-- 排名 -->
        <span class="mono text-gray-600 text-sm w-4 flex-shrink-0">${idx + 1}</span>

        <!-- 族群名 + 個股 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-3 mb-1">
            <span class="text-white font-medium text-sm">${sec.name}</span>
            <span class="tag tag-${getStatusTagClass(sec.status)}">${sec.status}</span>
          </div>
          <div class="flex flex-wrap gap-2">${stockBadges || '<span class="text-gray-600 text-xs">無資料</span>'}</div>
        </div>

        <!-- 強度 -->
        <div class="flex items-center gap-3 flex-shrink-0">
          <div class="w-24">
            <div class="strength-bar">
              <div class="strength-fill ${barColor}" style="width: ${pct}%"></div>
            </div>
          </div>
          <span class="mono font-bold text-sm ${statusColor} w-6 text-right">${sec.score}</span>
        </div>
      </div>`;
  }).join("");
}

// ─────────────────────────────────────────
// 平台突破
// ─────────────────────────────────────────
function renderBreakout(stocks) {
  const el = document.getElementById("breakout-list");
  if (!stocks || stocks.length === 0) {
    el.innerHTML = `<p class="text-gray-600 text-sm text-center py-4">今日無突破訊號</p>`;
    return;
  }
  el.innerHTML = stocks.map((s) => renderStockCard(s, "breakout")).join("");
}

// ─────────────────────────────────────────
// 第二波觀察池
// ─────────────────────────────────────────
function renderSecondWave(stocks) {
  const el = document.getElementById("second-wave-list");
  if (!stocks || stocks.length === 0) {
    el.innerHTML = `<p class="text-gray-600 text-sm text-center py-4">今日無第二波候選</p>`;
    return;
  }
  el.innerHTML = stocks.map((s) => renderStockCard(s, "second")).join("");
}

// ─────────────────────────────────────────
// 過熱與風險警示
// ─────────────────────────────────────────
function renderRiskAlerts(stocks) {
  const el = document.getElementById("risk-list");
  if (!stocks || stocks.length === 0) {
    el.innerHTML = `<p class="text-gray-600 text-sm text-center py-4">今日無風險警示</p>`;
    return;
  }
  el.innerHTML = stocks.map((s) => renderStockCard(s, "risk")).join("");
}

// ─────────────────────────────────────────
// 族群明細表
// ─────────────────────────────────────────
function renderStockDetails(sectors, allStocks) {
  const el = document.getElementById("stock-detail-list");

  // 只顯示分數 ≥ 4 的族群
  const activeSectors = sectors.filter((s) => s.score >= 4);

  el.innerHTML = activeSectors.map((sec) => {
    const secStocks = allStocks
      .filter((s) => s.sector === sec.name)
      .sort((a, b) => b.score - a.score);

    const rows = secStocks.map((s) => {
      const changeCls = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "flat";
      const changeSign = s.change_pct > 0 ? "+" : "";
      const scoreCls = s.score >= 70 ? "score-high" : s.score >= 50 ? "score-mid" : "score-low";
      const distSign = s.dist_ma20 >= 0 ? "+" : "";

      return `
        <tr class="table-row border-b border-gray-800 last:border-0">
          <td class="py-2 pr-4">
            <span class="text-white font-medium text-sm">${s.name}</span>
            <span class="text-gray-600 text-xs ml-1 mono">${s.ticker.replace(".TW","")}</span>
          </td>
          <td class="py-2 pr-4">
            <span class="text-xs px-2 py-0.5 rounded ${getPositionClass(s.position)}">${s.position}</span>
          </td>
          <td class="py-2 pr-4 mono text-sm ${changeCls}">${changeSign}${s.change_pct}%</td>
          <td class="py-2 pr-4 mono text-sm text-gray-400">${distSign}${s.dist_ma20}%</td>
          <td class="py-2 pr-4 mono text-sm text-gray-400">${s.vol_ratio}x</td>
          <td class="py-2 pr-4 mono text-sm font-bold ${scoreCls}">${s.score}</td>
          <td class="py-2">${renderLabels(s.labels)}</td>
        </tr>`;
    }).join("");

    return `
      <div>
        <div class="flex items-center gap-2 mb-2">
          <span class="text-gray-400 font-medium text-sm">${sec.name}</span>
          <span class="tag ${getStatusTagClass(sec.status) === 'hot' ? 'tag-breakout' : 'tag-watch'} text-xs">${sec.status} ${sec.score}分</span>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-gray-600 text-xs">
                <th class="text-left pb-2 pr-4">股票</th>
                <th class="text-left pb-2 pr-4">位階</th>
                <th class="text-left pb-2 pr-4">漲跌</th>
                <th class="text-left pb-2 pr-4">距月線</th>
                <th class="text-left pb-2 pr-4">量比</th>
                <th class="text-left pb-2 pr-4">評分</th>
                <th class="text-left pb-2">訊號</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }).join("");
}

// ─────────────────────────────────────────
// 個股卡片（小）
// ─────────────────────────────────────────
function renderStockCard(s, type) {
  const changeCls = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "flat";
  const changeSign = s.change_pct > 0 ? "+" : "";
  const scoreCls = s.score >= 70 ? "score-high" : s.score >= 50 ? "score-mid" : "score-low";

  return `
    <div class="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-white font-medium text-sm">${s.name}</span>
          <span class="text-gray-600 text-xs mono">${s.ticker.replace(".TW","")}</span>
        </div>
        <div class="flex items-center gap-1 mt-0.5">
          <span class="text-gray-500 text-xs">${s.sector}</span>
          <span class="text-gray-600">·</span>
          ${renderLabels(s.labels)}
        </div>
      </div>
      <div class="text-right">
        <div class="mono text-sm ${changeCls}">${changeSign}${s.change_pct}%</div>
        <div class="mono text-xs ${scoreCls}">${s.score}分</div>
      </div>
    </div>`;
}

// ─────────────────────────────────────────
// 標籤渲染
// ─────────────────────────────────────────
function renderLabels(labels) {
  if (!labels || labels.length === 0) return "";
  return labels.map((l) => {
    const cls = getLabelClass(l);
    return `<span class="tag ${cls}">${l}</span>`;
  }).join(" ");
}

function getLabelClass(label) {
  if (["平台突破"].includes(label)) return "tag-breakout";
  if (["回月線轉強", "補漲候選"].includes(label)) return "tag-second";
  if (["過熱勿追", "爆量長黑"].includes(label)) return "tag-hot";
  if (["趨勢轉弱", "動能轉弱"].includes(label)) return "tag-weak";
  return "tag-watch";
}

function getPositionClass(pos) {
  if (pos === "主升初期") return "pos-early";
  if (pos === "回檔再攻") return "pos-pullback";
  if (pos === "主升中段") return "pos-mid";
  if (pos === "過熱區") return "pos-hot";
  if (pos === "轉弱區") return "pos-weak";
  return "pos-default";
}

function getStatusColor(status) {
  if (status === "主流啟動") return "text-yellow-400";
  if (status === "資金回流") return "text-green-400";
  if (status === "觀察中") return "text-blue-400";
  return "text-gray-500";
}

function getStatusTagClass(status) {
  if (status === "主流啟動") return "hot";
  if (status === "資金回流") return "second";
  return "watch";
}

function getBarColor(score) {
  if (score >= 8) return "bg-yellow-400";
  if (score >= 6) return "bg-green-500";
  if (score >= 4) return "bg-blue-500";
  return "bg-gray-600";
}

// ─────────────────────────────────────────
// 錯誤提示
// ─────────────────────────────────────────
function showError(msg) {
  document.querySelector("main").innerHTML = `
    <div class="card p-8 text-center">
      <p class="text-red-400 text-lg mb-2">⚠️ ${msg}</p>
      <p class="text-gray-500 text-sm">請確認 data/ 目錄中的 JSON 檔案是否存在。</p>
    </div>`;
}

// 啟動
init();
