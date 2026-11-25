'use strict';

/* currency.js - the currency choice, the home-currency card and the converter.
   Your saved amounts are never changed; only the symbol and the comparisons change. */

function currencyLabel(code) { return `${CURRENCIES[code].name} (${CURRENCIES[code].symbol})`; }

function fillCurrencySelect(select, selected) {
  select.replaceChildren(...Object.keys(CURRENCIES).map((code) => el('option', { value: code, text: currencyLabel(code) })));
  select.value = selected;
}

/* Called once the profile is known (and again after it is saved). */
function applyProfile(me) {
  state.me = me;
  setCurrency(me.living_currency);
  $('#tx-currency').textContent = symbolOf();

  // GBP users most likely want the UK tax year, everyone else the Indian one. They can still switch.
  setFinancialYear(me.living_currency === 'GBP' ? 'uk' : 'india');

  fillCurrencySelect($('#profile-living'), me.living_currency);
  fillCurrencySelect($('#profile-home'), me.home_currency);
  fillCurrencySelect($('#convert-from'), me.home_currency);
  fillCurrencySelect($('#convert-to'), me.living_currency);
}

async function saveProfile(event) {
  event.preventDefault();
  const error = $('#profile-error');
  error.textContent = '';
  try {
    const me = await api('/me/profile', {
      method: 'PUT',
      body: { living_currency: $('#profile-living').value, home_currency: $('#profile-home').value },
    });
    applyProfile(me);
    toast('Currency saved');
    await refreshAll();
  } catch (err) {
    if (err.status !== 401) error.textContent = err.message;
  }
}

function rateText(rate, from, to, date) {
  const shown = rate >= 1 ? rate.toFixed(2) : rate.toPrecision(3);
  return `1 ${from} = ${shown} ${to}${date ? ` (rates of ${date})` : ''}`;
}

async function convert(event) {
  event.preventDefault();
  const out = $('#convert-result');
  const amount = Number($('#convert-amount').value);
  const from = $('#convert-from').value;
  const to = $('#convert-to').value;
  if (!(amount >= 0)) { out.textContent = 'Enter an amount.'; return; }
  out.textContent = 'Getting the latest rate...';
  try {
    const r = await api(`/rates?from=${from}&to=${to}&amount=${amount}`);
    out.replaceChildren(`${money(amount, from)} = ${money(r.converted, to)}`,
      el('div', { class: 'hint', text: rateText(r.rate, from, to, r.date) }));
  } catch (err) {
    if (err.status !== 401) out.textContent = err.message;
  }
}

/* Analytics: show this month and the tax year in the home currency, when it differs from the spending currency. */
async function renderHomeCard(data) {
  const card = $('#home-card');
  const me = state.me;
  if (!me || me.living_currency === me.home_currency) { card.hidden = true; return; }
  try {
    const r = await api(`/rates?from=${me.living_currency}&to=${me.home_currency}`);
    const thisMonth = data.months[data.months.length - 1];
    const home = (value) => money(value * r.rate, me.home_currency);
    $('#home-body').replaceChildren(
      el('div', { class: 'kv' }, el('span', { text: 'Spent this month' }), el('strong', { class: 'num', text: `${money(thisMonth.expense)}  ≈  ${home(thisMonth.expense)}` })),
      el('div', { class: 'kv' }, el('span', { text: `Spent this tax year (${data.financial_year.label})` }), el('strong', { class: 'num', text: `${money(data.financial_year.expense)}  ≈  ${home(data.financial_year.expense)}` })),
      el('div', { class: 'kv' }, el('span', { text: 'Saved this tax year' }), el('strong', { class: 'num', text: `${money(data.financial_year.savings)}  ≈  ${home(data.financial_year.savings)}` })),
      el('p', { class: 'hint', text: `${rateText(r.rate, me.living_currency, me.home_currency, r.date)}. Today's rate applied to all amounts, so this is an estimate.` }));
    card.hidden = false;
  } catch (err) {
    card.hidden = true;       // no rate, no card; the rest of Analytics still works
  }
}

function bindCurrencyEvents() {
  $('#profile-form').addEventListener('submit', saveProfile);
  $('#convert-form').addEventListener('submit', convert);
}