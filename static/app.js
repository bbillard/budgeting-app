const fmt = (n) => `${Number(n).toFixed(2)} €`;
const qs = (id) => document.getElementById(id);

const state = {
  breakdownLevel: 'primary',
  dashboardParentCategory: ''
};

const PIE_COLORS = ['#5A47E6','#06b6d4','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#3b82f6','#f97316','#e11d48','#84cc16','#0ea5e9'];

const FR_MONTHS_SHORT = ['jan', 'fév', 'mar', 'avr', 'mai', 'jun', 'jul', 'aoû', 'sep', 'oct', 'nov', 'déc'];
const FR_MONTHS_FULL = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

function formatMonthLabel(monthKey) {
  const [y, m] = monthKey.split('-').map(Number);
  const mName = FR_MONTHS_SHORT[(m || 1) - 1] || '';
  const yy = String(y || '').slice(-2);
  return `${mName} ${yy}`;
}

function renderCategoryPie(items) {
  if (!items.length) {
    return '<p class="muted">Aucune donnée pour la période sélectionnée.</p>';
  }

  const total = items.reduce((acc, item) => acc + Number(item.amount), 0) || 1;
  const radius = 120;
  const circumference = 2 * Math.PI * radius;

  let offset = 0;
  const circles = items.map((item, idx) => {
    const portion = Number(item.amount) / total;
    const dash = portion * circumference;
    const color = PIE_COLORS[idx % PIE_COLORS.length];
    const circle = `<circle class="pie-slice" data-category="${item.category}" r="${radius}" cx="150" cy="150" fill="transparent" stroke="${color}" stroke-width="48" stroke-dasharray="${dash} ${circumference - dash}" stroke-dashoffset="${-offset}" transform="rotate(-90 150 150)"></circle>`;
    offset += dash;
    return circle;
  }).join('');

  const legend = items.map((item, idx) => {
    const color = PIE_COLORS[idx % PIE_COLORS.length];
    const label = state.breakdownLevel === 'primary'
      ? `<button class="category-link" data-category="${item.category}">${item.category}</button>`
      : `<span class="legend-name">${item.category}</span>`;

    return `<div class="legend-item" data-category="${item.category}">
      <span class="legend-dot" style="background:${color}"></span>
      ${label}
      <span class="legend-val">${fmt(item.amount)} (${item.percentage}%)</span>
    </div>`;
  }).join('');

  return `<div class="pie-wrap">
      <svg width="300" height="300" viewBox="0 0 300 300" aria-label="Camembert catégories">
        <circle r="${radius}" cx="150" cy="150" fill="transparent" stroke="var(--line)" stroke-width="48"></circle>
        ${circles}
      </svg>
      <div class="pie-center">Total dépenses<strong>${fmt(total)}</strong></div>
    </div>
    <div class="pie-legend">${legend}</div>`;
}


function setPieHover(category) {
  const chart = qs('categoriesBars');
  if (!chart) return;

  const slices = chart.querySelectorAll('.pie-slice');
  const legends = chart.querySelectorAll('.legend-item');
  const monthChart = qs('monthlyBars');
  const monthSegments = monthChart ? monthChart.querySelectorAll('.segment') : [];
  const hasCategory = Boolean(category);

  chart.classList.toggle('is-hovering', hasCategory);
  if (monthChart) monthChart.classList.toggle('is-hovering', hasCategory);

  slices.forEach((el) => {
    const match = hasCategory && el.dataset.category === category;
    el.classList.toggle('is-hovered', match);
  });
  legends.forEach((el) => {
    const match = hasCategory && el.dataset.category === category;
    el.classList.toggle('is-hovered', match);
  });
  monthSegments.forEach((el) => {
    const match = hasCategory && el.dataset.category === category;
    el.classList.toggle('is-hovered', match);
  });
}

