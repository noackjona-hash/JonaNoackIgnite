// IGNITE MEDICAL WORKSTATION · INSPECTOR-PANELS, ANALYTIK-ANZEIGE, BERICHTE & EXPORTE
const $ = id => document.getElementById(id);
const fmt = (v, d = 1) => (v === undefined || v === null || isNaN(v)) ? '--' : v.toFixed(d);
const DIAG_DE = { INFLAMMATION: 'Entzündungsherd', PRESSURE_POINT: 'Druckstelle', INFLAMED_PRESSURE_POINT: 'Entzündete Druckstelle', BENIGN: 'Unkritisch' };
const OVERRIDES = ['', 'Entzündungsherd', 'Ulkus-Präcursor', 'Phlegmone / Abszessverdacht', 'Druckstelle', 'Venenstrang / Artefakt', 'Unkritisch'];
const hsLabel = (hs, i) => (S.overrides[i] || DIAG_DE[hs.assessment.diagnosis_type || hs.region.diagnosis_type] || hs.region.diagnosis_type);
const riskChip = r => r === 'CRITICAL' ? '<span class="chip crit">KRITISCH</span>' : r === 'MODERATE' ? '<span class="chip warn">MÄSSIG</span>' : '<span class="chip ok">UNKRITISCH</span>';
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

function patientPseudonym(name) { let h = 2166136261; for (const c of name) { h ^= c.charCodeAt(0); h = Math.imul(h, 16777619) >>> 0; } return 'ANON-' + h.toString(16).padStart(8, '0') + (h * 31 >>> 0).toString(16).padStart(4, '0').slice(0, 4); }

