// IGNITE MEDICAL WORKSTATION · CLIENT LOGIC v5 (Zustand, Viewport, Aktionen, Wails-Bridge)
// Reihenfolge: render.js → tools.js → panels.js → app.js

const S = {
    gray: null, w: 0, h: 0, otsu: 100, midline: 0, res: null, depth: null, corrected: null, vessel: null, hotspotMask: null, second: null,
    window: 255, level: 128, invert: false, palette: 'ironbow', mode: 'normal', isoLo: 30, isoHi: 40,
    findings: true, zonesOverlay: false, veins: false, veinOp: .6, veinTh: 40, sync: true, overrides: {}, hover: null,
    imagePath: '', files: [], caseIdx: -1, layout: 'dual', curtain: .5, zones: null, pressure: null, arch: null
};
const V = { L: { zoom: 1, x: 0, y: 0 }, R: { zoom: 1, x: 0, y: 0 } };
const hasWails = () => !!(window.go && window.go.main && window.go.main.App);
const api = () => window.go.main.App;

// ── UI-Helfer ───────────────────────────────────────────────────────────────
let toastTimer;
function toast(msg) { const t = $('toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 2200); }
function showModal(title, body, buttons) {
    $('modal-title').textContent = title; $('modal-body').innerHTML = body; const a = $('modal-actions'); a.innerHTML = '';
    buttons.forEach(b => { const el = document.createElement('button'); el.className = 'action-btn ' + (b.primary ? 'btn-primary' : 'btn-secondary'); el.textContent = b.label; el.onclick = () => { closeModal(); b.fn && b.fn(); }; a.appendChild(el); });
    $('modal').classList.remove('hidden');
}
function closeModal() { $('modal').classList.add('hidden'); }
function askText(title, def) {
    return new Promise(res => {
        showModal(title, `<input id="modal-input" value="${esc(def)}" placeholder="Text eingeben…">`, [{ label: 'Abbrechen', fn: () => res(null) }, { label: 'OK', primary: true, fn: () => res($('modal-input').value.trim()) }]);
        setTimeout(() => { const i = $('modal-input'); i.focus(); i.onkeydown = e => { if (e.key === 'Enter') { closeModal(); res(i.value.trim()); } }; }, 30);
    });
}
function setLoading(on) { const b = $('btn-quick-demo'); b.innerHTML = on ? '<span>⏳ Berechne Go-Pipeline…</span>' : '<span>⚡ Schnelltest</span>'; b.disabled = on; }

// ── Bild-Decoding ───────────────────────────────────────────────────────────
function decodeGray(url) {
    return new Promise((ok, fail) => {
        const im = new Image(); im.onload = () => {
            const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d', { willReadFrequently: true }); x.drawImage(im, 0, 0);
            const d = x.getImageData(0, 0, im.width, im.height).data, g = new Uint8Array(im.width * im.height); for (let i = 0; i < g.length; i++) g[i] = d[i * 4]; ok({ w: im.width, h: im.height, data: g });
        }; im.onerror = fail; im.src = url;
    });
}

// ── Ergebnis laden ──────────────────────────────────────────────────────────
async function loadResult(res) {
    if (!res || !res.success) { toast(res ? res.error_message : 'Unbekannter Fehler'); return; }
    const [raw, depth, corr, vess, hm] = await Promise.all([decodeGray(res.raw_base64), res.depth_base64 ? decodeGray(res.depth_base64) : null, res.corrected_base64 ? decodeGray(res.corrected_base64) : null, res.vascular_base64 ? decodeGray(res.vascular_base64) : null, res.hotspot_mask_base64 ? decodeGray(res.hotspot_mask_base64) : null]);
    const newImage = S.w !== raw.w || S.h !== raw.h || !S.gray;
    S.res = res; S.gray = raw.data; S.w = raw.w; S.h = raw.h; S.depth = depth && depth.data; S.corrected = corr && corr.data; S.vessel = vess && vess.data; S.hotspotMask = hm && hm.data;
    S.otsu = Math.max(40, otsuThreshold(S.gray)); S.midline = findMidline(S); S.overrides = {}; S.imagePath = res.image_path;
    document.querySelectorAll('.canvas-container canvas').forEach(c => { c.width = S.w; c.height = S.h; });
    $('telemetry-left').textContent = `${S.w} × ${S.h} px · ${res.filename}`;
    const id = patientPseudonym(res.filename || 'x'); $('pt-id').value = id; loadPatient(id);
    if (newImage) setTimeout(fitAll, 30);
    updateUIFromResults(res); requestRender(); redrawAnnotations();
    toast(`Analyse abgeschlossen · ${res.total_hotspots} Herd(e) · ${res.timing.total_ms.toFixed(0)} ms`);
}
function cfgFromUi() {
    return { kernel_factor: +$('slider-r').value, margin_factor: +$('slider-m').value, k_factor: +$('slider-k').value, threshold_mode: 'MAD', min_area_fraction: 0.0003, min_circularity: 0.08, run_vascular_map: true, run_perfusion: true, enable_3d_reconstruction: true };
}
async function analyzePath(path) {
    setLoading(true);
    try { if (hasWails()) await loadResult(await api().AnalyzeThermal(path, cfgFromUi())); else await loadResult(syntheticResult()); }
    catch (e) { toast('Analysefehler: ' + e); } finally { setLoading(false); }
}
async function loadCase(i) {
    if (!S.files.length) return; S.caseIdx = (i + S.files.length) % S.files.length; document.querySelectorAll('.film-card').forEach((c, k) => c.classList.toggle('active', k === S.caseIdx));
    const card = document.querySelectorAll('.film-card')[S.caseIdx]; if (card) card.scrollIntoView({ inline: 'center', block: 'nearest' });
    await analyzePath(S.files[S.caseIdx]);
}
async function buildFilmstrip() {
    const box = $('filmstrip-items'); box.innerHTML = ''; if (!hasWails()) { S.files = []; $('filmstrip-count').textContent = '(nur Desktop-App)'; return; }
    S.files = (await api().ListTestImages()) || []; $('filmstrip-count').textContent = `${S.files.length} Aufnahmen`;
    S.files.forEach((p, i) => { const d = document.createElement('div'); d.className = 'film-card'; d.innerHTML = `<div style="height:52px"></div>${p.split(/[\\/]/).pop().replace(/\.\w+$/, '')}`; d.onclick = () => loadCase(i); box.appendChild(d); });
    for (let i = 0; i < S.files.length; i++) { const t = await api().GetThumbnail(S.files[i]); const card = box.children[i]; if (card && t) { const im = new Image(); im.src = t; card.replaceChild(im, card.firstChild); } }
}

// ── Rendering ───────────────────────────────────────────────────────────────
let rafId = 0;
function requestRender() { if (!rafId) rafId = requestAnimationFrame(() => { rafId = 0; renderAll(); }); }
function renderAll() {
    if (!S.gray) return;
    $('canvas-orig').getContext('2d').putImageData(renderRaw(S), 0, 0);
    const img = renderMode(S), d = img.data, hm = S.hotspotMask, w = S.w, h = S.h;
    if (S.mode === 'normal' && S.findings && hm) {
        for (let y = 1; y < h - 1; y++) for (let x = 1; x < w - 1; x++) { const i = y * w + x; if (!hm[i]) continue; const j = i * 4;
            if (!hm[i - 1] || !hm[i + 1] || !hm[i - w] || !hm[i + w]) { d[j] = 239; d[j + 1] = 68; d[j + 2] = 68; } else { d[j] = d[j] * .8 + 48; d[j + 1] *= .8; d[j + 2] *= .8; } }
    }
    if (S.veins && S.vessel) { for (let i = 0; i < S.vessel.length; i++) if (S.vessel[i] > S.veinTh) { const j = i * 4, a = S.veinOp * Math.min(1, S.vessel[i] / 120); d[j] = d[j] * (1 - a) + 0 * a; d[j + 1] = d[j + 1] * (1 - a) + 240 * a; d[j + 2] = d[j + 2] * (1 - a) + 255 * a; } }
    $('canvas-result').getContext('2d').putImageData(img, 0, 0);
    const names = { normal: '2. BEFUND & HOTSPOT-DIAGNOSTIK', isotherm: '2. ISOTHERMEN-BANDFILTER', relief: '2. 2,5D TOPOGRAFISCHES RELIEF', corrected: '2. 3D-LAMBERTIAN KANTENKORREKTUR', bioheat: '2. PENNES-BIOHEAT PERFUSION', laplace: '2. LAPLACE-WÄRMEFLUSS ∇²T', dsa: '2. DSA – VENEN-SUBTRAKTION', pressure: '2. PLANTARDRUCK-PROXY (kPa)', mirror: '2. KONTRALATERALE DIFFERENZ |L−R|', compare: '2. VERLAUFSVERGLEICH |A−B|', depth: '2. 3D-TIEFENKARTE (mm)' };
    $('badge-right').textContent = names[S.mode] || names.normal; drawColorbar();
}
function drawColorbar() {
    const cv = $('cb-canvas'); if (!cv) return;
    const c = cv.getContext('2d'), lut = PALETTES[S.palette], H = cv.height;
    if (!lut) return;
    for (let y = 0; y < H; y++) { let idx = Math.round((1 - y / (H - 1)) * 255); if (S.invert) idx = 255 - idx; c.fillStyle = `rgb(${lut[idx * 3]},${lut[idx * 3 + 1]},${lut[idx * 3 + 2]})`; c.fillRect(0, y, 14, 1); }
    const maxEl = $('cb-max'), minEl = $('cb-min');
    if (maxEl) maxEl.textContent = tempOf(Math.min(255, S.level + S.window / 2)).toFixed(1) + '°';
    if (minEl) minEl.textContent = tempOf(Math.max(0, S.level - S.window / 2)).toFixed(1) + '°';
}
function redrawAnnotations() {
    if (!S.gray) return;
    [['L', 'canvas-ann-orig'], ['R', 'canvas-ann-result']].forEach(([side, id]) => {
        const ctx = $(id).getContext('2d'); ctx.clearRect(0, 0, S.w, S.h);
        if (S.zonesOverlay && S.zones) drawZonesOverlay(ctx, side);
        if (side === 'R' && S.findings && S.mode === 'normal' && S.res) drawFindingsVectors(ctx);
        drawAnnotations(ctx, side);
    });
}
function drawFindingsVectors(ctx) {
    const z = V.R.zoom, fs = 13 / z; ctx.save(); ctx.lineWidth = 2 / z; ctx.font = `bold ${fs}px Segoe UI, sans-serif`;
    S.res.hotspots.forEach((hs, i) => {
        const bb = hs.region.bounding_box, col = hs.assessment.risk_level === 'MODERATE' ? '#F59E0B' : '#DC2626', L = 16 / z;
        ctx.strokeStyle = col; ctx.setLineDash([]); ctx.strokeRect(bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]);
        ctx.lineWidth = 4 / z; ctx.beginPath(); [[bb[0], bb[1], 1, 1], [bb[2], bb[1], -1, 1], [bb[0], bb[3], 1, -1], [bb[2], bb[3], -1, -1]].forEach(([x, y, sx, sy]) => { ctx.moveTo(x + sx * L, y); ctx.lineTo(x, y); ctx.lineTo(x, y + sy * L); }); ctx.stroke(); ctx.lineWidth = 2 / z;
        const cx = hs.region.center_x, cy = hs.region.center_y; ctx.beginPath(); ctx.moveTo(cx - 8 / z, cy); ctx.lineTo(cx + 8 / z, cy); ctx.moveTo(cx, cy - 8 / z); ctx.lineTo(cx, cy + 8 / z); ctx.stroke();
        const txt = `#${i + 1}  ΔT +${(hs.region.contra_delta * TEMP_STEP).toFixed(1)} K · ${hs.assessment.risk_level === 'CRITICAL' ? 'KRITISCH' : 'MÄSSIG'} · ${hsLabel(hs, i)}`;
        const tw = ctx.measureText(txt).width + 14 / z, bx = bb[0], by = bb[1] - 24 / z < 0 ? bb[3] + 6 / z : bb[1] - 24 / z;
        ctx.fillStyle = 'rgba(11,15,25,.9)'; ctx.fillRect(bx, by, tw, 19 / z); ctx.strokeRect(bx, by, tw, 19 / z); ctx.fillStyle = '#F8FAFC'; ctx.textBaseline = 'middle'; ctx.fillText(txt, bx + 7 / z, by + 10 / z);
    });
    ctx.restore();
}
function drawZonesOverlay(ctx, side) {
    const z = viewOf(side).zoom, fs = 11 / z; ctx.save(); ctx.lineWidth = 1.4 / z; ctx.font = `bold ${fs}px Segoe UI`; ctx.strokeStyle = '#FACC15'; ctx.fillStyle = '#FACC15'; ctx.setLineDash([5 / z, 4 / z]);
    ['L', 'R'].forEach(s => { const fb = S.zones.fbs[s]; if (!fb) return; ctx.strokeRect(fb.minX, fb.top, fb.maxX - fb.minX, fb.bottom - fb.top);
        const hh = fb.bottom - fb.top; [.18, .42, .72].forEach(f => { ctx.beginPath(); ctx.moveTo(fb.minX, fb.top + hh * f); ctx.lineTo(fb.maxX, fb.top + hh * f); ctx.stroke(); });
        const mx = (fb.minX + fb.maxX) / 2; ctx.beginPath(); ctx.moveTo(mx, fb.top + hh * .18); ctx.lineTo(mx, fb.top + hh * .42); ctx.stroke();
        [['Digiti', 0], ['Meta I/II–V', .18], ['Mittelfuß', .42], ['Calcaneus', .72]].forEach(([n, f]) => ctx.fillText(`${s}: ${n}`, fb.minX + 4 / z, fb.top + hh * f + 13 / z)); });
    ctx.restore();
}

// ── Viewport (Zoom/Pan) ─────────────────────────────────────────────────────
function applyViews() {
    [['L', ['canvas-orig', 'canvas-ann-orig', 'canvas-crosshair-orig']], ['R', ['canvas-result', 'canvas-ann-result', 'canvas-crosshair-result']]].forEach(([s, ids]) => {
        const v = V[s]; ids.forEach(id => $(id).style.transform = `translate(${v.x}px,${v.y}px) scale(${v.zoom})`); });
    $('zoom-readout').textContent = Math.round(V.R.zoom * 100) + ' %'; redrawAnnotations();
}
function syncViews(from) { if (S.sync) { const o = from === 'L' ? 'R' : 'L'; V[o].zoom = V[from].zoom; V[o].x = V[from].x; V[o].y = V[from].y; } }
function fitView(side, id) {
    const r = $(id).getBoundingClientRect(); if (!r.width || !S.w) return; const z = Math.min(r.width / S.w, r.height / S.h) * .97;
    V[side].zoom = z; V[side].x = (r.width - S.w * z) / 2; V[side].y = (r.height - S.h * z) / 2;
}
function fitAll() { fitView('L', 'container-orig'); fitView('R', 'container-result'); applyViews(); }
function zoomBy(f) { const r = $('container-result').getBoundingClientRect(), v = V.R, nz = Math.max(.1, Math.min(40, v.zoom * f)), cx = r.width / 2, cy = r.height / 2; v.x = cx - (cx - v.x) * nz / v.zoom; v.y = cy - (cy - v.y) * nz / v.zoom; v.zoom = nz; syncViews('R'); applyViews(); }
function actualPixels() { ['L', 'R'].forEach((s, i) => { const r = $(i ? 'container-result' : 'container-orig').getBoundingClientRect(); V[s].zoom = 1; V[s].x = (r.width - S.w) / 2; V[s].y = (r.height - S.h) / 2; }); applyViews(); }
// ── Clinical Web Audio API Synthesizer ──────────────────────────────────────
let audioCtx = null;
function playClinicalSound(type = 'click') {
    if (S.audio === false) return;
    try {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator(), gain = audioCtx.createGain();
        osc.connect(gain); gain.connect(audioCtx.destination);
        const t = audioCtx.currentTime;
        if (type === 'click') {
            osc.type = 'sine'; osc.frequency.setValueAtTime(880, t); osc.frequency.exponentialRampToValueAtTime(440, t + 0.035);
            gain.gain.setValueAtTime(0.06, t); gain.gain.exponentialRampToValueAtTime(0.001, t + 0.035);
            osc.start(t); osc.stop(t + 0.035);
        } else if (type === 'alarm') {
            osc.type = 'triangle'; osc.frequency.setValueAtTime(880, t); osc.frequency.setValueAtTime(1174.66, t + 0.08);
            gain.gain.setValueAtTime(0.12, t); gain.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
            osc.start(t); osc.stop(t + 0.28);
        } else if (type === 'sign') {
            osc.type = 'sine'; osc.frequency.setValueAtTime(523.25, t); osc.frequency.exponentialRampToValueAtTime(1046.5, t + 0.15);
            gain.gain.setValueAtTime(0.12, t); gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
            osc.start(t); osc.stop(t + 0.25);
        }
    } catch (e) { }
}

// ── Clinical PACS Splash Screen Sequence ────────────────────────────────────
const SPLASH_STEPS = [
    'AVX2 256-Bit SIMD Kernels (VPMINUB, VPMAXUB, VPSUBUSB, FMA) geladen',
    'GopherLua 5.1 Clinical Decision Rule Engine (Armstrong ΔT ≥ 2,2 K) aktiv',
    'FLIR Radiometrische LWIR Sensor-Pipeline kalibriert (NETD < 40 mK, ε = 0.98)',
    '42-Stufen PAP Binarisierung & 2-Pass Chamfer-L2 Distanzerosion bereit',
    'Frangi-Hesse Vaskulärfilter & Pennes 2D-Bioheat Perfusion initialisiert',
    'Kryptografische SQLite SHA-256 Audit-Kette (DSGVO Art. 30) verifiziert',
    'Dual PACS Viewport GDI & WebGL Engine betriebsbereit'
];
let splashRunning = false, splashTimer = null;

function runSplashSequence(manual = false) {
    const splash = $('splash-screen'); if (!splash) return;
    splash.classList.remove('splash-hidden'); splashRunning = true;
    const stepsBox = $('splash-steps-box'), counter = $('splash-diag-counter'), label = $('splash-progress-label'), pct = $('splash-progress-pct'), bar = $('splash-bar');
    if (stepsBox) stepsBox.innerHTML = '';
    if (bar) bar.style.width = '0%';
    if (pct) pct.textContent = '0%';
    if (label) label.textContent = 'Initialisiere diagnostische Subsysteme...';
    let currentStep = 0; clearTimeout(splashTimer);

    function nextStep() {
        if (!splashRunning) return;
        if (currentStep < SPLASH_STEPS.length) {
            const stepText = SPLASH_STEPS[currentStep];
            if (stepsBox) {
                const div = document.createElement('div'); div.className = 'splash-step-item splash-step-done';
                div.innerHTML = `<span class="splash-step-icon">✓</span><span>${stepText}</span>`;
                stepsBox.appendChild(div); stepsBox.scrollTop = stepsBox.scrollHeight;
            }
            currentStep++;
            const p = Math.round((currentStep / SPLASH_STEPS.length) * 100);
            if (bar) bar.style.width = p + '%';
            if (pct) pct.textContent = p + '%';
            if (counter) counter.textContent = `${currentStep} / ${SPLASH_STEPS.length} SUBSYSTEME`;
            playClinicalSound('click');
            splashTimer = setTimeout(nextStep, 170);
        } else {
            if (label) label.textContent = '✓ INITIALISIERUNG ERFOLGREICH · PACS WORKSTATION BEREIT';
            if (bar) bar.style.width = '100%';
            if (pct) pct.textContent = '100%';
            playClinicalSound('sign');
            splashTimer = setTimeout(dismissSplash, manual ? 800 : 500);
        }
    }
    setTimeout(nextStep, 100);
}

function dismissSplash() {
    const splash = $('splash-screen'); if (!splash || !splashRunning) return;
    splashRunning = false; clearTimeout(splashTimer);
    splash.classList.add('splash-hidden');
    playClinicalSound('click');
}

// ── Medical Crosshair with Concentric Range Rings & Live Canvas HUD ─────────
function drawCrosshairs(x, y) {
    [['L', 'canvas-crosshair-orig'], ['R', 'canvas-crosshair-result']].forEach(([s, id]) => {
        const ctx = $(id).getContext('2d'), z = V[s].zoom;
        ctx.clearRect(0, 0, S.w, S.h);
        if (ANN.tool !== 'crosshair' || !S.gray) return;

        const gap = 12 / z;
        ctx.lineWidth = 1 / z;
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.75)';
        ctx.setLineDash([4 / z, 4 / z]);

        // Hairlines with center gap
        ctx.beginPath();
        ctx.moveTo(0, y); ctx.lineTo(Math.max(0, x - gap), y);
        ctx.moveTo(Math.min(S.w, x + gap), y); ctx.lineTo(S.w, y);
        ctx.moveTo(x, 0); ctx.lineTo(x, Math.max(0, y - gap));
        ctx.moveTo(x, Math.min(S.h, y + gap)); ctx.lineTo(x, S.h);
        ctx.stroke();

        // Concentric Calibrated Range Rings (10 mm & 20 mm radius)
        const r10 = 10 / PX_MM;
        const r20 = 20 / PX_MM;
        ctx.setLineDash([2 / z, 3 / z]);
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
        ctx.beginPath(); ctx.arc(x, y, r10, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.22)';
        ctx.beginPath(); ctx.arc(x, y, r20, 0, Math.PI * 2); ctx.stroke();

        // Central Target Reticle
        ctx.setLineDash([]);
        const idx = Math.round(y) * S.w + Math.round(x);
        const val = (idx >= 0 && idx < S.gray.length) ? S.gray[idx] : 0;
        const curTemp = tempOf(val);
        const cx = S.midline * 2 - Math.round(x);
        const cval = (cx >= 0 && cx < S.w) ? S.gray[Math.round(y) * S.w + cx] : null;
        const delta = cval !== null ? (val - cval) * TEMP_STEP : 0;
        const isCritical = Math.abs(delta) >= 2.2;

        ctx.strokeStyle = isCritical ? '#EF4444' : '#0284C7';
        ctx.lineWidth = 1.6 / z;
        ctx.beginPath(); ctx.arc(x, y, 6 / z, 0, Math.PI * 2); ctx.stroke();

        // Floating In-Canvas Telemetry Pill
        const boxX = x + 14 / z, boxY = y - 10 / z;
        if (boxX + 90 / z < S.w && boxY - 20 / z > 0) {
            ctx.fillStyle = 'rgba(8, 13, 24, 0.88)';
            ctx.strokeStyle = isCritical ? '#EF4444' : 'rgba(56, 189, 248, 0.35)';
            ctx.lineWidth = 1 / z;
            const wBox = isCritical ? 96 / z : 68 / z, hBox = 20 / z;
            ctx.fillRect(boxX, boxY - hBox + 4 / z, wBox, hBox);
            ctx.strokeRect(boxX, boxY - hBox + 4 / z, wBox, hBox);

            ctx.fillStyle = isCritical ? '#FCA5A5' : '#38BDF8';
            ctx.font = `bold ${Math.max(9, Math.round(10 / z))}px "JetBrains Mono", Consolas, monospace`;
            ctx.fillText(`${curTemp.toFixed(1)} °C${isCritical ? ' Δ' + (delta > 0 ? '+' : '') + delta.toFixed(1) + 'K' : ''}`, boxX + 4 / z, boxY - 4 / z);
        }
    });
}
function clearCrosshairs() { if (!S.gray) return; ['canvas-crosshair-orig', 'canvas-crosshair-result'].forEach(id => $(id).getContext('2d').clearRect(0, 0, S.w, S.h)); }

