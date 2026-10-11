import './style.css';
import { dictionaries } from './i18n.js';

const REPO = 'https://github.com/noackjona-hash/JonaNoackIgnite';
const DOWNLOAD_URL = `${REPO}/releases`;
const DOC_BASE = `${REPO}/blob/main/docs/`;

const links = [
  ['/', 'nav.home', 'Start', 'home'],
  ['/technik.html', 'nav.tech', 'Technik', 'tech'],
  ['/pipeline.html', 'nav.pipeline', 'Pipeline', 'pipeline'],
  ['/klinik.html', 'nav.clinic', 'Klinik', 'clinic'],
  ['/team.html', 'nav.team', 'Team', 'team']
];
const page = document.body.dataset.page;

const logo = id => `<span class="brand-mark"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.2C13.5 4.2 18.8 9.8 18.8 14.6C18.8 18.5 15.8 21.6 12 21.6C8.2 21.6 5.2 18.5 5.2 14.6C5.2 11.2 7.6 7.6 9.8 5.2C10.2 6.8 10.9 8.2 12.4 8.2C11.5 6.0 11.7 4.2 12 2.2Z" fill="#ffffff"/><path d="M12 11.4C13.6 13.0 14.5 14.5 14.5 16.0C14.5 17.5 13.4 18.6 12 18.6C10.6 18.6 9.5 17.5 9.5 16.0C9.5 14.5 10.4 13.0 12 11.4Z" fill="#dc2626"/></svg></span>`;

// ============ INJECT HEADER & FOOTER ============
document.getElementById('site-header').innerHTML = `
<div class="progress" id="progress"></div>
<header class="nav" id="nav"><div class="container nav-in">
  <a class="brand" href="/" aria-label="IGNITE Start">${logo('h')}<span class="brand-word">IGNITE<small>Medical Imaging Suite</small></span></a>
  <nav class="links" id="links">${links.map(l => `<a href="${l[0]}" data-i18n="${l[1]}" class="${l[3] === page ? 'active' : ''}">${l[2]}</a>`).join('')}</nav>
  <div class="nav-actions">
    <div class="lang">
      <select id="langSelect" aria-label="Sprache / Language">
        <option value="de">DE · Deutsch</option>
        <option value="en">EN · English</option>
        <option value="fr">FR · Français</option>
        <option value="es">ES · Español</option>
        <option value="zh">ZH · 中文</option>
      </select>
    </div>
    <a class="btn btn-primary btn-sm" data-download href="#" data-i18n="nav.dl">Download</a>
    <button class="burger" id="burger" aria-label="Menü">☰</button>
  </div></div></header>`;

document.getElementById('site-footer').innerHTML = `
<footer><div class="container">
  <div class="foot">
    <div><a class="brand" href="/" aria-label="IGNITE Start">${logo('f')}<span class="brand-word">IGNITE<small>Medical Imaging Suite</small></span></a><p data-i18n="foot.tag">Deterministische Infrarot-Thermografie zur Früherkennung diabetischer Fußulzera.</p></div>
    <div><h4 data-i18n="foot.explore">Entdecken</h4>${links.slice(0, 3).map(l => `<a href="${l[0]}" data-i18n="${l[1]}">${l[2]}</a>`).join('')}</div>
    <div><h4 data-i18n="foot.project">Projekt</h4>${links.slice(3).map(l => `<a href="${l[0]}" data-i18n="${l[1]}">${l[2]}</a>`).join('')}<a data-repo href="#" target="_blank" rel="noopener">GitHub ↗</a><a href="/impressum.html" data-i18n="nav.imprint">Impressum</a></div>
    <div><h4>Stack</h4><a>C# · .NET 10</a><a>Go 1.24+</a><a>AVX2 · Lua · SQLite</a></div>
  </div>
  <div class="legal"><span>© 2026 Jona Noack</span><span data-i18n="foot.legal">Jugend forscht 2026 · Forschungsprojekt, kein zertifiziertes Medizinprodukt</span><a href="/impressum.html" data-i18n="nav.imprint" style="text-decoration:underline">Impressum</a></div>
</div></footer>
<div class="dock" id="dock"><a class="btn btn-primary" data-download href="#"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16"/></svg><span data-i18n="common.download">Für Windows herunterladen</span></a><a class="btn btn-ghost" data-repo href="#" target="_blank" rel="noopener" aria-label="GitHub">↗</a></div>`;

document.querySelectorAll('[data-download]').forEach(a => { a.href = DOWNLOAD_URL; a.target = '_blank'; a.rel = 'noopener'; });
document.querySelectorAll('[data-repo]').forEach(a => { a.href = REPO; });
document.querySelectorAll('[data-doc]').forEach(a => { a.href = DOC_BASE + a.dataset.doc; });

