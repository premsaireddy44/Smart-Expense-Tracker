'use strict';

/* =====================================================================
   app.js - the dashboard
   Sections:  1. State          5. Alerts, stats, savings goal, categories, chart
              2. Start-up       6. Transactions and budgets lists
              3. Loading data   7. Add / edit transaction dialog
              4. Small helpers  8. Budget and goal dialogs, delete account, quick add, wiring
   ===================================================================== */

if (!getToken()) location.replace('/');

// Back button after logging out can show a saved copy of this page. Check again.
window.addEventListener('pageshow', (event) => {
  if (event.persisted && !getToken()) location.replace('/');
});

const PAGE_SIZE = 20;
const $ = (selector) => document.querySelector(selector);

/* ---------- 1. State: everything the page needs to remember ---------- */
const state = {
  year: 0,
  month: 0,              // 1-12, the month being viewed
  categories: [],        // [{id, name, kind}]
  byName: new Map(),     // "food" -> category
  byId: new Map(),       // 3 -> category
  budgets: [],
  summary: null,
  transactions: [],
  filter: 'all',         // all | expense | income
  hasMore: false,
};

/* ---------- 2. Start-up ---------- */
async function init() {
  const now = new Date();
  state.year = now.getFullYear();
  state.month = now.getMonth() + 1;

  bindEvents();
  $('#tx-currency').textContent = currencySymbol;
  $('#tx-date').max = toDateInput(new Date());

  try {
    const [me, categories] = await Promise.all([api('/me'), api('/categories')]);
    $('#user-email').textContent = me.email;
    state.categories = categories;
    state.byName = new Map(categories.map((c) => [c.name.toLowerCase(), c]));
    state.byId = new Map(categories.map((c) => [c.id, c]));
    await refreshAll();
  } catch (error) {
    if (error.status !== 401) showBanner(error.message);
  }
}

/* ---------- 3. Loading data from the API ---------- */
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

    renderMonth();
    renderStats();
    renderGoal();
    renderAlerts();
    renderCategories();
    renderBudgets();
    renderTrend(trend);
    await loadTransactions(true);
    hideBanner();
  } catch (error) {
    if (error.status !== 401) showBanner(error.message);
  }
}

async function loadTransactions(reset) {
  const skip = reset ? 0 : state.transactions.length;
  const typeQuery = state.filter === 'all' ? '' : `&type=${state.filter}`;
  const rows = await api(
    `/transactions?year=${state.year}&month=${state.month}${typeQuery}&skip=${skip}&limit=${PAGE_SIZE}`,
  );
  state.transactions = reset ? rows : state.transactions.concat(rows);
  state.hasMore = rows.length === PAGE_SIZE;
  renderTransactions();
}

/* ---------- 4. Small helpers ---------- */
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

function showBanner(message) {
  $('#banner-text').textContent = message;
  $('#banner').hidden = false;
}
function hideBanner() { $('#banner').hidden = true; }

let toastTimer = null;
function toast(message) {
  const box = $('#toast');
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 3000);
}