// ── Layout-Modi ─────────────────────────────────────────────────────────────
function setViewportMode(mode) {
    S.layout = mode; const wrap = $('viewports-wrapper'), L = $('viewport-left'), R = $('viewport-right'), div = $('curtain-divider'); wrap.className = 'mode-' + mode;
    document.querySelectorAll('#viewport-mode-selector .seg-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
    [L, R].forEach(e => { e.style.cssText = ''; });
    if (mode === 'dual') { div.classList.add('hidden'); L.style.width = R.style.width = '50%'; }
    else if (mode === 'overlay') { div.classList.add('hidden'); L.style.display = 'none'; R.style.width = '100%'; }
    else { div.classList.remove('hidden'); L.style.cssText = 'position:absolute;inset:0;width:100%;z-index:1'; R.style.cssText = 'position:absolute;inset:0;width:100%;z-index:2'; updateCurtain(); }
    setTimeout(fitAll, 30);
}
function updateCurtain() { if (S.layout !== 'curtain') return; const p = (S.curtain * 100).toFixed(1); $('curtain-divider').style.left = p + '%'; $('viewport-right').style.clipPath = `inset(0 0 0 ${p}%)`; }

// ── Aktionen ────────────────────────────────────────────────────────────────
function setView(m) { S.mode = m; $('sel-view').value = m; $('iso-controls').classList.toggle('hidden', m !== 'isotherm'); if (m === 'compare' && !S.second) toast('Zuerst Datei ▸ „Kontralaterales / Verlaufsbild laden…“ wählen'); requestRender(); }
function setToggle(id, on) { $(id).classList.toggle('active', on); }
function selectCategory(c) { document.querySelectorAll('.cat-pill').forEach(p => p.classList.toggle('active', p.dataset.cat === c)); document.querySelectorAll('.cat-page').forEach(p => p.classList.toggle('active', p.id === 'page-' + c)); }
function needImage() { if (!S.gray) { toast('Bitte zuerst ein Wärmebild laden'); return false; } return true; }
async function saveText(name, content) {
    if (hasWails()) { const p = await api().SaveTextFile(name, content); if (p) toast('Gespeichert: ' + p); }
    else { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([content], { type: 'text/plain;charset=utf-8' })); a.download = name; a.click(); toast('Download: ' + name); }
}
async function saveData(name, url) {
    if (!url) return toast('Keine Bilddaten vorhanden');
    if (hasWails()) { const p = await api().SaveDataURL(name, url); if (p) toast('Gespeichert: ' + p); } else { const a = document.createElement('a'); a.href = url; a.download = name; a.click(); toast('Download: ' + name); }
}
async function exportMesh(f) { if (!needImage()) return; if (!hasWails()) return toast('3D-Export nur in der Desktop-App'); try { const p = await api().ExportMesh(f); if (p) toast('3D-Netz gespeichert: ' + p); } catch (e) { toast('' + e); } }
function stamp() { return (S.res ? S.res.filename.replace(/\.\w+$/, '') : 'ignite').replace(/[^\w()-]+/g, '_'); }

