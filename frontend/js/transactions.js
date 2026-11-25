'use strict';

/* transactions.js - the Transactions tab and the add/edit dialog */

const PAGE_SIZE = 20;

/* ---------- The list ---------- */
async function loadTransactions(reset) {
  const skip = reset ? 0 : state.transactions.length;
  const typeQuery = state.filter === 'all' ? '' : `&type=${state.filter}`;
  const rows = await api(`/transactions?year=${state.year}&month=${state.month}${typeQuery}&skip=${skip}&limit=${PAGE_SIZE}`);
  state.transactions = reset ? rows : state.transactions.concat(rows);
  state.hasMore = rows.length === PAGE_SIZE;
  renderTransactions();
}

// Small grey words under a category that say where it came from.
const SOURCE_TEXT = { memory: 'remembered from your past choice', model: 'sorted automatically', rules: 'sorted by keyword' };

function renderTransactions() {
  const list = $('#txs');
  const empty = $('#txs-empty');

  if (!state.transactions.length) {
    list.replaceChildren();
    const what = state.filter === 'all' ? 'transactions' : (state.filter === 'income' ? 'income' : 'expenses');
    empty.textContent = `No ${what} in ${monthLabel(state.year, state.month)}. Use "Add transaction" to add one.`;
    empty.hidden = false;
    $('#tx-more').hidden = true;
    return;
  }
  empty.hidden = true;

  list.replaceChildren(...state.transactions.map((t) => {
    const category = state.byId.get(t.category_id);
    const when = new Date(t.transaction_date + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    const sign = t.type === 'income' ? '+' : '\u2212';
    const source = SOURCE_TEXT[t.category_source];

    return el('li', { class: 'tx' },
      el('span', { class: 'tx-date', text: when }),
      el('div', {},
        el('div', { class: 'tx-desc', text: t.description }),
        el('span', { class: category ? 'pill' : 'pill pill-none', text: category ? category.name : 'Uncategorized' }),
        source ? el('span', { class: 'source', text: source }) : null),
      el('span', { class: `tx-amt num ${t.type === 'income' ? 'is-income' : 'is-expense'}`, text: `${sign}${money(t.amount)}` }),
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

/* ---------- The add / edit dialog ---------- */
const txDialog = {
  mode: 'add',
  editing: null,         // the transaction being edited
  type: 'expense',
  catTouched: false,     // true once the user picks a category themselves
  originalDate: '',
  suggestSeq: 0,         // guards against slow, out-of-order suggestion replies
  suggestTimer: null,
};

/* Fill a dropdown with categories. `blank` is the first choice (the "no category" one). */
function fillSelect(select, categories, blank) {
  const options = categories.map((c) => el('option', { value: String(c.id), text: c.name }));
  if (blank) options.unshift(el('option', { value: '', text: blank }));
  select.replaceChildren(...options);
}

function setTxType(type) {
  txDialog.type = type;
  $$('#tx-dialog [data-type]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.type === type)));

  if (txDialog.mode === 'add') {
    $('#tx-title').textContent = type === 'income' ? 'Add income' : 'Add expense';
    $('#tx-save').textContent = type === 'income' ? 'Save income' : 'Save expense';
  }

  // Only offer categories that make sense: salary is not an expense.
  const select = $('#tx-cat');
  const before = select.value;
  fillSelect(select, state.categories.filter((c) => c.kind === type), 'Uncategorized');
  const stillFits = Array.from(select.options).some((o) => o.value === before);
  select.value = stillFits ? before : '';
  if (!stillFits) txDialog.catTouched = false;
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
  $('#tx-cat').value = '';

  if (mode === 'edit') {
    $('#tx-title').textContent = 'Edit transaction';
    $('#tx-save').textContent = 'Save changes';
    $('#tx-desc').value = tx.description;
    $('#tx-amount').value = tx.amount;
    txDialog.originalDate = tx.transaction_date;
    $('#tx-date').value = txDialog.originalDate;
    type = tx.type;
    txDialog.catTouched = tx.category_id !== null;    // keep the saved category, do not overwrite it with a guess
  } else {
    $('#tx-desc').value = prefill ? prefill.description : '';
    $('#tx-amount').value = prefill && prefill.amount ? prefill.amount : '';
    txDialog.originalDate = toDateInput(new Date());
    $('#tx-date').value = txDialog.originalDate;
  }

  setTxType(type);
  if (mode === 'edit' && tx.category_id !== null) $('#tx-cat').value = String(tx.category_id);
  $('#tx-dialog').showModal();
  (prefill && prefill.description && !prefill.amount ? $('#tx-amount') : $('#tx-desc')).focus();
}

/* Wait a moment after the last keystroke, then ask the server for a category. */
function requestSuggestion() {
  clearTimeout(txDialog.suggestTimer);
  txDialog.suggestTimer = setTimeout(runSuggestion, 200);
}

function suggestionWords(result) {
  if (result.source === 'memory') return 'From your earlier choices.';
  if (result.source === 'rules') return 'Matched a keyword.';
  return `About ${Math.round(result.confidence * 100)}% sure.`;
}

async function runSuggestion() {
  const note = $('#tx-cat-note');
  const description = $('#tx-desc').value.trim();
  if (txDialog.catTouched || description.length < 2) return;

  const seq = ++txDialog.suggestSeq;
  note.className = 'note';
  note.textContent = 'Thinking...';
  try {
    const result = await api(`/categories/suggest?description=${encodeURIComponent(description)}&type=${txDialog.type}`);
    if (seq !== txDialog.suggestSeq || txDialog.catTouched) return;   // an older reply, ignore it

    if (result.category_id) {
      $('#tx-cat').value = String(result.category_id);
      note.replaceChildren(el('span', { class: 'tag', text: 'Suggested' }), `${suggestionWords(result)} Pick another from the list if it is wrong.`);
    } else {
      $('#tx-cat').value = '';
      note.className = 'note is-warn';
      note.textContent = "We couldn't guess this one. Choose a category, or save it as Uncategorized.";
    }
  } catch (error) {
    note.textContent = '';   // suggestions are a nice-to-have; the user can still choose
  }
}

async function saveTransaction(event) {
  event.preventDefault();
  const error = $('#tx-error');
  error.textContent = '';

  const description = $('#tx-desc').value.trim();
  const amount = Number($('#tx-amount').value);
  const categoryId = $('#tx-cat').value ? Number($('#tx-cat').value) : null;
  const date = $('#tx-date').value;

  $('#tx-desc').toggleAttribute('aria-invalid', !description);
  $('#tx-amount').toggleAttribute('aria-invalid', !(amount > 0));

  if (!description) { error.textContent = 'Say what it was for.'; $('#tx-desc').focus(); return; }
  if (!(amount > 0)) { error.textContent = 'Enter an amount above 0.'; $('#tx-amount').focus(); return; }

  const body = { description, amount, type: txDialog.type, category_id: categoryId };
  // Only send a date when it was changed. Otherwise the server stamps today.
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
    .replace(/[\u20B9\u00A3\u20AC$]|\brs\.?(?=\s|\d|$)|\binr\b|\bgbp\b/gi, ' ')   // drop currency words
    .replace(/\s+/g, ' ')
    .trim();
  return { description, amount, type };
}

function bindTransactionEvents() {
  $('#tx-add').addEventListener('click', () => openTxDialog({ mode: 'add', type: 'expense' }));
  $('#tile-expense').addEventListener('click', () => openTxDialog({ mode: 'add', type: 'expense' }));
  $('#tile-income').addEventListener('click', () => openTxDialog({ mode: 'add', type: 'income' }));

  // Quick add opens the same dialog, already filled in, so the user can review it.
  $('#quick-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const text = $('#quick-input').value.trim();
    if (!text) { $('#quick-input').focus(); return; }
    const parsed = parseQuickAdd(text);
    $('#quick-input').value = '';
    openTxDialog({ mode: 'add', type: parsed.type, prefill: parsed });
  });

  $$('[data-filter]').forEach((button) => {
    button.addEventListener('click', async () => {
      state.filter = button.dataset.filter;
      $$('[data-filter]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      try { await loadTransactions(true); } catch (e) { if (e.status !== 401) toast(e.message); }
    });
  });
  $('#tx-more').addEventListener('click', async () => {
    try { await loadTransactions(false); } catch (e) { if (e.status !== 401) toast(e.message); }
  });

  $('#tx-form').addEventListener('submit', saveTransaction);
  $('#tx-cancel').addEventListener('click', () => $('#tx-dialog').close());
  $$('#tx-dialog [data-type]').forEach((b) => b.addEventListener('click', () => setTxType(b.dataset.type)));
  $('#tx-desc').addEventListener('input', requestSuggestion);
  $('#tx-cat').addEventListener('change', () => {
    txDialog.suggestSeq += 1;                                    // ignore any suggestion still on its way
    txDialog.catTouched = $('#tx-cat').value !== '';             // choosing "Uncategorized" hands control back to suggestions
    $('#tx-cat-note').textContent = '';
    $('#tx-cat-note').className = 'note';
    if (!txDialog.catTouched) requestSuggestion();
  });
}