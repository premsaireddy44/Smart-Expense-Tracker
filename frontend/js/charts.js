'use strict';

/* =====================================================================
   charts.js - charts drawn by hand with SVG. No chart library to download.
   A chart is just rectangles: the height of each one is value / biggest value * chart height.
   ===================================================================== */

const SVG_NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs = {}, ...children) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  children.forEach((child) => node.append(child));
  return node;
}

/* Adds a hover/screen-reader title to a shape. */
function withTitle(shape, text) {
  const title = svgEl('title');
  title.textContent = text;
  shape.append(title);
  return shape;
}

function shortMonth(label) {                       // "2026-10" -> "Oct"
  const [year, month] = label.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'short' });
}

function longMonth(label) {                        // "2026-10" -> "October 2026"
  const [year, month] = label.split('-').map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
}

/* Pairs of bars (income, spent) for each month.  points = [{month, income, expense}] */
function drawMonthsChart(container, points) {
  const hasData = points.some((p) => p.income || p.expense);
  if (!hasData) { container.replaceChildren(); return false; }

  const width = 640, height = 220, left = 8, bottom = 24, top = 18;
  const tallest = Math.max(...points.flatMap((p) => [p.income, p.expense]));
  const plotHeight = height - bottom - top;
  const slot = (width - left * 2) / points.length;
  const barWidth = Math.min(22, slot / 2 - 3);

  const svg = svgEl('svg', {
    viewBox: `0 0 ${width} ${height}`, role: 'img',
    'aria-label': `Income and spending for the last ${points.length} months. Tallest bar is ${money(tallest)}. A table with the exact numbers is available below.`,
  });
  svg.append(svgEl('line', { x1: left, x2: width - left, y1: height - bottom, y2: height - bottom, class: 'axis' }));
  const top_label = svgEl('text', { x: left, y: 11 });
  top_label.textContent = `Tallest bar: ${money(tallest)}`;
  svg.append(top_label);

  points.forEach((p, i) => {
    const centre = left + slot * i + slot / 2;
    [['income', -barWidth - 1], ['expense', 1]].forEach(([key, offset]) => {
      const barHeight = tallest ? (p[key] / tallest) * plotHeight : 0;
      const rect = svgEl('rect', {
        x: centre + offset, y: height - bottom - barHeight, width: barWidth, height: Math.max(barHeight, p[key] > 0 ? 2 : 0),
        rx: 3, class: key === 'income' ? 'bar-income' : 'bar-expense',
      });
      svg.append(withTitle(rect, `${longMonth(p.month)}: ${key === 'income' ? 'income' : 'spent'} ${money(p[key])}`));
    });
    const name = svgEl('text', { x: centre, y: height - 8, 'text-anchor': 'middle' });
    name.textContent = shortMonth(p.month);
    svg.append(name);
  });

  const legend = el('div', { class: 'legend' },
    el('span', {}, el('i', { style: 'background:var(--income)' }), 'Income'),
    el('span', {}, el('i', { style: 'background:var(--expense)' }), 'Spent'));
  container.className = 'chart';
  container.replaceChildren(svg, legend);
  return true;
}

/* One bar per item.  items = [{label, value}] */
function drawSimpleBars(container, items, unitLabel) {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (!total) { container.replaceChildren(el('p', { class: 'empty', text: 'Nothing to show yet.' })); return; }

  const width = 420, height = 190, bottom = 24, top = 16;
  const tallest = Math.max(...items.map((i) => i.value));
  const plotHeight = height - bottom - top;
  const slot = width / items.length;
  const barWidth = slot * 0.6;

  const svg = svgEl('svg', {
    viewBox: `0 0 ${width} ${height}`, role: 'img',
    'aria-label': `${unitLabel}: ${items.map((i) => `${i.label} ${money(i.value)}`).join(', ')}`,
  });
  svg.append(svgEl('line', { x1: 0, x2: width, y1: height - bottom, y2: height - bottom, class: 'axis' }));
  items.forEach((item, i) => {
    const barHeight = (item.value / tallest) * plotHeight;
    const x = slot * i + (slot - barWidth) / 2;
    const rect = svgEl('rect', { x, y: height - bottom - barHeight, width: barWidth, height: Math.max(barHeight, item.value > 0 ? 2 : 0), rx: 3, class: 'bar-plain' });
    svg.append(withTitle(rect, `${item.label}: ${money(item.value)}`));
    const text = svgEl('text', { x: slot * i + slot / 2, y: height - 8, 'text-anchor': 'middle' });
    text.textContent = item.label;
    svg.append(text);
  });
  container.className = 'chart';
  container.replaceChildren(svg);
}

/* A list of horizontal bars (plain HTML).  rows = [{name, total, note}] */
function drawHorizontalBars(list, rows) {
  const tallest = Math.max(...rows.map((r) => r.total), 1);
  list.replaceChildren(...rows.map((r) => el('li', { class: 'hbar' },
    el('div', { class: 'hbar-head' }, el('span', { text: r.name }), el('span', { class: 'num', text: r.note ? `${money(r.total)} \u00B7 ${r.note}` : money(r.total) })),
    el('div', { class: 'hbar-track', role: 'presentation' }, el('div', { class: 'hbar-fill', style: `width:${(r.total / tallest) * 100}%` })))));
}