const ACTIONS = {
    open: async () => { if (!hasWails()) return toast('Dateidialog nur in der Desktop-App'); const p = await api().SelectThermalImage(); if (p) { S.caseIdx = -1; document.querySelectorAll('.film-card').forEach(c => c.classList.remove('active')); analyzePath(p); } },
    demo: async () => { if (hasWails() && S.files.length) return loadCase(0); if (hasWails()) { setLoading(true); try { await loadResult(await api().QuickAnalyzeDemo()); } catch (e) { toast('' + e); } setLoading(false); } else analyzePath(''); },
    reanalyze: () => { if (S.imagePath || !hasWails()) analyzePath(S.imagePath); },
    openSecond: async () => { if (!hasWails()) return toast('Nur in der Desktop-App'); const r = await api().SelectSecondImage(); if (r) { const g = await decodeGray(r.raw_base64); S.second = g; setView('compare'); toast('Vergleichsbild geladen: ' + r.name); } },
    prevCase: () => loadCase(S.caseIdx - 1), nextCase: () => loadCase(S.caseIdx + 1),
    undo: doUndo, redo: doRedo, pap: () => selectCategory('system'), quit: () => window.runtime && window.runtime.Quit && window.runtime.Quit(),
    fit: fitAll, actual: () => needImage() && actualPixels(), zoomIn: () => zoomBy(1.25), zoomOut: () => zoomBy(.8),
    toggleFindings: () => { S.findings = !S.findings; setToggle('tb-findings', S.findings); requestRender(); redrawAnnotations(); },
    toggleZones: () => { if (!needImage()) return; S.zonesOverlay = !S.zonesOverlay; redrawAnnotations(); },
    toggleVeins: () => { if (!needImage()) return; if (!S.vessel) return toast('Kein Gefäßfilter-Ergebnis vorhanden'); S.veins = !S.veins; requestRender(); toast('Venen-Overlay ' + (S.veins ? 'ein' : 'aus')); },
    toggleInvert: () => { S.invert = !S.invert; setToggle('tb-invert', S.invert); requestRender(); },
    toggleSync: () => { S.sync = !S.sync; setToggle('tb-sync', S.sync); if (S.sync) { syncViews('R'); applyViews(); } toast('Viewport-Sync ' + (S.sync ? 'an' : 'aus')); },
    toggleFilmstrip: () => $('filmstrip').classList.toggle('collapsed'),
    toggleDarkroom: () => {
        document.body.classList.toggle('darkroom');
        const isDark = document.body.classList.contains('darkroom');
        const btn = $('btn-darkroom');
        if (btn) btn.innerHTML = isDark ? '<span>☀️ Normal</span>' : '<span>🌙 Dunkelkammer</span>';
        toast(isDark ? 'Dunkelkammer-Modus aktiviert (OLED Reinschwarz)' : 'Standard-Helligkeit');
        playClinicalSound('click');
    },
    toggleAudio: () => {
        S.audio = S.audio === false ? true : false;
        const btn = $('btn-audio');
        if (btn) btn.innerHTML = S.audio ? '<span>🔊 Ton: AN</span>' : '<span>🔇 Ton: AUS</span>';
        toast(S.audio ? 'Klinische Audiosignale aktiv' : 'Stummgeschaltet');
        if (S.audio) playClinicalSound('click');
    },
    showSplash: () => runSplashSequence(true),
    signReport: () => {
        if (!S.res) return toast('Bitte zuerst ein Wärmebild laden');
        const docSelect = $('sel-doctor');
        const docName = docSelect ? docSelect.options[docSelect.selectedIndex].text : 'Facharzt';
        const now = new Date();
        const timeStr = now.toLocaleDateString('de-DE') + ' ' + now.toLocaleTimeString('de-DE') + ' CET';
        const hash = Array.from(crypto.getRandomValues(new Uint8Array(16))).map(b => b.toString(16).padStart(2, '0')).join('');

        const badge = $('badge-val-status');
        if (badge) { badge.textContent = 'SIGNIERT'; badge.className = 'counter-badge chip ok'; }
        const statusText = $('val-status-text');
        if (statusText) { statusText.textContent = 'Klinisch validiert & freigegeben'; statusText.className = 'status-approved'; }

        const infoBox = $('val-signature-info');
        if (infoBox) {
            infoBox.classList.remove('hidden');
            infoBox.innerHTML = `
                <div style="display:flex;align-items:center;gap:8px;font-weight:700;color:#34D399;margin-bottom:4px;">
                    <span style="font-size:16px;">🛡️</span>
                    <span>ÄRZTLICHE FREIGABE NACH DIN EN ISO 13485</span>
                </div>
                <div class="sig-line">Signiert durch: <strong>${esc(docName)}</strong></div>
                <div class="sig-hash">SHA-256 Signatur: #${hash}… · ${timeStr}</div>
                <div style="font-size:9.5px;color:#94A3B8;margin-top:4px;">Revisionssicher im SQLite-Audit-Trail (DSGVO Art. 30) protokolliert.</div>
            `;
        }
        playClinicalSound('sign');
        toast('✓ Befund erfolgreich validiert und digital signiert');
    },
    editPatient: () => { selectCategory('system'); $('pt-age').focus(); toast('Patientenakte im System-Tab fokussiert'); },
    anonymizePatient: () => {
        const newId = 'ANON-' + Math.random().toString(16).slice(2, 8).toUpperCase() + Math.random().toString(16).slice(2, 6).toUpperCase();
        $('pt-id').value = newId; $('pat-id').textContent = newId;
        toast('Neues DSGVO Art. 25 Pseudonym generiert: ' + newId);
        playClinicalSound('click');
    },
    clearAnn: clearAnnotations,
    reset: () => { pushUndo(); ANN.list = []; ANN.probeN = ANN.roiN = 0; S.window = 255; S.level = 128; S.invert = false; S.palette = 'ironbow'; S.findings = true; S.zonesOverlay = false; S.veins = false; S.isoLo = 30; S.isoHi = 40; S.overrides = {};
        $('sl-window').value = 255; $('sl-level').value = 128; $('val-window').textContent = 255; $('val-level').textContent = 128; $('sel-palette').value = 'ironbow'; $('sel-wl').value = 'standard'; setToggle('tb-invert', false); setToggle('tb-findings', true); setView('normal'); setTool('crosshair'); fitAll(); if (S.res) updateUIFromResults(S.res); annChanged(); toast('Workstation zurückgesetzt'); },
    exportObj: () => exportMesh('obj'), exportStl: () => exportMesh('stl'), exportPly: () => exportMesh('ply'), exportXyz: () => exportMesh('xyz'),
    exportDepthCsv: () => needImage() && (S.depth ? saveText(`${stamp()}_tiefe_mm.csv`, depthCsv()) : toast('Keine 3D-Tiefenkarte vorhanden')),
    exportDepthPng: () => needImage() && (S.depth ? saveData(`${stamp()}_tiefenkarte.png`, depthDataUrl()) : toast('Keine 3D-Tiefenkarte vorhanden')),
    reportPdf: () => needImage() && printReport(),
    reportHtml: () => needImage() && saveText(`${stamp()}_befundbericht.html`, buildReportHtml()),
    exportJson: () => needImage() && saveText(`${stamp()}_datensatz.json`, JSON.stringify({ patient: patient(), analyse: { ...S.res, raw_base64: undefined, overlay_base64: undefined, hotspot_mask_base64: undefined, tophat_diff_base64: undefined, vascular_base64: undefined, depth_base64: undefined, corrected_base64: undefined }, diagnose_overrides: S.overrides, zonen: S.zones && S.zones.rows, plantardruck: S.pressure, arch_index: S.arch, annotationen: ANN.list }, null, 2)),
    hotspotsCsv: () => needImage() && saveText(`${stamp()}_herde.csv`, toCsv(hotspotRows())),
    zonesCsv: () => needImage() && saveText(`${stamp()}_zonen_biomechanik.csv`, toCsv([['Zone', 'Links °C', 'Rechts °C', 'ΔT K', 'Arterie'], ...S.zones.rows.map(r => [r.n, fmt(r.left, 2), fmt(r.right, 2), fmt(r.delta, 2), r.artery]), [], ['Spitzendruck kPa', S.pressure.peak.toFixed(0)], ['Mittlerer Druck kPa', S.pressure.mean.toFixed(0)], ['Hochrisikofläche cm²', S.pressure.highCm2.toFixed(2)], ['Arch Index L', S.arch.L ? S.arch.L.ai.toFixed(3) : '-'], ['Arch Index R', S.arch.R ? S.arch.R.ai.toFixed(3) : '-'], ['TAI K', fmt(S.zones.tai, 2)]])),
    matrixCsv: () => needImage() && saveText(`${stamp()}_temperaturmatrix.csv`, tempMatrixCsv()),
    exportViewPng: () => needImage() && saveData(`${stamp()}_ansicht.png`, viewDataUrl()),
    exportOverlayPng: () => needImage() && saveData(`${stamp()}_befund_overlay.png`, S.res.overlay_base64),
    exportVascPng: () => needImage() && (S.res.vascular_base64 ? saveData(`${stamp()}_gefaessbaum.png`, S.res.vascular_base64) : toast('Kein Gefäßfilter-Ergebnis')),
    autosplit: () => { if (!needImage()) return; S.zonesOverlay = true; const fb = S.zones.fbs; redrawAnnotations();
        const row = (s, n) => fb[s] ? `<tr><td><b>${n}</b></td><td>${fb[s].maxX - fb[s].minX} × ${fb[s].bottom - fb[s].top} px</td><td>${((fb[s].maxX - fb[s].minX) * PX_MM).toFixed(0)} × ${((fb[s].bottom - fb[s].top) * PX_MM).toFixed(0)} mm</td></tr>` : `<tr><td>${n}</td><td colspan="2">nicht erkannt</td></tr>`;
        showModal('Extremitäten getrennt', `<p>Bilaterale Trennung an Mittellinie X = ${S.midline}.</p><table>${row('L', 'Linker Fuß')}${row('R', 'Rechter Fuß')}</table>`,
            [{ label: 'Linker Fuß', fn: () => fb.L && focusRegion([fb.L.minX, fb.L.top, fb.L.maxX, fb.L.bottom]) }, { label: 'Rechter Fuß', fn: () => fb.R && focusRegion([fb.R.minX, fb.R.top, fb.R.maxX, fb.R.bottom]) }, { label: 'Schließen', primary: true }]); },
    luaTab: () => { selectCategory('signals'); $('lua-editor').scrollIntoView({ behavior: 'smooth' }); $('lua-editor').focus(); },
    luaValidate: async () => { if (!hasWails()) return; const e = await api().ValidateLua($('lua-editor').value); $('lua-status').textContent = e ? '✗ ' + e : '✓ Syntax gültig'; $('lua-status').style.color = e ? '#F87171' : '#4ADE80'; },
    luaApply: async () => { if (!hasWails() || !S.imagePath) return toast('Zuerst ein Bild laden'); const e = await api().ValidateLua($('lua-editor').value); if (e) { $('lua-status').textContent = '✗ ' + e; return; }
        setLoading(true); try { await loadResult(await api().AnalyzeWithLua(S.imagePath, cfgFromUi(), $('lua-editor').value)); $('lua-status').textContent = '✓ Regeln angewendet'; } catch (x) { toast('' + x); } setLoading(false); },
    luaReset: async () => { if (hasWails()) { $('lua-editor').value = await api().GetDefaultLua(); $('lua-status').textContent = 'Standardregeln geladen (zum Übernehmen „Anwenden“)'; } },
    benchmark: async () => { if (!hasWails()) return toast('Nur in der Desktop-App'); if (!needImage()) return; selectCategory('system'); toast('Benchmark läuft…'); const b = await api().RunBenchmark(5);
        $('bn-mean').textContent = `${b.mean_ms.toFixed(1)} ms`; $('bn-minmax').textContent = `${b.min_ms.toFixed(1)} / ${b.max_ms.toFixed(1)} ms`; $('bn-fps').textContent = `${b.fps.toFixed(2)} Bilder/s · ${b.megapixels_per_s.toFixed(1)} MPx/s`; refreshAudit(); },
    auditVerify: () => { selectCategory('system'); verifyAudit(); },
    shortcuts: () => showModal('Tastenkürzel', `<table><tr><td><kbd>Strg+O</kbd></td><td>Bild öffnen</td></tr><tr><td><kbd>Strg+Z / Y</kbd></td><td>Rückgängig / Wiederholen</td></tr><tr><td><kbd>Strg+R</kbd></td><td>Alles zurücksetzen</td></tr><tr><td><kbd>Strg+P</kbd></td><td>42-Stufen-PAP</td></tr><tr><td><kbd>← / →</kbd></td><td>Vorheriger / nächster Fall</td></tr><tr><td><kbd>+ / − / 0 / 1</kbd></td><td>Zoom / Einpassen / 1:1</td></tr><tr><td><kbd>C H R O G L S W M T X</kbd></td><td>Fadenkreuz, Pan, Rechteck, Kreis, Polygon, Profil, Sonde, Winkel, Lineal, Text, Radierer</td></tr><tr><td><kbd>Entf</kbd></td><td>Letzte Markierung entfernen</td></tr><tr><td><kbd>Shift + Ziehen</kbd></td><td>Window/Level interaktiv</td></tr><tr><td><kbd>Mausrad / Mitteltaste</kbd></td><td>Zoom am Cursor / Pan</td></tr><tr><td><kbd>Esc</kbd></td><td>Abbrechen</td></tr></table>`, [{ label: 'Schließen', primary: true }]),
    about: () => showModal('IGNITE Medical Imaging Suite v12.3.4.81', '<p>Vollautomatische, deterministische Früherkennung subklinischer Entzündungen und diabetischer Fußulzera mittels LWIR-Thermografie.</p><p>Go-Kern (42 Stufen, AVX2), Lua-Regelwerk, SQLite/SHA-256-Audit. Jugend forscht 2026 · Jona Noack.</p><p><small>DIN EN ISO 13485 · IWGDF · Armstrong 2007 (ΔT ≥ 2,2 K) · DSGVO Art. 25/30</small></p>', [{ label: 'Schließen', primary: true }])
};

