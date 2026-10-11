'use strict';

/* =====================================================================
   auth.js - the log in / create account page
   ===================================================================== */

// Already logged in? Go straight to the dashboard.
if (getToken()) location.replace('/app.html');

let mode = 'login'; // or 'register'

const form = document.querySelector('#auth-form');
const emailInput = document.querySelector('#email');
const passwordInput = document.querySelector('#password');
const errorBox = document.querySelector('#auth-error');
const submitButton = document.querySelector('#auth-submit');

// A message left by api() when a session expired.
const flash = takeFlash();
if (flash) {
  const notice = document.querySelector('#notice');
  notice.textContent = flash;
  notice.hidden = false;
}

function setMode(next) {
  mode = next;
  const isRegister = next === 'register';
  document.querySelector('#auth-title').textContent = isRegister ? 'Create your account' : 'Log in';
  submitButton.textContent = isRegister ? 'Create account' : 'Log in';
  document.querySelector('#mode-login').setAttribute('aria-pressed', String(!isRegister));
  document.querySelector('#mode-register').setAttribute('aria-pressed', String(isRegister));
  document.querySelector('#pw-hint').hidden = !isRegister;
  passwordInput.autocomplete = isRegister ? 'new-password' : 'current-password';
  errorBox.textContent = '';
}

document.querySelector('#mode-login').addEventListener('click', () => setMode('login'));
document.querySelector('#mode-register').addEventListener('click', () => setMode('register'));

document.querySelector('#pw-toggle').addEventListener('click', (event) => {
  const show = passwordInput.type === 'password';
  passwordInput.type = show ? 'text' : 'password';
  event.currentTarget.textContent = show ? 'Hide' : 'Show';
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.textContent = '';

  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    errorBox.textContent = 'Enter your email and password.';
    return;
  }
  if (mode === 'register' && password.length < 8) {
    errorBox.textContent = 'Use at least 8 characters for your password.';
    return;
  }

  submitButton.disabled = true;
  try {
    if (mode === 'register') {
      await api('/register', { method: 'POST', body: { email, password }, auth: false });
    }
    // Registering does not log you in, so we log in right after.
    const data = await api('/login', { method: 'POST', body: { email, password }, auth: false });
    setToken(data.access_token);
    location.href = '/app.html';
  } catch (error) {
    errorBox.textContent = error.message;
    submitButton.disabled = false;
  }
});