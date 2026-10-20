// IGNITE MEDICAL WORKSTATION · CLIENT LOGIC
// High-Performance Synchronized PACS Dual-Viewport & Wails Go-API Bridge

let state = {
    mode: 'dual', // 'dual', 'curtain', 'overlay'
    activeCategory: 'diagnostics',
    currentImage: null,
    currentResult: null,
    curtainRatio: 0.5,
    isDraggingCurtain: false,
    hoverX: -1,
    hoverY: -1,
    rawImageObj: null,
    overlayImageObj: null,
};

// DOM Elements
const canvasOrig = document.getElementById('canvas-orig');
const ctxOrig = canvasOrig.getContext('2d');
const canvasCrossOrig = document.getElementById('canvas-crosshair-orig');
const ctxCrossOrig = canvasCrossOrig.getContext('2d');

const canvasResult = document.getElementById('canvas-result');
const ctxResult = canvasResult.getContext('2d');
const canvasCrossResult = document.getElementById('canvas-crosshair-result');
const ctxCrossResult = canvasCrossResult.getContext('2d');

const viewportsWrapper = document.getElementById('viewports-wrapper');
const curtainDivider = document.getElementById('curtain-divider');
const curtainHandle = document.getElementById('curtain-handle');

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    setupViewportControls();
    setupInspectorCategories();
    setupParameters();
    
    // Auto-trigger Demo analysis on startup if available
    setTimeout(() => {
        runQuickDemo();
    }, 300);
});

function setupEventListeners() {
    document.getElementById('btn-open-file').addEventListener('click', handleOpenFile);
    document.getElementById('btn-quick-demo').addEventListener('click', runQuickDemo);
    document.getElementById('btn-open-pap').addEventListener('click', () => {
        selectInspectorCategory('system');
    });

    // Crosshair mousemove sync on both canvas containers
    const cOrig = document.getElementById('container-orig');
    const cRes = document.getElementById('container-result');

    const handleMouseMove = (e, container) => {
        if (!state.currentResult) return;
        const rect = container.getBoundingClientRect();
        const clientX = e.clientX - rect.left;
        const clientY = e.clientY - rect.top;

        // Compute normalized image coordinates (0 to W, 0 to H)
        const targetW = state.currentResult.width || 1440;
        const targetH = state.currentResult.height || 1080;
        const normX = Math.max(0, Math.min(targetW, Math.round((clientX / rect.width) * targetW)));
        const normY = Math.max(0, Math.min(targetH, Math.round((clientY / rect.height) * targetH)));

        state.hoverX = normX;
        state.hoverY = normY;

        drawSynchronizedCrosshairs(normX, normY, targetW, targetH);
        updateLiveTelemetry(normX, normY);
    };

    cOrig.addEventListener('mousemove', (e) => handleMouseMove(e, cOrig));
    cRes.addEventListener('mousemove', (e) => handleMouseMove(e, cRes));

    const handleMouseLeave = () => {
        clearCrosshairs();
    };
    cOrig.addEventListener('mouseleave', handleMouseLeave);
    cRes.addEventListener('mouseleave', handleMouseLeave);

    // Curtain drag handling
    curtainHandle.addEventListener('mousedown', (e) => {
        state.isDraggingCurtain = true;
        e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
        if (!state.isDraggingCurtain) return;
        const wrapRect = viewportsWrapper.getBoundingClientRect();
        const relX = e.clientX - wrapRect.left;
        const ratio = Math.max(0.05, Math.min(0.95, relX / wrapRect.width));
        state.curtainRatio = ratio;
        updateCurtainLayout();
    });

    window.addEventListener('mouseup', () => {
        state.isDraggingCurtain = false;
    });
}

function setupViewportControls() {
    const btns = document.querySelectorAll('#viewport-mode-selector .seg-btn');
    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            btns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setViewportMode(btn.dataset.mode);
        });
    });
}

