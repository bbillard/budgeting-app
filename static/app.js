const fmt = (n) => `${Number(n).toFixed(2)} €`;
const qs = (id) => document.getElementById(id);

function currentFilters() {
  const p = new URLSearchParams();
  if (qs('month').value) p.set('month', qs('month').value);
  if (qs('year').value) p.set('year', qs('year').value);
  if (qs('startDate').value) p.set('start_date', qs('startDate').value);
  if (qs('endDate').value) p.set('end_date', qs('endDate').value);
  if (qs('categoryFilter').value) p.set('category', qs('categoryFilter').value);
  if (qs('includeExcluded').checked) p.set('include_excluded', '1');
  return p;
}

async function loadDashboard() {
  const p = currentFilters();
  const [s, c, m] = await Promise.all([
    fetch(`/api/summary?${p}`).then(r => r.json()),
    fetch(`/api/categories-breakdown?${p}`).then(r => r.json()),
    fetch(`/api/monthly?${p}`).then(r => r.json())
  ]);

  qs('expenses').textContent = fmt(s.expenses);
  qs('income').textContent = fmt(s.income);
  qs('balance').textContent = fmt(s.balance);

  qs('categoriesBars').innerHTML = c.map(item => `
    <div class="barline"><strong>${item.category}</strong> — ${fmt(item.amount)} (${item.percentage}%)
      <div class="progress"><span style="width:${item.percentage}%"></span></div>
    </div>
  `).join('');

  const max = Math.max(...m.map(x => x.expenses), 1);
  qs('monthlyBars').innerHTML = m.map(item => {
    const h = Math.max(8, (item.expenses / max) * 140);
    return `<div class="bar" style="height:${h}px" title="${item.month} ${fmt(item.expenses)}"><small>${item.month.slice(5)}</small></div>`;
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
  return window.ALL_CATEGORIES.map(c => `<option ${c===current?'selected':''}>${c}</option>`).join('');
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

async function init() {
  window.ALL_CATEGORIES = [...qs('categoryFilter').options].slice(1).map(o => o.value);
  for (let m=1;m<=12;m++) qs('month').innerHTML += `<option value="${m}">${m}</option>`;
  const y = new Date().getFullYear();
  for (let d=y-5; d<=y+1; d++) qs('year').innerHTML += `<option value="${d}">${d}</option>`;

  initTabs();
  qs('applyFilters').onclick = async () => { await loadDashboard(); await loadTransactions(); };
  qs('searchText').oninput = () => loadTransactions();
  qs('onlyUncategorized').onchange = () => loadTransactions();
  qs('onlyExcluded').onchange = () => loadTransactions();

  qs('transactionsTable').addEventListener('change', async (e) => {
    const tr = e.target.closest('tr');
    if (!tr) return;
    await updateRow(tr);
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
    await loadDashboard();
    await loadTransactions();
  };

  qs('themeBtn').onclick = () => document.body.classList.toggle('dark');

  await loadDashboard();
  await loadTransactions();
}

init();