// ============ I18N SYSTEM (DE, EN, FR, ES, ZH) ============
const nodes = [...document.querySelectorAll('[data-i18n],[data-i18n-html]')];
nodes.forEach(n => { n.dataset.de = n.innerHTML; });

function setLang(l) {
  localStorage.setItem('ignite-lang', l);
  document.documentElement.lang = l;
  const dict = dictionaries[l] || {};
  nodes.forEach(n => {
    const key = n.dataset.i18n || n.dataset.i18nHtml;
    const v = l !== 'de' && dict[key] ? dict[key] : n.dataset.de;
    n.innerHTML = v;
  });
  const sel = document.getElementById('langSelect');
  if (sel) sel.value = l;
}

const langSelect = document.getElementById('langSelect');
if (langSelect) langSelect.addEventListener('change', e => setLang(e.target.value));

const detectedLang = (() => {
  const stored = localStorage.getItem('ignite-lang');
  if (stored && ['de', 'en', 'fr', 'es', 'zh'].includes(stored)) return stored;
  const navLangs = navigator.languages || [navigator.language || ''];
  for (const nl of navLangs) {
    const code = nl.slice(0, 2).toLowerCase();
    if (['de', 'en', 'fr', 'es', 'zh'].includes(code)) return code;
  }
  return 'de';
})();
setLang(detectedLang);

// ============ NAVIGATION & SCROLL DOCK ============
const nav = document.getElementById('nav');
const bar = document.getElementById('progress');
const dock = document.getElementById('dock');
const menu = document.getElementById('links');
const burger = document.getElementById('burger');

function onScroll() {
  nav.classList.toggle('scrolled', scrollY > 8);
  const max = document.documentElement.scrollHeight - innerHeight;
  if (bar) bar.style.transform = `scaleX(${max > 0 ? Math.min(scrollY / max, 1) : 0})`;
  if (dock) dock.classList.toggle('show', scrollY > 420 && scrollY < max - 500);
}
addEventListener('scroll', onScroll, { passive: true });
onScroll();

function toggleMenu(open) {
  menu.classList.toggle('open', open);
  document.body.classList.toggle('lock', open);
  burger.textContent = open ? '✕' : '☰';
}
if (burger) burger.addEventListener('click', () => toggleMenu(!menu.classList.contains('open')));
if (menu) menu.querySelectorAll('a').forEach(a => a.addEventListener('click', () => toggleMenu(false)));
addEventListener('resize', () => { if (innerWidth >= 980) toggleMenu(false); });