function updateUIFromResults(res) {
    // 1. Herde-Tabelle (klickbar, mit ärztlichem Override)
    const container = $('hotspot-list-container'); $('hotspot-count-badge').textContent = `${res.total_hotspots} HERD${res.total_hotspots === 1 ? '' : 'E'}`;
    if (!res.hotspots || !res.hotspots.length) {
        container.innerHTML = `<div class="empty-state"><div class="empty-icon" style="color:#22C55E">✓</div><div class="empty-text">Keine pathologischen Entzündungsherde detektiert. Gewebe im Normbereich.</div></div>`;
    } else {
        container.innerHTML = '';
        res.hotspots.forEach((hs, i) => {
            const isCrit = hs.assessment.risk_level === 'CRITICAL', card = document.createElement('div'); card.className = 'hotspot-card';
            const conf = hs.region.confidence_score || 0;
            card.innerHTML = `<div class="hotspot-header"><span class="hotspot-title">Fokus #${i + 1} (${hs.region.center_x}, ${hs.region.center_y})</span>
                <span class="sev-badge ${isCrit ? 'sev-critical' : 'sev-warning'}">${hs.assessment.risk_level}</span></div>
                <div class="hotspot-stats"><span>Fläche: ${hs.region.area_pixels} px (${(hs.region.area_pixels * PX_MM * PX_MM / 100).toFixed(1)} cm²)</span>
                <span>Max: ${tempOf(hs.region.max_val).toFixed(1)} °C</span><span style="color:#F59E0B">ΔT: +${(hs.region.contra_delta * TEMP_STEP).toFixed(1)} K</span></div>
                <div class="hotspot-stats"><span>Klasse: <b>${esc(hsLabel(hs, i))}</b></span><span>Konfidenz ${conf.toFixed(0)} %</span></div>
                <div class="conf-meter"><div style="width:${conf}%"></div></div>
                <div class="hotspot-rec">${esc(hs.assessment.recommendation)}</div>
                <select class="hs-override" title="Ärztliche Diagnose-Korrektur">${OVERRIDES.map(o => `<option ${S.overrides[i] === o || (!S.overrides[i] && !o) ? 'selected' : ''} value="${o}">${o || '— automatische Klassifikation —'}</option>`).join('')}</select>`;
            card.addEventListener('click', e => { if (e.target.tagName !== 'SELECT') focusRegion(hs.region.bounding_box); });
            card.querySelector('select').addEventListener('change', e => { pushUndo(); if (e.target.value) S.overrides[i] = e.target.value; else delete S.overrides[i]; updateUIFromResults(res); toast('Diagnose angepasst'); });
            container.appendChild(card);
        });
    }
    // 2. Risikostufe + Handlungsempfehlungen
    const fill = $('risk-score-fill'), title = $('risk-tier-title'), rec = $('risk-recommendation'), pill = $('triage-status-pill'), tt = $('triage-text');
    let acts;
    if (res.highest_risk === 'CRITICAL') {
        fill.style.width = '95%'; fill.style.background = '#DC2626'; title.textContent = 'Stufe 3: Akutes Prä-Ulkus (Armstrong-Alarm)'; title.style.color = '#F87171';
        rec.textContent = 'Pathologische Hyperthermie ΔT ≥ 2,2 K. Sofortige Druckentlastung und ärztliche Inspektion.';
        pill.style.cssText = 'background:rgba(220,38,38,.2);border-color:rgba(239,68,68,.4);color:#FECACA'; tt.textContent = 'CRITICAL: ARMSTRONG-ALARM';
        acts = ['Sofortige Druckentlastung (Total-Contact-Cast / Entlastungsschuh)', 'Ärztliche Inspektion, ggf. Debridement innerhalb von 24 h', 'Infekt-/Osteomyelitis-Abklärung (CRP, Röntgen/MRT)', 'Gefäßstatus prüfen (ABI/TBI, Revaskularisation erwägen)', 'ΔT-Kontrolle in 48–72 h (IWGDF 2023)'];
    } else if (res.highest_risk === 'MODERATE') {
        fill.style.width = '55%'; fill.style.background = '#F59E0B'; title.textContent = 'Stufe 1–2: Biomechanische Druckstelle'; title.style.color = '#FBBF24';
        rec.textContent = 'Subklinische Überwärmung. Orthopädische Schuhzurichtung prüfen.';
        pill.style.cssText = 'background:rgba(245,158,11,.2);border-color:rgba(245,158,11,.4);color:#FEF3C7'; tt.textContent = 'MODERATE RISIKO';
        acts = ['Orthopädische Einlagen / Schuhzurichtung prüfen', 'Tägliche Fußinspektion durch Patient', 'Thermografie-Kontrolle in 2 Wochen'];
    } else {
        fill.style.width = '15%'; fill.style.background = '#16A34A'; title.textContent = 'Physiologische Normaltemperatur'; title.style.color = '#4ADE80';
        rec.textContent = 'Keine signifikante thermische Asymmetrie nachweisbar (ΔT < 2,2 K).';
        pill.style.cssText = ''; tt.textContent = 'BENIGN: UNKRITISCH';
        acts = ['Regelmäßige Fußpflege & Selbstinspektion', 'Routinekontrolle nach IWGDF-Risikostratifizierung'];
    }
    $('action-list').innerHTML = acts.map(a => `<li>${a}</li>`).join('');
    // 3. Pipeline, 3D, Bioheat
    $('timing-total-val').textContent = `${fmt(res.timing.total_ms, 1)} ms`;
    const sc = $('stages-list-container'); sc.innerHTML = '';
    (res.stages || []).forEach(s => { const r = document.createElement('div'); r.className = 'stage-row'; r.title = s.description || '';
        r.innerHTML = `<span class="stage-num">${s.stage_number}</span><span class="stage-name">${esc(s.name)}</span><span class="stage-time">${(s.duration_us / 1000).toFixed(2)} ms</span>`; sc.appendChild(r); });
    $('recon-max-depth').textContent = `${fmt(res.max_depth_mm, 1)} mm`; $('recon-edge-comp').textContent = `+${fmt(res.edge_correction_k, 2)} K`;
    $('bioheat-mean').textContent = `${fmt(res.bioheat_mean, 1)} ml/min/100g`; $('bioheat-hyper').textContent = `${fmt(res.bioheat_hyper_pct, 1)} %`;
    $('bioheat-status').textContent = res.perfusion_status || '--';
    $('val-anatomy').textContent = 'Gewebe nicht fokussiert';
    updateAnalytics(); refreshAudit();
}

