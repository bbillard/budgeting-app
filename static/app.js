const fmt = (n) => `${Number(n).toFixed(2)} €`;
const qs = (id) => document.getElementById(id);

const state = {
  breakdownLevel: 'primary',
  dashboardParentCategory: ''
};

const PIE_COLORS = ['#5A47E6','#06b6d4','#22c55e','#f59e0b','#ef4444','#8b5cf6','#14b8a6','#3b82f6','#f97316','#e11d48','#84cc16','#0ea5e9'];

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
    const circle = `<circle r="${radius}" cx="150" cy="150" fill="transparent" stroke="${color}" stroke-width="48" stroke-dasharray="${dash} ${circumference - dash}" stroke-dashoffset="${-offset}" transform="rotate(-90 150 150)"></circle>`;
    offset += dash;
    return circle;
  }).join('');

  const legend = items.map((item, idx) => {
    const color = PIE_COLORS[idx % PIE_COLORS.length];
    const label = state.breakdownLevel === 'primary'
      ? `<button class="category-link" data-category="${item.category}">${item.category}</button>`
      : `<span class="legend-name">${item.category}</span>`;

    return `<div class="legend-item">
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


function fillSelect(select, items, placeholderLabel) {
  const previous = select.value;
  select.innerHTML = `<option value="">${placeholderLabel}</option>` + items.map(item => `<option>${item}</option>`).join('');
  if (previous && items.includes(previous)) {
    select.value = previous;
  }
}

function toPrimaryCategory(category) {
  return category.includes(' / ') ? category.split(' / ')[0] : category;
}

async function refreshCategories() {
  const categories = await fetch('/api/categories').then(r => r.json());
  window.ALL_CATEGORIES = categories;

  fillSelect(qs('categoryFilter'), categories, 'Toutes catégories');
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
  if (qs('month').value) p.set('month', qs('month').value);
  if (qs('year').value) p.set('year', qs('year').value);
  if (qs('startDate').value) p.set('start_date', qs('startDate').value);
  if (qs('endDate').value) p.set('end_date', qs('endDate').value);
  if (qs('categoryFilter').value) p.set('category', qs('categoryFilter').value);
  if (qs('includeExcluded').checked) p.set('include_excluded', '1');
  if (state.dashboardParentCategory) p.set('parent_category', state.dashboardParentCategory);
  return p;
}

function renderDashboardScopeLabel() {
  const label = state.dashboardParentCategory
    ? `Vue filtrée sur "${state.dashboardParentCategory}"`
    : 'Vue globale';
  qs('dashboardScopeLabel').textContent = `${label} — niveau: ${state.breakdownLevel === 'primary' ? 'catégories principales' : 'sous-catégories'}`;
  qs('toggleBreakdownLevel').textContent = state.breakdownLevel === 'primary' ? 'Afficher secondaires' : 'Afficher principales';
}

async function loadDashboard() {
  const p = currentFilters();
  p.set('level', state.breakdownLevel);

  const [s, c, m] = await Promise.all([
    fetch(`/api/summary?${p}`).then(r => r.json()),
    fetch(`/api/categories-breakdown?${p}`).then(r => r.json()),
    fetch(`/api/monthly?${p}`).then(r => r.json())
  ]);

  qs('expenses').textContent = fmt(s.expenses);
  qs('income').textContent = fmt(s.income);
  qs('balance').textContent = fmt(s.balance);

  qs('categoriesBars').innerHTML = renderCategoryPie(c);

  const max = Math.max(...m.map(x => x.expenses), 1);
  qs('monthlyBars').innerHTML = m.map(item => {
    const h = Math.max(8, (item.expenses / max) * 140);
    return `<div class="bar" style="height:${h}px" title="${item.month} ${fmt(item.expenses)}"><small>${item.month.slice(5)}</small></div>`;
  }).join('');

  renderDashboardScopeLabel();
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
  for (let m=1;m<=12;m++) qs('month').innerHTML += `<option value="${m}">${m}</option>`;
  const y = new Date().getFullYear();
  for (let d=y-5; d<=y+1; d++) qs('year').innerHTML += `<option value="${d}">${d}</option>`;

  initTabs();
  await refreshCategories();
  await refreshCategoryTree();
  await initCategoryManager();

  qs('applyFilters').onclick = async () => { await loadDashboard(); await loadTransactions(); };
  qs('searchText').oninput = () => loadTransactions();
  qs('onlyUncategorized').onchange = () => loadTransactions();
  qs('onlyExcluded').onchange = () => loadTransactions();

  qs('toggleBreakdownLevel').onclick = async () => {
    state.breakdownLevel = state.breakdownLevel === 'primary' ? 'secondary' : 'primary';
    await loadDashboard();
  };

  qs('clearDashboardScope').onclick = async () => {
    state.dashboardParentCategory = '';
    state.breakdownLevel = 'primary';
    await loadDashboard();
    await loadTransactions();
  };

  qs('categoriesBars').addEventListener('click', async (e) => {
    const btn = e.target.closest('button.category-link');
    if (!btn) return;
    state.dashboardParentCategory = btn.dataset.category;
    state.breakdownLevel = 'secondary';
    await loadDashboard();
    await loadTransactions();
  });

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
    await refreshCategories();
    await refreshCategoryTree();
    await loadDashboard();
    await loadTransactions();
  };

  qs('themeBtn').onclick = () => document.body.classList.toggle('dark');

  await loadDashboard();
  await loadTransactions();
}

init();
