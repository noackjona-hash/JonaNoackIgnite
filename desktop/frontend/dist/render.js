// IGNITE MEDICAL WORKSTATION · RENDER & ANALYTICS ENGINE
// Palettes, W/L, diagnostic view modes and client-side radiometric analytics.
// Temperaturmodell identisch zum Go-Kern: T = 20 °C + 0,1 K × Rohwert; Pixelpitch 0,6 mm.

const TEMP_BASE = 20.0, TEMP_STEP = 0.1, PX_MM = 0.6;
const tempOf = v => TEMP_BASE + v * TEMP_STEP;

function lutFromStops(stops) {
    const lut = new Uint8ClampedArray(768);
    for (let i = 0; i < 256; i++) {
        const t = i / 255;
        let k = 0;
        while (k < stops.length - 2 && t > stops[k + 1][0]) k++;
        const a = stops[k], b = stops[k + 1];
        const f = Math.max(0, Math.min(1, (t - a[0]) / (b[0] - a[0] || 1)));
        for (let c = 0; c < 3; c++) lut[i * 3 + c] = a[c + 1] + (b[c + 1] - a[c + 1]) * f;
    }
    return lut;
}

const PALETTES = {
    ironbow: lutFromStops([[0, 10, 15, 40], [.25, 0, 10, 160], [.5, 130, 70, 220], [.75, 240, 160, 0], [1, 255, 255, 255]]),
    rainbow: lutFromStops([[0, 0, 0, 128], [.2, 0, 80, 255], [.4, 0, 230, 200], [.6, 120, 255, 40], [.8, 255, 180, 0], [1, 255, 0, 0]]),
    inferno: lutFromStops([[0, 0, 0, 4], [.25, 87, 16, 110], [.5, 188, 55, 84], [.75, 249, 142, 9], [1, 252, 255, 164]]),
    gray: lutFromStops([[0, 0, 0, 0], [1, 255, 255, 255]]),
    turbo: lutFromStops([[0, 48, 18, 59], [.2, 70, 107, 227], [.4, 27, 207, 212], [.6, 164, 252, 60], [.8, 251, 128, 29], [1, 122, 4, 3]]),
    hot: lutFromStops([[0, 0, 0, 0], [.35, 230, 0, 0], [.7, 255, 210, 0], [1, 255, 255, 255]]),
    coolwarm: lutFromStops([[0, 59, 76, 192], [.5, 221, 221, 221], [1, 180, 4, 38]])
};
const PALETTE_NAMES = {
    ironbow: 'Ironbow (klinisch)', rainbow: 'Rainbow', inferno: 'Inferno', gray: 'Medizin-Graustufen',
    turbo: 'Turbo', hot: 'High-Contrast Hot', coolwarm: 'Cold-Warm'
};

const WL_PRESETS = {
    standard: { w: 255, l: 128, n: 'Standard LWIR' },
    druck: { w: 90, l: 190, n: 'Druck / Knochen' },
    vaskulaer: { w: 120, l: 150, n: 'Vaskulär / Perfusion' },
    zehen: { w: 70, l: 200, n: 'Extremitäten / Zehen' },
    voll: { w: 255, l: 128, n: 'Vollbereich' }
};

function buildWlTable(S) {
    const tab = new Uint8Array(256);
    const lo = S.level - S.window / 2;
    for (let v = 0; v < 256; v++) {
        let x = (v - lo) * 255 / S.window;
        x = x < 0 ? 0 : x > 255 ? 255 : x;
        tab[v] = S.invert ? 255 - x : x;
    }
    return tab;
}

function newImage(w, h) { return new ImageData(w, h); }
function putIdx(d, i, lut, idx) { const j = i * 4, k = idx * 3; d[j] = lut[k]; d[j + 1] = lut[k + 1]; d[j + 2] = lut[k + 2]; d[j + 3] = 255; }
const clamp255 = x => x < 0 ? 0 : x > 255 ? 255 : x | 0;

