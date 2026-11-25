'use strict';

/* =====================================================================
   app.js - starts the app and connects the tabs. Loaded LAST.
   Sections: 1. Guard  2. State  3. Small helpers  4. Tabs  5. Loading data  6. Start-up
   ===================================================================== */

/* ---------- 1. Guard: no token, no app ---------- */
if (typeof getToken === 'function' && !getToken()) location.replace('/');

/* Self-check: if a file is missing or is an old copy, say so in plain words instead of showing a broken page. */
const REQUIRED_FUNCTIONS = ['api', 'money', 'el', 'drawMonthsChart', 'renderStats', 'loadAnalytics',
  'loadTransactions', 'openTxDialog', 'renderBudgets', 'openBudgetDialog', 'bindPlanEvents',
  'applyProfile', 'fillSelect', 'bindCurrencyEvents'];
function missingFunctions() {
  return REQUIRED_FUNCTIONS.filter((name) => { try { return typeof eval(name) !== 'function'; } catch (e) { return true; } });
}

// After logging out, the Back button can show a saved copy of this page. Check again.
window.addEventListener('pageshow', (event) => {
  if (event.persisted && !getToken()) location.replace('/');
});

/* ---------- 2. State: everything the page needs to remember ---------- */
const state = {
  year: 0,
  month: 0,              // 1-12, the month being viewed
  categories: [],        // [{id, name, kind}]
  byName: new Map(),     // "food" -> category
  byId: new Map(),       // 3 -> category
  budgets: [],
  summary: null,
  analytics: null,
  transactions: [],
  filter: 'all',         // all | expense | income
  hasMore: false,
  tab: 'overview',
  me: null,              // your profile (email, currencies)
};

/* ---------- 3. Small helpers ---------- */
function toDateInput(date) {
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const dd = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${mm}-${dd}`;
}

function monthLabel(year, month) {
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
}

function isCurrentMonth() {
  const now = new Date();
  return state.year === now.getFullYear() && state.month === now.getMonth() + 1;
}

function showBanner(message) { $('#banner-text').textContent = message; $('#banner').hidden = false; }
function hideBanner() { $('#banner').hidden = true; }

let toastTimer = null;
function toast(message) {
  const box = $('#toast');
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 3000);
}

/* Ask "are you sure?" and wait for the answer (true / false). */
function confirmDialog(title, text, yesLabel) {
  const dialog = $('#confirm-dialog');
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  $('#confirm-yes').textContent = yesLabel;
  dialog.returnValue = '';
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), { once: true });
    dialog.showModal();
  });
}

/* ---------- 4. Tabs ---------- */
const TAB_NAMES = ['overview', 'analytics', 'transactions', 'plan', 'account'];
const TABS_WITH_MONTH = ['overview', 'transactions'];

function showTab(name, { focus = false } = {}) {
  if (!TAB_NAMES.includes(name)) name = 'overview';
  state.tab = name;
  TAB_NAMES.forEach((tab) => {
    const button = $(`#t-${tab}`);
    const active = tab === name;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
    $(`#p-${tab}`).hidden = !active;
  });
  $('#month-bar').hidden = !TABS_WITH_MONTH.includes(name);
  if (location.hash !== `#${name}`) history.replaceState(null, '', `#${name}`);
  if (focus) $(`#t-${name}`).focus();

  if (name === 'analytics') {
    loadAnalytics().catch((e) => { if (e.status !== 401) showBanner(e.message); });
  }
}

function bindTabEvents() {
  TAB_NAMES.forEach((name, index) => {
    const button = $(`#t-${name}`);
    button.addEventListener('click', () => showTab(name));
    button.addEventListener('keydown', (event) => {     // arrow keys, Home and End move between tabs
      let target = null;
      if (event.key === 'ArrowRight') target = TAB_NAMES[(index + 1) % TAB_NAMES.length];
      if (event.key === 'ArrowLeft') target = TAB_NAMES[(index + TAB_NAMES.length - 1) % TAB_NAMES.length];
      if (event.key === 'Home') target = TAB_NAMES[0];
      if (event.key === 'End') target = TAB_NAMES[TAB_NAMES.length - 1];
      if (target) { event.preventDefault(); showTab(target, { focus: true }); }
    });
  });
  window.addEventListener('hashchange', () => showTab(location.hash.slice(1)));
}

/* ---------- 5. Loading data ---------- */
async function refreshAll() {
  const period = `year=${state.year}&month=${state.month}`;
  try {
    const [summary, budgets, trend] = await Promise.all([
      api(`/summary?${period}`),
      api('/budgets'),
      api('/trend?months=6'),
    ]);
    state.summary = summary;
    state.budgets = budgets;

    $('#month-title').textContent = monthLabel(state.year, state.month);
    $('#month-next').disabled = isCurrentMonth();
    renderStats();
    renderGoal();
    renderAlerts();
    renderCategories();
    renderBudgets();
    renderTrend(trend);
    await loadTransactions(true);
    if (state.tab === 'analytics') await loadAnalytics();
    if (state.categories.length) hideBanner();
  } catch (error) {
    if (error.status !== 401) showBanner(error.message);
  }
}

/* ---------- 6. Start-up ---------- */
function bindEvents() {
  $('#logout').addEventListener('click', () => { clearToken(); location.replace('/'); });
  $('#banner-retry').addEventListener('click', () => location.reload());

  $('#month-prev').addEventListener('click', () => {
    state.month -= 1;
    if (state.month === 0) { state.month = 12; state.year -= 1; }
    refreshAll();
  });
  $('#month-next').addEventListener('click', () => {
    if (isCurrentMonth()) return;
    state.month += 1;
    if (state.month === 13) { state.month = 1; state.year += 1; }
    refreshAll();
  });

  bindTabEvents();
  bindTransactionEvents();
  bindPlanEvents();
  bindAnalyticsEvents();
  bindCurrencyEvents();

  // Clicking the dark area outside a dialog closes it.
  $$('dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  });
}

async function init() {
  const missing = missingFunctions();
  if (missing.length) {
    showBanner(`Some project files are old or missing (${missing.join(', ')}). Copy ALL files from the latest delivery into frontend/js, then press Ctrl+Shift+R.`);
    return;
  }
  const now = new Date();
  state.year = now.getFullYear();
  state.month = now.getMonth() + 1;

  bindEvents();
  $('#tx-date').max = toDateInput(now);

  $('#version').textContent = `v${APP_VERSION}`;
  try {
    const [me, categories] = await Promise.all([api('/me'), api('/categories')]);
    $('#user-email').textContent = me.email;
    $('#account-email').textContent = me.email;
    if (!categories.length) {
      showBanner('No categories found in the database. Stop the server, run: python seed_categories.py   then start it again.');
    }
    applyProfile(me);
    state.categories = categories;
    state.byName = new Map(categories.map((c) => [c.name.toLowerCase(), c]));
    state.byId = new Map(categories.map((c) => [c.id, c]));
    showTab(location.hash.slice(1) || 'overview');
    await refreshAll();
  } catch (error) {
    showTab(location.hash.slice(1) || 'overview');
    if (error.status !== 401) showBanner(error.message);
  }
}

init();