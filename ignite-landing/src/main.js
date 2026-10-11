import './style.css';

const REPO = 'https://github.com/noackjona-hash/JonaNoackIgnite';
// Download-Ziel: Releases-Seite des Repos (bitte anpassen, falls es eine direkte Installer-URL gibt)
const DOWNLOAD_URL = `${REPO}/releases`;
const DOC_BASE = `${REPO}/blob/main/docs/`;

const en = {
  'common.download': 'Download for Windows', 'common.github': 'Source code on GitHub',
  'nav.home': 'Home', 'nav.tech': 'Technology', 'nav.pipeline': 'Pipeline', 'nav.clinic': 'Clinical', 'nav.team': 'Team',
  'foot.tag': 'Deterministic infrared thermography for early detection of diabetic foot ulcers.',
  'foot.explore': 'Explore', 'foot.project': 'Project', 'foot.legal': 'Jugend forscht 2026 · research project, not a certified medical device',
  'home.eyebrow': 'Jugend forscht 2026 · Working world / Computer science',
  'home.h1a': 'See inflammation', 'home.h1b': 'before it becomes an ulcer.',
  'home.lead': 'IGNITE analyses infrared thermograms fully automatically, deterministically and contact-free – for early detection of subclinical tissue inflammation, diabetic foot ulcers and vascular perfusion disorders.',
  'home.cta2': 'View pipeline', 'home.meta1': 'Local & GDPR-oriented', 'home.meta2': 'Reproducible (bit-identical)', 'home.meta3': 'Rules adjustable without recompiling',
  'home.tagL': 'RAW INFRARED', 'home.tagR': 'DIAGNOSIS', 'home.curtainNote': 'Like in the workstation: drag the curtain to compare raw thermogram and findings.',
  'home.s1': 'deterministic pipeline stages', 'home.s2': 'hand-written AVX2 assembly kernels', 'home.s3': 'total runtime at 1440×1080 (measured)', 'home.s4': 'Armstrong criterion for side comparison',
  'home.pEyebrow': 'The problem', 'home.pH': 'An ulcer announces itself through heat – long before you can see it.',
  'home.pLead': 'In diabetic foot syndrome, a temperature difference of ≥ 2.2 K between contralateral sites is a significant predictor of an impending neuropathic ulcer (Armstrong et al., 2007). IGNITE automates this evaluation – traceable and fast.',
  'home.f1h': 'Contact-free thermography', 'home.f1p': 'Long-wave infrared (LWIR, 8–14 µm) reveals hyperthermia – no contact, no radiation.',
  'home.f2h': 'Deterministic & explainable', 'home.f2p': 'No random values, no black box: the same raw data always yields the same finding – each of the 42 stages is inspectable.',
  'home.f3h': 'Close-to-hardware fast', 'home.f3p': 'A Go pipeline with AVX2 SIMD kernels processes 32 pixels per clock – no C compiler, directly in the Go assembler.',
  'home.wEyebrow': 'How it works', 'home.wH': 'Four phases from raw image to finding',
  'home.ph1s': 'Stages 1–10', 'home.ph1h': 'Preprocessing', 'home.ph1p': 'Otsu segmentation separates tissue from background; Chamfer distance erosion suppresses edge artefacts.',
  'home.ph2s': 'Stages 11–20', 'home.ph2h': 'Hotspot detection', 'home.ph2p': 'Morphological white top-hat isolates focal temperature peaks from large-scale gradients.',
  'home.ph3s': 'Stages 21–30', 'home.ph3h': 'Robust threshold', 'home.ph3p': 'MAD-based outlier detection (median + k·1.4826·MAD) instead of fragile means.',
  'home.ph4s': 'Stages 31–42', 'home.ph4h': 'Classification', 'home.ph4p': 'Frangi vessel filter, bilateral comparison and Lua rules deliver the clinical finding.',
  'home.wMore': 'All stages with images',
  'home.aEyebrow': 'Architecture', 'home.aH': 'Five technologies, one goal.',
  'home.aLead': 'C# for the clinical UI, Go for the pipeline, assembly for the hotspot inner loop, Lua for swappable medical logic and SQLite for the tamper-evident audit log.',
  'home.aMore': 'Technology in detail',
  'home.cEyebrow': 'Try it', 'home.cH': 'IGNITE Medical Suite v5.0.0', 'home.cLead': 'Windows installer with workstation, compute core, Lua rules and test data – or browse the source code on GitHub.',
  'tech.eyebrow': 'Technology', 'tech.h1': 'Polyglot architecture,<br /><span class="grad">deliberately modular.</span>',
  'tech.lead': 'IGNITE combines native hardware acceleration with an ergonomic clinical interface. Each layer has exactly one job.',
  'tech.t1': 'Clinical PACS workstation: dual viewport with synchronised crosshair, curtain wipe, DICOM windowing (W/L), palettes, 3-point goniometer, PDF physician report and 3D export (OBJ, PLY, STL, XYZ).',
  'tech.t2': 'Deterministic 42-stage pipeline: Otsu, Chamfer-L2 distance erosion, Frangi-Hessian filter, O(N) histogram median and MAD – parallelised via goroutines. Called from C# via CLI/JSON.',
  'tech.t3': 'Six vector kernels in the Go assembler – no C compiler. 32 byte pixels or 8 float32 values simultaneously per clock cycle.',
  'tech.t4': 'Decoupled medical decision logic in <code class="chip">rules/*.lua</code>. Physicians adjust thresholds – without recompiling.',
  'tech.t5': 'Tamper-evident audit log per GDPR Art. 30 with pseudonymised patient IDs (<code class="chip">ANON-&lt;hash&gt;</code>) and hash chains for forensic immutability.',
  'tech.kH': 'Six kernels in the inner loop', 'tech.kLead': 'Where millions of pixels per image are processed, hand-written assembly takes over.',
  'tech.kTh1': 'Task', 'tech.kTh2': 'Instruction',
  'tech.k1': 'Morphological erosion (32 pixels/clock)', 'tech.k2': 'Morphological dilation (32 pixels/clock)', 'tech.k3': 'Saturating subtraction for the top-hat',
  'tech.k4': 'Vectorised difference |a − b| for side comparison', 'tech.k5': 'Binarise, threshold and tissue-mask in 256-bit registers', 'tech.k6': 'Floating-point convolution for the Frangi vessel filter',
  'tech.pEyebrow': 'Performance', 'tech.pH': 'Measured runtime at 1440×1080', 'tech.pLead': 'Values from the project documentation (README, per-stage measurement).',
  'tech.pTh1': 'Pipeline stage', 'tech.pTh2': 'Technology', 'tech.pTh3': 'Latency',
  'tech.p1': 'Body masking (Otsu + Chamfer)', 'tech.p2': 'Top-hat filter (opening + difference)', 'tech.p3': 'Outlier thresholding (MAD + mask)', 'tech.p4': 'Geometry & circularity',
  'tech.p5': 'Frangi vein mapping (3 scales)', 'tech.p6': 'Longitudinal gradient (perfusion)', 'tech.p7': 'Bilateral side comparison', 'tech.p8': 'Clinical risk assessment', 'tech.p9': 'Total pipeline (end-to-end)',
  'tech.rH': 'Rules as text files', 'tech.rP': 'Classification lives in three Lua files in the <code>rules/</code> folder.',
  'tech.dH': 'Deterministic by design', 'tech.dP': 'No random values, no undocumented heuristics: the same raw data yields a bit-identical finding.',
  'pipe.eyebrow': 'Pipeline', 'pipe.h1': '42 stages.<br /><span class="grad">Each one traceable.</span>',
  'pipe.lead': 'From raw capture to clinical finding – with real intermediate results of the pipeline on an example thermogram.',
  'pipe.s0h': 'Raw thermogram', 'pipe.s0p': 'The radiometric capture (LWIR) as input. All further stages work deterministically on these values.',
  'pipe.s1h': 'Body mask', 'pipe.s1p': 'Otsu thresholding separates tissue from the room background. A 2-pass Chamfer-L2 distance transform erodes the edge in a controlled way and suppresses reflection artefacts.',
  'pipe.s2h': '3D depth map', 'pipe.s2p': 'A surface depth map is reconstructed from the mask – the basis for Lambertian angle compensation.',
  'pipe.s3h': 'Edge-corrected thermogram', 'pipe.s3p': 'Lambertian 3D edge correction compensates angle-dependent emission loss at curved edges – inflammation at toe tips is preserved.',
  'pipe.s4h': 'Top-hat difference', 'pipe.s4p': 'The morphological white top-hat isolates focal temperature peaks from large-scale background gradients:',
  'pipe.s5h': 'Hotspot mask', 'pipe.s5p': 'Robust MAD thresholding after Hampel separates pathological outliers from normal tissue (default k = 3.0):',
  'pipe.s6h': 'Vascular tree', 'pipe.s6p': 'The multi-scale Frangi filter evaluates the Hessian eigenvalues λ₁, λ₂ and distinguishes tubular vessels from round inflammation foci.',
  'pipe.s7h': 'Diagnosis overlay', 'pipe.s7p': 'Foci are prioritised by risk score and ΔT; the Lua rules deliver the clinical grading (Armstrong criterion ΔT ≥ 2.2 K).',
  'pipe.cH': 'Explore the stages yourself', 'pipe.cLead': 'In the workstation, the “42 Stufen” tab shows every stage with runtime and description.', 'pipe.cMore': 'To technology',
  'cl.eyebrow': 'Clinical', 'cl.h1': 'From temperature<br /><span class="grad">to decision.</span>',
  'cl.lead': 'IGNITE follows established guidelines and delivers structured, traceable findings for clinical practice.',
  'cl.aH': 'The Armstrong criterion', 'cl.warn': 'CONSPICUOUS',
  'cl.aP': 'A contralateral temperature difference of ΔT ≥ 2.2 K (≈ 2.2 °C) is a significant predictor of an impending neuropathic tissue ulcer (Armstrong et al., 2007). IGNITE compares both feet mirror-wise and raises an alarm when exceeded.',
  'cl.fEyebrow': 'Features', 'cl.fH': 'What the workstation does clinically',
  'cl.c1h': 'Bilateral side comparison', 'cl.c1p': 'Distinguishes harmless mechanical load from true inflammation by comparing both limbs.',
  'cl.c2h': 'Hotspot triage', 'cl.c2p': 'Foci are sorted by risk score and ΔT – the most acute focus appears as focus #1 with a callout card.',
  'cl.c3h': 'Perfusion & vessels', 'cl.c3p': 'Longitudinal gradient dT/dy to detect distal perfusion breaks; Frangi vein mapping.',
  'cl.c4h': '7-day risk prediction', 'cl.c4p': 'Multivariate model based on Armstrong delta and Pennes bioheat THDI (heat-congestion index).',
  'cl.c5h': 'Angiosomes & 5 zones', 'cl.c5p': 'Six Taylor & Palmer angiosome territories and five anatomical load zones (hallux to calcaneus).',
  'cl.c6h': 'Structured physician report', 'cl.c6p': 'PDF findings report per IWGDF/Wagner-Armstrong criteria; plus JSON and CSV export.',
  'cl.gEyebrow': 'Standards & privacy', 'cl.gH': 'Guideline-oriented. Local and traceable.',
  'cl.g1': 'Quality management for medical devices – guiding principle for structure and documentation.',
  'cl.g2': 'International Working Group on the Diabetic Foot – guidelines for prevention and treatment.',
  'cl.g3': 'Local storage, pseudonymisation (ANON-&lt;hash&gt;) and SQLite audit trail with SHA-256 hash chains.',
  'cl.note': 'IGNITE is a research project (Jugend forscht 2026) and does not replace a medical diagnosis. Results are supportive and must be assessed by qualified medical staff.',
  'tm.eyebrow': 'Team & project', 'tm.h1': 'A competition project<br /><span class="grad">with clinical ambition.</span>',
  'tm.lead': 'IGNITE was created for the German youth competition Jugend forscht 2026 in the field Working world / Computer science.',
  'tm.role': 'Development & research · Jugend forscht 2026',
  'tm.openH': 'Open source code', 'tm.openP': 'All code – workstation, Go core, assembly kernels and Lua rules – is on GitHub.',
  'tm.dEyebrow': 'Documentation', 'tm.dH': 'Read up & verify',
  'tm.d1h': 'Written paper (PDF)', 'tm.d1p': 'The print version for Jugend forscht 2026.', 'tm.d2h': 'Scientific monograph', 'tm.d2p': 'Scientific documentation v5.0.0.',
  'tm.d3h': 'Architecture v5.0.0', 'tm.d3p': 'The multi-tier pipeline in detail.', 'tm.d4h': 'Algorithms', 'tm.d4p': 'Mathematical description of the methods.',
  'tm.d5h': 'Optimisations & benchmarks', 'tm.d5p': 'Measurements and performance report.', 'tm.d6h': 'Optimisation guide', 'tm.d6p': 'Performance hints for developers.',
  'tm.cH': 'Try IGNITE'
};