// ── Analytics ───────────────────────────────────────────────────────────────
function otsuThreshold(g) {
    const hist = new Float64Array(256); for (let i = 0; i < g.length; i++) hist[g[i]]++;
    let sum = 0; for (let t = 0; t < 256; t++) sum += t * hist[t];
    let wB = 0, sB = 0, best = 0, thr = 100; const tot = g.length;
    for (let t = 0; t < 256; t++) {
        wB += hist[t]; if (!wB) continue; const wF = tot - wB; if (!wF) break;
        sB += t * hist[t]; const mB = sB / wB, mF = (sum - sB) / wF;
        const v = wB * wF * (mB - mF) * (mB - mF); if (v > best) { best = v; thr = t; }
    }
    return thr;
}
function histogram(g, minV) { const h = new Float64Array(256); for (let i = 0; i < g.length; i++) if (g[i] >= minV) h[g[i]]++; return h; }
function medianMAD(g, minV) {
    const h = histogram(g, minV); let n = 0; for (const c of h) n += c; if (!n) return { med: 0, mad: 0, n: 0 };
    const q = (hh, nn) => { let a = 0; for (let v = 0; v < 256; v++) { a += hh[v]; if (a >= nn / 2) return v; } return 0; };
    const med = q(h, n); const d = new Float64Array(256);
    for (let v = 0; v < 256; v++) d[Math.abs(v - med)] += h[v];
    return { med, mad: q(d, n), n };
}
function percentile(g, minV, p) { const h = histogram(g, minV); let n = 0; for (const c of h) n += c; let a = 0; for (let v = 0; v < 256; v++) { a += h[v]; if (a >= n * p) return v; } return 255; }

function boxBlur(g, w, h, r) {
    const I = new Float64Array((w + 1) * (h + 1));
    for (let y = 0; y < h; y++) { let row = 0; for (let x = 0; x < w; x++) { row += g[y * w + x]; I[(y + 1) * (w + 1) + x + 1] = I[y * (w + 1) + x + 1] + row; } }
    const out = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
        const y0 = Math.max(0, y - r), y1 = Math.min(h, y + r + 1);
        for (let x = 0; x < w; x++) {
            const x0 = Math.max(0, x - r), x1 = Math.min(w, x + r + 1);
            const s = I[y1 * (w + 1) + x1] - I[y0 * (w + 1) + x1] - I[y1 * (w + 1) + x0] + I[y0 * (w + 1) + x0];
            out[y * w + x] = s / ((x1 - x0) * (y1 - y0));
        }
    }
    return out;
}

function pressureKpa(v, thr) { return v < thr ? 0 : 80 + (v - thr) / Math.max(1, 255 - thr) * 420; }

// Bilateral midline = Spalte mit minimaler Gewebedichte zwischen 30 % und 70 % der Breite
function findMidline(S) {
    const { gray, w, h } = S; const thr = S.otsu; let best = Math.floor(w / 2), bv = 1e9;
    for (let x = Math.floor(w * .3); x < w * .7; x++) { let c = 0; for (let y = 0; y < h; y += 2) if (gray[y * w + x] >= thr) c++; if (c < bv) { bv = c; best = x; } }
    return best;
}