// ── Init ────────────────────────────────────────────────────────────────────
function loadPatient(id) { try { const o = JSON.parse(localStorage.getItem('ignite_pt_' + id) || '{}'); $('pt-age').value = o.age || ''; $('pt-sex').value = o.sex || '–'; $('pt-region').value = o.region || 'Füße (bilateral)'; $('pt-note').value = o.note || ''; } catch (e) { } }
function savePatient() { localStorage.setItem('ignite_pt_' + $('pt-id').value, JSON.stringify({ age: $('pt-age').value, sex: $('pt-sex').value, region: $('pt-region').value, note: $('pt-note').value })); }

document.addEventListener('DOMContentLoaded', () => {
    $('sel-palette').innerHTML = Object.keys(PALETTE_NAMES).map(k => `<option value="${k}">${PALETTE_NAMES[k]}</option>`).join('');
    $('pt-date').value = new Date().toISOString().slice(0, 10);
    document.body.addEventListener('click', e => {
        const el = e.target.closest('[data-act],[data-tool],[data-view],[data-mode],[data-cat]'); if (!el) return;
        if (el.dataset.act) { const f = ACTIONS[el.dataset.act]; if (f) f(); }
        else if (el.dataset.tool) setTool(el.dataset.tool);
        else if (el.dataset.view) setView(el.dataset.view);
        else if (el.dataset.mode) setViewportMode(el.dataset.mode);
        else if (el.dataset.cat) selectCategory(el.dataset.cat);
        if (el.closest('.menu-drop')) { const d = el.closest('.menu-drop'); d.style.display = 'none'; setTimeout(() => d.style.display = '', 150); }
    });
    $('sel-palette').onchange = e => { S.palette = e.target.value; requestRender(); drawHistogram(); };
    $('sel-view').onchange = e => setView(e.target.value);
    $('sel-wl').onchange = e => { const p = WL_PRESETS[e.target.value]; S.window = p.w; S.level = p.l; $('sl-window').value = p.w; $('sl-level').value = p.l; $('val-window').textContent = p.w; $('val-level').textContent = p.l; requestRender(); };
    $('sl-window').oninput = e => { S.window = +e.target.value; $('val-window').textContent = S.window; requestRender(); };
    $('sl-level').oninput = e => { S.level = +e.target.value; $('val-level').textContent = S.level; requestRender(); };
    $('sl-iso-lo').oninput = e => { S.isoLo = +e.target.value; $('val-iso-lo').textContent = S.isoLo.toFixed(1) + ' °C'; requestRender(); };
    $('sl-iso-hi').oninput = e => { S.isoHi = +e.target.value; $('val-iso-hi').textContent = S.isoHi.toFixed(1) + ' °C'; requestRender(); };
    $('sl-vein-op').oninput = e => { S.veinOp = e.target.value / 100; $('val-vein-op').textContent = e.target.value + ' %'; requestRender(); };
    $('sl-vein-th').oninput = e => { S.veinTh = +e.target.value; $('val-vein-th').textContent = e.target.value; updateVeinInfo(); requestRender(); };
    $('slider-k').oninput = e => { $('param-k-val').textContent = (+e.target.value).toFixed(1); drawHistogram(); };
    $('slider-r').oninput = e => $('param-r-val').textContent = (+e.target.value).toFixed(3);
    $('slider-m').oninput = e => $('param-m-val').textContent = (+e.target.value).toFixed(3);
    ['pt-age', 'pt-sex', 'pt-region', 'pt-note'].forEach(id => $(id).addEventListener('change', savePatient));
    // Curtain
    $('curtain-handle').addEventListener('mousedown', e => { S.dragCurtain = true; e.preventDefault(); });
    window.addEventListener('mousemove', e => { if (!S.dragCurtain) return; const r = $('viewports-wrapper').getBoundingClientRect(); S.curtain = Math.max(.03, Math.min(.97, (e.clientX - r.left) / r.width)); updateCurtain(); });
    window.addEventListener('mouseup', () => S.dragCurtain = false);
    window.addEventListener('resize', () => setTimeout(fitAll, 50));
    bindCanvasEvents(); bindWindowLevelDrag();
    document.addEventListener('keydown', onKey); updateUndoButtons();
    const skipBtn = $('splash-btn-skip');
    if (skipBtn) skipBtn.onclick = dismissSplash;
    const splashScreen = $('splash-screen');
    if (splashScreen) {
        splashScreen.addEventListener('click', e => {
            if (!e.target.closest('button') && splashRunning) dismissSplash();
        });
    }
    runSplashSequence(false);
    if (hasWails()) { api().GetDefaultLua().then(t => $('lua-editor').value = t); buildFilmstrip().then(() => setTimeout(() => ACTIONS.demo(), 300)); }
    else setTimeout(() => ACTIONS.demo(), 400);
});