const links = [['/', 'nav.home', 'Start', 'home'], ['/technik.html', 'nav.tech', 'Technik', 'tech'], ['/pipeline.html', 'nav.pipeline', 'Pipeline', 'pipeline'], ['/klinik.html', 'nav.clinic', 'Klinik', 'clinic'], ['/team.html', 'nav.team', 'Team', 'team']];
const page = document.body.dataset.page;

const logo = id => `<span class="brand-mark"><svg viewBox="0 0 24 24" aria-hidden="true"><defs><linearGradient id="ignCore${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#fde047"/><stop offset="100%" stop-color="#ea580c"/></linearGradient></defs><path d="M12 2.2C13.5 4.2 18.8 9.8 18.8 14.6C18.8 18.5 15.8 21.6 12 21.6C8.2 21.6 5.2 18.5 5.2 14.6C5.2 11.2 7.6 7.6 9.8 5.2C10.2 6.8 10.9 8.2 12.4 8.2C11.5 6.0 11.7 4.2 12 2.2Z" fill="#ffffff"/><path d="M12 11.4C13.6 13.0 14.5 14.5 14.5 16.0C14.5 17.5 13.4 18.6 12 18.6C10.6 18.6 9.5 17.5 9.5 16.0C9.5 14.5 10.4 13.0 12 11.4Z" fill="url(#ignCore${id})"/></svg></span>`;

