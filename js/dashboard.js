const fmtPct = (v) => (v === null || v === undefined ? "-" : `${v.toFixed ? v.toFixed(2) : v}%`);
const safe = (v) => (v === null || v === undefined ? "-" : v);

function badge(text) {
  let cls = "badge";
  if (["主流啟動", "資金回流", "強勢核心", "平台突破", "回月線轉強", "主升初期", "回檔再攻"].includes(text)) cls += " good";
  if (["過熱勿追", "過熱區", "爆量長黑", "趨勢轉弱", "轉弱區", "MACD轉弱"].includes(text)) cls += " bad";
  if (["觀察中", "主升中段", "降低部位"].includes(text)) cls += " warn";
  return `<span class="${cls}">${text}</span>`;
}

function stockItem(s) {
  return `
    <div class="stock-item">
      <div>
        <div class="stock-name">${s.stock_id} ${s.stock_name}</div>
        <div class="stock-meta">${s.theme}｜${s.phase}｜距月線 ${fmtPct(s.distance_ma20_pct)}｜收盤 ${safe(s.close)}</div>
        <div>${(s.tags || []).map(badge).join("")}</div>
      </div>
      <div class="score">${s.score}</div>
    </div>
  `;
}

async function loadDashboard() {
  const res = await fetch("data/market_report.json?ts=" + Date.now());
  const data = await res.json();

  document.getElementById("generatedAt").textContent = data.generated_at || "-";
  document.getElementById("topSector").textContent = data.sector_ranking?.[0]?.theme || "-";
  document.getElementById("secondWaveCount").textContent = data.second_wave?.length ?? 0;
  document.getElementById("breakoutCount").textContent = data.platform_breakouts?.length ?? 0;
  document.getElementById("alertCount").textContent = data.hot_alerts?.length ?? 0;

  document.getElementById("sectorRanking").innerHTML = (data.sector_ranking || []).map((s, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${s.theme}</strong></td>
      <td>${s.score}</td>
      <td>${badge(s.status)}</td>
      <td>${s.stocks_count}</td>
    </tr>
  `).join("");

  document.getElementById("secondWaveList").innerHTML =
    (data.second_wave || []).slice(0, 10).map(stockItem).join("") || "<p>目前無符合條件標的。</p>";

  document.getElementById("breakoutList").innerHTML =
    (data.platform_breakouts || []).slice(0, 10).map(stockItem).join("") || "<p>目前無符合條件標的。</p>";

  document.getElementById("alertList").innerHTML =
    (data.hot_alerts || []).slice(0, 20).map(stockItem).join("") || "<p>目前無風險警示。</p>";

  const themeHtml = Object.entries(data.top_by_theme || {}).map(([theme, stocks]) => `
    <div class="theme-box">
      <h3>${theme}</h3>
      ${(stocks || []).map(stockItem).join("")}
    </div>
  `).join("");
  document.getElementById("themeStocks").innerHTML = themeHtml;

  document.getElementById("allStocks").innerHTML = (data.all_stocks || []).map(s => `
    <tr>
      <td>${s.stock_id}</td>
      <td><strong>${s.stock_name}</strong></td>
      <td>${s.theme}</td>
      <td>${safe(s.close)}</td>
      <td>${fmtPct(s.change_pct)}</td>
      <td>${fmtPct(s.distance_ma20_pct)}</td>
      <td>${badge(s.phase)}</td>
      <td><strong>${s.score}</strong></td>
      <td>${(s.tags || []).map(badge).join("")}</td>
    </tr>
  `).join("");
}

loadDashboard().catch(err => {
  console.error(err);
  document.body.innerHTML = `<main><section class="card"><h1>資料讀取失敗</h1><p>${err.message}</p><p>請確認 data/market_report.json 是否存在，或先執行 GitHub Actions / scripts/generate_report.py。</p></section></main>`;
});