// 5-Zonen-Modell (Bounding-Box-Näherung): Digiti, Metatarsale I, Metatarsale II–V, Mittelfuß, Calcaneus
const ZONES = [
    { id: 'toes', n: 'Hallux & Digiti', artery: 'A. tibialis anterior (A. dorsalis pedis)', terr: 'Dorsaler Vorfuß' },
    { id: 'meta1', n: 'Metatarsale I (Ballen)', artery: 'A. tibialis posterior (A. plantaris medialis)', terr: 'Mediale Plantarregion' },
    { id: 'meta2', n: 'Metatarsale II–V', artery: 'A. tibialis posterior (A. plantaris lateralis)', terr: 'Laterale Plantarregion' },
    { id: 'mid', n: 'Mittelfuß & Gewölbe', artery: 'A. tibialis anterior / A. peronea', terr: 'Fußrücken & Gewölbe' },
    { id: 'heel', n: 'Calcaneus (Ferse)', artery: 'A. peronea / A. tibialis posterior (Rr. calcanei)', terr: 'Calcaneus-Region' }
];
function footBoxes(S) {
    const { gray, w, h } = S, thr = S.otsu, mid = S.midline; const out = {};
    ['L', 'R'].forEach(side => {
        const x0 = side === 'L' ? 0 : mid, x1 = side === 'L' ? mid : w;
        let top = h, minX = w, maxX = 0;
        for (let y = 0; y < h; y++) for (let x = x0; x < x1; x++) if (gray[y * w + x] >= thr) { if (y < top) top = y; if (x < minX) minX = x; if (x > maxX) maxX = x; }
        if (top >= h) { out[side] = null; return; }
        const bottom = Math.min(h - 1, Math.round(top + 0.68 * (h - top)));
        out[side] = { side, top, bottom, minX, maxX, x0, x1 };
    });
    return out;
}
function zoneOf(S, fb, x, y) {
    if (!fb || y < fb.top || y > fb.bottom) return null;
    const f = (y - fb.top) / Math.max(1, fb.bottom - fb.top);
    if (f < .18) return 'toes'; if (f < .42) { const inner = fb.side === 'L' ? (x > (fb.minX + fb.maxX) / 2) : (x < (fb.minX + fb.maxX) / 2); return inner ? 'meta1' : 'meta2'; }
    if (f < .72) return 'mid'; return 'heel';
}
function zoneStats(S) {
    const fbs = footBoxes(S), thr = S.otsu, { gray, w, h } = S;
    const acc = { L: {}, R: {} }; ZONES.forEach(z => { acc.L[z.id] = { s: 0, n: 0, mx: 0 }; acc.R[z.id] = { s: 0, n: 0, mx: 0 }; });
    ['L', 'R'].forEach(side => {
        const fb = fbs[side]; if (!fb) return;
        for (let y = fb.top; y <= fb.bottom; y++) for (let x = fb.x0; x < fb.x1; x++) {
            const v = gray[y * w + x]; if (v < thr) continue; const z = zoneOf(S, fb, x, y); if (!z) continue;
            const a = acc[side][z]; a.s += v; a.n++; if (v > a.mx) a.mx = v;
        }
    });
    const rows = ZONES.map(z => {
        const l = acc.L[z.id], r = acc.R[z.id];
        const lm = l.n ? tempOf(l.s / l.n) : NaN, rm = r.n ? tempOf(r.s / r.n) : NaN;
        const lx = l.n ? tempOf(l.mx) : NaN, rx = r.n ? tempOf(r.mx) : NaN;
        return { ...z, left: lm, right: rm, leftMax: lx, rightMax: rx, delta: (isNaN(lm) || isNaN(rm)) ? NaN : Math.abs(lm - rm), deltaMax: (isNaN(lx) || isNaN(rx)) ? NaN : Math.abs(lx - rx) };
    });
    const ds = rows.map(r => r.delta).filter(d => !isNaN(d));
    const tai = ds.length ? ds.reduce((a, b) => a + b, 0) / ds.length : NaN;
    return { rows, fbs, tai };
}
function pressureStats(S) {
    const { gray, w, h } = S, thr = S.otsu; let sum = 0, n = 0, peak = 0, px = 0, py = 0, hi = 0;
    const fbs = footBoxes(S);
    ['L', 'R'].forEach(side => { const fb = fbs[side]; if (!fb) return;
        for (let y = fb.top; y <= fb.bottom; y++) for (let x = fb.x0; x < fb.x1; x++) {
            const v = gray[y * w + x]; if (v < thr) continue; const p = pressureKpa(v, thr);
            sum += p; n++; if (p > peak) { peak = p; px = x; py = y; } if (p >= 320) hi++;
        } });
    return { peak, px, py, mean: n ? sum / n : 0, highPx: hi, highCm2: hi * PX_MM * PX_MM / 100, cat: peak >= 450 ? 'Kritisch (≥ 450 kPa)' : peak >= 320 ? 'Erhöht (≥ 320 kPa)' : 'Physiologisch' };
}
function archIndex(S) {
    const fbs = footBoxes(S), thr = S.otsu, { gray, w } = S, res = {};
    ['L', 'R'].forEach(side => {
        const fb = fbs[side]; if (!fb) { res[side] = null; return; }
        const y0 = fb.top + Math.round(.18 * (fb.bottom - fb.top)), len = fb.bottom - y0, t = len / 3;
        const c = [0, 0, 0];
        for (let y = y0; y <= fb.bottom; y++) { const k = Math.min(2, Math.floor((y - y0) / t)); for (let x = fb.x0; x < fb.x1; x++) if (gray[y * w + x] >= thr) c[k]++; }
        const tot = c[0] + c[1] + c[2]; const ai = tot ? c[1] / tot : NaN;
        res[side] = { ai, type: isNaN(ai) ? '—' : ai < .21 ? 'Pes Cavus (Hohlfuß)' : ai <= .26 ? 'Normalfuß' : 'Pes Planus (Senk-/Plattfuß / Charcot-Verdacht)' };
    });
    return res;
}
function polygonContains(pts, x, y) {
    let c = false;
    for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
        if (((pts[i].y > y) !== (pts[j].y > y)) && (x < (pts[j].x - pts[i].x) * (y - pts[i].y) / (pts[j].y - pts[i].y) + pts[i].x)) c = !c;
    }
    return c;
}
function roiStats(S, a) {
    const { gray, w, h } = S; let x0, y0, x1, y1, inside;
    if (a.type === 'rect') { x0 = Math.min(a.pts[0].x, a.pts[1].x); x1 = Math.max(a.pts[0].x, a.pts[1].x); y0 = Math.min(a.pts[0].y, a.pts[1].y); y1 = Math.max(a.pts[0].y, a.pts[1].y); inside = () => true; }
    else if (a.type === 'circle') { const cx = (a.pts[0].x + a.pts[1].x) / 2, cy = (a.pts[0].y + a.pts[1].y) / 2, rx = Math.abs(a.pts[1].x - a.pts[0].x) / 2 || 1, ry = Math.abs(a.pts[1].y - a.pts[0].y) / 2 || 1;
        x0 = cx - rx; x1 = cx + rx; y0 = cy - ry; y1 = cy + ry; inside = (x, y) => ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1; }
    else { x0 = Math.min(...a.pts.map(p => p.x)); x1 = Math.max(...a.pts.map(p => p.x)); y0 = Math.min(...a.pts.map(p => p.y)); y1 = Math.max(...a.pts.map(p => p.y)); inside = (x, y) => polygonContains(a.pts, x, y); }
    x0 = Math.max(0, Math.floor(x0)); y0 = Math.max(0, Math.floor(y0)); x1 = Math.min(w - 1, Math.ceil(x1)); y1 = Math.min(h - 1, Math.ceil(y1));
    let n = 0, s = 0, s2 = 0, mn = 255, mx = 0;
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (inside(x, y)) { const v = gray[y * w + x]; n++; s += v; s2 += v * v; if (v < mn) mn = v; if (v > mx) mx = v; }
    if (!n) return null; const m = s / n, sd = Math.sqrt(Math.max(0, s2 / n - m * m));
    return { n, areaMm2: n * PX_MM * PX_MM, min: tempOf(mn), max: tempOf(mx), mean: tempOf(m), sd: sd * TEMP_STEP };
}
function sampleProfile(S, p0, p1) {
    const len = Math.max(2, Math.round(Math.hypot(p1.x - p0.x, p1.y - p0.y))); const out = [];
    for (let i = 0; i <= len; i++) { const t = i / len, x = Math.round(p0.x + (p1.x - p0.x) * t), y = Math.round(p0.y + (p1.y - p0.y) * t);
        out.push(x >= 0 && y >= 0 && x < S.w && y < S.h ? S.gray[y * S.w + x] : 0); }
    return out;
}

