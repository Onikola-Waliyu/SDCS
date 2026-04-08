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
const srcEl = document.getElementById('searchInput');
if (srcEl) {
    srcEl.addEventListener('input', (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        loadTransactions(e.target.value.trim());
      }, 350);
    });
}

// ── Businesses ─────────────────────────────────
async function loadBusinesses() {
  const tbody = document.getElementById('businesses-list');
  tbody.innerHTML = `<tr><td colspan="5" class="text-center py-6 text-gray-500">Querying registry...</td></tr>`;
  try {
    const r = await fetch('/api/admin/businesses');
    const data = await r.json();
    if (!data.businesses || data.businesses.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="text-center py-6 text-gray-500">No active businesses found.</td></tr>`;
      return;
    }
    
    tbody.innerHTML = data.businesses.map(b => `
      <tr class="hover:bg-gray-50 dark:hover:bg-slate-700/50 transition border-t border-gray-50 dark:border-slate-700">
          <td class="py-4 px-5 text-sm text-gray-900 dark:text-white font-medium">
             ${escHtml(b.name)}
             <span class="block text-xs text-gray-500">ID: ${b.id} • Since ${fmt.date(b.created_at)}</span>
          </td>
          <td class="py-4 px-5 text-sm text-gray-600 dark:text-gray-300">
             ${escHtml(b.owner_name)}
             <span class="block text-xs text-blue-500">+${b.owner_phone}</span>
          </td>
          <td class="py-4 px-5 text-center">
             <span class="bg-gray-100 dark:bg-slate-600 text-gray-600 dark:text-gray-300 text-xs font-bold px-3 py-1 rounded-full">${b.staff.length} Agents</span>
          </td>
          <td class="py-4 px-5 text-sm text-green-600 dark:text-green-400 font-bold">
             ${fmt.currency(b.total_revenue)}
             <span class="block text-xs text-gray-500 dark:text-gray-400 font-normal py-1 border-t border-gray-100 dark:border-slate-600 mt-1">${fmt.number(b.total_transactions)} total entries</span>
          </td>
          <td class="py-4 px-5 text-right flex items-center justify-end gap-2">
             <a href="/api/admin/businesses/${b.id}/export/csv" class="p-2 bg-slate-100 dark:bg-slate-600 hover:bg-slate-200 dark:hover:bg-slate-500 rounded-lg text-slate-600 dark:text-slate-300 transition shadow-sm" title="Download CSV"><i class="ph ph-file-csv text-lg"></i></a>
             <a href="/api/admin/businesses/${b.id}/export/pdf" class="p-2 bg-blue-100 dark:bg-blue-900/30 hover:bg-blue-200 dark:hover:bg-blue-800/50 rounded-lg text-blue-600 dark:text-blue-400 transition shadow-sm" title="Download PDF Report"><i class="ph ph-file-pdf text-lg"></i></a>
          </td>
      </tr>
    `).join('');
  } catch (e) {
    console.error(e);
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-6 text-red-500">Error loading business registry.</td></tr>`;
  }
}

// ── Init ───────────────────────────────────────
(async () => {
  await Promise.all([loadStats(), loadTransactions(), loadBusinesses()]);
})();

// Auto-refresh stats & transactions every 30 seconds
setInterval(() => {
  loadStats();
  const searchEl = document.getElementById('searchInput');
  const search = searchEl ? searchEl.value.trim() : "";
  loadTransactions(search);
}, 30_000);
