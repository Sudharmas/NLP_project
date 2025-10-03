const api = {
  connect: async (connStr) => {
    const res = await fetch('/api/connect-database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ connection_string: connStr })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Connection failed');
    return res.json();
  },
  upload: async (files) => {
    const fd = new FormData();
    for (const f of files) fd.append('files', f);
    const res = await fetch('/api/upload-documents', { method: 'POST', body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || 'Upload failed');
    return res.json();
  },
  status: async (jobId) => (await fetch(`/api/ingestion-status/${jobId}`)).json(),
  query: async (query, page, pageSize) => {
    const res = await fetch('/api/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, page, page_size: pageSize })
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Query failed');
    return res.json();
  },
  schema: async () => (await fetch('/api/schema')).json(),
  history: async () => (await fetch('/api/query/history')).json()
};

const statusEl = document.getElementById('status');
const connectMsg = document.getElementById('connectMsg');
const schemaView = document.getElementById('schemaView');
const uploadMsg = document.getElementById('uploadMsg');
const ingestStatus = document.getElementById('ingestStatus');
const metrics = document.getElementById('metrics');
const results = document.getElementById('results');
const historySel = document.getElementById('history');

async function refreshSchema() {
  try {
    const s = await api.schema();
    schemaView.textContent = JSON.stringify(s.schema, null, 2);
  } catch {}
}

async function refreshHistory() {
  const h = await api.history();
  historySel.innerHTML = '<option value="">History</option>' + h.map(it => `<option>${it.query}</option>`).join('');
}

function renderTable(data) {
  if (!data || !data.rows) return '<div>No rows</div>';
  const cols = data.columns || Object.keys(data.rows[0] || {});
  const header = `<tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr>`;
  const rows = data.rows.map(r => `<tr>${cols.map(c => `<td>${r[c] ?? ''}</td>`).join('')}</tr>`).join('');
  return `<table>${header}${rows}</table>`;
}

function renderDocs(docs) {
  if (!docs || !docs.length) return '<div>No documents</div>';
  return `<div class="cards">${docs.map(d => `<div class="card"><pre>${(d.text||'').slice(0,1200)}</pre><div class="meta">${JSON.stringify(d.metadata)}</div></div>`).join('')}</div>`;
}

async function init() {
  document.getElementById('btnConnect').onclick = async () => {
    const connStr = document.getElementById('connStr').value.trim();
    connectMsg.textContent = 'Connecting...';
    try {
      const res = await api.connect(connStr);
      connectMsg.textContent = 'Connected!';
      await refreshSchema();
    } catch (e) {
      connectMsg.textContent = e.message;
    }
  };

  document.getElementById('btnUpload').onclick = async () => {
    const files = document.getElementById('fileInput').files;
    if (!files || files.length === 0) {
      uploadMsg.textContent = 'Please select one or more files before uploading.';
      return;
    }
    uploadMsg.textContent = 'Uploading...';
    try {
      const { job_id, accepted } = await api.upload(files);
      uploadMsg.textContent = `Job ${job_id} started. Accepted files: ${accepted}`;
      const poll = setInterval(async () => {
        const st = await api.status(job_id);
        ingestStatus.textContent = JSON.stringify(st, null, 2);
        if (st.status === 'completed' || st.status === 'failed') clearInterval(poll);
      }, 1000);
    } catch (e) {
      uploadMsg.textContent = e.message;
    }
  };

  document.getElementById('btnQuery').onclick = async () => {
    const q = document.getElementById('queryInput').value.trim();
    metrics.textContent = 'Processing...';
    results.innerHTML = '';
    try {
      const res = await api.query(q, 1, 50);
      metrics.innerHTML = `Type: ${res.query_type} | Time: ${res.performance.response_time_ms} ms | Cache hit: ${res.cache.hit}`;
      if (res.query_type === 'sql') {
        results.innerHTML = renderTable(res.results);
      } else if (res.query_type === 'document') {
        results.innerHTML = renderDocs(res.results);
      } else if (res.query_type === 'hybrid') {
        results.innerHTML = `<h3>Table</h3>${renderTable(res.results.table)}<h3>Documents</h3>${renderDocs(res.results.documents)}`;
      } else {
        results.textContent = JSON.stringify(res.results, null, 2);
      }
      await refreshHistory();
    } catch (e) {
      metrics.textContent = e.message;
    }
  };

  historySel.onchange = () => {
    document.getElementById('queryInput').value = historySel.value;
  };

  await refreshSchema();
  await refreshHistory();
}

window.addEventListener('DOMContentLoaded', init);