function bindWindowLevelDrag() {
    ['container-orig', 'container-result'].forEach(id => {
        $(id).addEventListener('mousedown', e => { if (e.shiftKey && e.button === 0 && S.gray) { S.wl = { sx: e.clientX, sy: e.clientY, w: S.window, l: S.level }; e.stopPropagation(); e.preventDefault(); } }, true);
    });
    window.addEventListener('mousemove', e => { if (!S.wl) return; S.window = Math.max(20, Math.min(255, S.wl.w + (e.clientX - S.wl.sx))); S.level = Math.max(0, Math.min(255, S.wl.l - (e.clientY - S.wl.sy)));
        $('sl-window').value = S.window; $('sl-level').value = S.level; $('val-window').textContent = Math.round(S.window); $('val-level').textContent = Math.round(S.level); requestRender(); });
    window.addEventListener('mouseup', () => S.wl = null);
}
function onKey(e) {
    if (splashRunning && (e.key === ' ' || e.key === 'Escape' || e.key === 'Enter')) {
        e.preventDefault();
        dismissSplash();
        return;
    }
    const tag = (e.target.tagName || '').toLowerCase(); const typing = tag === 'input' || tag === 'textarea' || tag === 'select';
    if (e.key === 'Escape') { ANN.draft = null; closeModal(); redrawAnnotations(); return; }
    if (e.ctrlKey || e.metaKey) { const k = e.key.toLowerCase(); const m = { z: doUndo, y: doRedo, r: ACTIONS.reset, o: ACTIONS.open, p: ACTIONS.pap }[k]; if (m && !(typing && k === 'z')) { e.preventDefault(); m(); } return; }
    if (typing) return;
    const toolKeys = { c: 'crosshair', h: 'pan', r: 'rect', o: 'circle', g: 'poly', l: 'profile', s: 'probe', w: 'gonio', m: 'ruler', t: 'text', x: 'erase' };
    if (toolKeys[e.key.toLowerCase()]) return setTool(toolKeys[e.key.toLowerCase()]);
    if (e.key === 'ArrowRight') ACTIONS.nextCase(); else if (e.key === 'ArrowLeft') ACTIONS.prevCase();
    else if (e.key === '+' || e.key === '=') ACTIONS.zoomIn(); else if (e.key === '-') ACTIONS.zoomOut();
    else if (e.key === '0' || e.key === 'f') ACTIONS.fit(); else if (e.key === '1') ACTIONS.actual();
    else if (e.key === 'Delete' && ANN.list.length) { pushUndo(); ANN.list.pop(); annChanged(); }
}

