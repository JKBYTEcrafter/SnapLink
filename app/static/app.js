/* =====================================================
   SnapLink — Frontend Application Logic
   ===================================================== */

const API_BASE = 'http://localhost:8000';

let currentShortCode = null;
let currentQrUrl = null;

// ---- Navbar scroll effect ----
window.addEventListener('scroll', () => {
  const navbar = document.getElementById('navbar');
  if (window.scrollY > 20) navbar.classList.add('scrolled');
  else navbar.classList.remove('scrolled');
});

// ---- Auth Helpers ----
function getAuthHeaders() {
  const token = localStorage.getItem('snaplink_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

document.addEventListener('DOMContentLoaded', updateAuthUI);

function updateAuthUI() {
  const token = localStorage.getItem('snaplink_token');
  const authNav = document.getElementById('auth-nav');
  if (!authNav) return;
  if (token) {
    authNav.innerHTML = `
      <a href="/dashboard">Dashboard</a>
      <a href="#" onclick="logout(event)" style="color:#fca5a5;">Logout</a>
    `;
  } else {
    authNav.innerHTML = `
      <a href="#" class="nav-link" onclick="openAuthModal('login')">Login</a>
      <a href="#" class="nav-link" onclick="openAuthModal('signup')">Sign Up</a>
    `;
  }
}

function logout(e) {
  if (e) e.preventDefault();
  localStorage.removeItem('snaplink_token');
  window.location.reload();
}

// ---- Advanced Options Toggle ----
function toggleAdvanced() {
  const opts = document.getElementById('advanced-options');
  const arrow = document.getElementById('advanced-arrow');
  const isOpen = opts.classList.toggle('open');
  arrow.textContent = isOpen ? '▾' : '▸';
}

// ---- Shorten URL ----
async function shortenURL() {
  const longUrl = document.getElementById('long-url').value.trim();
  const customAlias = document.getElementById('custom-alias').value.trim();
  const expiryDate = document.getElementById('expiry-date').value;

  hideError();
  hideResult();

  if (!longUrl) {
    showError('⚠️ Please enter a URL to shorten.');
    return;
  }
  if (!isValidUrl(longUrl)) {
    showError('⚠️ Please enter a valid URL (including http:// or https://).');
    return;
  }

  showLoading(true);
  disableBtn(true);

  const payload = { long_url: longUrl };
  if (customAlias) payload.custom_alias = customAlias;
  if (expiryDate) payload.expiry_date = new Date(expiryDate).toISOString();

  try {
    const res = await fetch(`${API_BASE}/shorten`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || 'Something went wrong. Please try again.');
    }

    currentShortCode = data.short_code;
    currentQrUrl = data.qr_url;

    showResult(data);
  } catch (err) {
    showError('❌ ' + (err.message || 'Failed to connect to the server. Is Docker running?'));
  } finally {
    showLoading(false);
    disableBtn(false);
  }
}

// ---- Show / Hide Result ----
function showResult(data) {
  const card = document.getElementById('result-card');
  const shortUrlEl = document.getElementById('result-short-url');
  const originalUrlEl = document.getElementById('result-original-url');
  const timeEl = document.getElementById('result-time');

  shortUrlEl.href = data.short_url;
  shortUrlEl.textContent = data.short_url;
  originalUrlEl.textContent = data.long_url;
  timeEl.textContent = formatTime(data.created_at);

  // Attach QR & analytics button handlers
  document.getElementById('qr-btn').onclick = () => toggleQR(data.qr_url);
  document.getElementById('analytics-btn').onclick = () => {
    document.getElementById('analytics-code-input').value = data.short_code;
    document.getElementById('analytics-section').scrollIntoView({ behavior: 'smooth' });
    setTimeout(() => lookupAnalytics(), 500);
  };

  card.classList.add('show');
  closeQR();
}

function hideResult() {
  document.getElementById('result-card').classList.remove('show');
  closeQR();
}

// ---- Copy URL ----
async function copyURL() {
  const url = document.getElementById('result-short-url').href;
  const btn = document.getElementById('copy-btn');
  try {
    await navigator.clipboard.writeText(url);
    btn.innerHTML = '<span>✅</span> Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.innerHTML = '<span>📋</span> Copy';
      btn.classList.remove('copied');
    }, 2000);
  } catch {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = url;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.innerHTML = '<span>✅</span> Copied!';
    setTimeout(() => { btn.innerHTML = '<span>📋</span> Copy'; }, 2000);
  }
}

