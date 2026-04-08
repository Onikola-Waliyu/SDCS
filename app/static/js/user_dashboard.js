// =============================================
//   GHOST LEDGER — User Dashboard Logic
// =============================================

const fmt = {
  currency: (n) => '₦' + Number(n || 0).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  date: (iso) => {
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
};

let currentPeriod = 'today';
let customFrom = null;
let customTo   = null;

// ── Build query string ────────────────────────────────────────────────────────
function buildQS() {
  let qs = `period=${currentPeriod}`;
  if (customFrom) qs += `&from_date=${customFrom}`;
  if (customTo)   qs += `&to_date=${customTo}`;
  const search = document.getElementById('searchInput').value.trim();
  if (search)     qs += `&search=${encodeURIComponent(search)}`;
  return qs;
}

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const r = await fetch(`/api/my/stats?${buildQS()}`);
    if (r.status === 401) { location.href = '/my-ledger'; return; }
    const d = await r.json();
    document.getElementById('stat-revenue').textContent = fmt.currency(d.total_revenue);
    document.getElementById('stat-count').textContent   = d.total_transactions;
    document.getElementById('stat-today').textContent   = fmt.currency(d.today_revenue);
    document.getElementById('stat-avg').textContent     = fmt.currency(d.avg_sale_value);
  } catch(e) { console.error('Stats error:', e); }
}

// ── Transactions ──────────────────────────────────────────────────────────────
async function loadTransactions() {
  const tbody = document.getElementById('ledger-body');
  tbody.innerHTML = `<tr><td colspan="7" class="loading-state">Loading…</td></tr>`;
  try {
    const r = await fetch(`/api/my/transactions?${buildQS()}`);
    if (r.status === 401) { location.href = '/my-ledger'; return; }
    const data = await r.json();
    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="loading-state">No transactions found for this period.</td></tr>`;
      return;
    }
    tbody.innerHTML = data.items.map(tx => `
      <tr class="${tx.status === 'returned' ? 'opacity-80 bg-red-50/40 dark:bg-red-900/10' : ''}">
        <td>${fmt.date(tx.created_at)}</td>
        <td>${esc(tx.item || '—')}</td>
        <td>${tx.quantity != null ? tx.quantity + (tx.unit ? ' ' + tx.unit : '') : '—'}</td>
        <td class="${tx.status === 'returned' ? 'line-through text-red-500 font-medium' : 'font-medium'}">${fmt.currency(tx.amount)}</td>
        <td>${esc(tx.customer || '—')}</td>
        <td>${esc(tx.recorded_by || '—')}</td>
        <td>
            <div class="flex items-center gap-2">
                ${tx.status === 'returned' 
                    ? '<span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-bold bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Refunded</span>'
                    : '<span class="inline-flex items-center px-2 py-1 rounded-md text-xs font-bold bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Recorded</span>'}
                <button onclick="toggleTxStatus(${tx.id})" title="Toggle Return Status" class="p-1 text-gray-400 hover:text-gray-900 hover:bg-gray-200 dark:hover:bg-slate-600 dark:hover:text-white rounded transition">
                    <i class="ph ph-arrow-u-down-left text-lg"></i>
                </button>
            </div>
        </td>
      </tr>
    `).join('');
  } catch(e) {
    console.error('Transactions error:', e);
    document.getElementById('ledger-body').innerHTML = `<tr><td colspan="7" class="loading-state">⚠️ Failed to load transactions.</td></tr>`;
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str)));
  return d.innerHTML;
}

// ── Status Engine ─────────────────────────────────────────────────────────────
async function toggleTxStatus(txId) {
    if (!confirm("Confirm changing this transaction's status?")) return;
    try {
        const res = await fetch(`/api/my/transactions/${txId}/toggle-status`, { method: "POST" });
        if (res.ok) {
            refresh();
        } else {
            alert("Status change failed.");
        }
    } catch(e) {
        console.error("Status change error", e);
    }
}

// ── Period Tab Switching ──────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentPeriod = btn.dataset.period;
    customFrom = null;
    customTo   = null;
    document.getElementById('fromDate').value = '';
    document.getElementById('toDate').value   = '';
    refresh();
  });
});

// ── Custom Date Range ─────────────────────────────────────────────────────────
function applyDateRange() {
  const from = document.getElementById('fromDate').value;
  const to   = document.getElementById('toDate').value;
  if (!from && !to) return;
  customFrom = from || null;
  customTo   = to   || null;
  currentPeriod = 'all'; // override period when custom date is used
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  refresh();
}

// ── Export ────────────────────────────────────────────────────────────────────
function triggerExport(type='csv') {
  window.location.href = `/api/my/export/${type}?${buildQS()}`;
}

// ── Search ────────────────────────────────────────────────────────────────────
let searchTimer;
document.getElementById('searchInput').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(refresh, 350);
});

// ── Refresh ───────────────────────────────────────────────────────────────────
function refresh() {
  loadStats();
  loadTransactions();
}

// ── Init ──────────────────────────────────────────────────────────────────────
refresh();
setInterval(refresh, 30_000);