function updateAnalytics() {
    if (!S.gray) return;
    const z = zoneStats(S); S.zones = z; const tb = $('tbl-zones').querySelector('tbody'); tb.innerHTML = '';
    z.rows.forEach(r => { const st = isNaN(r.delta) ? '—' : r.delta >= 2.2 ? '<span class="chip crit">Armstrong</span>' : r.delta >= 1.0 ? '<span class="chip warn">Beobachten</span>' : '<span class="chip ok">Symmetrisch</span>';
        tb.insertAdjacentHTML('beforeend', `<tr><td>${r.n}</td><td>${fmt(r.left)}</td><td>${fmt(r.right)}</td><td>${fmt(r.delta, 2)}</td><td>${st}</td></tr>`); });
    $('m-tai').textContent = isNaN(z.tai) ? '--' : `${z.tai.toFixed(2)} K`;
    const p5 = percentile(S.gray, S.otsu, .05), p95 = percentile(S.gray, S.otsu, .95); $('m-thdi').textContent = `${((p95 - p5) * TEMP_STEP).toFixed(1)} K (P95−P5)`;
    const ab = $('tbl-angio').querySelector('tbody'); ab.innerHTML = '';
    z.rows.forEach(r => ab.insertAdjacentHTML('beforeend', `<tr><td>${r.terr}</td><td style="font-family:inherit">${r.artery}</td><td>${fmt(r.delta, 1)}</td></tr>`));
    $('zone-grid').innerHTML = z.rows.map(r => `<div class="zone-card"><span class="zone-name">${r.n}</span><span class="zone-temp">${fmt((r.left + r.right) / 2)} °C</span><span class="zone-delta">ΔT L/R: ${fmt(r.delta, 2)} K</span></div>`).join('');
    const pr = pressureStats(S); S.pressure = pr;
    $('bm-peak').textContent = `${pr.peak.toFixed(0)} kPa`; $('bm-mean').textContent = `${pr.mean.toFixed(0)} kPa`; $('bm-area').textContent = `${pr.highCm2.toFixed(2)} cm²`;
    $('bm-loc').textContent = `X ${pr.px}, Y ${pr.py}`; $('bm-cat').textContent = pr.cat;
    const ai = archIndex(S); S.arch = ai;
    $('ai-left').textContent = ai.L ? `${ai.L.ai.toFixed(3)} · ${ai.L.type}` : '--'; $('ai-right').textContent = ai.R ? `${ai.R.ai.toFixed(3)} · ${ai.R.type}` : '--';
    drawHistogram(); updateMeasurementPanels(); updateVeinInfo();
}

function updateVeinInfo() {
    if (!S.vessel) { $('vein-px').textContent = 'nicht berechnet'; return; }
    let n = 0; const th = +$('sl-vein-th').value; for (let i = 0; i < S.vessel.length; i++) if (S.vessel[i] > th) n++; $('vein-px').textContent = n.toLocaleString('de-DE') + ' px';
}