function bindPieInteractions() {
  const chart = qs('categoriesBars');
  if (!chart) return;

  chart.onmouseover = (e) => {
    const target = e.target.closest('[data-category]');
    if (!target) return;
    setPieHover(target.dataset.category);
  };

  chart.onmouseout = (e) => {
    if (!chart.contains(e.relatedTarget)) {
      setPieHover('');
    }
  };

  chart.onclick = async (e) => {
    const target = e.target.closest('[data-category]');
    if (!target) return;

    if (state.breakdownLevel !== 'primary') return;

    state.dashboardParentCategory = target.dataset.category;
    state.breakdownLevel = 'secondary';
    updateResetFiltersButton();
    await loadDashboard();
    await loadTransactions();
  };
}

function bindMonthlyInteractions() {
  const monthly = qs('monthlyBars');
  if (!monthly) return;

  monthly.onmouseover = (e) => {
    const target = e.target.closest('[data-category]');
    if (!target) return;
    setPieHover(target.dataset.category);
  };

  monthly.onmouseout = (e) => {
    if (!monthly.contains(e.relatedTarget)) {
      setPieHover('');
    }
  };
}

function fillSelect(select, items, placeholderLabel) {
  const previous = select.value;
  select.innerHTML = `<option value="">${placeholderLabel}</option>` + items.map(item => `<option>${item}</option>`).join('');
  if (previous && items.includes(previous)) {
    select.value = previous;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function selectedValues(dropdownId) {
  return [...document.querySelectorAll(`#${dropdownId} .multi-option input:checked`)].map((input) => input.value);
}

function setSelectedValues(dropdownId, values) {
  const wanted = new Set(values);
  document.querySelectorAll(`#${dropdownId} .multi-option input`).forEach((input) => {
    input.checked = wanted.has(input.value);
  });
  updateMultiDropdownLabel(dropdownId);
}

function updateMultiDropdownLabel(dropdownId) {
  const dropdown = qs(dropdownId);
  if (!dropdown) return;

  const selected = selectedValues(dropdownId);
  const labelsByValue = Object.fromEntries(
    [...dropdown.querySelectorAll('.multi-option input')].map((input) => [input.value, input.dataset.label || input.value])
  );
  const placeholder = dropdown.dataset.placeholder || 'Sélectionner';
  const toggle = dropdown.querySelector('.multi-dropdown-toggle');

  if (!selected.length) {
    toggle.textContent = placeholder;
    return;
  }

  const selectedLabels = selected.map((val) => labelsByValue[val] || val);
  toggle.textContent = selectedLabels.length <= 2 ? selectedLabels.join(', ') : `${selectedLabels.length} sélectionnés`;
}

function renderMultiDropdown(dropdownId, items) {
  const dropdown = qs(dropdownId);
  if (!dropdown) return;

  const previous = new Set(selectedValues(dropdownId));
  const menu = dropdown.querySelector('.multi-dropdown-menu');
  menu.innerHTML = items.map((item) => {
    const checked = previous.has(item.value) ? 'checked' : '';
    return `<label class="multi-option"><input type="checkbox" value="${escapeHtml(item.value)}" data-label="${escapeHtml(item.label)}" ${checked} /><span>${escapeHtml(item.label)}</span></label>`;
  }).join('');

  updateMultiDropdownLabel(dropdownId);
}

function initMultiDropdown(dropdownId) {
  const dropdown = qs(dropdownId);
  if (!dropdown) return;

  const toggle = dropdown.querySelector('.multi-dropdown-toggle');
  toggle.onclick = () => {
    if (dropdown.classList.contains('is-disabled')) return;
    document.querySelectorAll('.multi-dropdown.is-open').forEach((el) => {
      if (el !== dropdown) el.classList.remove('is-open');
    });
    dropdown.classList.toggle('is-open');
  };

  dropdown.addEventListener('change', (e) => {
    if (!e.target.matches('.multi-option input')) return;
    updateMultiDropdownLabel(dropdownId);
    updateDateRangeMode();
    updateResetFiltersButton();
  });
}

function hasDateRange() {
  return Boolean(qs('startDate').value || qs('endDate').value);
}

function updateDateRangeMode() {
  const disabled = hasDateRange();
  ['monthFilter', 'yearFilter'].forEach((id) => {
    const el = qs(id);
    if (!el) return;
    el.classList.toggle('is-disabled', disabled);
  });
}

function hasActiveFilters() {
  return Boolean(
    selectedValues('monthFilter').length ||
    selectedValues('yearFilter').length ||
    qs('startDate').value ||
    qs('endDate').value ||
    selectedValues('categoryFilter').length ||
    state.dashboardParentCategory
  );
}

function updateResetFiltersButton() {
  qs('resetFilters').hidden = !hasActiveFilters();
}

function toPrimaryCategory(category) {
  return category.includes(' / ') ? category.split(' / ')[0] : category;
}

async function refreshCategories() {
  const categories = await fetch('/api/categories').then(r => r.json());
  window.ALL_CATEGORIES = categories;

  renderMultiDropdown('categoryFilter', categories.map((name) => ({ value: name, label: name })));
  fillSelect(qs('bulkCategory'), categories, 'Catégorie bulk');
  fillSelect(qs('categoryToDelete'), categories.filter(c => c !== 'À catégoriser'), 'Catégorie à supprimer');

  const parentChoices = [...new Set(categories.map(toPrimaryCategory))].filter(c => c && c !== 'À catégoriser');
  fillSelect(qs('parentForSubcategory'), parentChoices, 'Catégorie parente');
}

async function refreshCategoryTree() {
  const tree = await fetch('/api/categories/tree').then(r => r.json());
  const html = tree.map(node => {
    const children = node.subcategories.map(sub => `<li>${sub}</li>`).join('');
    return `<div><strong>${node.name}</strong>${children ? `<ul>${children}</ul>` : ''}</div>`;
  }).join('');
  qs('categoryTree').innerHTML = html || '<p class="muted">Aucune catégorie.</p>';
}

function currentFilters() {
  const p = new URLSearchParams();
  const useDateRange = hasDateRange();

  const months = selectedValues('monthFilter');
  const years = selectedValues('yearFilter');
  const categories = selectedValues('categoryFilter');

  if (!useDateRange && months.length) p.set('months', months.join('||'));
  if (!useDateRange && years.length) p.set('years', years.join('||'));
  if (qs('startDate').value) p.set('start_date', qs('startDate').value);
  if (qs('endDate').value) p.set('end_date', qs('endDate').value);

  if (categories.length) p.set('categories', categories.join('||'));

  if (state.dashboardParentCategory) p.set('parent_category', state.dashboardParentCategory);
  return p;
}

function renderDashboardScopeLabel() {}

async function loadDashboard() {
  const p = currentFilters();
  p.set('level', state.breakdownLevel);

  const pMonthly = new URLSearchParams(p.toString());
  pMonthly.set('level', state.breakdownLevel);

  const [s, c, m] = await Promise.all([
    fetch(`/api/summary?${p}`).then(r => r.json()),
    fetch(`/api/categories-breakdown?${p}`).then(r => r.json()),
    fetch(`/api/monthly-breakdown?${pMonthly}`).then(r => r.json())
  ]);

  qs('expenses').textContent = fmt(s.expenses);
  qs('income').textContent = fmt(s.income);
  qs('balance').textContent = fmt(s.balance);

  qs('categoriesBars').innerHTML = renderCategoryPie(c);

  const colorByCategory = Object.fromEntries(c.map((item, idx) => [item.category, PIE_COLORS[idx % PIE_COLORS.length]]));
  const max = Math.max(...m.map(x => Number(x.total || 0)), 1);

  qs('monthlyBars').innerHTML = m.map(item => {
    const total = Number(item.total || 0);
    const h = Math.max(12, (total / max) * 220);

    const segments = (item.categories || []).map(cat => {
      const ratio = total > 0 ? (Number(cat.amount) / total) * 100 : 0;
      const colorKey = state.breakdownLevel === 'secondary' ? cat.category : toPrimaryCategory(cat.category);
      const color = colorByCategory[colorKey] || '#94a3b8';
      return `<span class="segment" data-category="${cat.category}" style="height:${ratio}%; background:${color};" title="${cat.category}: ${fmt(cat.amount)}"></span>`;
    }).join('');

    const details = (item.categories || []).map(cat => `${cat.category}: ${fmt(cat.amount)}`).join(' | ');
    return `<div class="bar-wrap" title="${formatMonthLabel(item.month)} — ${fmt(total)}${details ? ' | ' + details : ''}">
      <div class="bar stacked" style="height:${h}px">${segments}</div>
      <small>${formatMonthLabel(item.month)}</small>
    </div>`;
  }).join('');

}

async function loadTransactions() {
  const p = currentFilters();
  if (qs('searchText').value) p.set('search', qs('searchText').value);
  if (qs('onlyUncategorized').checked) p.set('uncategorized', '1');
  if (qs('onlyExcluded').checked) p.set('excluded_only', '1');
  const rows = await fetch(`/api/transactions?${p}`).then(r => r.json());
  const tbody = qs('transactionsTable').querySelector('tbody');
  tbody.innerHTML = rows.map(row => `
    <tr data-id="${row.id}">
      <td><input type="checkbox" class="select-row"/></td>
      <td>${row.date}</td>
      <td>${row.description}</td>
      <td>${fmt(row.amount_original)}</td>
      <td>
        <select class="category-select">${categoryOptions(row.category)}</select>
      </td>
      <td><input type="checkbox" class="exclude-cb" ${row.is_excluded ? 'checked' : ''}/></td>
      <td><input type="number" min="0" max="100" value="${Math.round(row.split_ratio * 100)}" class="split-input"/></td>
      <td>${fmt(row.amount_effective)}</td>
    </tr>
  `).join('');
}

function categoryOptions(current) {
  const ordered = [...window.ALL_CATEGORIES];
  if (current && !ordered.includes(current)) ordered.push(current);
  return ordered.map(c => `<option ${c===current?'selected':''}>${c}</option>`).join('');
}

async function updateRow(tr) {
  const id = tr.dataset.id;
  const category = tr.querySelector('.category-select').value;
  const is_excluded = tr.querySelector('.exclude-cb').checked;
  const split_ratio = Number(tr.querySelector('.split-input').value) / 100;
  await fetch(`/api/transactions/${id}`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({category, is_excluded, split_ratio})
  });
}

function initTabs() {
  document.querySelectorAll('.tab').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      qs(btn.dataset.tab).classList.add('active');
    };
  });
}