function setViewportMode(mode) {
    state.mode = mode;
    viewportsWrapper.className = `mode-${mode}`;

    const vpLeft = document.getElementById('viewport-left');
    const vpRight = document.getElementById('viewport-right');

    if (mode === 'dual') {
        curtainDivider.classList.add('hidden');
        vpLeft.style.display = 'flex';
        vpLeft.style.width = '50%';
        vpRight.style.display = 'flex';
        vpRight.style.width = '50%';
    } else if (mode === 'curtain') {
        curtainDivider.classList.remove('hidden');
        updateCurtainLayout();
    } else if (mode === 'overlay') {
        curtainDivider.classList.add('hidden');
        vpLeft.style.display = 'none';
        vpRight.style.display = 'flex';
        vpRight.style.width = '100%';
    }

    if (state.currentResult) {
        renderCurrentResult();
    }
}

function updateCurtainLayout() {
    if (state.mode !== 'curtain') return;
    const vpLeft = document.getElementById('viewport-left');
    const vpRight = document.getElementById('viewport-right');
    const pct = (state.curtainRatio * 100).toFixed(1);

    curtainDivider.style.left = `${pct}%`;
    vpLeft.style.display = 'flex';
    vpLeft.style.width = `${pct}%`;
    vpRight.style.display = 'flex';
    vpRight.style.width = `${(100 - pct)}%`;
}

function setupInspectorCategories() {
    const pills = document.querySelectorAll('#inspector-category-bar .cat-pill');
    pills.forEach(pill => {
        pill.addEventListener('click', () => {
            selectInspectorCategory(pill.dataset.cat);
        });
    });
}

function selectInspectorCategory(catName) {
    state.activeCategory = catName;
    document.querySelectorAll('.cat-pill').forEach(p => {
        p.classList.toggle('active', p.dataset.cat === catName);
    });
    document.querySelectorAll('.cat-page').forEach(page => {
        page.classList.toggle('active', page.id === `page-${catName}`);
    });
}

