const API_BASE_AUTH = window.location.origin;

function openAuthModal(targetTab = 'login') {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
  switchAuthTab(targetTab);
  
  // Clear previous errors/inputs
  document.getElementById('auth-error-msg').textContent = '';
  document.getElementById('auth-email').value = '';
  document.getElementById('auth-password').value = '';
}

function closeAuthModal(e) {
  const modal = document.getElementById('auth-modal');
  if (e && e.target !== modal && !e.target.closest('.modal-close')) return;
  modal.classList.remove('open');
  document.body.style.overflow = '';
}

function switchAuthTab(tabName) {
  const tabsContainer = document.getElementById('auth-tabs-container');
  tabsContainer.setAttribute('data-active', tabName);
  
  document.querySelectorAll('.auth-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(`auth-pane-${tabName}`).classList.add('active');
  
  const submitBtn = document.getElementById('auth-submit-btn');
  submitBtn.querySelector('.btn-text').textContent = tabName === 'login' ? 'Sign In' : 'Create Account';
  
  document.getElementById('auth-error-msg').textContent = '';
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🔒';
    btn.title = 'Hide password';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
    btn.title = 'Show password';
  }
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const tabsContainer = document.getElementById('auth-tabs-container');
  const activeTab = tabsContainer.getAttribute('data-active'); // 'login' or 'signup'
  
  const email = document.getElementById('auth-email').value;
  const password = document.getElementById('auth-password').value;
  const errorEl = document.getElementById('auth-error-msg');
  const submitBtn = document.getElementById('auth-submit-btn');
  
  if (activeTab === 'signup' && password.length < 8) {
    errorEl.textContent = 'Password must be at least 8 characters.';
    return;
  }
  
  errorEl.textContent = '';
  submitBtn.disabled = true;
  submitBtn.querySelector('.btn-text').textContent = 'Processing...';

  try {
    const endpoint = activeTab === 'login' ? '/auth/login' : '/auth/signup';
    let res = await fetch(`${API_BASE_AUTH}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    let data = await res.json();

    if (!res.ok) {
        errorEl.textContent = data.detail || 'Authentication failed.';
        return;
    }

    if (activeTab === 'signup') {
        // Auto-login after successful signup
        res = await fetch(`${API_BASE_AUTH}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        data = await res.json();
        if (!res.ok) {
            errorEl.textContent = 'Account created, but auto-login failed. Please sign in.';
            switchAuthTab('login');
            return;
        }
    }

    // Success login/auto-login
    localStorage.setItem('snaplink_token', data.access_token);
    
    // Redirect to dashboard or reload if already on dashboard
    if (window.location.pathname === '/' || window.location.pathname === '') {
        window.location.href = '/dashboard';
    } else {
        window.location.reload();
    }
    
  } catch (err) {
    errorEl.textContent = 'Network error. Please try again.';
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector('.btn-text').textContent = activeTab === 'login' ? 'Sign In' : 'Create Account';
  }
}

// Add escape key listener to close modal
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeAuthModal();
});
