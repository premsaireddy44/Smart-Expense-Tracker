'use strict';

/* =====================================================================
   common.js - small helpers shared by the login page and the dashboard
   ===================================================================== */

/* Change these two values to switch currency (for example GBP / en-GB). */
const CURRENCY = { locale: 'en-IN', code: 'INR' };

/* Your details for the footer and the privacy page. Change them in this one place. */
const SITE = {
  owner: 'Prem Sai Reddy',
  location: 'Hyderabad , India',
  contact: 'publicfixcomplaints@gmail.com',
};

const TOKEN_KEY = 'set_token';
const FLASH_KEY = 'set_flash';

/* ---------- Token storage ----------
   The JWT lives in sessionStorage: it survives a page refresh, but it is gone when the tab
   or the browser is closed. So opening the link in a new tab always starts at the login page.
   Every access is wrapped in try/catch because browsers can block storage. */
function getToken() {
  try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; }
}
function setToken(token) {
  try { sessionStorage.setItem(TOKEN_KEY, token); } catch { /* ignore */ }
}
function clearToken() {
  try { sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}
// Older versions kept the token in localStorage. Remove that old copy so nobody stays logged in.
try { localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
function setFlash(message) {
  try { sessionStorage.setItem(FLASH_KEY, message); } catch { /* ignore */ }
}
function takeFlash() {
  try {
    const message = sessionStorage.getItem(FLASH_KEY);
    sessionStorage.removeItem(FLASH_KEY);
    return message;
  } catch { return null; }
}

/* ---------- Talking to the backend ---------- */
class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

/* FastAPI sends errors as {"detail": "text"} or, for validation errors,
   {"detail": [{"msg": "..."}, ...]}. Turn either into one readable sentence. */
function formatDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => String(d.msg || 'Invalid value').replace(/^Value error, /, ''))
      .join('. ');
  }
  return 'Something went wrong. Please try again.';
}

async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  let data = null;
  try { data = await response.json(); } catch { /* empty body */ }

  // An expired or invalid token: clear it and send the user back to log in.
  if (response.status === 401 && auth) {
    clearToken();
    setFlash('Your session ended. Please log in again.');
    location.replace('/');
    throw new ApiError(401, 'Session ended');
  }
  if (!response.ok) throw new ApiError(response.status, formatDetail(data && data.detail));
  return data;
}

/* ---------- Money ---------- */
const wholeFmt = new Intl.NumberFormat(CURRENCY.locale, {
  style: 'currency', currency: CURRENCY.code, minimumFractionDigits: 0, maximumFractionDigits: 0,
});
const centsFmt = new Intl.NumberFormat(CURRENCY.locale, {
  style: 'currency', currency: CURRENCY.code, minimumFractionDigits: 2, maximumFractionDigits: 2,
});
/* 50000 -> "₹50,000"   250.5 -> "₹250.50" */
function money(n) {
  return (Number.isInteger(n) ? wholeFmt : centsFmt).format(n);
}
const currencySymbol = wholeFmt.formatToParts(0).find((p) => p.type === 'currency').value;

/* ---------- Tiny DOM helpers ----------
   Everything the user typed is put on the page with textContent (inside el()),
   never innerHTML, so a description like "<script>" can't run as code. */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2).toLowerCase(), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child !== null && child !== undefined && child !== false) node.append(child);
  }
  return node;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
function icon(name) {
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS(SVG_NS, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

/* ---------- Footer ----------
   Shows who runs the site, what it is, and where to ask for data deletion. */
function renderFooter() {
  const footer = document.querySelector('#site-footer');
  if (!footer) return;
  footer.replaceChildren(
    el('p', {
      text: `Smart Expense Tracker is a personal portfolio project by ${SITE.owner}, ${SITE.location}. `
        + 'It is not a registered business and does not give financial advice.',
    }),
    el('p', {},
      'Contact: ', el('a', { href: `mailto:${SITE.contact}`, text: SITE.contact }),
      ' · ', el('a', { href: 'privacy.html', text: 'Privacy and data deletion' })),
  );
}
renderFooter();