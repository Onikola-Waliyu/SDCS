// =============================================
//   SDCS LEDGER — User Dashboard Logic
// =============================================

const fmt = {
  currency: (n) => '₦' + Number(n || 0).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  date: (iso) => {
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }
};

// ── Pagination state ──────────────────────────────────────────────────────────
const PAGE_LIMIT    = 50;
let currentOffset   = 0;
let totalCount      = 0;
let isLoadingMore   = false;

// ── Filter state ──────────────────────────────────────────────────────────────
let currentPeriod = 'today';
let customFrom    = null;
let customTo      = null;

// ── Build query string ─────────────────────────────────────────────────────────
function buildQS(offset = 0) {
  let qs = `period=${currentPeriod}&limit=${PAGE_LIMIT}&offset=${offset}`;
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

// ── Render a single transaction row ───────────────────────────────────────────
function renderRow(tx) {
  return `
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
  `;
}

// ── Load More button state helper ─────────────────────────────────────────────
function syncLoadMoreBtn() {
  const btn = document.getElementById('load-more-btn');
  const wrap = document.getElementById('load-more-wrap');
  if (!btn || !wrap) return;

  const loaded = currentOffset; // offset = count already shown
  if (loaded >= totalCount) {
    wrap.classList.remove('hidden');
    btn.disabled = true;
    btn.textContent = 'All records loaded';
    btn.className = 'w-full py-3 text-sm font-semibold text-gray-400 dark:text-gray-500 cursor-default';
  } else {
    wrap.classList.remove('hidden');
    btn.disabled = false;
    const remaining = totalCount - loaded;
    btn.textContent = `Load More (${remaining} remaining)`;
    btn.className = 'w-full py-3 text-sm font-semibold text-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 rounded-xl border border-green-200 dark:border-green-900/40 transition';
  }
}

// ── Transactions — initial load (replaces table) ───────────────────────────────
async function loadTransactions() {
  currentOffset = 0;
  const tbody = document.getElementById('ledger-body');
  tbody.innerHTML = `<tr><td colspan="7" class="text-center py-12 text-gray-400 dark:text-gray-500 text-sm">Loading…</td></tr>`;
  // Hide load-more while fetching first page
  const wrap = document.getElementById('load-more-wrap');
  if (wrap) wrap.classList.add('hidden');

  try {
    const r = await fetch(`/api/my/transactions?${buildQS(0)}`);
    if (r.status === 401) { location.href = '/my-ledger'; return; }
    const data = await r.json();

    totalCount    = data.total;
    currentOffset = data.items.length;

    if (!data.items || data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-center py-12 text-gray-400 dark:text-gray-500 text-sm">No transactions found for this period.</td></tr>`;
      syncLoadMoreBtn();
      return;
    }

    tbody.innerHTML = data.items.map(renderRow).join('');
    syncLoadMoreBtn();
  } catch(e) {
    console.error('Transactions error:', e);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-10 text-red-400 text-sm">⚠️ Failed to load transactions.</td></tr>`;
  }
}

// ── Load More — appends next page ─────────────────────────────────────────────
async function loadMore() {
  if (isLoadingMore || currentOffset >= totalCount) return;
  isLoadingMore = true;

  const btn = document.getElementById('load-more-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Loading…';
  }

  try {
    const r = await fetch(`/api/my/transactions?${buildQS(currentOffset)}`);
    if (r.status === 401) { location.href = '/my-ledger'; return; }
    const data = await r.json();

    totalCount = data.total;

    if (data.items && data.items.length > 0) {
      const tbody = document.getElementById('ledger-body');
      tbody.insertAdjacentHTML('beforeend', data.items.map(renderRow).join(''));
      currentOffset += data.items.length;
    }

    syncLoadMoreBtn();
  } catch(e) {
    console.error('Load more error:', e);
    if (btn) btn.textContent = '⚠️ Failed. Try again.';
  } finally {
    isLoadingMore = false;
  }
}

function esc(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str)));
  return d.innerHTML;
}

// ── Status toggle ─────────────────────────────────────────────────────────────
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
  currentPeriod = 'all';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  refresh();
}

// ── Web Manual Entry ──────────────────────────────────────────────────────────
function openEntryModal() {
    const modal = document.getElementById('entry-modal');
    const content = document.getElementById('entry-modal-content');
    modal.classList.remove('hidden');
    setTimeout(() => {
        content.classList.remove('scale-95', 'opacity-0');
        content.classList.add('scale-100', 'opacity-100');
    }, 10);
}

function closeEntryModal() {
    const modal = document.getElementById('entry-modal');
    const content = document.getElementById('entry-modal-content');
    content.classList.remove('scale-100', 'opacity-100');
    content.classList.add('scale-95', 'opacity-0');
    setTimeout(() => {
        modal.classList.add('hidden');
        document.getElementById('add-entry-form').reset();
    }, 300);
}

document.getElementById('add-entry-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('submit-entry-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="ph ph-spinner animate-spin"></i> Saving...';

    const payload = {
        item: document.getElementById('entry-item').value.trim(),
        quantity: parseFloat(document.getElementById('entry-qty').value),
        unit: document.getElementById('entry-unit').value.trim(),
        amount: parseFloat(document.getElementById('entry-amt').value),
        customer: document.getElementById('entry-customer').value.trim()
    };

    try {
        const res = await fetch('/api/my/transactions', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Failed to save');
        closeEntryModal();
        refresh();
    } catch(err) {
        console.error(err);
        alert('Failed to save transaction: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="ph ph-check-circle"></i> Save Entry';
    }
});

// ── Export ────────────────────────────────────────────────────────────────────
function triggerExport(type='csv') {
  window.location.href = `/api/my/export/${type}?${buildQS()}`;
}

// ── Search (debounced, resets pagination) ─────────────────────────────────────
let searchTimer;
document.getElementById('searchInput').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(refresh, 350);
});

// ── Refresh (always resets to page 1) ────────────────────────────────────────
function refresh() {
  loadStats();
  loadTransactions();
}

// ── Init ──────────────────────────────────────────────────────────────────────
refresh();
setInterval(refresh, 30_000);
