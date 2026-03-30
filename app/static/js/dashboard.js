// =============================================
//   GHOST LEDGER DASHBOARD — Client Logic
// =============================================

const fmt = {
  currency: (n) => '₦' + Number(n || 0).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  number: (n) => Number(n || 0).toLocaleString(),
  date: (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
};

// ── Stats ──────────────────────────────────────
async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    if (!r.ok) throw new Error('stats fetch failed');
    const d = await r.json();
    document.getElementById('stat-revenue').textContent   = fmt.currency(d.total_revenue);
    document.getElementById('stat-count').textContent     = fmt.number(d.total_transactions);
    document.getElementById('stat-customers').textContent = fmt.number(d.total_customers);
    document.getElementById('stat-today').textContent     = fmt.currency(d.today_revenue);

    const trendEl = document.getElementById('stat-trend');
    const pct = d.trend_percentage;
    const sign = pct >= 0 ? '+' : '';
    trendEl.innerHTML = pct >= 0
      ? `<i class="ph ph-trend-up"></i> ${sign}${pct}% vs yesterday`
      : `<i class="ph ph-trend-down"></i> ${pct}% vs yesterday`;
    trendEl.className = 'trend ' + (pct >= 0 ? 'positive' : 'negative');
  } catch (e) {
    console.error('Could not load stats:', e);
  }
}

// ── Transactions ───────────────────────────────
let allRows = [];
async function loadTransactions(search = '') {
  const tbody = document.getElementById('ledger-body');
  tbody.innerHTML = `<tr><td colspan="6" class="loading-state">Loading…</td></tr>`;

  try {
    const url = `/api/transactions?limit=100${search ? '&search=' + encodeURIComponent(search) : ''}`;
    const r = await fetch(url);
    if (!r.ok) throw new Error('tx fetch failed');
    const data = await r.json();
    allRows = data.items;
    renderRows(allRows);
  } catch (e) {
    console.error('Could not load transactions:', e);
    tbody.innerHTML = `<tr><td colspan="6" class="loading-state">⚠️ Failed to load transactions.</td></tr>`;
  }
}

function renderRows(rows) {
  const tbody = document.getElementById('ledger-body');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-state">No transactions found.</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(tx => `
    <tr>
      <td>${fmt.date(tx.created_at)}</td>
      <td>${escHtml(tx.item || '—')}</td>
      <td>${tx.quantity != null ? tx.quantity + (tx.unit ? ' ' + tx.unit : '') : '—'}</td>
      <td>${fmt.currency(tx.amount)}</td>
      <td>${escHtml(tx.customer || tx.phone_number || '—')}</td>
      <td><span class="badge badge-success">Recorded</span></td>
    </tr>
  `).join('');
}

// XSS helper
function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(str));
  return d.innerHTML;
}

// ── Search ─────────────────────────────────────
let searchTimer = null;
document.getElementById('searchInput').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    loadTransactions(e.target.value.trim());
  }, 350);
});

// ── Init ───────────────────────────────────────
(async () => {
  await Promise.all([loadStats(), loadTransactions()]);
})();

// Auto-refresh stats & transactions every 30 seconds
setInterval(() => {
  loadStats();
  const search = document.getElementById('searchInput').value.trim();
  loadTransactions(search);
}, 30_000);