// ── View-Mode Renderer ──────────────────────────────────────────────────────
function renderRaw(S) {
    const { gray, w, h } = S; const img = newImage(w, h), d = img.data, tab = buildWlTable(S), lut = PALETTES.gray;
    for (let i = 0; i < gray.length; i++) putIdx(d, i, lut, tab[gray[i]]);
    return img;
}
function renderMode(S) {
    const { gray, w, h } = S, mode = S.mode; const img = newImage(w, h), d = img.data, tab = buildWlTable(S), lut = PALETTES[S.palette] || PALETTES.ironbow;
    const N = gray.length;
    switch (mode) {
        case 'isotherm': {
            const lo = Math.round((S.isoLo - TEMP_BASE) / TEMP_STEP), hi = Math.round((S.isoHi - TEMP_BASE) / TEMP_STEP);
            for (let i = 0; i < N; i++) { const v = gray[i]; if (v >= lo && v <= hi) putIdx(d, i, lut, tab[v]); else { const g = (tab[v] * .3) | 0; const j = i * 4; d[j] = g; d[j + 1] = g; d[j + 2] = g; d[j + 3] = 255; } }
            break; }
        case 'relief': {
            const sm = boxBlur(gray, w, h, 2);
            for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
                const i = y * w + x; const gx = sm[y * w + Math.min(w - 1, x + 1)] - sm[y * w + Math.max(0, x - 1)], gy = sm[Math.min(h - 1, y + 1) * w + x] - sm[Math.max(0, y - 1) * w + x];
                const sh = Math.max(.25, Math.min(1.6, 1 - (gx * .7 + gy * .7) * .06)); const k = tab[gray[i]] * 3, j = i * 4;
                d[j] = Math.min(255, lut[k] * sh); d[j + 1] = Math.min(255, lut[k + 1] * sh); d[j + 2] = Math.min(255, lut[k + 2] * sh); d[j + 3] = 255;
            } break; }
        case 'laplace': {
            const L = PALETTES.coolwarm;
            for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
                const i = y * w + x, c = gray[i];
                const lap = 4 * c - gray[y * w + Math.min(w - 1, x + 1)] - gray[y * w + Math.max(0, x - 1)] - gray[Math.min(h - 1, y + 1) * w + x] - gray[Math.max(0, y - 1) * w + x];
                putIdx(d, i, L, clamp255(128 - lap * 5));
            } break; }
        case 'dsa': {
            const bg = boxBlur(gray, w, h, 20);
            for (let i = 0; i < N; i++) { const r = gray[i] - bg[i]; putIdx(d, i, lut, clamp255(r * 6 + 40)); }
            break; }
        case 'pressure': {
            for (let i = 0; i < N; i++) { const p = pressureKpa(gray[i], S.otsu); putIdx(d, i, PALETTES.turbo, p ? clamp255((p - 80) / 420 * 255) : 0); }
            break; }
        case 'bioheat': {
            const { med } = medianMAD(gray, S.otsu);
            for (let i = 0; i < N; i++) { const v = gray[i]; const p = v < S.otsu ? 0 : 1.5 + 12 * Math.max(0, (v - med + 40) / 80); putIdx(d, i, PALETTES.turbo, clamp255(p / 14 * 255)); }
            break; }
        case 'mirror': {
            for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = y * w + x; putIdx(d, i, PALETTES.hot, clamp255(Math.abs(gray[i] - gray[y * w + (S.midline * 2 - x < 0 || S.midline * 2 - x >= w ? x : S.midline * 2 - x)]) * 5)); }
            break; }
        case 'compare': {
            const B = S.second; for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const i = y * w + x; let b = 0;
                if (B) { const bx = Math.min(B.w - 1, Math.floor(x * B.w / w)), by = Math.min(B.h - 1, Math.floor(y * B.h / h)); b = B.data[by * B.w + bx]; }
                putIdx(d, i, PALETTES.hot, clamp255(Math.abs(gray[i] - b) * 5)); }
            break; }
        case 'depth': {
            if (S.depth) for (let i = 0; i < N; i++) putIdx(d, i, PALETTES.turbo, S.depth[i]); else for (let i = 0; i < N; i++) putIdx(d, i, lut, tab[gray[i]]);
            break; }
        case 'corrected': {
            const src = S.corrected || gray; for (let i = 0; i < N; i++) putIdx(d, i, lut, tab[src[i]]);
            break; }
        default:
            for (let i = 0; i < N; i++) putIdx(d, i, lut, tab[gray[i]]);
    }
    return img;
}