/* Fill a <datalist> so the category box offers a search-as-you-type list. */
function fillCategoryList(datalist, categories) {
  datalist.replaceChildren(...categories.map((c) => el('option', { value: c.name })));
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

/* ---------- 5. Alerts, stats, categories, chart ---------- */
function renderMonth() {
  $('#month-title').textContent = monthLabel(state.year, state.month);
  $('#month-next').disabled = isCurrentMonth();
}

function renderStats() {
  const s = state.summary;
  $('#stat-income').textContent = money(s.total_income);
  $('#stat-spent').textContent = money(s.total_expense);

  const saved = $('#stat-saved');
  saved.textContent = money(s.savings);
  saved.classList.toggle('is-negative', s.savings < 0);

  let note = 'Add income to see how much you keep.';
  if (s.total_income > 0) {
    note = s.savings >= 0
      ? `${s.savings_rate_percent}% of your income`
      : 'You spent more than you earned';
  }
  $('#stat-note').textContent = note;
}

function renderGoal() {
  const goal = state.summary.savings_goal;
  const body = $('#goal-body');
  $('#goal-edit').textContent = goal ? 'Change goal' : 'Set a goal';

  if (!goal) {
    body.replaceChildren(el('p', { class: 'empty', text: 'No savings goal yet. Choose how much of your income you want to keep, and we will warn you when your spending puts it at risk.' }));
    return;
  }
  if (goal.status === 'no_income') {
    body.replaceChildren(el('p', { class: 'empty', text: `Your goal is to keep ${goal.ratio_percent}% of your income. Add this month's income to see how you are doing.` }));
    return;
  }

  const usedPercent = goal.max_spend > 0 ? Math.min(100, (goal.spent / goal.max_spend) * 100) : 100;
  const left = goal.left_to_spend;
  const spendLine = left >= 0
    ? `You can spend ${money(goal.max_spend)} this month. You have spent ${money(goal.spent)}, so ${money(left)} is left.`
    : `You can spend ${money(goal.max_spend)} this month. You have spent ${money(goal.spent)}, which is ${money(-left)} too much.`;

  const lines = [
    el('div', { class: 'goal-line', text: `Keep ${goal.ratio_percent}% of your income (${money(goal.goal_amount)})` }),
    el('div', { class: `goal-bar goal-${goal.status}`, role: 'img', 'aria-label': `${Math.round(usedPercent)}% of the money you can spend is used` },
      el('div', { class: 'goal-fill', style: `width:${usedPercent}%` })),
    el('div', { class: 'goal-meta', text: spendLine }),
  ];
  if (goal.projected_spend !== null && goal.projected_spend !== undefined) {
    lines.push(el('div', { class: 'goal-meta', text: `At this pace you will spend about ${money(Math.round(goal.projected_spend))} by the end of the month.` }));
  }
  body.replaceChildren(...lines);
}

function renderAlerts() {
  const list = $('#alerts');
  const alerts = state.summary.alerts;
  const rows = alerts.map((a) => {
    const iconName = a.level === 'info' ? 'info' : 'warning';
    return el('li', { class: `alert alert-${a.level}` }, icon(iconName), el('span', { text: a.message }));
  });

  if (!rows.length) {
    if (state.budgets.length || state.summary.savings_goal) {
      rows.push(el('li', { class: 'alert alert-ok' }, icon('check'), el('span', { text: 'You are on track this month.' })));
    } else {
      rows.push(el('li', { class: 'alert alert-info' }, icon('info'), el('span', { text: 'Set a budget or a savings goal and we will warn you before you overspend.' })));
    }
  }
  list.replaceChildren(...rows);
}

const STATUS_TEXT = { over: 'Over budget', warning: 'Close to budget', ok: 'On track' };

function renderCategories() {
  const s = state.summary;
  const list = $('#cats');
  const empty = $('#cats-empty');

  if (!s.categories.length) {
    list.replaceChildren();
    empty.textContent = `No spending recorded in ${monthLabel(state.year, state.month)} yet.`;
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  // Bars show "% of income" so they line up with budgets. With no income yet,
  // fall back to each category's share of total spending.
  const hasIncome = s.total_income > 0;
  const values = s.categories.map((c) => (hasIncome ? c.percent_of_income : (c.amount / s.total_expense) * 100));
  const ratios = hasIncome ? s.categories.map((c) => c.budget_ratio || 0) : [];
  const scale = Math.max(...values, ...ratios, 1) * 1.1;

  list.replaceChildren(...s.categories.map((c, i) => {
    const fill = el('div', { class: 'bar-fill', style: `width:${Math.min(100, (values[i] / scale) * 100)}%` });
    const bar = el('div', { class: 'bar' }, fill);
    if (hasIncome && c.budget_ratio) {
      bar.append(el('div', { class: 'bar-tick', style: `left:${(c.budget_ratio / scale) * 100}%` }));
    }

    const parts = [hasIncome ? `${c.percent_of_income}% of income` : `${Math.round(values[i])}% of spending`];
    if (c.budget_ratio) parts.push(`budget ${c.budget_ratio}%`);
    if (c.category === 'Uncategorized') parts.push('needs a category');
    const meta = el('div', { class: 'cat-meta' }, parts.join(' · '));
    if (STATUS_TEXT[c.status]) meta.append(' · ', el('span', { class: 'flag', text: STATUS_TEXT[c.status] }));

    return el('li', { class: `cat is-${c.status}` },
      el('div', { class: 'cat-head' }, el('span', { text: c.category }), el('span', { class: 'num', text: money(c.amount) })),
      bar,
      meta);
  }));
}

/* The 6-month chart is drawn with plain HTML boxes: each bar is a <div> whose height is
   its share of the tallest value. No chart library is needed. */
function renderTrend(points) {
  const box = $('#trend-chart');
  const hasData = points.some((p) => p.income || p.expense);
  $('#trend-empty').hidden = hasData;
  box.hidden = !hasData;
  $('#trend-scale').textContent = '';
  if (!hasData) {
    box.replaceChildren();
    return;
  }

  const tallest = Math.max(...points.flatMap((p) => [p.income, p.expense]));
  $('#trend-scale').textContent = `Tallest bar: ${money(tallest)}`;
  box.style.gridTemplateColumns = `repeat(${points.length}, 1fr)`;

  const columns = points.map((p) => {
    const [year, month] = p.month.split('-').map(Number);
    const shortName = new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'short' });
    const summary = `${monthLabel(year, month)}: income ${money(p.income)}, spent ${money(p.expense)}`;

    const incomeBar = el('div', { class: 'trend-bar trend-income', style: `height:${(p.income / tallest) * 100}%` });
    const spentBar = el('div', { class: 'trend-bar trend-spent', style: `height:${(p.expense / tallest) * 100}%` });

    return el('div', { class: 'trend-col', title: summary, 'aria-label': summary },
      el('div', { class: 'trend-bars' }, incomeBar, spentBar),
      el('div', { class: 'trend-label', text: shortName }));
  });
  box.replaceChildren(...columns);
}

