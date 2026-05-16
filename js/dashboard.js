/**
 * dashboard.js — 台股盤後市場結構觀測系統
 * 淡白底精緻版
 */

async function loadJSON(path) {
  const res = await fetch(path + "?t=" + Date.now());
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
    renderSummary(report);
    renderSectors(sectors.sectors, signals.all_stocks);
    renderBreakout(signals.breakout);
    renderSecondWave(signals.second_wave);
    renderRisk(signals.risk_alerts);
    renderDetails(sectors.sectors, signals.all_stocks);
    document.getElementById("update-time").textContent = "更新：" + report.update_time;
    document.getElementById("trade-date").textContent = report.trade_date;
  } catch (e) {
    console.error(e);
    document.querySelector("main").innerHTML =
      `<div class="card p-8 text-center" style="color:var(--up);">⚠️ 資料載入失敗，請稍後重試。</div>`;
  }
}

// ── Summary ──
function renderSummary(r) {
  const s = r.summary;
  document.getElementById("top-sector").textContent   = s.top_sector || "—";
  document.getElementById("strong-count").textContent = s.strong_stocks || 0;
  document.getElementById("breakout-count").textContent = s.breakout_count || 0;
  document.getElementById("risk-count").textContent   = s.risk_count || 0;
}

// ── 族群排行 ──
function renderSectors(sectors, allStocks) {
  const el = document.getElementById("sector-list");
  el.innerHTML = sectors.map((sec, i) => {
    const pct = Math.round((sec.score / 10) * 100);
    const barCls = sec.score >= 8 ? "bar-gold" : sec.score >= 6 ? "bar-green" : sec.score >= 4 ? "bar-blue" : "bar-gray";
    const statusCls = sec.score >= 8 ? "status-main" : sec.score >= 6 ? "status-flow" : sec.score >= 4 ? "status-watch" : "status-none";

    const secStocks = allStocks.filter(s => s.sector === sec.name);
    const badges = secStocks.slice(0, 5).map(s => {
      const cls = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "flat";
      const sign = s.change_pct > 0 ? "+" : "";
      return `<span class="${cls} mono" style="font-size:11px;">${s.name} ${sign}${s.change_pct}%</span>`;
    }).join('<span style="color:var(--border2);margin:0 4px;">·</span>');

    return `
      <div class="trow flex items-center gap-4 py-3 px-1">
        <span class="mono" style="color:var(--faint);font-size:11px;width:14px;">${i + 1}</span>
        <div style="flex:1;min-width:0;">
          <div class="flex items-center gap-2 mb-1">
            <span style="font-weight:600;font-size:13px;">${sec.name}</span>
            <span class="${statusCls}" style="font-size:11px;">${sec.status}</span>
          </div>
          <div class="flex flex-wrap items-center gap-1">${badges || '<span style="color:var(--faint);font-size:11px;">無資料</span>'}</div>
        </div>
        <div class="flex items-center gap-3" style="flex-shrink:0;">
          <div class="bar-track" style="width:80px;">
            <div class="bar-fill ${barCls}" style="width:${pct}%;"></div>
          </div>
          <span class="mono ${statusCls}" style="font-size:13px;width:16px;text-align:right;">${sec.score}</span>
        </div>
      </div>`;
  }).join("");
}

// ── 小卡片 ──
function stockCard(s) {
  const cls  = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "flat";
  const sign = s.change_pct > 0 ? "+" : "";
  const scoreCls = s.score >= 70 ? "score-high" : s.score >= 50 ? "score-mid" : "score-low";
  return `
    <div class="trow flex items-center justify-between py-2">
      <div>
        <div class="flex items-center gap-2">
          <span style="font-weight:600;font-size:13px;">${s.name}</span>
          <span class="mono" style="color:var(--faint);font-size:11px;">${s.code}</span>
        </div>
        <div class="flex items-center gap-1 mt-0.5">
          <span style="color:var(--faint);font-size:11px;">${s.sector}</span>
          <span style="color:var(--border2);">·</span>
          ${renderLabels(s.labels)}
        </div>
      </div>
      <div style="text-align:right;">
        <div class="mono" style="font-size:13px;font-weight:500;color:var(--text);">$${s.close}</div>
        <div class="mono ${cls}" style="font-size:12px;">${sign}${s.change_pct}%</div>
        <div class="mono ${scoreCls}" style="font-size:11px;">${s.score}分</div>
      </div>
    </div>`;
}

function emptyMsg(msg) {
  return `<p style="color:var(--faint);font-size:12px;text-align:center;padding:16px 0;">${msg}</p>`;
}

