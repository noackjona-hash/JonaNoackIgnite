// IGNITE MEDICAL WORKSTATION · MESS- & ANNOTATIONSWERKZEUGE
// ROI (Rechteck/Kreis/Polygon), Profil, Sonden, Goniometer, Lineal, Text, Radierer, Undo/Redo.

const ANN = { list: [], undo: [], redo: [], tool: 'crosshair', draft: null, nextId: 1, probeN: 0, roiN: 0, pan: null };

function annSnapshot() { return JSON.stringify({ list: ANN.list, ov: S.overrides, nid: ANN.nextId, pn: ANN.probeN, rn: ANN.roiN }); }
function annRestore(s) { const o = JSON.parse(s); ANN.list = o.list; S.overrides = o.ov || {}; ANN.nextId = o.nid; ANN.probeN = o.pn; ANN.roiN = o.rn; annChanged(false); }
function pushUndo() { ANN.undo.push(annSnapshot()); if (ANN.undo.length > 100) ANN.undo.shift(); ANN.redo = []; updateUndoButtons(); }
function doUndo() { if (!ANN.undo.length) return toast('Nichts zum Rückgängigmachen'); ANN.redo.push(annSnapshot()); annRestore(ANN.undo.pop()); updateUndoButtons(); toast('↶ Rückgängig'); }
function doRedo() { if (!ANN.redo.length) return toast('Nichts zum Wiederholen'); ANN.undo.push(annSnapshot()); annRestore(ANN.redo.pop()); updateUndoButtons(); toast('↷ Wiederholt'); }
function updateUndoButtons() {
    const u = document.getElementById('btn-undo'), r = document.getElementById('btn-redo');
    if (u) u.style.opacity = ANN.undo.length ? 1 : .4; if (r) r.style.opacity = ANN.redo.length ? 1 : .4;
}
function annChanged(refreshPanels = true) { redrawAnnotations(); if (refreshPanels) updateMeasurementPanels(); else updateMeasurementPanels(); }
function clearAnnotations() { if (!ANN.list.length) return; pushUndo(); ANN.list = []; ANN.probeN = 0; ANN.roiN = 0; annChanged(); toast('Alle Markierungen gelöscht'); }

function setTool(t) {
    ANN.tool = t; ANN.draft = null;
    document.querySelectorAll('.tool-btn').forEach(b => b.classList.toggle('active', b.dataset.tool === t));
    document.querySelectorAll('.canvas-container').forEach(c => c.classList.toggle('tool-pan', t === 'pan'));
    redrawAnnotations();
    const names = { crosshair: 'Fadenkreuz', pan: 'Verschieben', rect: 'Rechteck-ROI', circle: 'Kreis-ROI', poly: 'Polygon-ROI (Doppelklick schließt)', profile: 'Schnittprofil', probe: 'Punktsonde', gonio: 'Goniometer (3 Punkte)', ruler: 'Lineal', text: 'Text-Annotation', erase: 'Radierer' };
    toast('Werkzeug: ' + names[t]);
}

function viewOf(side) { return side === 'L' ? V.L : V.R; }
function imgPoint(e, container, side) {
    const r = container.getBoundingClientRect(), v = viewOf(side);
    return { x: (e.clientX - r.left - v.x) / v.zoom, y: (e.clientY - r.top - v.y) / v.zoom };
}
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

