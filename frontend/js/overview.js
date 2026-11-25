'use strict';

/* overview.js - the Overview tab: stats, alerts, savings goal, category bars, 6-month chart */

function renderStats() {
  const s = state.summary;
  $('#stat-income').textContent = money(s.total_income);
  $('#stat-spent').textContent = money(s.total_expense);
  const saved = $('#stat-saved');
  saved.textContent = money(s.savings);
  saved.classList.toggle('is-negative', s.savings < 0);

  let note = 'Add income to see how much you keep.';
  if (s.total_income > 0) {
    note = s.savings >= 0 ? `${s.savings_rate_percent}% of your income` : 'You spent more than you earned';
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
  const alerts = state.summary.alerts;
  const rows = alerts.map((a) => el('li', { class: `alert alert-${a.level}` }, icon(a.level === 'info' ? 'info' : 'warning'), el('span', { text: a.message })));
  if (!rows.length) {
    const text = (state.budgets.length || state.summary.savings_goal)
      ? 'You are on track this month.'
      : 'Set a budget or a savings goal and we will warn you before you overspend.';
    rows.push(el('li', { class: `alert ${state.budgets.length || state.summary.savings_goal ? 'alert-ok' : 'alert-info'}` },
      icon(state.budgets.length || state.summary.savings_goal ? 'check' : 'info'), el('span', { text })));
  }
  $('#alerts').replaceChildren(...rows);
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
  const scale = Math.max(...values, ...ratios, 20) * 1.1;   // at least 20%, so a tiny category never looks huge

  list.replaceChildren(...s.categories.map((c, i) => {
    const bar = el('div', { class: 'bar' }, el('div', { class: 'bar-fill', style: `width:${Math.min(100, (values[i] / scale) * 100)}%` }));
    if (hasIncome && c.budget_ratio) bar.append(el('div', { class: 'bar-tick', style: `left:${(c.budget_ratio / scale) * 100}%` }));

    const parts = [hasIncome ? `${c.percent_of_income}% of income` : `${Math.round(values[i])}% of spending`];
    if (c.budget_ratio) parts.push(`budget ${c.budget_ratio}%`);
    if (c.category === 'Uncategorized' || c.category === 'Uncategorised') parts.push('needs a category');
    const meta = el('div', { class: 'cat-meta' }, parts.join(' \u00B7 '));
    if (STATUS_TEXT[c.status]) meta.append(' \u00B7 ', el('span', { class: 'flag', text: STATUS_TEXT[c.status] }));

    return el('li', { class: `cat is-${c.status}` },
      el('div', { class: 'cat-head' }, el('span', { text: c.category }), el('span', { class: 'num', text: money(c.amount) })),
      bar, meta);
  }));
}

function renderTrend(points) {
  const shown = drawMonthsChart($('#trend-chart'), points);
  $('#trend-empty').hidden = shown;
}