'use strict';

/* analytics.js - the Analytics tab. All the maths is done by pandas on the server (app/analytics.py);
   this file only draws the answer. */

let financialYearType = 'uk';

function setFinancialYear(type) {
  financialYearType = type;
  $$('[data-fy]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.fy === type)));
}

async function loadAnalytics() {
  const data = await api(`/analytics?fy=${financialYearType}`);
  state.analytics = data;

  $('#insights').replaceChildren(...data.insights.map((text) => el('li', { text })));
  renderPace(data.month_end);
  renderFinancialYear(data.financial_year);

  drawMonthsChart($('#year-chart'), data.months);
  renderYearTable(data.months);
  renderChanges(data.category_changes);

  const merchants = data.top_merchants;
  $('#merchants-empty').hidden = merchants.length > 0;
  drawHorizontalBars($('#merchants'), merchants.map((m) => ({ name: m.name, total: m.total, note: `${m.count}\u00D7` })));

  drawSimpleBars($('#weekday-chart'), data.weekdays.map((d) => ({ label: d.day, value: d.total })), 'Spending by weekday');
  renderUnusual(data.unusual);
  renderAccuracy(data.suggestion_accuracy);
  renderHomeCard(data);
}

function renderPace(pace) {
  const body = $('#pace');
  if (!pace.spent_so_far) {
    body.replaceChildren(el('p', { class: 'empty', text: 'No spending yet this month.' }));
    return;
  }
  body.replaceChildren(
    el('div', { class: 'kv' }, el('span', { text: 'Spent so far' }), el('strong', { class: 'num', text: money(pace.spent_so_far) })),
    el('div', { class: 'kv' }, el('span', { text: 'Likely month total' }), el('strong', { class: 'num', text: money(Math.round(pace.estimate)) })),
    el('div', { class: 'kv' }, el('span', { text: 'Days left' }), el('strong', { text: String(pace.days_left) })),
    el('p', { class: 'hint', text: 'The estimate assumes you keep spending at the same daily rate.' }));
}

function renderFinancialYear(fy) {
  $('#fy-body').replaceChildren(
    el('p', { class: 'hint', text: `${financialYearType === 'uk' ? 'UK tax year' : 'Indian financial year'} ${fy.label}, starting ${new Date(fy.start + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}` }),
    el('div', { class: 'kv' }, el('span', { text: 'Income' }), el('strong', { class: 'num is-income', text: money(fy.income) })),
    el('div', { class: 'kv' }, el('span', { text: 'Spent' }), el('strong', { class: 'num is-expense', text: money(fy.expense) })),
    el('div', { class: 'kv' }, el('span', { text: 'Saved' }), el('strong', { class: `num ${fy.savings < 0 ? 'is-negative' : ''}`, text: money(fy.savings) })));
}

function renderYearTable(months) {
  $('#year-table').replaceChildren(
    el('thead', {}, el('tr', {}, el('th', { text: 'Month' }), el('th', { class: 'r', text: 'Income' }), el('th', { class: 'r', text: 'Spent' }), el('th', { class: 'r', text: 'Saved' }))),
    el('tbody', {}, ...months.map((m) => el('tr', {},
      el('td', { text: longMonth(m.month) }),
      el('td', { class: 'r num', text: money(m.income) }),
      el('td', { class: 'r num', text: money(m.expense) }),
      el('td', { class: 'r num', text: money(m.savings) })))));
}

function renderChanges(rows) {
  $('#changes-empty').hidden = rows.length > 0;
  const table = $('#changes-table');
  if (!rows.length) { table.replaceChildren(); return; }
  table.replaceChildren(
    el('thead', {}, el('tr', {}, el('th', { text: 'Category' }), el('th', { class: 'r', text: 'This month' }), el('th', { class: 'r', text: 'Last month' }), el('th', { class: 'r', text: 'Change' }))),
    el('tbody', {}, ...rows.map((r) => {
      let change = 'new';
      let cls = '';
      if (r.change_percent !== null) {
        const arrow = r.change_percent > 0 ? '\u25B2' : r.change_percent < 0 ? '\u25BC' : '';
        change = `${arrow} ${Math.abs(r.change_percent)}%`.trim();
        cls = r.change_percent > 0 ? 'up' : r.change_percent < 0 ? 'down' : '';   // for spending, up is the worrying direction
      }
      return el('tr', {},
        el('td', { text: r.category }),
        el('td', { class: 'r num', text: money(r.this_month) }),
        el('td', { class: 'r num', text: money(r.last_month) }),
        el('td', { class: `r num ${cls}`, text: change }));
    })));
}

function renderUnusual(rows) {
  if (!rows.length) {
    $('#unusual').replaceChildren(el('li', { class: 'empty', text: 'Nothing unusual. Your recent spending looks normal for you.' }));
    return;
  }
  $('#unusual').replaceChildren(...rows.map((u) => el('li', {},
    el('strong', { text: `${u.description} \u00B7 ${money(u.amount)}` }),
    el('div', { class: 'hint', text: `${u.category} on ${new Date(u.date + 'T00:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}. Your normal top for this category is about ${money(Math.round(u.usual_limit))}.` }))));
}

function renderAccuracy(acc) {
  const body = $('#accuracy');
  if (!acc.checked) {
    body.replaceChildren(el('p', { class: 'empty', text: 'Once you add transactions where we suggested a category, this shows how often you kept our suggestion.' }));
    return;
  }
  body.replaceChildren(
    el('div', { class: 'big-number num', text: `${acc.percent}%` }),
    el('p', { text: `We made ${acc.checked} suggestion${acc.checked === 1 ? '' : 's'} you reviewed. You kept ${acc.kept} and changed ${acc.checked - acc.kept}.` }),
    el('p', { class: 'hint', text: 'When you change a category, the app remembers it for next time, so this number should rise as you use it.' }));
}

function bindAnalyticsEvents() {
  $$('[data-fy]').forEach((button) => {
    button.addEventListener('click', async () => {
      setFinancialYear(button.dataset.fy);
      try { await loadAnalytics(); } catch (e) { if (e.status !== 401) toast(e.message); }
    });
  });
}