function bindCanvasEvents() {
    [['L', 'container-orig'], ['R', 'container-result']].forEach(([side, id]) => {
        const c = document.getElementById(id);
        c.addEventListener('contextmenu', e => e.preventDefault());
        c.addEventListener('wheel', e => {
            if (!S.gray) return; e.preventDefault();
            const r = c.getBoundingClientRect(), v = viewOf(side), f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
            const nz = Math.max(.1, Math.min(40, v.zoom * f)), mx = e.clientX - r.left, my = e.clientY - r.top;
            v.x = mx - (mx - v.x) * nz / v.zoom; v.y = my - (my - v.y) * nz / v.zoom; v.zoom = nz; syncViews(side); applyViews();
        }, { passive: false });
        c.addEventListener('mousedown', e => {
            if (!S.gray) return; const p = imgPoint(e, c, side);
            if (e.button === 1 || e.button === 2 || ANN.tool === 'pan') {
                const v = viewOf(side); ANN.pan = { side, sx: e.clientX, sy: e.clientY, vx: v.x, vy: v.y }; c.classList.add('dragging'); e.preventDefault(); return;
            }
            if (e.button !== 0) return;
            const t = ANN.tool;
            if (t === 'rect' || t === 'circle' || t === 'profile' || t === 'ruler') { ANN.draft = { type: t, pts: [p, { ...p }], side }; }
            else if (t === 'poly') { if (!ANN.draft) ANN.draft = { type: 'poly', pts: [p, { ...p }], side }; else { ANN.draft.pts[ANN.draft.pts.length - 1] = p; ANN.draft.pts.push({ ...p }); } }
            else if (t === 'gonio') { if (!ANN.draft) ANN.draft = { type: 'gonio', pts: [p, { ...p }], side }; else { ANN.draft.pts[ANN.draft.pts.length - 1] = p; if (ANN.draft.pts.length >= 3) { commitDraft(); } else ANN.draft.pts.push({ ...p }); } }
            else if (t === 'probe') { pushUndo(); ANN.list.push({ id: ANN.nextId++, type: 'probe', label: 'S' + (++ANN.probeN), pts: [p] }); annChanged(); }
            else if (t === 'text') { askText('Text-Annotation', '').then(txt => { if (txt) { pushUndo(); ANN.list.push({ id: ANN.nextId++, type: 'text', text: txt, pts: [p] }); annChanged(); } }); }
            else if (t === 'erase') eraseAt(p, side);
            redrawAnnotations();
        });
        c.addEventListener('dblclick', e => { if (ANN.tool === 'poly' && ANN.draft && ANN.draft.pts.length >= 4) { ANN.draft.pts.pop(); ANN.draft.pts.pop(); commitDraft(); } });
        c.addEventListener('mousemove', e => {
            if (!S.gray) return; const p = imgPoint(e, c, side);
            if (ANN.pan) { const v = viewOf(ANN.pan.side); v.x = ANN.pan.vx + e.clientX - ANN.pan.sx; v.y = ANN.pan.vy + e.clientY - ANN.pan.sy; syncViews(ANN.pan.side); applyViews(); return; }
            if (ANN.draft) { ANN.draft.pts[ANN.draft.pts.length - 1] = p; redrawAnnotations(); }
            S.hover = p; drawCrosshairs(p.x, p.y); updateLiveTelemetry(Math.round(p.x), Math.round(p.y));
        });
        c.addEventListener('mouseup', e => {
            if (ANN.pan) { ANN.pan = null; c.classList.remove('dragging'); return; }
            const d = ANN.draft; if (!d) return;
            if (['rect', 'circle', 'profile', 'ruler'].includes(d.type)) { if (dist(d.pts[0], d.pts[1]) > 3) commitDraft(); else { ANN.draft = null; redrawAnnotations(); } }
        });
        c.addEventListener('mouseleave', () => { clearCrosshairs(); });
    });
    window.addEventListener('mouseup', () => { if (ANN.pan) { ANN.pan = null; document.querySelectorAll('.canvas-container').forEach(c => c.classList.remove('dragging')); } });
}

function commitDraft() {
    const d = ANN.draft; ANN.draft = null; if (!d) return;
    pushUndo(); const a = { id: ANN.nextId++, type: d.type, pts: d.pts };
    if (['rect', 'circle', 'poly'].includes(d.type)) a.label = 'ROI ' + (++ANN.roiN);
    if (d.type === 'profile') ANN.lastProfile = a;
    ANN.list.push(a); annChanged();
}
function eraseAt(p, side) {
    const tol = 10 / viewOf(side).zoom; let hit = -1, best = 1e9;
    ANN.list.forEach((a, i) => {
        let d = Math.min(...a.pts.map(q => dist(p, q)));
        if (a.type === 'rect' || a.type === 'circle') { const xs = a.pts.map(q => q.x), ys = a.pts.map(q => q.y); if (p.x >= Math.min(...xs) && p.x <= Math.max(...xs) && p.y >= Math.min(...ys) && p.y <= Math.max(...ys)) d = Math.min(d, tol - 1); }
        if (a.type === 'poly' && polygonContains(a.pts, p.x, p.y)) d = Math.min(d, tol - 1);
        if (d < tol && d < best) { best = d; hit = i; }
    });
    if (hit >= 0) { pushUndo(); ANN.list.splice(hit, 1); annChanged(); toast('Markierung entfernt'); }
}

function annAngle(a) {
    const [p, q, r] = a.pts; const v1 = { x: p.x - q.x, y: p.y - q.y }, v2 = { x: r.x - q.x, y: r.y - q.y };
    const dot = v1.x * v2.x + v1.y * v2.y, m = Math.hypot(v1.x, v1.y) * Math.hypot(v2.x, v2.y);
    return m ? Math.acos(Math.max(-1, Math.min(1, dot / m))) * 180 / Math.PI : 0;
}

