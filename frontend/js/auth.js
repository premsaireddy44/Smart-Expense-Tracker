'use strict';

/* auth.js - the login / create-account page */

// Already logged in? Go straight to the app. (The app checks the token again.)
if (getToken()) location.replace('/app.html');

const tabs = { login: $('#tab-login'), register: $('#tab-register') };
const panels = { login: $('#panel-login'), register: $('#panel-register') };

function showTab(name) {
  for (const key of Object.keys(tabs)) {
    const active = key === name;
    tabs[key].setAttribute('aria-selected', String(active));
    tabs[key].tabIndex = active ? 0 : -1;
    panels[key].hidden = !active;
  }
}

Object.entries(tabs).forEach(([name, button]) => {
  button.addEventListener('click', () => showTab(name));
  // Arrow keys move between the two tabs, like a normal tab control.
  button.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      const other = name === 'login' ? 'register' : 'login';
      showTab(other);
      tabs[other].focus();
    }
  });
});

const flash = takeFlash();
if (flash) {
  $('#flash').textContent = flash;
  $('#flash').hidden = false;
}

function markInvalid(input, bad) { input.toggleAttribute('aria-invalid', bad); }

async function logIn(email, password) {
  const result = await api('/login', { method: 'POST', body: { email, password }, auth: false });
  setToken(result.access_token);
  location.replace('/app.html');
}

panels.login.addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = $('#login-email');
  const password = $('#login-password');
  const error = $('#login-error');
  error.textContent = '';
  markInvalid(email, !email.value.trim());
  markInvalid(password, !password.value);
  if (!email.value.trim() || !password.value) {
    error.textContent = 'Enter your email and password.';
    (email.value.trim() ? password : email).focus();
    return;
  }
  const button = $('#login-submit');
  button.disabled = true;
  try {
    await logIn(email.value.trim(), password.value);
  } catch (err) {
    error.textContent = err.message;      // includes "Too many wrong passwords..." after 5 failures
    button.disabled = false;
  }
});

panels.register.addEventListener('submit', async (event) => {
  event.preventDefault();
  const email = $('#reg-email');
  const password = $('#reg-password');
  const age = $('#reg-age');
  const error = $('#reg-error');
  error.textContent = '';
  $('#reg-exists').hidden = true;

  markInvalid(email, !email.value.trim());
  markInvalid(password, password.value.length < 8);
  markInvalid(age, !age.checked);
  if (!email.value.trim()) { error.textContent = 'Enter your email.'; email.focus(); return; }
  if (password.value.length < 8) { error.textContent = 'Your password needs at least 8 characters.'; password.focus(); return; }
  if (!age.checked) { error.textContent = 'Please confirm the box about age and privacy.'; age.focus(); return; }

  const button = $('#reg-submit');
  button.disabled = true;
  try {
    await api('/register', { method: 'POST', body: { email: email.value.trim(), password: password.value, currency: $('#reg-currency').value }, auth: false });
    await logIn(email.value.trim(), password.value);
  } catch (err) {
    if (err.message === 'Email already registered') {
      $('#reg-exists').hidden = false;
    } else {
      error.textContent = err.message;
    }
    button.disabled = false;
  }
});

$('#reg-go-login').addEventListener('click', () => {
  $('#login-email').value = $('#reg-email').value;
  showTab('login');
  $('#login-password').focus();
});