document.getElementById('site-header').innerHTML = `
<div class="progress" id="progress"></div>
<header class="nav" id="nav"><div class="container nav-in">
  <a class="brand" href="/" aria-label="IGNITE Start">${logo('h')}<span class="brand-word">IGNITE<small>Medical Imaging Suite</small></span></a>
  <nav class="links" id="links">${links.map(l => `<a href="${l[0]}" data-i18n="${l[1]}" class="${l[3] === page ? 'active' : ''}">${l[2]}</a>`).join('')}</nav>
  <div class="nav-actions">
    <div class="lang"><button data-lang="de">DE</button><button data-lang="en">EN</button></div>
    <a class="btn btn-primary btn-sm" data-download href="#" data-i18n="nav.dl">Download</a>
    <button class="burger" id="burger" aria-label="Menü">☰</button>
  </div></div></header>`;
en['nav.dl'] = 'Download';

document.getElementById('site-footer').innerHTML = `
<footer><div class="container">
  <div class="foot">
    <div><a class="brand" href="/" aria-label="IGNITE Start">${logo('f')}<span class="brand-word">IGNITE<small>Medical Imaging Suite</small></span></a><p data-i18n="foot.tag">Deterministische Infrarot-Thermografie zur Früherkennung diabetischer Fußulzera.</p></div>
    <div><h4 data-i18n="foot.explore">Entdecken</h4>${links.slice(0, 3).map(l => `<a href="${l[0]}" data-i18n="${l[1]}">${l[2]}</a>`).join('')}</div>
    <div><h4 data-i18n="foot.project">Projekt</h4>${links.slice(3).map(l => `<a href="${l[0]}" data-i18n="${l[1]}">${l[2]}</a>`).join('')}<a data-repo href="#" target="_blank" rel="noopener">GitHub ↗</a></div>
    <div><h4>Stack</h4><a>C# · .NET 10</a><a>Go 1.24+</a><a>AVX2 · Lua · SQLite</a></div>
  </div>
  <div class="legal"><span>© 2026 Jona Noack</span><span data-i18n="foot.legal">Jugend forscht 2026 · Forschungsprojekt, kein zertifiziertes Medizinprodukt</span></div>
</div></footer>
<div class="dock" id="dock"><a class="btn btn-primary" data-download href="#"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16"/></svg><span data-i18n="common.download">Für Windows herunterladen</span></a><a class="btn btn-ghost" data-repo href="#" target="_blank" rel="noopener" aria-label="GitHub">↗</a></div>`;

