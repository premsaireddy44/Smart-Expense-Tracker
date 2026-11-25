'use strict';

/* =====================================================================
   common.js - small tools used by every page
   1. Money   2. Login token   3. Talking to the API   4. Building HTML safely   5. Icons
   ===================================================================== */

const APP_VERSION = '2.1.0';

/* ---------- 1. Money ---------- */
// The currencies the app knows. The server has the same list (app/rates.py).
const CURRENCIES = {
  INR: { symbol: '\u20B9', name: 'Indian rupee' },
  GBP: { symbol: '\u00A3', name: 'British pound' },
  USD: { symbol: '$', name: 'US dollar' },
  EUR: { symbol: '\u20AC', name: 'Euro' },
};
let currentCurrency = 'INR';          // set from your profile when the app starts

function setCurrency(code) { if (CURRENCIES[code]) currentCurrency = code; }
function symbolOf(code) { return (CURRENCIES[code || currentCurrency] || CURRENCIES.INR).symbol; }

/* money(2500) -> "₹2,500".  money(40, 'GBP') -> "£40" */
function money(value, code) {
  const number = Number(value) || 0;
  const text = Math.abs(number).toLocaleString('en-GB', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  return `${number < 0 ? '\u2212' : ''}${symbolOf(code)}${text}`;
}

/* ---------- 2. Login token ----------
   sessionStorage forgets the token when the tab is closed, which is safer than localStorage. */
const TOKEN_KEY = 'expense_token';
function getToken() { try { return sessionStorage.getItem(TOKEN_KEY); } catch (e) { return null; } }
function setToken(token) { try { sessionStorage.setItem(TOKEN_KEY, token); } catch (e) { /* storage blocked */ } }
function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch (e) { /* ignore */ } }

/* A one-time message shown on the login page after logout or account deletion. */
function setFlash(message) { try { sessionStorage.setItem('expense_flash', message); } catch (e) { /* ignore */ } }
function takeFlash() {
  try {
    const message = sessionStorage.getItem('expense_flash');
    sessionStorage.removeItem('expense_flash');
    return message;
  } catch (e) { return null; }
}

/* ---------- 3. Talking to the API ----------
   api('/budgets')                       -> the JSON answer
   api('/budgets', {method:'POST', body:{...}})
   Failures throw an Error with a readable message and a .status number. */
async function api(path, { method = 'GET', body = null, auth = true } = {}) {
  const headers = {};
  if (body !== null) headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(path, { method, headers, body: body !== null ? JSON.stringify(body) : undefined });
  } catch (networkError) {
    const error = new Error('Cannot reach the server. Check that it is running, then try again.');
    error.status = 0;
    throw error;
  }

  if (response.status === 401 && auth) {
    clearToken();
    location.replace('/');
    const error = new Error('Please log in again.');
    error.status = 401;
    throw error;
  }

  let data = null;
  try { data = await response.json(); } catch (e) { /* empty answer */ }

  if (!response.ok) {
    const error = new Error(readableError(data, response.status));
    error.status = response.status;
    throw error;
  }
  return data;
}

function readableError(data, status) {
  if (data && typeof data.detail === 'string') return data.detail;
  if (data && Array.isArray(data.detail) && data.detail.length) {
    // FastAPI validation errors look like: "Value error, Password must be at least 8 characters"
    const first = data.detail[0];
    const field = first.loc ? first.loc[first.loc.length - 1] : '';
    const text = String(first.msg || 'Invalid value').replace(/^Value error, /, '');
    return field && field !== 'body' ? `${field}: ${text}` : text;
  }
  return `Something went wrong (error ${status}).`;
}

/* ---------- 4. Building HTML safely ----------
   el('li', {class:'x', text:'hello'}, child1, child2)
   Text goes in with textContent, never innerHTML, so a description like
   "<script>" is shown as plain text and can never run. */
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'text') node.textContent = value;
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child);
  }
  return node;
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

/* ---------- 5. Icons (tiny inline SVG, no files to download) ---------- */
const ICON_PATHS = {
  pencil: 'M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z',
  trash: 'M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6',
  warning: 'M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  info: 'M12 16v-4M12 8h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  check: 'M20 6 9 17l-5-5',
  plus: 'M12 5v14M5 12h14',
};

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '22');
  svg.setAttribute('height', '22');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('stroke', 'currentColor');
  svg.setAttribute('stroke-width', '2.25');
  svg.setAttribute('stroke-linecap', 'round');
  svg.setAttribute('stroke-linejoin', 'round');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', ICON_PATHS[name] || '');
  svg.append(path);
  return svg;
}