function drawHistogram() {
    const cv = $('cv-hist'), ctx = cv.getContext('2d'), W = cv.width, H = cv.height; ctx.clearRect(0, 0, W, H);
    if (!S.gray) return; const h = histogram(S.gray, 40); let mx = 0; for (let i = 0; i < 256; i++) if (h[i] > mx) mx = h[i];
    ctx.fillStyle = '#0284C7'; for (let i = 0; i < 256; i++) { const bh = Math.sqrt(h[i] / mx) * (H - 14); ctx.fillStyle = `rgb(${PALETTES[S.palette].slice(i * 3, i * 3 + 3).join(',')})`; ctx.fillRect(i * W / 256, H - 12 - bh, W / 256 + .5, bh); }
    const { med, mad } = medianMAD(S.gray, S.otsu), k = +$('slider-k').value, thr = med + k * 1.4826 * mad;
    const mark = (v, col, t) => { const x = v * W / 256; ctx.strokeStyle = col; ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H - 12); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = col; ctx.font = '9px Consolas'; ctx.fillText(t, Math.min(W - 60, x + 3), 10); };
    mark(med, '#4ADE80', 'Median'); mark(Math.min(255, thr), '#F87171', `τ=${(Math.min(255, thr)).toFixed(0)}`);
    ctx.fillStyle = '#64748B'; ctx.font = '9px Consolas'; ctx.fillText(`${tempOf(0).toFixed(0)}°C`, 2, H - 2); ctx.fillText(`${tempOf(255).toFixed(1)}°C`, W - 46, H - 2);
    $('hist-info').textContent = `${tempOf(med).toFixed(1)} °C / τ = ${tempOf(Math.min(255, thr)).toFixed(1)} °C (k=${k.toFixed(1)}, MAD=${mad})`;
}
function drawProfileGraph() {
    const cv = $('cv-profile'), ctx = cv.getContext('2d'), W = cv.width, H = cv.height; ctx.clearRect(0, 0, W, H);
    const a = ANN.lastProfile && ANN.list.includes(ANN.lastProfile) ? ANN.lastProfile : [...ANN.list].reverse().find(x => x.type === 'profile');
    if (!a) { $('profile-info').textContent = 'Werkzeug „╱“ wählen und Linie ziehen'; return; }
    const pr = sampleProfile(S, a.pts[0], a.pts[1]); const lo = Math.min(...pr), hi = Math.max(...pr), rng = Math.max(1, hi - lo);
    ctx.strokeStyle = '#FACC15'; ctx.lineWidth = 1.5; ctx.beginPath(); pr.forEach((v, i) => { const x = i / (pr.length - 1) * (W - 8) + 4, y = H - 14 - (v - lo) / rng * (H - 28); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke();
    ctx.fillStyle = '#94A3B8'; ctx.font = '9px Consolas'; ctx.fillText(`${tempOf(hi).toFixed(1)}°C`, 4, 10); ctx.fillText(`${tempOf(lo).toFixed(1)}°C`, 4, H - 2); ctx.fillText(`${(pr.length * PX_MM).toFixed(0)} mm`, W - 56, H - 2);
    let maxGrad = 0; for (let i = 1; i < pr.length; i++) maxGrad = Math.max(maxGrad, Math.abs(pr[i] - pr[i - 1]) * TEMP_STEP / PX_MM);
    $('profile-info').textContent = `Länge ${(pr.length * PX_MM).toFixed(1)} mm · ΔT ${((hi - lo) * TEMP_STEP).toFixed(1)} K · max. Gradient ${maxGrad.toFixed(2)} K/mm`;
}

function updateMeasurementPanels() {
    if (!S.gray) return;
    const rb = $('tbl-roi').querySelector('tbody'); rb.innerHTML = '';
    ANN.list.filter(a => ['rect', 'circle', 'poly'].includes(a.type)).forEach(a => { const s = roiStats(S, a); if (s) rb.insertAdjacentHTML('beforeend', `<tr><td>${a.label}</td><td>${s.areaMm2.toFixed(0)}</td><td>${s.min.toFixed(1)}</td><td>${s.max.toFixed(1)}</td><td>${s.mean.toFixed(1)}</td><td>${s.sd.toFixed(2)}</td></tr>`); });
    const probes = ANN.list.filter(a => a.type === 'probe'), pb = $('tbl-probes').querySelector('tbody'); pb.innerHTML = '';
    const T = probes.map(p => tempOf(S.gray[Math.round(p.pts[0].y) * S.w + Math.round(p.pts[0].x)]));
    probes.forEach((p, i) => pb.insertAdjacentHTML('beforeend', `<tr><td>${p.label}</td><td>${Math.round(p.pts[0].x)}</td><td>${Math.round(p.pts[0].y)}</td><td>${T[i].toFixed(1)}</td><td style="font-family:inherit">${zoneName(p.pts[0].x, p.pts[0].y)}</td></tr>`));
    const pm = $('probe-matrix'); if (probes.length >= 2) {
        let h = `<div class="matrix" style="grid-template-columns:repeat(${probes.length + 1},1fr)"><div class="hd">ΔT K</div>${probes.map(p => `<div class="hd">${p.label}</div>`).join('')}`;
        probes.forEach((p, i) => { h += `<div class="hd">${p.label}</div>`; probes.forEach((q, j) => { const d = T[i] - T[j]; h += `<div style="${Math.abs(d) >= 2.2 ? 'color:#FCA5A5;font-weight:700' : ''}">${i === j ? '–' : d.toFixed(2)}</div>`; }); }); pm.innerHTML = h + '</div>';
    } else pm.innerHTML = '';
    const mb = $('tbl-meas').querySelector('tbody'); mb.innerHTML = '';
    ANN.list.filter(a => a.type === 'ruler').forEach(a => mb.insertAdjacentHTML('beforeend', `<tr><td style="font-family:inherit">Lineal</td><td>${(dist(a.pts[0], a.pts[1]) * PX_MM).toFixed(1)} mm</td></tr>`));
    ANN.list.filter(a => a.type === 'gonio').forEach(a => mb.insertAdjacentHTML('beforeend', `<tr><td style="font-family:inherit">Winkel</td><td>${annAngle(a).toFixed(1)}°</td></tr>`));
    const al = $('ann-list'); al.innerHTML = ANN.list.length ? ANN.list.map(a => `<div class="audit-row">#${a.id} ${a.type}${a.label ? ' · ' + a.label : ''}${a.text ? ' · ' + esc(a.text) : ''}</div>`).join('') : '<div class="audit-row">Keine Annotationen</div>';
    drawProfileGraph();
}
function zoneName(x, y) {
    if (!S.zones) return '—'; const side = x < S.midline ? 'L' : 'R', fb = S.zones.fbs[side], zid = zoneOf(S, fb, x, y);
    const z = ZONES.find(q => q.id === zid); return z ? `${z.n} (${side})` : 'Außerhalb Fuß-Modell';
}

function focusRegion(bb) {
    const c = $('container-result'), r = c.getBoundingClientRect(), bw = bb[2] - bb[0] + 80, bh = bb[3] - bb[1] + 80;
    const z = Math.min(r.width / bw, r.height / bh, 6), v = V.R; v.zoom = z; v.x = r.width / 2 - (bb[0] + bb[2]) / 2 * z; v.y = r.height / 2 - (bb[1] + bb[3]) / 2 * z; syncViews('R'); applyViews(); toast('Herd fokussiert');
}

function updateLiveTelemetry(x, y) {
    if (!S.gray || x < 0 || y < 0 || x >= S.w || y >= S.h) return;
    const v = S.gray[y * S.w + x]; $('val-coords').textContent = `X: ${x}, Y: ${y}`; $('val-temp').textContent = `${tempOf(v).toFixed(1)} °C`;
    const cx = S.midline * 2 - x, cv = (cx >= 0 && cx < S.w) ? S.gray[y * S.w + cx] : null;
    $('val-contra').textContent = cv === null ? '--.- °C' : `${tempOf(cv).toFixed(1)} °C`;
    const d = cv === null ? NaN : (v - cv) * TEMP_STEP; $('val-delta').textContent = isNaN(d) ? '±-.-- K' : `${d >= 0 ? '+' : ''}${d.toFixed(2)} K`;
    $('val-delta').style.color = Math.abs(d) >= 2.2 ? '#F87171' : '';
    const dz = S.depth ? (S.depth[y * S.w + x] / 255 * (S.res ? S.res.max_depth_mm : 0)) : NaN; $('val-depth').textContent = isNaN(dz) ? '-- mm' : `${dz.toFixed(1)} mm`; $('recon-cursor-depth').textContent = $('val-depth').textContent;
    $('val-anatomy').textContent = zoneName(x, y);
}

// ── Audit ───────────────────────────────────────────────────────────────────
async function refreshAudit() {
    const c = $('audit-list-container'); if (!hasWails()) { c.innerHTML = '<div class="audit-row">Audit-Trail nur in der Desktop-App verfügbar.</div>'; return; }
    const items = (await window.go.main.App.GetAuditLogs()) || [];
    c.innerHTML = items.slice().reverse().map(e => `<div class="audit-row">${e.timestamp} · <b>${esc(e.patient_hash)}</b><br>${esc(e.action)} · Herde ${e.hotspots} · ${e.highest_risk} · ${e.duration_ms.toFixed(1)} ms<br><span class="audit-hash">#${e.hash.slice(0, 20)}… ← ${e.prev_hash.slice(0, 10)}…</span></div>`).join('') || '<div class="audit-row">Noch keine Einträge</div>';
}
async function verifyAudit() {
    if (!hasWails()) return toast('Nur in der Desktop-App');
    const bad = await window.go.main.App.VerifyAuditChain(), el = $('audit-integrity');
    el.textContent = bad < 0 ? '✓ Hash-Kette intakt (SHA-256)' : `✗ Manipulation ab Eintrag ${bad + 1}`; el.style.color = bad < 0 ? '#4ADE80' : '#F87171'; toast(el.textContent);
}

// ── Berichte & Exporte ──────────────────────────────────────────────────────
const csvCell = v => { const s = String(v); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const toCsv = rows => rows.map(r => r.map(csvCell).join(';')).join('\r\n');
const patient = () => ({ id: $('pt-id').value, age: $('pt-age').value || '–', sex: $('pt-sex').value, region: $('pt-region').value, date: $('pt-date').value, note: $('pt-note').value });

function hotspotRows() {
    return [['ID', 'Klasse', 'Risiko', 'Zentrum X', 'Zentrum Y', 'Fläche px', 'Fläche cm²', 'Max °C', 'ΔT kontralateral K', 'Prominenz K', 'Zirkularität', 'Konfidenz %', 'Score', 'Empfehlung'],
    ...S.res.hotspots.map((h, i) => [i + 1, hsLabel(h, i), h.assessment.risk_level, h.region.center_x, h.region.center_y, h.region.area_pixels, (h.region.area_pixels * PX_MM * PX_MM / 100).toFixed(2), tempOf(h.region.max_val).toFixed(1), (h.region.contra_delta * TEMP_STEP).toFixed(1), (h.region.local_prominence * TEMP_STEP).toFixed(1), h.region.circularity, h.region.confidence_score, h.assessment.score, h.assessment.recommendation])];
}
function buildReportHtml() {
    const p = patient(), r = S.res, z = S.zones, pr = S.pressure;
    const rows = r.hotspots.map((h, i) => `<tr><td>${i + 1}</td><td>${esc(hsLabel(h, i))}</td><td>${h.assessment.risk_level}</td><td>${tempOf(h.region.max_val).toFixed(1)} °C</td><td>+${(h.region.contra_delta * TEMP_STEP).toFixed(1)} K</td><td>${(h.region.area_pixels * PX_MM * PX_MM / 100).toFixed(1)} cm²</td><td>${esc(h.assessment.recommendation)}</td></tr>`).join('') || '<tr><td colspan="7">Keine pathologischen Herde</td></tr>';
    const zr = z.rows.map(q => `<tr><td>${q.n}</td><td>${fmt(q.left)}</td><td>${fmt(q.right)}</td><td>${fmt(q.delta, 2)}</td></tr>`).join('');
    return `<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><title>IGNITE Befundbericht ${esc(p.id)}</title><style>
    body{font-family:Segoe UI,Arial,sans-serif;color:#0F172A;margin:28px}h1{color:#0284C7;margin:0}h2{border-bottom:2px solid #0284C7;padding-bottom:3px;margin-top:22px;font-size:15px}
    table{border-collapse:collapse;width:100%;font-size:12px}td,th{border:1px solid #CBD5E1;padding:4px 7px;text-align:left}th{background:#E0F2FE}.imgs{display:flex;gap:10px}.imgs img{width:49%;border:1px solid #94A3B8}
    .risk{padding:8px 12px;border-radius:6px;font-weight:700;background:${r.highest_risk === 'CRITICAL' ? '#FEE2E2;color:#B91C1C' : r.highest_risk === 'MODERATE' ? '#FEF3C7;color:#B45309' : '#DCFCE7;color:#15803D'}}.sig{margin-top:50px;display:flex;gap:60px}.sig div{border-top:1px solid #000;width:240px;padding-top:4px;font-size:11px}small{color:#64748B}</style></head><body>
    <h1>IGNITE Medical Imaging Suite – Thermografischer Befundbericht</h1><small>DIN EN ISO 13485 · IWGDF · Armstrong-Kriterien (ΔT ≥ 2,2 K) · erzeugt ${new Date().toLocaleString('de-DE')}</small>
    <h2>Patient</h2><table><tr><td>Pseudonym</td><td>${esc(p.id)}</td><td>Alter / Geschlecht</td><td>${esc(p.age)} / ${esc(p.sex)}</td></tr><tr><td>Region</td><td>${esc(p.region)}</td><td>Untersuchung</td><td>${esc(p.date)}</td></tr><tr><td>Bilddatei</td><td colspan="3">${esc(r.filename)} (${r.width}×${r.height} px)</td></tr><tr><td>Notiz</td><td colspan="3">${esc(p.note)}</td></tr></table>
    <h2>Gesamtbefund</h2><div class="risk">${$('risk-tier-title').textContent} – ${$('risk-recommendation').textContent}</div>
    <h2>Thermogramme</h2><div class="imgs"><img src="${r.raw_base64}"><img src="${r.overlay_base64}"></div>
    <h2>Herde &amp; Triage</h2><table><tr><th>#</th><th>Klasse</th><th>Risiko</th><th>Max T</th><th>ΔT</th><th>Fläche</th><th>Empfehlung</th></tr>${rows}</table>
    <h2>5-Zonen Bilateralvergleich</h2><table><tr><th>Zone</th><th>Links °C</th><th>Rechts °C</th><th>ΔT K</th></tr>${zr}</table><p>TAI: ${fmt(z.tai, 2)} K · Plantardruck-Proxy: Spitze ${pr.peak.toFixed(0)} kPa, Hochrisikofläche ${pr.highCm2.toFixed(2)} cm² (${pr.cat})</p>
    <h2>Maßnahmen</h2><ul>${$('action-list').innerHTML}</ul>
    <div class="sig"><div>Datum / Ort</div><div>Unterschrift Facharzt</div></div><p><small>Computergestützte Vorbefundung – ersetzt nicht die ärztliche Beurteilung. Berechnung deterministisch in-process (Go ${r.stages ? r.stages.length : 42} Stufen).</small></p></body></html>`;
}
function printReport() {
    const f = document.createElement('iframe'); f.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0'; document.body.appendChild(f);
    f.srcdoc = buildReportHtml(); f.onload = () => { try { f.contentWindow.focus(); f.contentWindow.print(); } catch (e) { toast('Druck nicht verfügbar – HTML-Export nutzen'); } setTimeout(() => f.remove(), 60000); };
}
function viewDataUrl() {
    const t = document.createElement('canvas'); t.width = S.w; t.height = S.h; const c = t.getContext('2d');
    c.drawImage($('canvas-result'), 0, 0); c.save(); const z = V.R.zoom; V.R.zoom = 1; drawAnnotations(c, 'R'); V.R.zoom = z; c.restore(); return t.toDataURL('image/png');
}
function depthDataUrl() {
    const sv = S.mode; S.mode = 'depth'; const img = renderMode(S); S.mode = sv; const t = document.createElement('canvas'); t.width = S.w; t.height = S.h; t.getContext('2d').putImageData(img, 0, 0); return t.toDataURL('image/png');
}
function tempMatrixCsv() { const rows = []; for (let y = 0; y < S.h; y++) { const r = new Array(S.w); for (let x = 0; x < S.w; x++) r[x] = tempOf(S.gray[y * S.w + x]).toFixed(1); rows.push(r.join(';')); } return rows.join('\r\n'); }
function depthCsv() { const m = S.res.max_depth_mm / 255, rows = []; for (let y = 0; y < S.h; y += 2) { const r = []; for (let x = 0; x < S.w; x += 2) r.push((S.depth[y * S.w + x] * m).toFixed(2)); rows.push(r.join(';')); } return rows.join('\r\n'); }