document.querySelectorAll('[data-download]').forEach(a => { a.href = DOWNLOAD_URL; a.target = '_blank'; a.rel = 'noopener'; });
document.querySelectorAll('[data-repo]').forEach(a => { a.href = REPO; });
document.querySelectorAll('[data-doc]').forEach(a => { a.href = DOC_BASE + a.dataset.doc; });

// i18n: Deutsch ist der HTML-Standardtext, Englisch kommt aus dem Wörterbuch
const nodes = [...document.querySelectorAll('[data-i18n],[data-i18n-html]')];
nodes.forEach(n => { n.dataset.de = n.innerHTML; });
function setLang(l) {
  localStorage.setItem('ignite-lang', l);
  document.documentElement.lang = l;
  nodes.forEach(n => {
    const key = n.dataset.i18n || n.dataset.i18nHtml;
    const v = l === 'en' && en[key] ? en[key] : n.dataset.de;
    n.innerHTML = v;
  });
  document.querySelectorAll('.lang button').forEach(b => b.classList.toggle('on', b.dataset.lang === l));
}
document.querySelectorAll('.lang button').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
setLang(localStorage.getItem('ignite-lang') || (navigator.language.startsWith('de') ? 'de' : 'en'));

// Navigation
const nav = document.getElementById('nav');
const bar = document.getElementById('progress');
const dock = document.getElementById('dock');
const menu = document.getElementById('links');
const burger = document.getElementById('burger');
function onScroll() {
  nav.classList.toggle('scrolled', scrollY > 8);
  const max = document.documentElement.scrollHeight - innerHeight;
  bar.style.transform = `scaleX(${max > 0 ? Math.min(scrollY / max, 1) : 0})`;
  dock.classList.toggle('show', scrollY > 420 && scrollY < max - 500);
}
addEventListener('scroll', onScroll, { passive: true });
onScroll();
function toggleMenu(open) {
  menu.classList.toggle('open', open);
  document.body.classList.toggle('lock', open);
  burger.textContent = open ? '✕' : '☰';
}
burger.addEventListener('click', () => toggleMenu(!menu.classList.contains('open')));
menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => toggleMenu(false)));
addEventListener('resize', () => { if (innerWidth >= 980) toggleMenu(false); });

// Reveal on scroll
const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }), { threshold: .12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

// Curtain wipe
const c = document.getElementById('curtain');
if (c) c.querySelector('input').addEventListener('input', e => c.style.setProperty('--pos', e.target.value + '%'));