/* ---------- 6. Transactions and budgets lists ---------- */
function renderTransactions() {
  const list = $('#txs');
  const empty = $('#txs-empty');

  if (!state.transactions.length) {
    list.replaceChildren();
    const what = state.filter === 'all' ? 'transactions' : `${state.filter === 'income' ? 'income' : 'expenses'}`;
    empty.textContent = `No ${what} in ${monthLabel(state.year, state.month)}. Use the buttons above to add one.`;
    empty.hidden = false;
    $('#tx-more').hidden = true;
    return;
  }
  empty.hidden = true;

  list.replaceChildren(...state.transactions.map((t) => {
    const category = state.byId.get(t.category_id);
    const when = new Date(t.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    const sign = t.type === 'income' ? '+' : '−';

    return el('li', { class: 'tx' },
      el('span', { class: 'tx-date', text: when }),
      el('div', {},
        el('div', { class: 'tx-desc', text: t.description }),
        el('span', { class: category ? 'pill' : 'pill pill-none', text: category ? category.name : 'Uncategorized' })),
      el('span', { class: `tx-amt num is-${t.type}`, text: `${sign}${money(t.amount)}` }),
      el('div', { class: 'tx-actions' },
        el('button', { class: 'icon-btn', type: 'button', 'aria-label': `Edit ${t.description}`, onclick: () => openTxDialog({ mode: 'edit', tx: t }) }, icon('pencil')),
        el('button', { class: 'icon-btn danger', type: 'button', 'aria-label': `Delete ${t.description}`, onclick: () => deleteTransaction(t) }, icon('trash'))));
  }));

  $('#tx-more').hidden = !state.hasMore;
}

async function deleteTransaction(t) {
  const ok = await confirmDialog('Delete this transaction?', `${t.description} (${money(t.amount)}) will be removed for good.`, 'Delete');
  if (!ok) return;
  try {
    await api(`/transactions/${t.id}`, { method: 'DELETE' });
    toast('Transaction deleted');
    await refreshAll();
  } catch (error) {
    if (error.status !== 401) toast(error.message);
  }
}

function renderBudgets() {
  const list = $('#budgets');
  const empty = $('#budgets-empty');
  empty.hidden = state.budgets.length > 0;

  const income = state.summary.total_income;
  const spentByName = new Map(state.summary.categories.map((c) => [c.category, c.amount]));

  const rows = state.budgets
    .map((b) => ({ b, name: (state.byId.get(b.category_id) || { name: 'Unknown' }).name }))
    .sort((x, y) => x.name.localeCompare(y.name))
    .map(({ b, name }) => {
      let meta = `${b.ratio_percent}% of income`;
      if (income > 0) {
        const limit = (income * b.ratio_percent) / 100;
        meta = `${b.ratio_percent}% of income · spent ${money(spentByName.get(name) || 0)} of ${money(limit)}`;
      }
      return el('li', { class: 'budget' },
        el('span', { class: 'budget-name', text: name }),
        el('span', { class: 'budget-meta', text: meta }),
        el('div', { class: 'budget-actions' },
          el('button', { class: 'icon-btn', type: 'button', 'aria-label': `Edit ${name} budget`, onclick: () => openBudgetDialog(b) }, icon('pencil')),
          el('button', { class: 'icon-btn danger', type: 'button', 'aria-label': `Delete ${name} budget`, onclick: () => deleteBudget(b, name) }, icon('trash'))));
    });
  list.replaceChildren(...rows);
}

async function deleteBudget(b, name) {
  const ok = await confirmDialog('Delete this budget?', `Your ${b.ratio_percent}% budget for ${name} will be removed.`, 'Delete');
  if (!ok) return;
  try {
    await api(`/budgets/${b.id}`, { method: 'DELETE' });
    toast('Budget deleted');
    await refreshAll();
  } catch (error) {
    if (error.status !== 401) toast(error.message);
  }
}

/* ---------- 7. Add / edit transaction dialog ---------- */
const txDialog = {
  mode: 'add',
  editing: null,         // the transaction being edited
  type: 'expense',
  catTouched: false,     // true once the user picks a category themselves
  originalDate: '',
  suggestSeq: 0,         // guards against slow, out-of-order suggestion replies
  suggestTimer: null,
};

function setTxType(type) {
  txDialog.type = type;
  document.querySelectorAll('#tx-dialog [data-type]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.type === type)));

  if (txDialog.mode === 'add') {
    $('#tx-title').textContent = type === 'income' ? 'Add income' : 'Add expense';
    $('#tx-save').textContent = type === 'income' ? 'Save income' : 'Save expense';
  }

  // Only offer categories that make sense: salary is not an expense.
  fillCategoryList($('#cat-list'), state.categories.filter((c) => c.kind === type));

  // A category chosen for the other type no longer fits.
  const current = state.byName.get($('#tx-cat').value.trim().toLowerCase());
  if (current && current.kind !== type) {
    $('#tx-cat').value = '';
    txDialog.catTouched = false;
  }
  requestSuggestion();
}

function openTxDialog({ mode, type = 'expense', tx = null, prefill = null }) {
  txDialog.mode = mode;
  txDialog.editing = tx;
  txDialog.catTouched = false;
  $('#tx-error').textContent = '';
  $('#tx-cat-note').textContent = '';
  $('#tx-cat-note').className = 'note';
  ['#tx-desc', '#tx-amount', '#tx-cat'].forEach((id) => $(id).removeAttribute('aria-invalid'));

  if (mode === 'edit') {
    $('#tx-title').textContent = 'Edit transaction';
    $('#tx-save').textContent = 'Save changes';
    $('#tx-desc').value = tx.description;
    $('#tx-amount').value = tx.amount;
    const category = state.byId.get(tx.category_id);
    $('#tx-cat').value = category ? category.name : '';
    txDialog.catTouched = Boolean(category);
    txDialog.originalDate = toDateInput(new Date(tx.created_at));
    $('#tx-date').value = txDialog.originalDate;
    type = tx.type;
  } else {
    $('#tx-desc').value = prefill ? prefill.description : '';
    $('#tx-amount').value = prefill && prefill.amount ? prefill.amount : '';
    $('#tx-cat').value = '';
    txDialog.originalDate = toDateInput(new Date());
    $('#tx-date').value = txDialog.originalDate;
  }

  setTxType(type);
  $('#tx-dialog').showModal();
  (prefill && prefill.description && !prefill.amount ? $('#tx-amount') : $('#tx-desc')).focus();
}

/* Wait 350 ms after the last keystroke, then ask the backend for a category. */
function requestSuggestion() {
  clearTimeout(txDialog.suggestTimer);
  txDialog.suggestTimer = setTimeout(runSuggestion, 350);
}

async function runSuggestion() {
  const note = $('#tx-cat-note');
  const description = $('#tx-desc').value.trim();
  if (txDialog.catTouched || description.length < 2) return;

  const seq = ++txDialog.suggestSeq;
  try {
    const result = await api(`/categories/suggest?description=${encodeURIComponent(description)}&type=${txDialog.type}`);
    if (seq !== txDialog.suggestSeq || txDialog.catTouched) return; // an older reply, ignore it

    if (result.category_name) {
      $('#tx-cat').value = result.category_name;
      note.className = 'note';
      note.replaceChildren(el('span', { class: 'tag', text: 'Suggested' }), 'Change it if it is wrong.');
    } else {
      $('#tx-cat').value = '';
      note.className = 'note is-warn';
      note.textContent = "We couldn't guess this one. Choose a category, or save it as Uncategorized.";
    }
  } catch (error) {
    // Suggestions are a nice-to-have. If it fails, the user can still pick a category.
  }
}

async function saveTransaction(event) {
  event.preventDefault();
  const error = $('#tx-error');
  error.textContent = '';

  const description = $('#tx-desc').value.trim();
  const amount = Number($('#tx-amount').value);
  const categoryText = $('#tx-cat').value.trim();
  const category = categoryText ? state.byName.get(categoryText.toLowerCase()) : null;
  const date = $('#tx-date').value;

  $('#tx-desc').toggleAttribute('aria-invalid', !description);
  $('#tx-amount').toggleAttribute('aria-invalid', !(amount > 0));
  $('#tx-cat').toggleAttribute('aria-invalid', Boolean(categoryText) && !category);

  if (!description) { error.textContent = 'Say what it was for.'; $('#tx-desc').focus(); return; }
  if (!(amount > 0)) { error.textContent = 'Enter an amount above 0.'; $('#tx-amount').focus(); return; }
  if (categoryText && !category) { error.textContent = 'Pick a category from the list, or clear the box.'; $('#tx-cat').focus(); return; }

  const body = {
    description,
    amount,
    type: txDialog.type,
    category_id: category ? category.id : null,
  };
  // Only send a date when it was changed. Otherwise the server stamps "now".
  if (date && date !== txDialog.originalDate) body.transaction_date = date;

  const button = $('#tx-save');
  button.disabled = true;
  try {
    if (txDialog.mode === 'edit') {
      await api(`/transactions/${txDialog.editing.id}`, { method: 'PUT', body });
    } else {
      await api('/transactions', { method: 'POST', body });
    }
    $('#tx-dialog').close();

    const savedDate = date ? new Date(`${date}T12:00:00`) : new Date();
    const sameMonth = savedDate.getFullYear() === state.year && savedDate.getMonth() + 1 === state.month;
    toast(sameMonth ? 'Saved' : `Saved to ${monthLabel(savedDate.getFullYear(), savedDate.getMonth() + 1)}`);
    await refreshAll();
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

/* ---------- 8. Budget dialog, quick add, wiring ---------- */
const budgetDialog = { editing: null };

function openBudgetDialog(budget = null) {
  budgetDialog.editing = budget;
  $('#budget-error').textContent = '';
  ['#budget-cat', '#budget-ratio'].forEach((id) => $(id).removeAttribute('aria-invalid'));

  const input = $('#budget-cat');
  if (budget) {
    $('#budget-title').textContent = 'Edit budget';
    input.value = state.byId.get(budget.category_id).name;
    input.readOnly = true;          // the category of a budget can't change, only its share
    $('#budget-ratio').value = budget.ratio_percent;
  } else {
    $('#budget-title').textContent = 'Set a budget';
    input.value = '';
    input.readOnly = false;
    $('#budget-ratio').value = '';
    // Only offer expense categories that don't have a budget yet.
    const taken = new Set(state.budgets.map((b) => b.category_id));
    fillCategoryList($('#budget-cat-list'), state.categories.filter((c) => c.kind === 'expense' && !taken.has(c.id)));
  }
  updateBudgetNote();
  $('#budget-dialog').showModal();
  (budget ? $('#budget-ratio') : input).focus();
}

function updateBudgetNote() {
  const ratio = Number($('#budget-ratio').value);
  const income = state.summary ? state.summary.total_income : 0;
  const note = $('#budget-note');
  if (ratio > 0 && ratio <= 100 && income > 0) {
    note.textContent = `That is up to ${money((income * ratio) / 100)} out of this month's ${money(income)} income.`;
  } else if (income === 0) {
    note.textContent = "Budgets are a share of income. Add this month's income to see the amount.";
  } else {
    note.textContent = '';
  }
}

async function saveBudget(event) {
  event.preventDefault();
  const error = $('#budget-error');
  error.textContent = '';

  const categoryText = $('#budget-cat').value.trim();
  const category = state.byName.get(categoryText.toLowerCase());
  const ratio = Number($('#budget-ratio').value);

  $('#budget-cat').toggleAttribute('aria-invalid', !category);
  $('#budget-ratio').toggleAttribute('aria-invalid', !(ratio > 0 && ratio <= 100));

  if (!category) { error.textContent = 'Pick a category from the list.'; $('#budget-cat').focus(); return; }
  if (!(ratio > 0 && ratio <= 100)) { error.textContent = 'Enter a share between 1 and 100.'; $('#budget-ratio').focus(); return; }

  const button = $('#budget-save');
  button.disabled = true;
  try {
    if (budgetDialog.editing) {
      await api(`/budgets/${budgetDialog.editing.id}`, { method: 'PUT', body: { ratio_percent: ratio } });
    } else {
      await api('/budgets', { method: 'POST', body: { ratio_percent: ratio, category_id: category.id } });
    }
    $('#budget-dialog').close();
    toast('Budget saved');
    await refreshAll();
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

/* ---------- Savings goal dialog ---------- */
function openGoalDialog() {
  const goal = state.summary ? state.summary.savings_goal : null;
  $('#goal-error').textContent = '';
  $('#goal-ratio').removeAttribute('aria-invalid');
  $('#goal-ratio').value = goal ? goal.ratio_percent : '';
  $('#goal-remove').hidden = !goal;
  updateGoalNote();
  $('#goal-dialog').showModal();
  $('#goal-ratio').focus();
}

function updateGoalNote() {
  const ratio = Number($('#goal-ratio').value);
  const income = state.summary ? state.summary.total_income : 0;
  const note = $('#goal-note');
  if (ratio > 0 && ratio <= 100 && income > 0) {
    const keep = (income * ratio) / 100;
    note.textContent = `You would keep ${money(keep)} and could spend up to ${money(income - keep)} of this month's ${money(income)} income.`;
  } else if (income === 0) {
    note.textContent = "The goal is a share of income. Add this month's income to see the amounts.";
  } else {
    note.textContent = '';
  }
}

async function saveGoal(event) {
  event.preventDefault();
  const error = $('#goal-error');
  error.textContent = '';
  const ratio = Number($('#goal-ratio').value);

  $('#goal-ratio').toggleAttribute('aria-invalid', !(ratio > 0 && ratio <= 100));
  if (!(ratio > 0 && ratio <= 100)) {
    error.textContent = 'Enter a share between 1 and 100.';
    $('#goal-ratio').focus();
    return;
  }

  const button = $('#goal-save');
  button.disabled = true;
  try {
    await api('/savings-goal', { method: 'PUT', body: { ratio_percent: ratio } });
    $('#goal-dialog').close();
    toast('Savings goal saved');
    await refreshAll();
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  } finally {
    button.disabled = false;
  }
}

async function removeGoal() {
  $('#goal-dialog').close();
  const ok = await confirmDialog('Remove your savings goal?', 'You will stop getting savings alerts until you set a new goal.', 'Remove');
  if (!ok) return;
  try {
    await api('/savings-goal', { method: 'DELETE' });
    toast('Savings goal removed');
    await refreshAll();
  } catch (error) {
    if (error.status !== 401) toast(error.message);
  }
}

/* ---------- Delete my account ---------- */
function openDeleteDialog() {
  $('#delete-password').value = '';
  $('#delete-error').textContent = '';
  $('#delete-dialog').showModal();
  $('#delete-password').focus();
}

async function deleteAccount(event) {
  event.preventDefault();
  const error = $('#delete-error');
  const password = $('#delete-password').value;
  if (!password) {
    error.textContent = 'Enter your password to confirm.';
    return;
  }
  try {
    await api('/me', { method: 'DELETE', body: { password } });
    clearToken();
    setFlash('Your account and all your data were deleted.');
    location.replace('/');
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  }
}

/* "Swiggy 250" -> { description: "Swiggy", amount: 250, type: "expense" }
   A leading "+" means income:  "+50000 salary". */
function parseQuickAdd(text) {
  let t = text.trim();
  let type = 'expense';
  if (t.startsWith('+')) { type = 'income'; t = t.slice(1).trim(); }

  const numbers = [...t.matchAll(/\d[\d,]*(?:\.\d+)?/g)];
  if (!numbers.length) return { description: t, amount: null, type };

  const last = numbers[numbers.length - 1];                // "Swiggy 250": use the last number
  const amount = parseFloat(last[0].replace(/,/g, ''));
  const description = (t.slice(0, last.index) + ' ' + t.slice(last.index + last[0].length))
    .replace(/₹|\brs\.?(?=\s|\d|$)|\binr\b/gi, ' ')   // drop currency words
    .replace(/\s+/g, ' ')
    .trim();
  return { description, amount, type };
}

function bindEvents() {
  $('#logout').addEventListener('click', () => { clearToken(); location.replace('/'); });
  $('#banner-retry').addEventListener('click', () => location.reload());

  // Month switcher
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

  // The three big tiles
  $('#tile-expense').addEventListener('click', () => openTxDialog({ mode: 'add', type: 'expense' }));
  $('#tile-income').addEventListener('click', () => openTxDialog({ mode: 'add', type: 'income' }));
  $('#tile-budget').addEventListener('click', () => openBudgetDialog());
  $('#tile-savings').addEventListener('click', openGoalDialog);
  $('#goal-edit').addEventListener('click', openGoalDialog);

  // Quick add opens the same dialog, already filled in, so the user can review it.
  $('#quick-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const text = $('#quick-input').value.trim();
    if (!text) { $('#quick-input').focus(); return; }
    const parsed = parseQuickAdd(text);
    $('#quick-input').value = '';
    openTxDialog({ mode: 'add', type: parsed.type, prefill: parsed });
  });

  // Filter chips and "Show more"
  document.querySelectorAll('[data-filter]').forEach((button) => {
    button.addEventListener('click', async () => {
      state.filter = button.dataset.filter;
      document.querySelectorAll('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      try { await loadTransactions(true); } catch (e) { if (e.status !== 401) toast(e.message); }
    });
  });
  $('#tx-more').addEventListener('click', async () => {
    try { await loadTransactions(false); } catch (e) { if (e.status !== 401) toast(e.message); }
  });

  // Transaction dialog
  $('#tx-form').addEventListener('submit', saveTransaction);
  $('#tx-cancel').addEventListener('click', () => $('#tx-dialog').close());
  document.querySelectorAll('#tx-dialog [data-type]').forEach((b) => {
    b.addEventListener('click', () => setTxType(b.dataset.type));
  });
  $('#tx-desc').addEventListener('input', requestSuggestion);
  $('#tx-cat').addEventListener('input', () => {
    txDialog.catTouched = $('#tx-cat').value.trim() !== '';   // clearing the box hands control back to suggestions
    $('#tx-cat-note').textContent = '';
    $('#tx-cat-note').className = 'note';
    if (!txDialog.catTouched) requestSuggestion();
  });

  // Budget dialog
  $('#budget-form').addEventListener('submit', saveBudget);
  $('#budget-cancel').addEventListener('click', () => $('#budget-dialog').close());
  $('#budget-ratio').addEventListener('input', updateBudgetNote);

  // Savings goal dialog
  $('#goal-form').addEventListener('submit', saveGoal);
  $('#goal-cancel').addEventListener('click', () => $('#goal-dialog').close());
  $('#goal-remove').addEventListener('click', removeGoal);
  $('#goal-ratio').addEventListener('input', updateGoalNote);

  // Delete my account
  $('#delete-account').addEventListener('click', openDeleteDialog);
  $('#delete-form').addEventListener('submit', deleteAccount);
  $('#delete-cancel').addEventListener('click', () => $('#delete-dialog').close());

  // Clicking the dark area outside a dialog closes it.
  document.querySelectorAll('dialog').forEach((dialog) => {
    dialog.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  });
}

init();