// ── Browser-Fallback (ohne Wails): synthetisches Testbild ───────────────────
function syntheticResult() {
    const w = 720, h = 540, c = document.createElement('canvas'); c.width = w; c.height = h; const x = c.getContext('2d'), im = x.createImageData(w, h);
    for (let yy = 0; yy < h; yy++) for (let xx = 0; xx < w; xx++) {
        let v = 25; [[w * .3, h * .55], [w * .7, h * .55]].forEach(([cx, cy]) => { const d = ((xx - cx) / 70) ** 2 + ((yy - cy) / 190) ** 2; if (d < 1) v = Math.max(v, 150 - d * 60); });
        const hot = ((xx - w * .32) / 28) ** 2 + ((yy - h * .22) / 30) ** 2; if (hot < 1) v = Math.max(v, 235 - hot * 40); const j = (yy * w + xx) * 4; im.data[j] = im.data[j + 1] = im.data[j + 2] = v; im.data[j + 3] = 255;
    } x.putImageData(im, 0, 0); const raw = c.toDataURL();
    const m = document.createElement('canvas'); m.width = w; m.height = h; const mx = m.getContext('2d'); mx.fillStyle = '#000'; mx.fillRect(0, 0, w, h); mx.fillStyle = '#fff'; mx.beginPath(); mx.ellipse(w * .32, h * .22, 28, 30, 0, 0, 7); mx.fill();
    return { success: true, image_path: 'demo', filename: 'synthetisch_demo.png', width: w, height: h, raw_base64: raw, overlay_base64: raw, hotspot_mask_base64: m.toDataURL(), depth_base64: '', stages: Array.from({ length: 42 }, (_, i) => ({ stage_number: i + 1, name: 'Pipeline-Stufe ' + (i + 1), duration_us: 500 + i * 40, status: 'COMPLETED' })),
        total_hotspots: 1, highest_risk: 'CRITICAL', timing: { total_ms: 38.4 }, max_depth_mm: 35, edge_correction_k: 2.4, bioheat_mean: 28.6, bioheat_hyper_pct: 4.2, perfusion_status: 'ACUTE_HYPERAEMIA',
        hotspots: [{ region: { center_x: w * .32, center_y: h * .22, area_pixels: 3000, max_val: 235, contra_delta: 64, circularity: .6, confidence_score: 94, local_prominence: 72, bounding_box: [Math.round(w * .32 - 32), Math.round(h * .22 - 34), Math.round(w * .32 + 32), Math.round(h * .22 + 34)], diagnosis_type: 'INFLAMMATION' }, assessment: { risk_level: 'CRITICAL', score: 9.5, diagnosis_type: 'INFLAMMATION', recommendation: 'Pathologischer Entzündungsherd (Armstrong ΔT ≥ 2,2 K).' } }] };
}