function renderBreakout(stocks) {
  const el = document.getElementById("breakout-list");
  el.innerHTML = stocks?.length ? stocks.map(stockCard).join("") : emptyMsg("今日無突破訊號");
}
function renderSecondWave(stocks) {
  const el = document.getElementById("second-wave-list");
  el.innerHTML = stocks?.length ? stocks.map(stockCard).join("") : emptyMsg("今日無第二波候選");
}
function renderRisk(stocks) {
  const el = document.getElementById("risk-list");
  el.innerHTML = stocks?.length ? stocks.map(stockCard).join("") : emptyMsg("今日無風險警示");
}

// ── 族群明細表 ──
function renderDetails(sectors, allStocks) {
  const el = document.getElementById("stock-detail-list");
  const activeSectors = sectors.filter(s => s.score >= 4);

  el.innerHTML = activeSectors.map(sec => {
    const stocks = allStocks
      .filter(s => s.sector === sec.name)
      .sort((a, b) => b.score - a.score);

    const rows = stocks.map(s => {
      const cls  = s.change_pct > 0 ? "up" : s.change_pct < 0 ? "down" : "flat";
      const sign = s.change_pct > 0 ? "+" : "";
      const dSign = s.dist_ma20 >= 0 ? "+" : "";
      const scoreCls = s.score >= 70 ? "score-high" : s.score >= 50 ? "score-mid" : "score-low";
      return `
        <tr class="trow">
          <td style="padding:8px 12px 8px 0;">
            <span style="font-weight:600;font-size:13px;">${s.name}</span>
            <span class="mono" style="color:var(--faint);font-size:11px;margin-left:4px;">${s.code}</span>
          </td>
          <td style="padding:8px 12px 8px 0;">
            <span class="tag" style="font-size:10px;" class="${getPosClass(s.position)}">${s.position}</span>
          </td>
          <td class="mono" style="padding:8px 12px 8px 0;font-size:13px;font-weight:500;color:var(--text);">$${s.close}</td>
          <td class="mono ${cls}" style="padding:8px 12px 8px 0;font-size:12px;">${sign}${s.change_pct}%</td>
          <td class="mono" style="padding:8px 12px 8px 0;font-size:12px;color:var(--muted);">${dSign}${s.dist_ma20}%</td>
          <td class="mono" style="padding:8px 12px 8px 0;font-size:12px;color:var(--muted);">${s.vol_ratio}x</td>
          <td class="mono ${scoreCls}" style="padding:8px 12px 8px 0;font-size:13px;font-weight:600;">${s.score}</td>
          <td style="padding:8px 0;">${renderLabels(s.labels)}</td>
        </tr>`;
    }).join("");

    const statusCls = sec.score >= 8 ? "status-main" : sec.score >= 6 ? "status-flow" : "status-watch";

    return `
      <div>
        <div class="flex items-center gap-2 mb-3">
          <span style="font-weight:600;font-size:13px;">${sec.name}</span>
          <span class="${statusCls}" style="font-size:11px;">${sec.status} ${sec.score}分</span>
        </div>
        <div style="overflow-x:auto;">
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="color:var(--faint);font-size:11px;letter-spacing:0.04em;">
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">股票</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">位階</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">收盤</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">漲跌</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">距月線</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">量比</th>
                <th style="text-align:left;padding-bottom:8px;padding-right:12px;font-weight:500;">評分</th>
                <th style="text-align:left;padding-bottom:8px;font-weight:500;">訊號</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </div>`;
  }).join("");
}

// ── 工具函式 ──
function renderLabels(labels) {
  if (!labels?.length) return "";
  return labels.map(l => `<span class="tag ${getLabelCls(l)}">${l}</span>`).join(" ");
}

function getLabelCls(l) {
  if (["平台突破"].includes(l)) return "tag-breakout";
  if (["回月線轉強", "補漲候選"].includes(l)) return "tag-second";
  if (["過熱勿追", "爆量長黑"].includes(l)) return "tag-hot";
  if (["趨勢轉弱", "動能轉弱"].includes(l)) return "tag-weak";
  return "tag-watch";
}

function getPosClass(pos) {
  if (pos === "主升初期") return "pos-early";
  if (pos === "回檔再攻") return "pos-pullback";
  if (pos === "主升中段") return "pos-mid";
  if (pos === "過熱區")   return "pos-hot";
  if (pos === "轉弱區")   return "pos-weak";
  return "pos-default";
}

init();