function drawAnnotations(ctx, side) {
    const z = viewOf(side).zoom, lw = 1.8 / z, fs = 12 / z;
    ctx.save(); ctx.lineWidth = lw; ctx.font = `bold ${fs}px Consolas, monospace`; ctx.textBaseline = 'bottom';
    const label = (txt, x, y, col) => { const w = ctx.measureText(txt).width; ctx.fillStyle = 'rgba(7,10,18,.82)'; ctx.fillRect(x - 2 / z, y - fs - 2 / z, w + 4 / z, fs + 4 / z); ctx.fillStyle = col; ctx.fillText(txt, x, y); };
    const all = ANN.draft ? [...ANN.list, { ...ANN.draft, draft: true }] : ANN.list;
    all.forEach(a => {
        const P = a.pts; ctx.strokeStyle = ctx.fillStyle = '#38BDF8'; ctx.setLineDash(a.draft ? [6 / z, 4 / z] : []);
        if (a.type === 'rect') {
            const x = Math.min(P[0].x, P[1].x), y = Math.min(P[0].y, P[1].y), w = Math.abs(P[1].x - P[0].x), h = Math.abs(P[1].y - P[0].y);
            ctx.fillStyle = 'rgba(56,189,248,.12)'; ctx.fillRect(x, y, w, h); ctx.strokeRect(x, y, w, h);
            if (!a.draft) { const s = roiStats(S, a); if (s) label(`${a.label} Ø${s.mean.toFixed(1)}°C`, x, y - 2 / z, '#38BDF8'); }
        } else if (a.type === 'circle') {
            const cx = (P[0].x + P[1].x) / 2, cy = (P[0].y + P[1].y) / 2, rx = Math.abs(P[1].x - P[0].x) / 2, ry = Math.abs(P[1].y - P[0].y) / 2;
            ctx.beginPath(); ctx.ellipse(cx, cy, rx, ry, 0, 0, 7); ctx.fillStyle = 'rgba(56,189,248,.12)'; ctx.fill(); ctx.stroke();
            if (!a.draft) { const s = roiStats(S, a); if (s) label(`${a.label} Ø${s.mean.toFixed(1)}°C`, cx - rx, cy - ry - 2 / z, '#38BDF8'); }
        } else if (a.type === 'poly') {
            ctx.beginPath(); P.forEach((q, i) => i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y)); if (!a.draft) ctx.closePath();
            ctx.fillStyle = 'rgba(56,189,248,.12)'; if (!a.draft) ctx.fill(); ctx.stroke();
            if (!a.draft) { const s = roiStats(S, a); if (s) label(`${a.label} Ø${s.mean.toFixed(1)}°C`, P[0].x, P[0].y - 2 / z, '#38BDF8'); }
        } else if (a.type === 'profile') {
            ctx.strokeStyle = ctx.fillStyle = '#FACC15'; ctx.beginPath(); ctx.moveTo(P[0].x, P[0].y); ctx.lineTo(P[1].x, P[1].y); ctx.stroke();
            label('A', P[0].x + 4 / z, P[0].y - 4 / z, '#FACC15'); label('B', P[1].x + 4 / z, P[1].y - 4 / z, '#FACC15');
        } else if (a.type === 'ruler') {
            ctx.strokeStyle = ctx.fillStyle = '#FB923C'; ctx.beginPath(); ctx.moveTo(P[0].x, P[0].y); ctx.lineTo(P[1].x, P[1].y); ctx.stroke();
            label(`${(dist(P[0], P[1]) * PX_MM).toFixed(1)} mm`, (P[0].x + P[1].x) / 2, (P[0].y + P[1].y) / 2 - 4 / z, '#FB923C');
        } else if (a.type === 'gonio') {
            ctx.strokeStyle = ctx.fillStyle = '#4ADE80'; ctx.beginPath(); P.forEach((q, i) => i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y)); ctx.stroke();
            if (P.length >= 3) label(`${annAngle(a).toFixed(1)}°`, P[1].x + 8 / z, P[1].y - 8 / z, '#4ADE80');
        } else if (a.type === 'probe') {
            const v = S.gray[Math.round(P[0].y) * S.w + Math.round(P[0].x)]; ctx.strokeStyle = ctx.fillStyle = '#F472B6';
            ctx.beginPath(); ctx.arc(P[0].x, P[0].y, 5 / z, 0, 7); ctx.stroke(); ctx.beginPath(); ctx.arc(P[0].x, P[0].y, 1.5 / z, 0, 7); ctx.fill();
            label(`${a.label} ${tempOf(v).toFixed(1)}°C`, P[0].x + 8 / z, P[0].y - 6 / z, '#F472B6');
        } else if (a.type === 'text') {
            ctx.strokeStyle = ctx.fillStyle = '#F8FAFC'; ctx.beginPath(); ctx.moveTo(P[0].x, P[0].y); ctx.lineTo(P[0].x + 28 / z, P[0].y - 22 / z); ctx.stroke();
            ctx.beginPath(); ctx.arc(P[0].x, P[0].y, 3 / z, 0, 7); ctx.fill(); label(a.text, P[0].x + 30 / z, P[0].y - 22 / z, '#F8FAFC');
        }
    });
    ctx.restore();
}