// ============ REVEAL ON SCROLL ============
const io = new IntersectionObserver(es => es.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
}), { threshold: .12 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

// ============ CURTAIN WIPE & LIVE PROBE HUD ============
const c = document.getElementById('curtain');
if (c) {
  const slider = c.querySelector('input');
  slider.addEventListener('input', e => c.style.setProperty('--pos', e.target.value + '%'));

  const probe = document.getElementById('curtainProbe');
  const probeCoords = document.getElementById('probeCoords');
  const probeTemp = document.getElementById('probeTemp');
  const probeZone = document.getElementById('probeZone');

  function updateProbe(clientX, clientY) {
    const rect = c.getBoundingClientRect();
    const relX = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const relY = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height));
    const imgX = Math.round(relX * 1440);
    const imgY = Math.round(relY * 1080);

    probeCoords.textContent = `X: ${imgX} Y: ${imgY}`;

    // Radiometrische Simulation basierend auf echtem Bild (Left Big Toe Hotspot bei ~ (530, 350))
    if (imgX >= 480 && imgX <= 600 && imgY >= 290 && imgY <= 420) {
      probeTemp.textContent = '34,8 °C';
      probeZone.textContent = 'Hallux L (ΔT = +2,7 K Alarm)';
      probe.style.borderColor = 'rgba(220, 38, 38, .8)';
    } else if (imgX >= 180 && imgX <= 420 && imgY >= 720 && imgY <= 900) {
      probeTemp.textContent = '30,4 °C';
      probeZone.textContent = 'Calcaneus L';
      probe.style.borderColor = 'rgba(255, 255, 255, .2)';
    } else if (imgX >= 820 && imgX <= 1180 && imgY >= 290 && imgY <= 450) {
      probeTemp.textContent = '32,1 °C';
      probeZone.textContent = 'Hallux R (Kontralateral)';
      probe.style.borderColor = 'rgba(255, 255, 255, .2)';
    } else {
      const baseTemp = (31.2 + (1 - relY) * 1.5).toFixed(1);
      probeTemp.textContent = `${baseTemp} °C`;
      probeZone.textContent = 'Planta pedis';
      probe.style.borderColor = 'rgba(255, 255, 255, .2)';
    }
  }

  c.addEventListener('mousemove', e => updateProbe(e.clientX, e.clientY));
  c.addEventListener('touchmove', e => {
    if (e.touches[0]) updateProbe(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
}

// ============ INTERACTIVE ARMSTRONG CALCULATOR ============
const sTL = document.getElementById('sliderTL');
const sTR = document.getElementById('sliderTR');
if (sTL && sTR) {
  const vTL = document.getElementById('valTL');
  const vTR = document.getElementById('valTR');
  const dVal = document.getElementById('calcDeltaVal');
  const sBadge = document.getElementById('calcStatusBadge');
  const sText = document.getElementById('calcStatusText');
  const aText = document.getElementById('calcActionText');
  const thdiVal = document.getElementById('calcThdi');
  const riskVal = document.getElementById('calcRiskPct');

  function calculateArmstrong() {
    const tL = parseFloat(sTL.value);
    const tR = parseFloat(sTR.value);
    vTL.textContent = `${tL.toFixed(1)} °C`;
    vTR.textContent = `${tR.toFixed(1)} °C`;

    const delta = Math.abs(tL - tR);
    dVal.textContent = `${tL >= tR ? '+' : '-'}${delta.toFixed(1)} K`;

    const currentLang = document.documentElement.lang || 'de';

    if (delta >= 2.2) {
      sBadge.className = 'pill crit';
      sBadge.style.color = 'var(--crit)';
      sBadge.style.background = '#fef2f2';
      sBadge.style.borderColor = '#fecaca';

      const statusMap = {
        de: 'ARMSTRONG-ALARM (SIGNIFIKANT)',
        en: 'ARMSTRONG ALERT (SIGNIFICANT)',
        fr: 'ALERTE ARMSTRONG (SIGNIFICATIVE)',
        es: 'ALARMA DE ARMSTRONG (SIGNIFICATIVA)',
        zh: '阿姆斯特朗严重预警（超标）'
      };
      const descMap = {
        de: 'Signifikanter Entzündungsherd mit hohem Ulkusrisiko (ΔT ≥ 2,2 K nach Armstrong et al., 2007). Sofortige Druckentlastung und radiometrische Verlaufskontrolle innerhalb von 48 Stunden indiziert.',
        en: 'Significant inflammatory focus with high ulcer risk (ΔT ≥ 2.2 K per Armstrong et al., 2007). Immediate offloading and follow-up scan within 48 hours strongly indicated.',
        fr: 'Foyer inflammatoire significatif à risque élevé d’ulcère (ΔT ≥ 2,2 K, Armstrong 2007). Décharge immédiate et contrôle radiométrique sous 48 h requis.',
        es: 'Foco inflamatorio significativo con alto riesgo de úlcera (ΔT ≥ 2,2 K según Armstrong 2007). Descarga mecánica inmediata y control termográfico en 48 h.',
        zh: '对侧显著炎症病灶，溃疡高风险（ΔT ≥ 2.2 K，Armstrong 2007 标准）。建议立即减压并于 48 小时内实施红外随访。'
      };

      sText.textContent = statusMap[currentLang] || statusMap.de;
      aText.textContent = descMap[currentLang] || descMap.de;
      thdiVal.textContent = `${(1.2 + delta * 0.25).toFixed(2)} W/(m²·K)`;
      riskVal.textContent = `${Math.min(96, Math.round(55 + delta * 12))}%`;
    } else if (delta >= 1.0) {
      sBadge.className = 'pill warn';
      sBadge.style.color = 'var(--warn)';
      sBadge.style.background = '#fffbeb';
      sBadge.style.borderColor = '#fde68a';

      const statusMap = {
        de: 'SUBKLINISCHE ASYMMETRIE',
        en: 'SUBCLINICAL ASYMMETRY',
        fr: 'ASYMÉTRIE INFRACLINIQUE',
        es: 'ASIMETRÍA SUBCLÍNICA',
        zh: '亚临床双侧不对称（需关注）'
      };
      const descMap = {
        de: 'Mäßige Temperaturdifferenz (1,0 K ≤ ΔT < 2,2 K). Erhöhte Wachsamkeit: Lokale Druckstellen prüfen und Kontrolle in 7 Tagen anberaumen.',
        en: 'Moderate temperature difference (1.0 K ≤ ΔT < 2.2 K). Check mechanical pressure points and schedule re-evaluation within 7 days.',
        fr: 'Écart thermique modéré (1,0 K ≤ ΔT < 2,2 K). Surveillance accrue : vérifier les zones de friction et réévaluer à 7 jours.',
        es: 'Diferencia térmica moderada (1,0 K ≤ ΔT < 2,2 K). Vigilar hiperpresiones locales y programar revisión en 7 días.',
        zh: '中度双侧温差（1.0 K ≤ ΔT < 2.2 K）。建议排查足底异常高压区域并在 7 天内复查。'
      };

      sText.textContent = statusMap[currentLang] || statusMap.de;
      aText.textContent = descMap[currentLang] || descMap.de;
      thdiVal.textContent = `${(0.6 + delta * 0.2).toFixed(2)} W/(m²·K)`;
      riskVal.textContent = `${Math.round(20 + delta * 12)}%`;
    } else {
      sBadge.className = 'pill ok';
      sBadge.style.color = 'var(--ok)';
      sBadge.style.background = '#f0fdf4';
      sBadge.style.borderColor = '#bbf7d0';

      const statusMap = {
        de: 'PHYSIOLOGISCH (UNAUFFÄLLIG)',
        en: 'PHYSIOLOGICAL (NORMAL)',
        fr: 'PHYSIOLOGIQUE (NORMAL)',
        es: 'FISIOLÓGICO (NORMAL)',
        zh: '生理性正常（双侧对称）'
      };
      const descMap = {
        de: 'Symmetrisches Temperaturprofil im physiologischen Normalbereich (ΔT < 1,0 K). Keine akute Interventionsnotwendigkeit.',
        en: 'Symmetric temperature profile within normal physiological range (ΔT < 1.0 K). No acute intervention required.',
        fr: 'Profil thermique symétrique dans les normes physiologiques (ΔT < 1,0 K). Aucune intervention urgente requise.',
        es: 'Perfil térmico simétrico dentro de la normalidad fisiológica (ΔT < 1,0 K). Sin necesidad de intervención aguda.',
        zh: '双侧微循环温度对称处于正常生理范围（ΔT < 1.0 K），无需特殊临床干预。'
      };

      sText.textContent = statusMap[currentLang] || statusMap.de;
      aText.textContent = descMap[currentLang] || descMap.de;
      thdiVal.textContent = '0.18 W/(m²·K)';
      riskVal.textContent = '< 5%';
    }
  }

  sTL.addEventListener('input', calculateArmstrong);
  sTR.addEventListener('input', calculateArmstrong);

  const btnDemo = document.getElementById('btnDemoCase');
  if (btnDemo) {
    btnDemo.addEventListener('click', () => {
      sTL.value = 34.8;
      sTR.value = 32.1;
      calculateArmstrong();
    });
  }

  const btnNorm = document.getElementById('btnNormalCase');
  if (btnNorm) {
    btnNorm.addEventListener('click', () => {
      sTL.value = 31.4;
      sTR.value = 31.2;
      calculateArmstrong();
    });
  }

  const chips = document.getElementById('calcZoneChips');
  if (chips) {
    chips.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        chips.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const zone = btn.dataset.zone;
        if (zone === 'hallux') { sTL.value = 34.8; sTR.value = 32.1; }
        else if (zone === 'meta') { sTL.value = 33.2; sTR.value = 32.8; }
        else if (zone === 'heel') { sTL.value = 30.5; sTR.value = 30.2; }
        else if (zone === 'arch') { sTL.value = 31.8; sTR.value = 31.9; }
        calculateArmstrong();
      });
    });
  }

  calculateArmstrong();
}

// ============ SMART KEYBOARD SHORTCUTS ============
let curtainAnimating = false;
addEventListener('keydown', e => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;

  if (e.key === '1') window.location.href = '/';
  else if (e.key === '2') window.location.href = '/technik.html';
  else if (e.key === '3') window.location.href = '/pipeline.html';
  else if (e.key === '4') window.location.href = '/klinik.html';
  else if (e.key === '5') window.location.href = '/team.html';
  else if (e.key.toLowerCase() === 'd') {
    const sim = document.getElementById('simulator');
    if (sim) sim.scrollIntoView({ behavior: 'smooth' });
  } else if (e.code === 'Space' && c && !curtainAnimating) {
    e.preventDefault();
    curtainAnimating = true;
    let step = 0;
    const dur = 60;
    const startVal = parseFloat(c.style.getPropertyValue('--pos') || 50);
    const targetVal = startVal > 50 ? 15 : 85;
    const interval = setInterval(() => {
      step++;
      const current = startVal + (targetVal - startVal) * (step / dur);
      c.style.setProperty('--pos', current + '%');
      const input = c.querySelector('input');
      if (input) input.value = current;
      if (step >= dur) {
        clearInterval(interval);
        curtainAnimating = false;
      }
    }, 16);
  }
});
