'use strict';

/* theme.js - light / dark choice. Loaded in <head> so the page never flashes the wrong colours. */
(function () {
  let saved = null;
  try { saved = localStorage.getItem('expense_theme'); } catch (e) { /* storage blocked */ }
  document.documentElement.setAttribute('data-theme', saved === 'dark' ? 'dark' : 'light');
})();

function toggleTheme() {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('expense_theme', next); } catch (e) { /* ignore */ }
  const button = document.getElementById('theme-toggle');
  if (button) button.textContent = next === 'dark' ? 'Light mode' : 'Dark mode';
}

document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('theme-toggle');
  if (!button) return;
  button.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? 'Light mode' : 'Dark mode';
  button.addEventListener('click', toggleTheme);
});