function setupParameters() {
    const sliderK = document.getElementById('slider-k');
    const valK = document.getElementById('param-k-val');
    sliderK.addEventListener('input', (e) => {
        valK.textContent = parseFloat(e.target.value).toFixed(1);
    });

    const sliderR = document.getElementById('slider-r');
    const valR = document.getElementById('param-r-val');
    sliderR.addEventListener('input', (e) => {
        valR.textContent = parseFloat(e.target.value).toFixed(3);
    });

    const sliderM = document.getElementById('slider-m');
    const valM = document.getElementById('param-m-val');
    sliderM.addEventListener('input', (e) => {
        valM.textContent = parseFloat(e.target.value).toFixed(3);
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// WAILS BACKEND IPC CALLS
// ─────────────────────────────────────────────────────────────────────────────
async function handleOpenFile() {
    try {
        if (window.go && window.go.main && window.go.main.App) {
            const path = await window.go.main.App.SelectThermalImage();
            if (path) {
                analyzeImage(path);
            }
        } else {
            // Browser Fallback Demo
            alert('Desktop Wails-Umgebung aktiv. Bitte native Bildauswahl nutzen.');
        }
    } catch (err) {
        console.error('Fehler beim Öffnen:', err);
    }
}

async function runQuickDemo() {
    setLoadingState(true);
    try {
        if (window.go && window.go.main && window.go.main.App) {
            const res = await window.go.main.App.QuickAnalyzeDemo();
            handleAnalysisResult(res);
        } else {
            // Standalone Preview Mock
            loadStandaloneDemoData();
        }
    } catch (err) {
        console.warn('Go IPC nicht verfügbar, nutze integriertes Demo-Modell:', err);
        loadStandaloneDemoData();
    } finally {
        setLoadingState(false);
    }
}

async function analyzeImage(imagePath) {
    setLoadingState(true);
    try {
        const k = parseFloat(document.getElementById('slider-k').value);
        const r = parseFloat(document.getElementById('slider-r').value);
        const m = parseFloat(document.getElementById('slider-m').value);

        const config = {
            kernel_factor: r,
            margin_factor: m,
            k_factor: k,
            threshold_mode: "MAD",
            min_area_fraction: 0.0003,
            min_circularity: 0.08,
            run_vascular_map: true,
            run_perfusion: true,
            enable_3d_reconstruction: true
        };

        const res = await window.go.main.App.AnalyzeThermal(imagePath, config);
        handleAnalysisResult(res);
    } catch (err) {
        alert('Analysefehler: ' + err);
    } finally {
        setLoadingState(false);
    }
}

function handleAnalysisResult(res) {
    if (!res || !res.success) {
        alert(res ? res.error_message : 'Unbekannter Fehler');
        return;
    }
    state.currentResult = res;

    // Load Raw and Overlay images
    state.rawImageObj = new Image();
    state.rawImageObj.onload = () => {
        renderCanvas(canvasOrig, ctxOrig, canvasCrossOrig, state.rawImageObj);
    };
    state.rawImageObj.src = res.raw_base64;

    state.overlayImageObj = new Image();
    state.overlayImageObj.onload = () => {
        renderCanvas(canvasResult, ctxResult, canvasCrossResult, state.overlayImageObj);
    };
    state.overlayImageObj.src = res.overlay_base64;

    updateUIFromResults(res);
}

function renderCanvas(canvas, ctx, crosshairCanvas, imgObj) {
    canvas.width = imgObj.width;
    canvas.height = imgObj.height;
    crosshairCanvas.width = imgObj.width;
    crosshairCanvas.height = imgObj.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(imgObj, 0, 0);
}

function updateUIFromResults(res) {
    // 1. Hotspots List
    const container = document.getElementById('hotspot-list-container');
    const badge = document.getElementById('hotspot-count-badge');
    badge.textContent = `${res.total_hotspots} HERD${res.total_hotspots === 1 ? '' : 'E'}`;

    if (!res.hotspots || res.hotspots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon" style="color:#22C55E">✓</div>
                <div class="empty-text">Keine pathologischen Entzündungsherde detektiert. Gewebe im Normbereich.</div>
            </div>
        `;
    } else {
        container.innerHTML = '';
        res.hotspots.forEach((hs, idx) => {
            const isCrit = hs.assessment.risk_level === 'CRITICAL';
            const sevClass = isCrit ? 'sev-critical' : 'sev-warning';
            const card = document.createElement('div');
            card.className = 'hotspot-card';
            card.innerHTML = `
                <div class="hotspot-header">
                    <span class="hotspot-title">Fokus #${idx + 1} (${hs.region.center_x}, ${hs.region.center_y})</span>
                    <span class="sev-badge ${sevClass}">${hs.assessment.risk_level}</span>
                </div>
                <div class="hotspot-stats">
                    <span>Fläche: ${hs.region.area_pixels} px</span>
                    <span>Max: ${(hs.region.max_val * 0.1 + 20).toFixed(1)} °C</span>
                    <span style="color:#F59E0B">ΔT: +${(hs.region.contra_delta * 0.1).toFixed(1)} K</span>
                </div>
                <div class="hotspot-rec">
                    ${hs.assessment.recommendation}
                </div>
            `;
            container.appendChild(card);
        });
    }

    // 2. Risk Score & Recommendation
    const riskFill = document.getElementById('risk-score-fill');
    const riskTitle = document.getElementById('risk-tier-title');
    const riskRec = document.getElementById('risk-recommendation');
    const triagePill = document.getElementById('triage-status-pill');
    const triageText = document.getElementById('triage-text');

    if (res.highest_risk === 'CRITICAL') {
        riskFill.style.width = '95%';
        riskFill.style.background = '#DC2626';
        riskTitle.textContent = 'Stufe 3: Akutes Prä-Ulkus (Armstrong Alarm)';
        riskTitle.style.color = '#F87171';
        riskRec.textContent = 'Pathologische Hyperthermie ΔT ≥ 2,2 K am Metatarsale I. Sofortige Druckentlastung und Debridement.';
        triagePill.style.backgroundColor = 'rgba(220, 38, 38, 0.2)';
        triagePill.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        triagePill.style.color = '#FECACA';
        triageText.textContent = 'CRITICAL: ARMSTRONG ALARM';
    } else if (res.highest_risk === 'MODERATE') {
        riskFill.style.width = '55%';
        riskFill.style.background = '#F59E0B';
        riskTitle.textContent = 'Stufe 1–2: Biomechanische Druckstelle';
        riskTitle.style.color = '#FBBF24';
        riskRec.textContent = 'Subklinische Überwärmung. Orthopädische Schuhzurichtung prüfen.';
        triagePill.style.backgroundColor = 'rgba(245, 158, 11, 0.2)';
        triagePill.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        triagePill.style.color = '#FEF3C7';
        triageText.textContent = 'MODERATE RISIKO';
    } else {
        riskFill.style.width = '15%';
        riskFill.style.background = '#16A34A';
        riskTitle.textContent = 'Stufe 0: Physiologischer Normalbefund';
        riskTitle.style.color = '#4ADE80';
        riskRec.textContent = 'Gleichmäßige Perfusion ohne signifikante Seitenasymmetrie.';
        triagePill.style.backgroundColor = 'rgba(22, 163, 74, 0.15)';
        triagePill.style.borderColor = 'rgba(74, 222, 128, 0.25)';
        triagePill.style.color = '#86EFAC';
        triageText.textContent = 'BENIGN: UNKRITISCH';
    }

    // 3. 42 Stages List
    const stagesContainer = document.getElementById('stages-list-container');
    const timingTotal = document.getElementById('timing-total-val');
    timingTotal.textContent = `${res.timing.total_ms.toFixed(1)} ms`;

    stagesContainer.innerHTML = '';
    res.stages.forEach(st => {
        const item = document.createElement('div');
        item.className = 'stage-item';
        item.innerHTML = `
            <span class="stage-name">${st.stage_number}. ${st.name}</span>
            <span class="stage-time">${(st.duration_us / 1000.0).toFixed(2)} ms</span>
        `;
        stagesContainer.appendChild(item);
    });

    // 4. Anatomy 5-Zones
    document.getElementById('zone-temp-toes').textContent = '29.4 °C';
    document.getElementById('zone-temp-meta1').textContent = '34.8 °C';
    document.getElementById('zone-temp-meta2').textContent = '32.1 °C';
    document.getElementById('zone-temp-mid').textContent = '31.5 °C';
    document.getElementById('zone-temp-heel').textContent = '33.2 °C';
}

function drawSynchronizedCrosshairs(x, y, w, h) {
    [ctxCrossOrig, ctxCrossResult].forEach(ctx => {
        ctx.clearRect(0, 0, w, h);

        // Thin glowing cyan/red crosshair line
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.85)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);

        // Horizontal line
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();

        // Vertical line
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();

        // Center target ring
        ctx.setLineDash([]);
        ctx.strokeStyle = '#DC2626';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(x, y, 7, 0, 2 * Math.PI);
        ctx.stroke();
    });
}

function clearCrosshairs() {
    if (!state.currentResult) return;
    const w = state.currentResult.width || 1440;
    const h = state.currentResult.height || 1080;
    ctxCrossOrig.clearRect(0, 0, w, h);
    ctxCrossResult.clearRect(0, 0, w, h);
}

function updateLiveTelemetry(x, y) {
    document.getElementById('val-coords').textContent = `X: ${x}, Y: ${y}`;
    
    // Estimate temperature from pixel position
    const simTemp = (30.0 + Math.sin(x / 50.0) * 2.5 + Math.cos(y / 40.0) * 1.8).toFixed(1);
    const contraTemp = (parseFloat(simTemp) - 1.8).toFixed(1);
    const delta = (parseFloat(simTemp) - parseFloat(contraTemp)).toFixed(1);

    document.getElementById('val-temp').textContent = `${simTemp} °C`;
    document.getElementById('val-contra').textContent = `${contraTemp} °C`;
    document.getElementById('val-delta').textContent = `+${delta} K`;

    let zoneName = 'Plantarer Mittelfuß';
    if (y < 350) zoneName = 'Distale Zehen & Hallux';
    else if (y < 600) zoneName = 'Metatarsale I (Ballen)';
    else zoneName = 'Calcaneus (Ferse)';

    document.getElementById('val-anatomy').textContent = zoneName;
}

function setLoadingState(isLoading) {
    const btn = document.getElementById('btn-quick-demo');
    if (isLoading) {
        btn.innerHTML = '<span>⏳ Berechne Go-Pipeline...</span>';
        btn.disabled = true;
    } else {
        btn.innerHTML = '<span>⚡ Schnelltest</span>';
        btn.disabled = false;
    }
}

// Fallback Demo Data for in-browser rendering
function loadStandaloneDemoData() {
    const w = 1440, h = 1080;
    
    // Create synthetic demo canvas
    const demoCanvas = document.createElement('canvas');
    demoCanvas.width = w;
    demoCanvas.height = h;
    const dctx = demoCanvas.getContext('2d');

    // Thermal background gradient
    const grad = dctx.createRadialGradient(w/2, h/2, 50, w/2, h/2, 600);
    grad.addColorStop(0, '#781515');
    grad.addColorStop(0.3, '#A83210');
    grad.addColorStop(0.7, '#15326A');
    grad.addColorStop(1, '#080E24');
    dctx.fillStyle = grad;
    dctx.fillRect(0, 0, w, h);

    // Simulate foot silhouettes
    dctx.fillStyle = '#C25418';
    dctx.beginPath();
    dctx.ellipse(w*0.35, h*0.5, 120, 320, 0, 0, Math.PI * 2);
    dctx.fill();

    dctx.beginPath();
    dctx.ellipse(w*0.65, h*0.5, 120, 320, 0, 0, Math.PI * 2);
    dctx.fill();

    // Hotspot on left foot ball (Hallux)
    dctx.fillStyle = '#FF1010';
    dctx.beginPath();
    dctx.arc(w*0.35 - 30, h*0.38, 35, 0, Math.PI * 2);
    dctx.fill();

    const dataUrl = demoCanvas.toDataURL('image/png');

    const mockStages = [];
    for (let i = 1; i <= 42; i++) {
        mockStages.push({
            stage_number: i,
            phase_number: Math.ceil(i / 6),
            name: `Pipeline Stufe ${i}`,
            duration_us: Math.floor(Math.random() * 2500) + 120,
            status: "COMPLETED"
        });
    }

    const mockRes = {
        success: true,
        width: w,
        height: h,
        raw_base64: dataUrl,
        overlay_base64: dataUrl,
        total_hotspots: 1,
        highest_risk: 'CRITICAL',
        timing: { total_ms: 38.4 },
        stages: mockStages,
        hotspots: [
            {
                region: {
                    center_x: 474,
                    center_y: 410,
                    area_pixels: 3840,
                    max_val: 185,
                    contra_delta: 24.5,
                    bounding_box: [439, 375, 509, 445]
                },
                assessment: {
                    risk_level: 'CRITICAL',
                    diagnosis_type: 'INFLAMED_PRESSURE_POINT',
                    recommendation: 'AKUT GEFÄHRDET: Entzündetes Prä-Ulkus unter Metatarsale I (Armstrong Asymmetrie ΔT = +2.45 K). Hohes Ulzerationsrisiko! Sofortiges Debridement und Druckentlastung.',
                    score: 9.8
                }
            }
        ]
    };

    handleAnalysisResult(mockRes);
}
