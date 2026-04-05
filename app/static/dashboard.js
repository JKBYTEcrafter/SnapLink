/* =====================================================
   SnapLink Dashboard — JavaScript
   ===================================================== */

const API_BASE = 'http://localhost:8000';

// ---- State ----
let currentPage = 1;
let currentFilter = 'all';
let currentSearch = '';
let totalPages = 1;
let allStatsLoaded = false;
let deleteTarget = null;
let searchTimeout = null;
let bulkPanelOpen = false;

// ---- Auth Helpers ----
function getAuthHeaders() {
  const token = localStorage.getItem('snaplink_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

function updateDashboardNav() {
  const token = localStorage.getItem('snaplink_token');
  const authNav = document.getElementById('auth-nav');
  if (!authNav) return;
  if (token) {
    authNav.innerHTML = `
      <a href="/" class="nav-link">Home</a>
      <a href="#" class="nav-link" onclick="logout(event)" style="color:#fca5a5;">Logout</a>
    `;
  } else {
    authNav.innerHTML = `
      <a href="/" class="nav-link">Home</a>
      <a href="#" class="nav-link" onclick="openAuthModal('login')">Login</a>
      <a href="#" class="nav-link" onclick="openAuthModal('signup')">Sign Up</a>
    `;
  }
}

function logout(e) {
  if (e) e.preventDefault();
  localStorage.removeItem('snaplink_token');
  window.location.href = '/';
}

// =====================================================
// INIT
// =====================================================

document.addEventListener('DOMContentLoaded', () => {
  updateDashboardNav();
  loadLinks();
  setupBulkTextareaCounter();
});

// =====================================================
// LOAD LINKS
// =====================================================

async function loadLinks(page = 1) {
  currentPage = page;
  showTableLoading(true);

  const params = new URLSearchParams({ page, limit: 15 });
  if (currentSearch) params.set('q', currentSearch);
  if (currentFilter !== 'all') params.set('status', currentFilter);

  try {
    const res = await fetch(`${API_BASE}/links?${params}`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) throw new Error('Failed to load links');
    const data = await res.json();
    totalPages = data.pages;
    renderTable(data);
    renderPagination(data);
    if (!allStatsLoaded) {
      computeStats(data);
      allStatsLoaded = true;
    }
  } catch (err) {
    document.getElementById('db-loading').style.display = 'none';
    document.getElementById('db-empty').style.display = 'flex';
    document.getElementById('db-empty').querySelector('p').textContent =
      'Could not load links. Is the server running?';
    console.error(err);
  }
}

// =====================================================
// RENDER TABLE
// =====================================================

function renderTable(data) {
  showTableLoading(false);

  const tbody = document.getElementById('db-tbody');
  const table = document.getElementById('db-table');
  const empty = document.getElementById('db-empty');

  tbody.innerHTML = '';

  if (!data.items || data.items.length === 0) {
    table.style.display = 'none';
    empty.style.display = 'flex';
    return;
  }

  empty.style.display = 'none';
  table.style.display = 'table';

  data.items.forEach(link => {
    const tr = document.createElement('tr');
    tr.className = 'db-row';
    if (link.is_expired) tr.classList.add('expired-row');

    const shortDisplay = link.short_url.replace(/^https?:\/\//, '');
    const longDisplay = link.long_url.length > 60
      ? link.long_url.slice(0, 57) + '...'
      : link.long_url;
    const createdDate = link.created_at
      ? new Date(link.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
      : '—';

    const statusPill = link.is_expired
      ? `<span class="status-pill pill-expired">Expired</span>`
      : `<span class="status-pill pill-active">Active</span>`;

    tr.innerHTML = `
      <td>
        <div class="short-link-cell">
          <a href="${link.short_url}" target="_blank" class="short-link-text">${shortDisplay}</a>
          <button class="icon-btn" onclick="copyToClipboard('${link.short_url}', this)" title="Copy">📋</button>
        </div>
      </td>
      <td>
        <div class="long-url-cell" title="${link.long_url}">
          <span class="long-url-text">${longDisplay}</span>
        </div>
      </td>
      <td>
        <span class="click-badge">${link.click_count.toLocaleString()}</span>
      </td>
      <td class="date-cell">${createdDate}</td>
      <td>${statusPill}</td>
      <td>
        <div class="action-btns">
          <button class="tbl-action-btn btn-edit" onclick="openEditModal(${JSON.stringify(link).replace(/"/g, '&quot;')})" title="Edit">✏️</button>
          <button class="tbl-action-btn btn-preview" onclick="openPreviewModal('${link.short_code}', '${link.preview_url}')" title="Preview Card">🖼️</button>
          <button class="tbl-action-btn btn-qr" onclick="openQRModal('${link.qr_url}')" title="QR Code">📱</button>
          <button class="tbl-action-btn btn-analytics" onclick="goToAnalytics('${link.short_code}')" title="Analytics">📊</button>
          <button class="tbl-action-btn btn-delete" onclick="openDeleteModal('${link.short_code}')" title="Delete">🗑️</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// =====================================================
// STATS
// =====================================================

async function computeStats(firstPageData) {
  // Load all for active/expired count
  try {
    const [allRes, expiredRes] = await Promise.all([
      fetch(`${API_BASE}/links?limit=1`, { headers: getAuthHeaders() }),
      fetch(`${API_BASE}/links?limit=1&status=expired`, { headers: getAuthHeaders() }),
    ]);
    const allData = await allRes.json();
    const expiredData = await expiredRes.json();

    const total = allData.total || 0;
    const expired = expiredData.total || 0;
    const active = total - expired;

    document.getElementById('db-stat-total').textContent = total.toLocaleString();
    document.getElementById('db-stat-active').textContent = active.toLocaleString();
    document.getElementById('db-stat-expired').textContent = expired.toLocaleString();

    // Total clicks from first page data (partial — if small dataset)
    const totalClicks = (firstPageData.items || []).reduce((sum, l) => sum + l.click_count, 0);
    document.getElementById('db-stat-clicks').textContent = totalClicks.toLocaleString() + (total > 15 ? '+' : '');
  } catch (e) {
    console.warn('Stats load failed', e);
  }
}

// =====================================================
// PAGINATION
// =====================================================

function renderPagination(data) {
  const container = document.getElementById('db-pagination');
  container.innerHTML = '';

  if (data.pages <= 1) return;

  const makeBtn = (label, page, active = false, disabled = false) => {
    const btn = document.createElement('button');
    btn.className = 'page-btn' + (active ? ' active' : '') + (disabled ? ' disabled' : '');
    btn.textContent = label;
    if (!disabled && !active) btn.onclick = () => loadLinks(page);
    return btn;
  };

  container.appendChild(makeBtn('←', currentPage - 1, false, currentPage <= 1));

  const start = Math.max(1, currentPage - 2);
  const end = Math.min(data.pages, currentPage + 2);

  if (start > 1) {
    container.appendChild(makeBtn('1', 1));
    if (start > 2) container.appendChild(Object.assign(document.createElement('span'), { className: 'page-ellipsis', textContent: '…' }));
  }

  for (let p = start; p <= end; p++) {
    container.appendChild(makeBtn(p, p, p === currentPage));
  }

  if (end < data.pages) {
    if (end < data.pages - 1) container.appendChild(Object.assign(document.createElement('span'), { className: 'page-ellipsis', textContent: '…' }));
    container.appendChild(makeBtn(data.pages, data.pages));
  }

  container.appendChild(makeBtn('→', currentPage + 1, false, currentPage >= data.pages));
}

// =====================================================
// SEARCH & FILTER
// =====================================================

function debouncedSearch() {
  clearTimeout(searchTimeout);
  const val = document.getElementById('db-search').value.trim();
  document.getElementById('db-search-clear').style.display = val ? 'flex' : 'none';
  searchTimeout = setTimeout(() => {
    currentSearch = val;
    allStatsLoaded = false;
    loadLinks(1);
  }, 350);
}

function clearSearch() {
  document.getElementById('db-search').value = '';
  document.getElementById('db-search-clear').style.display = 'none';
  currentSearch = '';
  allStatsLoaded = false;
  loadLinks(1);
}

function setFilter(f) {
  currentFilter = f;
  allStatsLoaded = false;
  document.querySelectorAll('.db-filter-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('filter-' + f).classList.add('active');
  loadLinks(1);
}

// =====================================================
// BULK SHORTENING
// =====================================================

function toggleBulkPanel() {
  bulkPanelOpen = !bulkPanelOpen;
  const panel = document.getElementById('bulk-panel');
  const btn = document.getElementById('bulk-toggle-btn');
  panel.classList.toggle('open', bulkPanelOpen);
  btn.classList.toggle('active', bulkPanelOpen);
}

function setupBulkTextareaCounter() {
  const ta = document.getElementById('bulk-textarea');
  ta.addEventListener('input', () => updateBulkCount(ta.value));
}

function updateBulkCount(value) {
  const lines = value.split('\n').map(l => l.trim()).filter(Boolean);
  const info = document.getElementById('bulk-count-info');
  info.textContent = `${lines.length} URL${lines.length !== 1 ? 's' : ''} entered`;
  if (lines.length > 50) {
    info.style.color = '#f87171';
    info.textContent += ' (max 50)';
  } else {
    info.style.color = '';
  }
}

function handleCSVUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const text = e.target.result;
    const urls = text.split(/[\n,]/).map(l => l.trim()).filter(l => l.startsWith('http'));
    document.getElementById('bulk-textarea').value = urls.join('\n');
    updateBulkCount(urls.join('\n'));
  };
  reader.readAsText(file);
}

async function submitBulk() {
  const ta = document.getElementById('bulk-textarea');
  const rawLines = ta.value.split('\n').map(l => l.trim()).filter(Boolean);
  const urls = rawLines.slice(0, 50);

  if (urls.length === 0) {
    alert('Please enter at least one URL.');
    return;
  }

  const btn = document.getElementById('bulk-submit-btn');
  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Processing...';

  const resultsEl = document.getElementById('bulk-results');
  resultsEl.innerHTML = '<div class="bulk-loading">⏳ Shortening ' + urls.length + ' URLs...</div>';

  try {
    const payload = { urls: urls.map(u => ({ long_url: u })) };
    const res = await fetch(`${API_BASE}/shorten/bulk`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      resultsEl.innerHTML = `<div class="bulk-error">❌ ${data.detail || 'Bulk request failed.'}</div>`;
      return;
    }

    renderBulkResults(data);
    // Refresh table
    allStatsLoaded = false;
    loadLinks(1);
  } catch (err) {
    resultsEl.innerHTML = `<div class="bulk-error">❌ Server error: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Shorten All';
  }
}

function renderBulkResults(data) {
  const el = document.getElementById('bulk-results');
  const summary = `
    <div class="bulk-summary">
      <span class="bulk-badge-success">✅ ${data.succeeded} succeeded</span>
      <span class="bulk-badge-fail">❌ ${data.failed} failed</span>
      <span class="bulk-badge-total">Total: ${data.total}</span>
    </div>
  `;

  const rows = data.results.map((r, i) => {
    if (r.success) {
      return `
        <div class="bulk-result-row bulk-result-ok">
          <span class="bulk-result-idx">#${r.index + 1}</span>
          <a href="${r.data.short_url}" target="_blank" class="bulk-result-url">${r.data.short_url}</a>
          <span class="bulk-result-orig">${r.data.long_url.slice(0, 50)}${r.data.long_url.length > 50 ? '…' : ''}</span>
          <button class="icon-btn" onclick="copyToClipboard('${r.data.short_url}', this)" title="Copy">📋</button>
        </div>
      `;
    } else {
      return `
        <div class="bulk-result-row bulk-result-err">
          <span class="bulk-result-idx">#${r.index + 1}</span>
          <span class="bulk-result-error">❌ ${r.error}</span>
        </div>
      `;
    }
  }).join('');

  el.innerHTML = summary + `<div class="bulk-results-list">${rows}</div>`;
}

// =====================================================
// EDIT MODAL
// =====================================================

function openEditModal(link) {
  document.getElementById('edit-short-code').value = link.short_code;
  document.getElementById('edit-long-url').value = link.long_url;
  document.getElementById('edit-alias').value = '';
  document.getElementById('edit-expiry').value = link.expiry_date
    ? link.expiry_date.slice(0, 16)
    : '';
  document.getElementById('edit-error').textContent = '';
  document.getElementById('edit-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeEditModal(e) {
  if (e && e.target !== document.getElementById('edit-modal')) return;
  document.getElementById('edit-modal').classList.remove('open');
  document.body.style.overflow = '';
}

async function saveEdit() {
  const shortCode = document.getElementById('edit-short-code').value;
  const longUrl = document.getElementById('edit-long-url').value.trim();
  const alias = document.getElementById('edit-alias').value.trim();
  const expiry = document.getElementById('edit-expiry').value;
  const errEl = document.getElementById('edit-error');
  const btn = document.getElementById('edit-save-btn');

  errEl.textContent = '';

  if (!longUrl) { errEl.textContent = '⚠️ Destination URL is required.'; return; }

  const payload = { long_url: longUrl };
  if (alias) payload.custom_alias = alias;
  if (expiry) payload.expiry_date = new Date(expiry).toISOString();

  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Saving...';

  try {
    const res = await fetch(`${API_BASE}/links/${shortCode}`, {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      errEl.textContent = '❌ ' + (data.detail || 'Failed to update.');
      return;
    }
    document.getElementById('edit-modal').classList.remove('open');
    document.body.style.overflow = '';
    allStatsLoaded = false;
    loadLinks(currentPage);
  } catch (err) {
    errEl.textContent = '❌ Server error: ' + err.message;
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Save Changes';
  }
}

// =====================================================
// DELETE MODAL
// =====================================================

function openDeleteModal(shortCode) {
  deleteTarget = shortCode;
  document.getElementById('delete-code-display').textContent = shortCode;
  document.getElementById('delete-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeDeleteModal(e) {
  if (e && e.target !== document.getElementById('delete-modal')) return;
  document.getElementById('delete-modal').classList.remove('open');
  document.body.style.overflow = '';
}

async function confirmDelete() {
  if (!deleteTarget) return;
  const btn = document.getElementById('delete-confirm-btn');
  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Deleting...';

  try {
    const res = await fetch(`${API_BASE}/links/${deleteTarget}`, { 
      method: 'DELETE',
      headers: getAuthHeaders() 
    });
    if (!res.ok && res.status !== 204) {
      const data = await res.json();
      alert('Delete failed: ' + (data.detail || 'Unknown error'));
      return;
    }
    document.getElementById('delete-modal').classList.remove('open');
    document.body.style.overflow = '';
    deleteTarget = null;
    allStatsLoaded = false;
    loadLinks(currentPage > 1 && totalPages === currentPage ? currentPage - 1 : currentPage);
  } catch (err) {
    alert('Server error: ' + err.message);
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Delete';
  }
}

// =====================================================
// PREVIEW IMAGE MODAL
// =====================================================

function openPreviewModal(shortCode, previewUrl) {
  const img = document.getElementById('preview-img');
  const dlBtn = document.getElementById('preview-download-btn');
  img.src = previewUrl + '?t=' + Date.now();
  dlBtn.href = previewUrl;
  dlBtn.download = `preview-${shortCode}.png`;
  document.getElementById('preview-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closePreviewModal(e) {
  if (e && e.target !== document.getElementById('preview-modal')) return;
  document.getElementById('preview-modal').classList.remove('open');
  document.body.style.overflow = '';
}

// =====================================================
// QR CODE MODAL (inline, reuses preview modal)
// =====================================================

function openQRModal(qrUrl) {
  const img = document.getElementById('preview-img');
  const dlBtn = document.getElementById('preview-download-btn');
  img.src = qrUrl;
  dlBtn.href = qrUrl;
  dlBtn.download = 'qrcode.png';
  document.getElementById('preview-modal').querySelector('.modal-title').textContent = '📱 QR Code';
  document.getElementById('preview-modal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

// =====================================================
// ANALYTICS REDIRECT
// =====================================================

function goToAnalytics(shortCode) {
  window.location.href = `/#analytics-section?code=${shortCode}`;
}

// =====================================================
// UTILITIES
// =====================================================

async function copyToClipboard(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const orig = btn.textContent;
    btn.textContent = '✅';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  } catch {
    // fallback
  }
}

function showTableLoading(show) {
  document.getElementById('db-loading').style.display = show ? 'block' : 'none';
  document.getElementById('db-table').style.display = show ? 'none' : '';
  if (show) document.getElementById('db-empty').style.display = 'none';
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
    document.body.style.overflow = '';
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    e.preventDefault();
    document.getElementById('db-search').focus();
  }
});

// Navbar scroll
window.addEventListener('scroll', () => {
  const navbar = document.getElementById('navbar');
  if (navbar) {
    if (window.scrollY > 20) navbar.classList.add('scrolled');
    else navbar.classList.remove('scrolled');
  }
});
