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
  const mainForm = document.getElementById('auth-form');
  const forgotPane = document.getElementById('auth-pane-forgot');
  const resetPane = document.getElementById('auth-pane-reset');

  // Reset displays
  tabsContainer.style.display = 'flex';
  mainForm.style.display = 'block';
  forgotPane.style.display = 'none';
  resetPane.style.display = 'none';

  if (tabName === 'login' || tabName === 'signup') {
    tabsContainer.setAttribute('data-active', tabName);
    document.querySelectorAll('.auth-pane').forEach(p => p.classList.remove('active'));
    document.getElementById(`auth-pane-${tabName}`).classList.add('active');
    
    const submitBtn = document.getElementById('auth-submit-btn');
    submitBtn.querySelector('.btn-text').textContent = tabName === 'login' ? 'Sign In' : 'Create Account';
    
    document.getElementById('auth-error-msg').textContent = '';
  } else if (tabName === 'forgot') {
    tabsContainer.style.display = 'none';
    mainForm.style.display = 'none';
    forgotPane.style.display = 'block';
    document.getElementById('forgot-error-msg').textContent = '';
  } else if (tabName === 'reset') {
    tabsContainer.style.display = 'none';
    mainForm.style.display = 'none';
    resetPane.style.display = 'block';
    document.getElementById('reset-error-msg').textContent = '';
  }
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
  const activeTab = tabsContainer.getAttribute('data-active'); 
  
  const email = document.getElementById('auth-email').value;
  const password = document.getElementById('auth-password').value;
  const errorEl = document.getElementById('auth-error-msg');
  const submitBtn = document.getElementById('auth-submit-btn');
  
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
    window.location.href = '/dashboard';
    
  } catch (err) {
    errorEl.textContent = 'Network error. Please try again.';
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector('.btn-text').textContent = activeTab === 'login' ? 'Sign In' : 'Create Account';
  }
}

async function handleForgotSubmit() {
  const email = document.getElementById('forgot-email').value;
  const errorEl = document.getElementById('forgot-error-msg');
  const btn = document.getElementById('forgot-submit-btn');

  if (!email) {
    errorEl.textContent = 'Email is required.';
    return;
  }

  errorEl.textContent = '';
  btn.disabled = true;
  btn.querySelector('.btn-text').textContent = 'Sending...';

  try {
    const res = await fetch(`${API_BASE_AUTH}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    
    if (res.ok) {
      // Switch to reset pane
      switchAuthTab('reset');
      // Pre-fill email hiddenly or globally if needed, for simplicity we ask for it again or handle globally
      window.recoveryEmail = email; 
    } else {
      errorEl.textContent = data.detail || 'Failed to send OTP.';
    }
  } catch (err) {
    errorEl.textContent = 'Network error.';
  } finally {
    btn.disabled = false;
    btn.querySelector('.btn-text').textContent = 'Send OTP';
  }
}

async function handleResetSubmit() {
  const otp = document.getElementById('reset-otp').value;
  const newPassword = document.getElementById('reset-new-password').value;
  const errorEl = document.getElementById('reset-error-msg');
  const btn = document.getElementById('reset-confirm-btn');

  if (!otp || !newPassword) {
    errorEl.textContent = 'Please fill all fields.';
    return;
  }

  errorEl.textContent = '';
  // Reuse button if we had one or just select it
  const submitBtn = document.getElementById('reset-submit-btn');
  submitBtn.disabled = true;
  submitBtn.querySelector('.btn-text').textContent = 'Updating...';

  try {
    const res = await fetch(`${API_BASE_AUTH}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        email: window.recoveryEmail, 
        otp_code: otp,
        new_password: newPassword 
      })
    });
    const data = await res.json();
    
    if (res.ok) {
      alert('Password updated successfully! Please login.');
      switchAuthTab('login');
    } else {
      errorEl.textContent = data.detail || 'Reset failed.';
    }
  } catch (err) {
    errorEl.textContent = 'Network error.';
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector('.btn-text').textContent = 'Update Password';
  }
}

// Add escape key listener to close modal
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeAuthModal();
});
