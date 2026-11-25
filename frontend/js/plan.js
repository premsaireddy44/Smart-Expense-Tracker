'use strict';

/* plan.js - budgets, the savings goal dialog, and deleting the account */

/* ---------- Budgets list ---------- */
function renderBudgets() {
  const list = $('#budgets');
  $('#budgets-empty').hidden = state.budgets.length > 0;

  const income = state.summary.total_income;
  const spentByName = new Map(state.summary.categories.map((c) => [c.category, c.amount]));

  list.replaceChildren(...state.budgets
    .map((b) => ({ b, name: (state.byId.get(b.category_id) || { name: `Category #${b.category_id}` }).name }))
    .sort((x, y) => x.name.localeCompare(y.name))
    .map(({ b, name }) => {
      let meta = `${b.ratio_percent}% of income`;
      if (income > 0) {
        const limit = (income * b.ratio_percent) / 100;
        meta = `${b.ratio_percent}% of income \u00B7 spent ${money(spentByName.get(name) || 0)} of ${money(limit)}`;
      }
      return el('li', { class: 'budget' },
        el('span', { class: 'budget-name', text: name }),
        el('span', { class: 'budget-meta', text: meta }),
        el('div', { class: 'budget-actions' },
          el('button', { class: 'icon-btn', type: 'button', 'aria-label': `Edit ${name} budget`, onclick: () => openBudgetDialog(b) }, icon('pencil')),
          el('button', { class: 'icon-btn danger', type: 'button', 'aria-label': `Delete ${name} budget`, onclick: () => deleteBudget(b, name) }, icon('trash'))));
    }));
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

/* ---------- Budget dialog ---------- */
const budgetDialog = { editing: null };

function openBudgetDialog(budget = null) {
  budgetDialog.editing = budget;
  $('#budget-error').textContent = '';
  ['#budget-cat', '#budget-ratio'].forEach((id) => $(id).removeAttribute('aria-invalid'));

  const input = $('#budget-cat');
  if (budget) {
    $('#budget-title').textContent = 'Edit budget';
    const own = state.byId.get(budget.category_id) || { id: budget.category_id, name: `Category #${budget.category_id}` };
    fillSelect(input, [own]);
    input.disabled = true;          // the category of a budget can't change, only its share
    $('#budget-ratio').value = budget.ratio_percent;
  } else {
    $('#budget-title').textContent = 'Set a budget';
    input.disabled = false;
    $('#budget-ratio').value = '';
    const taken = new Set(state.budgets.map((b) => b.category_id));      // one budget per category
    fillSelect(input, state.categories.filter((c) => c.kind === 'expense' && !taken.has(c.id)), 'Choose a category...');
  }
  updateBudgetNote();
  $('#budget-dialog').showModal();
  (budget ? $('#budget-ratio') : input).focus();
}

function incomeNote(ratio, wording) {
  const income = state.summary ? state.summary.total_income : 0;
  if (ratio > 0 && ratio <= 100 && income > 0) return wording(income, (income * ratio) / 100);
  if (income === 0) return "This is a share of income. Add this month's income to see the amount.";
  return '';
}

function updateBudgetNote() {
  $('#budget-note').textContent = incomeNote(Number($('#budget-ratio').value),
    (income, part) => `That is up to ${money(part)} out of this month's ${money(income)} income.`);
}

async function saveBudget(event) {
  event.preventDefault();
  const error = $('#budget-error');
  error.textContent = '';

  const categoryId = Number($('#budget-cat').value) || null;
  const ratio = Number($('#budget-ratio').value);
  $('#budget-cat').toggleAttribute('aria-invalid', !categoryId);
  $('#budget-ratio').toggleAttribute('aria-invalid', !(ratio > 0 && ratio <= 100));

  if (!categoryId) { error.textContent = 'Choose a category.'; $('#budget-cat').focus(); return; }
  if (!(ratio > 0 && ratio <= 100)) { error.textContent = 'Enter a share between 1 and 100.'; $('#budget-ratio').focus(); return; }

  const button = $('#budget-save');
  button.disabled = true;
  try {
    if (budgetDialog.editing) {
      await api(`/budgets/${budgetDialog.editing.id}`, { method: 'PUT', body: { ratio_percent: ratio } });
    } else {
      await api('/budgets', { method: 'POST', body: { ratio_percent: ratio, category_id: categoryId } });
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
  $('#goal-note').textContent = incomeNote(Number($('#goal-ratio').value),
    (income, keep) => `You would keep ${money(keep)} and could spend up to ${money(income - keep)} of this month's ${money(income)} income.`);
}

async function saveGoal(event) {
  event.preventDefault();
  const error = $('#goal-error');
  error.textContent = '';
  const ratio = Number($('#goal-ratio').value);
  $('#goal-ratio').toggleAttribute('aria-invalid', !(ratio > 0 && ratio <= 100));
  if (!(ratio > 0 && ratio <= 100)) { error.textContent = 'Enter a share between 1 and 100.'; $('#goal-ratio').focus(); return; }

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
  if (!password) { error.textContent = 'Enter your password to confirm.'; return; }
  try {
    await api('/me', { method: 'DELETE', body: { password } });
    clearToken();
    setFlash('Your account and all your data were deleted.');
    location.replace('/');
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  }
}

function bindPlanEvents() {
  $('#tile-budget').addEventListener('click', () => openBudgetDialog());
  $('#budget-form').addEventListener('submit', saveBudget);
  $('#budget-cancel').addEventListener('click', () => $('#budget-dialog').close());
  $('#budget-ratio').addEventListener('input', updateBudgetNote);

  $('#goal-edit').addEventListener('click', openGoalDialog);
  $('#goal-form').addEventListener('submit', saveGoal);
  $('#goal-cancel').addEventListener('click', () => $('#goal-dialog').close());
  $('#goal-remove').addEventListener('click', removeGoal);
  $('#goal-ratio').addEventListener('input', updateGoalNote);

  $('#delete-account').addEventListener('click', openDeleteDialog);
  $('#delete-form').addEventListener('submit', deleteAccount);
  $('#delete-cancel').addEventListener('click', () => $('#delete-dialog').close());
}