// ---- QR Code ----
function toggleQR(qrUrl) {
  const panel = document.getElementById('qr-panel');
  if (panel.classList.contains('show')) {
    closeQR();
    return;
  }
  const img = document.getElementById('qr-image');
  const dlBtn = document.getElementById('qr-download');
  img.src = qrUrl;
  dlBtn.href = qrUrl;
  panel.classList.add('show');
}

function closeQR() {
  document.getElementById('qr-panel').classList.remove('show');
}

// ---- Analytics Lookup ----
async function lookupAnalytics() {
  const code = document.getElementById('analytics-code-input').value.trim();
  const resultsEl = document.getElementById('analytics-results');

  if (!code) {
    alert('Please enter a short code to look up.');
    return;
  }

  resultsEl.classList.remove('show');

  try {
    const res = await fetch(`${API_BASE}/analytics/${code}`);
    const data = await res.json();

    if (!res.ok) {
      alert(data.detail || 'Short code not found.');
      return;
    }

    renderAnalytics(data);
    resultsEl.classList.add('show');
    resultsEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (err) {
    alert('Failed to fetch analytics. Is the server running?');
  }
}

function renderAnalytics(data) {
  // Summary stats
  document.getElementById('stat-total-clicks').textContent = data.total_clicks ?? 0;

  const countries = data.geo_breakdown ? Object.keys(data.geo_breakdown).length : 0;
  document.getElementById('stat-countries').textContent = countries;

  const topDevice = getTopKey(data.device_breakdown);
  document.getElementById('stat-top-device').textContent = capitalize(topDevice || '—');

  const topBrowser = getTopKey(data.browser_breakdown);
  document.getElementById('stat-top-browser').textContent = capitalize(topBrowser || '—');

  // Device Chart
  renderBarChart('device-chart', data.device_breakdown || {});

  // Browser Chart
  renderBarChart('browser-chart', data.browser_breakdown || {});

  // Recent clicks table
  renderClicksTable(data.recent_clicks || []);
}

function renderBarChart(containerId, breakdown) {
  const container = document.getElementById(containerId);
  container.innerHTML = '';

  const entries = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
  const max = entries[0]?.[1] || 1;

  if (entries.length === 0) {
    container.innerHTML = '<p style="color:var(--text-dim);font-size:13px;">No data yet</p>';
    return;
  }

  entries.forEach(([label, count]) => {
    const pct = Math.round((count / max) * 100);
    const item = document.createElement('div');
    item.className = 'bar-item';
    item.innerHTML = `
      <span class="bar-label">${capitalize(label)}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width: 0%" data-width="${pct}%"></div>
      </div>
      <span class="bar-count">${count}</span>
    `;
    container.appendChild(item);
  });

  // Animate bars
  requestAnimationFrame(() => {
    container.querySelectorAll('.bar-fill').forEach(bar => {
      bar.style.width = bar.dataset.width;
    });
  });
}

function renderClicksTable(clicks) {
  const tbody = document.getElementById('clicks-tbody');
  tbody.innerHTML = '';

  if (!clicks.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-dim);padding:20px;">No clicks recorded yet</td></tr>`;
    return;
  }

  clicks.forEach(click => {
    const tr = document.createElement('tr');
    const deviceClass = `chip-${(click.device_type || 'other').toLowerCase()}`;
    tr.innerHTML = `
      <td>${formatTime(click.clicked_at)}</td>
      <td><span class="device-chip ${deviceClass}">${capitalize(click.device_type || 'unknown')}</span></td>
      <td>${click.browser || '—'}</td>
      <td>${click.geo_country || '—'}</td>
      <td>${click.geo_city || '—'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---- Error Handling ----
function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.classList.add('show');
}
function hideError() {
  document.getElementById('error-msg').classList.remove('show');
}

// ---- Loading ----
function showLoading(show) {
  const el = document.getElementById('loading-overlay');
  if (show) el.classList.add('show');
  else el.classList.remove('show');
}

// ---- Disable Button ----
function disableBtn(disabled) {
  const btn = document.getElementById('shorten-btn');
  btn.disabled = disabled;
  btn.querySelector('.btn-text').textContent = disabled ? 'Creating...' : 'Shorten Now';
}

// ---- Enter key on URL input ----
document.getElementById('long-url').addEventListener('keydown', e => {
  if (e.key === 'Enter') shortenURL();
});
document.getElementById('analytics-code-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') lookupAnalytics();
});

// ---- Utility functions ----
function isValidUrl(str) {
  try {
    const url = new URL(str);
    return url.protocol === 'http:' || url.protocol === 'https:';
  } catch { return false; }
}

function formatTime(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return iso; }
}

function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function getTopKey(obj) {
  if (!obj) return null;
  const entries = Object.entries(obj).sort((a, b) => b[1] - a[1]);
  return entries[0]?.[0] || null;
}

// ---- Smooth scroll for nav links ----
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const target = document.querySelector(link.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  });
});

// ---- Animate feature cards on scroll (Intersection Observer) ----
const observerOpts = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
      observer.unobserve(entry.target);
    }
  });
}, observerOpts);

document.querySelectorAll('.feature-card, .step-card, .analytics-stat-card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(30px)';
  el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
  observer.observe(el);
});

// ---- Tab Switching (Single / Bulk) ----
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  document.getElementById('pane-' + tab).classList.add('active');
}

// ---- Bulk Shorten (Home page) ----
function updateBulkHomeCount() {
  const ta = document.getElementById('bulk-home-textarea');
  const lines = ta.value.split('\n').map(l => l.trim()).filter(Boolean);
  const el = document.getElementById('bulk-home-count');
  el.textContent = `${lines.length} URL${lines.length !== 1 ? 's' : ''}`;
  el.style.color = lines.length > 50 ? '#f87171' : '';
}

async function submitBulkHome() {
  const ta = document.getElementById('bulk-home-textarea');
  const rawLines = ta.value.split('\n').map(l => l.trim()).filter(Boolean);
  const urls = rawLines.slice(0, 50);
  const resultsEl = document.getElementById('bulk-home-results');
  const btn = document.getElementById('bulk-home-btn');

  if (urls.length === 0) {
    resultsEl.innerHTML = '<p style="color:#fca5a5;font-size:13px;">⚠️ Please enter at least one URL.</p>';
    return;
  }

  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Processing...';
  resultsEl.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">⏳ Shortening ' + urls.length + ' URLs...</p>';

  try {
    const payload = { urls: urls.map(u => ({ long_url: u })) };
    const res = await fetch(`${API_BASE}/shorten/bulk`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (!res.ok) {
      resultsEl.innerHTML = `<p style="color:#fca5a5;font-size:13px;">❌ ${data.detail || 'Request failed.'}</p>`;
      return;
    }

    renderBulkHomeResults(data);
  } catch (err) {
    resultsEl.innerHTML = `<p style="color:#fca5a5;font-size:13px;">❌ ${err.message}</p>`;
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Shorten All';
  }
}

function renderBulkHomeResults(data) {
  const el = document.getElementById('bulk-home-results');
  const summary = `
    <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap;">
      <span class="bulk-badge-success">✅ ${data.succeeded} succeeded</span>
      <span class="bulk-badge-fail">❌ ${data.failed} failed</span>
    </div>
  `;
  const rows = data.results.map(r => {
    if (r.success) {
      return `
        <div class="bulk-result-row bulk-result-ok">
          <span class="bulk-result-idx">#${r.index + 1}</span>
          <a href="${r.data.short_url}" target="_blank" class="bulk-result-url">${r.data.short_url}</a>
          <span class="bulk-result-orig">${r.data.long_url.length > 50 ? r.data.long_url.slice(0, 50) + '…' : r.data.long_url}</span>
          <button class="icon-btn" onclick="copyShortUrl('${r.data.short_url}', this)">📋</button>
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

async function copyShortUrl(url, btn) {
  try {
    await navigator.clipboard.writeText(url);
    const orig = btn.textContent;
    btn.textContent = '✅';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  } catch { /* ignore */ }
}
