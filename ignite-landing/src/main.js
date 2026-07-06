import './style.css'

// Pipeline Steps Data
const pipelineSteps = {
  1: {
    image: '/images/step1.png',
    title: 'Schritt 1: Infrarot-Originalbild',
    description: 'Das rohe Infrarotbild direkt aus der Wärmebildkamera. Die Farbskalierung bildet die ungefilterte Oberflächentemperatur des Fußes ab. Zu diesem Zeitpunkt sind Rauschen, Hosenbeine und Raum-Hintergrundreflexionen noch voll vorhanden.',
    bullets: [
      'Kalibrierung über anpassbaren Temperatur-Offset',
      'Präzise Pixel-Temperatur-Konvertierung'
    ]
  },
  2: {
    image: '/images/step2.png',
    title: 'Schritt 2: Anatomische Rumpf-Maske',
    description: 'Ein adaptiver Otsu-Schwellwertalgorithmus detektiert den Fußkontakt und extrahiert eine präzise anatomische Maske (Body Mask). Hintergrund-Rauschen sowie Hosenbeine und Raumeinflüsse werden hierdurch geometrisch ausgeblendet.',
    bullets: [
      'Automatischer Konturausschluss',
      'Denoising über morphologisches Closing'
    ]
  },
  3: {
    image: '/images/step3.png',
    title: 'Schritt 3: Lokale Hitze-Differenz',
    description: 'Ein morphologischer Top-Hat-Filter vergleicht die Intensitäten und ermittelt die lokale Hitze-Differenz. Lokale Temperaturspitzen werden gegenüber dem umgebenden Gewebe des restlichen Fußes stark hervorgehoben.',
    bullets: [
      'Top-Hat Kernel zur Gewebedifferenzierung',
      'Eliminierung globaler Raumtemperaturdrifts'
    ]
  },
  4: {
    image: '/images/step4.png',
    title: 'Schritt 4: Detektierte Hotspots',
    description: 'Die finalen Hotspots werden über das CPU- (Rust) oder GPU-Backend (PyTorch) segmentiert. Mittels anatomischer Y-Achsen-Einschränkung werden Knöchel- und Ferseneinflüsse ignoriert, sodass nur echte Entzündungsherde (z.B. am großen Zeh) verbleiben.',
    bullets: [
      'Natives Rust-Multi-Threading & GPU-Backend',
      'Anatomischer Y-Einschränkungsfilter für hohe Spezifität'
    ]
  }
};

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const tabButtons = document.querySelectorAll('.tab-btn');
  const showcaseImage = document.getElementById('showcase-image');
  const showcaseTitle = document.getElementById('showcase-title');
  const showcaseDescription = document.getElementById('showcase-description');
  const showcaseBullets = document.getElementById('showcase-bullets');
  const navbar = document.getElementById('navbar');

  // Tab switcher logic
  tabButtons.forEach(button => {
    button.addEventListener('click', (e) => {
      // Remove active from all
      tabButtons.forEach(btn => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
      });

      // Add active to clicked
      button.classList.add('active');
      button.setAttribute('aria-selected', 'true');

      const step = button.getAttribute('data-step');
      const stepData = pipelineSteps[step];

      if (stepData) {
        // Fade effect transition
        showcaseImage.style.opacity = 0;
        
        setTimeout(() => {
          showcaseImage.src = stepData.image;
          showcaseImage.alt = stepData.title;
          showcaseTitle.textContent = stepData.title;
          showcaseDescription.textContent = stepData.description;

          // Clear and recreate bullets
          showcaseBullets.innerHTML = '';
          stepData.bullets.forEach(bulletText => {
            const li = document.createElement('li');
            li.textContent = bulletText;
            showcaseBullets.appendChild(li);
          });
          
          showcaseImage.style.opacity = 1;
        }, 150);
      }
    });
  });

  // Simple fade transition initialization
  if (showcaseImage) {
    showcaseImage.style.transition = 'opacity 0.15s ease-in-out';
  }

  // Header scroll shadow effect
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      navbar.style.backgroundColor = 'rgba(9, 9, 11, 0.95)';
      navbar.style.boxShadow = '0 4px 20px rgba(0,0,0,0.4)';
    } else {
      navbar.style.backgroundColor = 'rgba(9, 9, 11, 0.8)';
      navbar.style.boxShadow = 'none';
    }
  });

  // Interactive Before/After Slider Logic
  const sliderContainer = document.querySelector('.slider-container');
  if (sliderContainer) {
    const afterImage = sliderContainer.querySelector('.image-after');
    const handle = sliderContainer.querySelector('.slider-handle');
    let isDragging = false;

    const moveSlider = (clientX) => {
      const rect = sliderContainer.getBoundingClientRect();
      const x = clientX - rect.left;
      let percentage = (x / rect.width) * 100;
      
      // Keep boundary limits
      if (percentage < 0) percentage = 0;
      if (percentage > 100) percentage = 100;

      // Update layout width and handle position
      afterImage.style.width = `${percentage}%`;
      handle.style.left = `${percentage}%`;
    };

    const startDrag = (e) => {
      isDragging = true;
      e.preventDefault();
    };

    const stopDrag = () => {
      isDragging = false;
    };

    // Desktop Mouse Events
    handle.addEventListener('mousedown', startDrag);
    window.addEventListener('mouseup', stopDrag);
    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      moveSlider(e.clientX);
    });

    // Mobile/Tablet Touch Events
    handle.addEventListener('touchstart', startDrag);
    window.addEventListener('touchend', stopDrag);
    window.addEventListener('touchmove', (e) => {
      if (!isDragging) return;
      if (e.touches && e.touches.length > 0) {
        moveSlider(e.touches[0].clientX);
      }
    });

    // Clicking the container to jump to position
    sliderContainer.addEventListener('click', (e) => {
      if (e.target === handle) return;
      moveSlider(e.clientX);
    });
  }
});