async function initCategoryManager() {
  qs('addMainCategory').onclick = async () => {
    const name = qs('newMainCategory').value.trim();
    if (!name) return;
    await fetch('/api/categories', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name})
    });
    qs('newMainCategory').value = '';
    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  };

  qs('addSubCategory').onclick = async () => {
    const parent_name = qs('parentForSubcategory').value;
    const name = qs('newSubCategory').value.trim();
    if (!parent_name || !name) return;
    await fetch('/api/categories', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, parent_name})
    });
    qs('newSubCategory').value = '';
    await refreshCategories();
    await refreshCategoryTree();
  };

  qs('deleteCategory').onclick = async () => {
    const name = qs('categoryToDelete').value;
    if (!name) return;
    if (!confirm(`Supprimer la catégorie "${name}" ?`)) return;

    await fetch('/api/categories/delete', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name})
    });

    if (state.dashboardParentCategory === name || state.dashboardParentCategory === toPrimaryCategory(name)) {
      state.dashboardParentCategory = '';
      state.breakdownLevel = 'primary';
    }

    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  };
}

async function init() {
  window.ALL_CATEGORIES = [];
  const monthItems = FR_MONTHS_FULL.map((label, idx) => ({ value: String(idx + 1), label }));
  renderMultiDropdown('monthFilter', monthItems);

  const y = new Date().getFullYear();
  const yearItems = [];
  for (let d = y - 5; d <= y + 1; d++) yearItems.push({ value: String(d), label: String(d) });
  renderMultiDropdown('yearFilter', yearItems);

  initTabs();
  await refreshCategories();
  await refreshCategoryTree();
  await initCategoryManager();
  bindPieInteractions();
  bindMonthlyInteractions();
  initMultiDropdown('monthFilter');
  initMultiDropdown('yearFilter');
  initMultiDropdown('categoryFilter');

  document.addEventListener('click', (e) => {
    document.querySelectorAll('.multi-dropdown.is-open').forEach((el) => {
      if (!el.contains(e.target)) el.classList.remove('is-open');
    });
  });

  qs('applyFilters').onclick = async () => { updateDateRangeMode(); updateResetFiltersButton(); await loadDashboard(); await loadTransactions(); };
  qs('searchText').oninput = () => loadTransactions();
  qs('onlyUncategorized').onchange = () => loadTransactions();
  qs('onlyExcluded').onchange = () => loadTransactions();

  ['startDate', 'endDate'].forEach((id) => {
    qs(id).addEventListener('input', () => { updateDateRangeMode(); updateResetFiltersButton(); });
    qs(id).addEventListener('change', () => { updateDateRangeMode(); updateResetFiltersButton(); });
  });

  qs('resetFilters').onclick = async () => {
    setSelectedValues('monthFilter', []);
    setSelectedValues('yearFilter', []);
    setSelectedValues('categoryFilter', []);
    qs('startDate').value = '';
    qs('endDate').value = '';
    state.dashboardParentCategory = '';
    state.breakdownLevel = 'primary';
    updateDateRangeMode();
    updateResetFiltersButton();
    await loadDashboard();
    await loadTransactions();
  };


  qs('clearDashboardScope').onclick = async () => {
    state.dashboardParentCategory = '';
    state.breakdownLevel = 'primary';
    updateResetFiltersButton();
    await loadDashboard();
    await loadTransactions();
  };


  qs('transactionsTable').addEventListener('change', async (e) => {
    if (e.target.classList.contains('select-row')) return;
    const tr = e.target.closest('tr');
    if (!tr) return;
    await updateRow(tr);
    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  });

  qs('bulkApply').onclick = async () => {
    const category = qs('bulkCategory').value;
    const ids = [...document.querySelectorAll('.select-row:checked')].map(cb => Number(cb.closest('tr').dataset.id));
    if (!category || !ids.length) return;
    await fetch('/api/transactions/bulk-update', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ids, category})
    });
    await refreshCategories();
    await refreshCategoryTree();
    await loadTransactions();
    await loadDashboard();
  };

  qs('importBtn').onclick = async () => {
    const file = qs('csvFile').files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/import-csv', {method:'POST', body:fd});
    const json = await res.json();
    qs('importStatus').textContent = json.error || `${json.imported} ligne(s) importée(s)`;
    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  };

  qs('exportCsv').onclick = () => window.open(`/api/export.csv?${currentFilters()}`, '_blank');
  qs('backupJson').onclick = async () => {
    const r = await fetch(`/api/backup.json?${currentFilters()}`).then(x=>x.json());
    alert(`Backup créé: ${r.path} (${r.rows} lignes)`);
  };
  qs('resetDb').onclick = async () => {
    if (!confirm('Confirmer reset complet ?')) return;
    await fetch('/api/reset', {method:'POST'});
    state.dashboardParentCategory = '';
    state.breakdownLevel = 'primary';
    updateResetFiltersButton();
    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  };

  qs('themeBtn').onclick = () => document.body.classList.toggle('dark');

  updateDateRangeMode();
  updateResetFiltersButton();
  await loadDashboard();
  await loadTransactions();
}

init();
