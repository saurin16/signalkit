const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const ordinal = (value) => { const n=Math.round(value); const suffix=(n%100>=11&&n%100<=13)?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th'); return `${n}${suffix}`; };
let cities = [];
let state = {packages: [], sites: []};
let lastRun = null;

function option(value, selected) { return `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${esc(value)}</option>`; }
function orientationOptions(selected, includeBoth) { return (includeBoth ? ['both','landscape','portrait'] : ['landscape','portrait']).map(v => option(v, selected)).join(''); }
function renderEditors() {
  $('#packages').innerHTML = state.packages.map((p, i) => `<div class="entry" data-kind="package" data-index="${i}"><div class="entry-index">${String(i+1).padStart(2,'0')}</div><div class="fields"><div class="field"><label>Package ID</label><input data-key="id" value="${esc(p.id)}" maxlength="32" aria-label="Package ${i+1} ID"></div><div class="field"><label>Creative name</label><input data-key="title" value="${esc(p.title)}" maxlength="60" aria-label="Package ${i+1} name"></div><div class="field"><label>Artist anchor</label><input data-key="artist" value="${esc(p.artist)}" maxlength="80" aria-label="Package ${i+1} artist"></div><div class="field"><label>Format</label><select data-key="orientation" aria-label="Package ${i+1} format">${orientationOptions(p.orientation,true)}</select></div></div><button class="delete" type="button" data-remove="package" data-index="${i}" aria-label="Remove package ${i+1}">×</button></div>`).join('');
  $('#sites').innerHTML = state.sites.map((s, i) => `<div class="entry" data-kind="site" data-index="${i}"><div class="entry-index">${String(i+1).padStart(2,'0')}</div><div class="fields"><div class="field"><label>Site ID</label><input data-key="id" value="${esc(s.id)}" maxlength="32" aria-label="Site ${i+1} ID"></div><div class="field"><label>Site name</label><input data-key="name" value="${esc(s.name)}" maxlength="80" aria-label="Site ${i+1} name"></div><div class="field"><label>Metro</label><select data-key="city" aria-label="Site ${i+1} metro">${cities.map(c=>option(c,s.city)).join('')}</select></div><div class="field"><label>Screen</label><select data-key="orientation" aria-label="Site ${i+1} screen">${orientationOptions(s.orientation,false)}</select></div></div><button class="delete" type="button" data-remove="site" data-index="${i}" aria-label="Remove site ${i+1}">×</button></div>`).join('');
  $('#packageCount').textContent = String(state.packages.length).padStart(2,'0');
  $('#siteCount').textContent = String(state.sites.length).padStart(2,'0');
  $('#addPackage').disabled = state.packages.length >= 5;
  $('#addSite').disabled = state.sites.length >= 12;
}
function setState(example) { state = structuredClone(example); lastRun = null; $('#results').hidden = true; $('#error').hidden = true; renderEditors(); }

document.addEventListener('input', e => {
  const entry = e.target.closest('.entry');
  const key = e.target.dataset.key;
  if (!entry || !key) return;
  const collection = entry.dataset.kind === 'package' ? state.packages : state.sites;
  collection[Number(entry.dataset.index)][key] = e.target.value;
});
document.addEventListener('change', e => {
  if (!e.target.matches('select[data-key]')) return;
  const entry = e.target.closest('.entry');
  (entry.dataset.kind === 'package' ? state.packages : state.sites)[Number(entry.dataset.index)][e.target.dataset.key] = e.target.value;
});
document.addEventListener('click', e => {
  const button = e.target.closest('[data-remove]');
  if (!button) return;
  const arr = button.dataset.remove === 'package' ? state.packages : state.sites;
  if (arr.length <= (button.dataset.remove === 'package' ? 2 : 1)) return;
  arr.splice(Number(button.dataset.index), 1); renderEditors();
});
$('#addPackage').addEventListener('click', () => { if(state.packages.length>=5)return; const n=state.packages.length+1; state.packages.push({id:`PKG-${n}`,title:'New creative',artist:'',orientation:'both'});renderEditors();$('#packages .entry:last-child input[data-key="artist"]').focus(); });
$('#addSite').addEventListener('click', () => { if(state.sites.length>=12)return; const n=state.sites.length+1; state.sites.push({id:`SITE-${n}`,name:'New installation',city:'Chicago, IL',orientation:'landscape'});renderEditors();$('#sites .entry:last-child input[data-key="name"]').focus(); });

function showError(message) { $('#error').textContent = message; $('#error').hidden = false; }
function validate() {
  if (state.packages.some(p => !p.id.trim() || !p.title.trim() || !p.artist.trim())) return 'Complete the ID, name and artist for every package.';
  if (state.sites.some(s => !s.id.trim() || !s.name.trim() || !s.city)) return 'Complete every site and choose a metro.';
  if (new Set(state.packages.map(p=>p.id)).size !== state.packages.length) return 'Package IDs must be unique.';
  if (new Set(state.sites.map(s=>s.id)).size !== state.sites.length) return 'Site IDs must be unique.';
  return null;
}

$('#analyzeBtn').addEventListener('click', async () => {
  $('#error').hidden = true;
  const problem = validate(); if (problem) return showError(problem);
  const button = $('#analyzeBtn'); button.disabled = true; button.querySelector('span:first-child').textContent = 'Reading live Qloo signals…';
  try {
    const response = await fetch('/api/analyze', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Analysis failed. Please retry.');
    lastRun = result; renderResults(result); $('#results').hidden = false; $('#results').scrollIntoView({behavior:'smooth',block:'start'});
  } catch (err) { showError(err.message); }
  finally {button.disabled = false; button.querySelector('span:first-child').textContent = 'Analyze site fit';}
});

function renderResults(run) {
  const clear = run.assignments.filter(a => a.confidence !== 'review').length;
  const review = run.assignments.length - clear;
  $('#resultTime').textContent = `${(run.elapsed_ms / 1000).toFixed(1)}s`;
  $('#summaryStrip').innerHTML = `<div class="summary-item"><strong>${run.sites.length}</strong><span>sites analyzed<br>with live Qloo data</span></div><div class="summary-item"><strong>${clear}</strong><span>clear assignments<br>ready for technician check</span></div><div class="summary-item"><strong>${review}</strong><span>sites flagged<br>for extra review</span></div>`;
  $('#matrix').innerHTML = `<table class="matrix"><thead><tr><th>INSTALLATION SITE</th>${run.packages.map(p=>`<th>${esc(p.title)}<br><small>${esc(p.artist)}</small></th>`).join('')}</tr></thead><tbody>${run.assignments.map(a=>`<tr><td class="city">${esc(a.site.city)}<br><small style="color:#8ea1af;font-weight:400">${esc(a.site.name)}</small></td>${a.options.map(o=>{const val=o.percentile;return `<td><div class="bar-cell"><div class="bar ${a.winner===o.package_id?'winner':''}"><span style="width:${val===null?0:Math.max(2,Math.min(100,val))}%"></span></div><b>${val===null?'—':Math.round(val)}</b></div>${!o.compatible?'<small style="color:#f6a96e">Format mismatch</small>':''}</td>`;}).join('')}</tr>`).join('')}</tbody></table>`;
  $('#assignments').innerHTML = run.assignments.map(a=>{const pkg=run.packages.find(p=>p.id===a.winner);const win=a.options.find(o=>o.package_id===a.winner);const choices=a.options.filter(o=>o.eligible);return `<article class="assignment"><div class="assignment-top"><div class="assignment-tag"><span>${esc(a.site.id)} · ${esc(a.site.orientation.toUpperCase())}</span><span class="status ${a.confidence==='review'?'review':''}">${a.confidence==='review'?'REVIEW':a.confidence==='manual'?'TECH CHOICE':'CLEAR FIT'}</span></div><h4>${esc(a.site.name)}</h4><div class="sub">${esc(a.site.city)}</div></div><div class="assignment-bottom"><div class="pkg-icon">✳</div><div><strong>${pkg?esc(pkg.title):'No assignment'}</strong><small>${pkg?`${esc(pkg.id)} · ${win?ordinal(win.percentile):'—'} percentile`:'Check package compatibility'}</small></div></div><div class="assignment-note">${esc(a.reason)}</div><label class="override-label">Technician choice<select data-override="${esc(a.site.id)}" ${choices.length?'':'disabled'} aria-label="Package for ${esc(a.site.name)}">${choices.map(o=>`<option value="${esc(o.package_id)}" ${o.package_id===a.winner?'selected':''}>${esc(o.title)} · ${ordinal(o.percentile)}</option>`).join('')}</select></label></article>`;}).join('');
  $('#traceContent').innerHTML = run.trace.map(t=>`<div class="trace-row"><div><strong>${esc(t.agent)}</strong> — ${esc(t.result)}</div><span>${t.calls} QLOO CALL${t.calls===1?'':'S'}</span></div>`).join('')+run.qloo_calls.map(c=>`<div class="trace-row"><div>${esc(c.endpoint)} — ${esc(c.purpose)}</div><span>${c.cached?'CACHED':c.status+' · '+c.ms+'ms'}</span></div>`).join('');
  $('#approveBtn').hidden = false; $('#approveBtn').disabled = false; $('#approveBtn').innerHTML = 'Approve deployment <span>→</span>'; $('#exportBtn').hidden = true;
}

$('#assignments').addEventListener('change', async e => {
  const select = e.target.closest('select[data-override]');
  if (!select || !lastRun) return;
  select.disabled = true;
  try {
    const response = await fetch(`/api/runs/${encodeURIComponent(lastRun.id)}/assignments/${encodeURIComponent(select.dataset.override)}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({package_id:select.value})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Could not save technician choice.');
    const index = lastRun.assignments.findIndex(a => a.site.id === select.dataset.override);
    lastRun.assignments[index] = result.assignment;
    lastRun.approved = false;
    renderResults(lastRun);
  } catch (err) {showError(err.message); select.disabled = false;}
});

$('#approveBtn').addEventListener('click', async () => {
  if (!lastRun) return;
  const btn = $('#approveBtn'); btn.disabled = true;
  try {
    const response = await fetch(`/api/runs/${encodeURIComponent(lastRun.id)}/approve`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({approved:true})});
    if (!response.ok) throw new Error('Approval could not be saved. Please retry.');
    btn.hidden = true; $('#exportBtn').hidden = false; $('#exportBtn').href = `/api/runs/${encodeURIComponent(lastRun.id)}/export.csv`;
  } catch (err) {showError(err.message);btn.disabled=false;}
});

let example = null;
async function boot(){
  try { const response=await fetch('/api/config'); if(!response.ok)throw new Error(); const data=await response.json();cities=data.cities;example=data.example;setState(example);}
  catch {showError('Could not load the app configuration. Please refresh.');}
}
$('#resetBtn').addEventListener('click',()=>{if(example)setState(example);});
boot();
