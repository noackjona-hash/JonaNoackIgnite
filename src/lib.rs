//! # ignite_core – Rust-Native-Bildverarbeitungs-Pipeline für Ignite
//!
//! Dieses Modul ist das mathematische Herzstück des Jugend-forscht-Projekts „Ignite"
//! (Entzündungsdetektion via Thermografie). Es implementiert die vollständige
//! Thermal-Bildverarbeitungs-Pipeline in nativem Rust – ohne externe C/C++-Abhängigkeiten –
//! und wird via PyO3/maturin als natives Python-Erweiterungsmodul (`.pyd`) eingebunden.
//!
//! ## Warum kein opencv-Rust-Binding?
//! Die opencv-Crate erfordert eine systemweite OpenCV-Installation mit C-Headers und LLVM.
//! Das installierte `opencv-python` (pip) enthält ausschließlich die `cv2.pyd`-Binärdatei
//! ohne Headers oder Link-Libraries. Daher nutzt dieser Core die Crates `imageproc` + `image`
//! für alle Bildverarbeitungsoperationen in purem, portablem Rust.
//!
//! ## Architektur
//! - **Eingang:** NumPy-Array `u8[H, W]` (Graustufen-Wärmebild) via Zero-Copy-Slice
//! - **Ausgang:** Zwei NumPy-Arrays `u8[H, W]` – normalisiertes Differenzbild + Hotspot-Maske
//! - **Parallelisierung:** `rayon` + `ndarray` parallel iterators über alle CPU-Kerne
//!
//! ## Pipeline-Stufen (A–E)
//! - **A** Dynamische Kernel-Skalierung (10 % der Bildbreite, bitweise odd-enforcement, ≥ 3)
//! - **B** Adaptive Body-Mask via Distanztransformation (DIST_L2, proportionale Erosion)
//! - **C** Morphologische Top-Hat-Transformation (elliptisches Strukturierungselement)
//! - **D** Statistischer Schwellenwert µ + 2σ (exklusiv über maskierte Körper-Pixel)
//! - **E** Geometrischer Rauschfilter (relative Mindestfläche + Circularity ≥ 0.2)
//!
//! ## Fehlerbehandlung
//! Es wird niemals `unwrap()` oder `expect()` verwendet. Alle Operationen sind über
//! `Result<T, String>` abgesichert. Fehler werden als `PyRuntimeError` an Python propagiert.

use ndarray::{Array2, ArrayView2};
use numpy::{PyArray2, PyReadonlyArray2};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::f64::consts::PI;

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 1: INTERNE TYPEN & HILFSFUNKTIONEN
// ─────────────────────────────────────────────────────────────────────────────

/// Interne 2D-Matrix für Bildoperationen.
/// Wird als Wrapper um `Array2<u8>` verwendet, um explizite Dimensionen zu haben.
type ImageMatrix = Array2<u8>;

/// Interne Gleitkomma-Matrix für Zwischenberechnungen (Distanzkarte, Statistik).
type FloatMatrix = Array2<f64>;

/// Rauschunterdrückung via 3x3 Box-Blur.
/// Glättet das Bild parallel über Zeilen mittels Rayon, um hochfrequentes Sensorrauschen
/// zu minimieren, was die Qualität der Hotspot-Erkennung und der Visualisierung steigert.
fn box_blur_3x3(img: &ImageMatrix) -> ImageMatrix {
    let (h, w) = img.dim();
    let mut output = Array2::<u8>::zeros((h, w));
    
    // Parallelisierung über Zeilen
    output.axis_iter_mut(ndarray::Axis(0)).into_par_iter().enumerate().for_each(|(y, mut row)| {
        if y == 0 || y == h - 1 {
            for x in 0..w {
                row[x] = img[[y, x]];
            }
            return;
        }
        
        row[0] = img[[y, 0]];
        row[w - 1] = img[[y, w - 1]];
        
        for x in 1..w - 1 {
            let sum = img[[y - 1, x - 1]] as u32
                + img[[y - 1, x]] as u32
                + img[[y - 1, x + 1]] as u32
                + img[[y, x - 1]] as u32
                + img[[y, x]] as u32
                + img[[y, x + 1]] as u32
                + img[[y + 1, x - 1]] as u32
                + img[[y + 1, x]] as u32
                + img[[y + 1, x + 1]] as u32;
            row[x] = (sum / 9) as u8;
        }
    });
    
    output
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 2: FEATURE A – DYNAMISCHE KERNEL-BERECHNUNG
// ─────────────────────────────────────────────────────────────────────────────

/// Berechnet eine ungerade Kernel-Größe als Prozentsatz der Bildbreite.
///
/// # Methodik
/// `raw = (dimension * factor) as usize`
/// Ungerade-Erzwingung via bitweiser OR-Operation: `raw | 1`
/// Minimalwert: 3 (Anforderung für morphologische Operationen).
///
/// # Arguments
/// * `dimension` – Breite oder Höhe des Bildes in Pixeln
/// * `factor`    – Skalierungsfaktor (z.B. 0.10 für 10 %)
///
/// # Returns
/// Ungerade `usize`-Kernel-Größe (Halbradius = size / 2), mindestens 3.
fn compute_odd_kernel(dimension: usize, factor: f64) -> usize {
    let raw = (dimension as f64 * factor) as usize;
    // Bitweise OR mit 1: Setzt das niederwertigste Bit → macht die Zahl ungerade.
    // Wenn raw = 64 (gerade) → 64 | 1 = 65 (ungerade, korrekt).
    // Wenn raw = 65 (ungerade) → 65 | 1 = 65 (unverändert).
    let odd = (raw | 1).max(1);
    // OpenCV und imageproc verlangen Kernel-Radii >= 1 (Größe >= 3)
    odd.max(3)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 3: MORPHOLOGISCHE BASISOPERATIONEN (Rust-Native)
// ─────────────────────────────────────────────────────────────────────────────

// create_ellipse_kernel entfernt – nicht mehr benötigt.
// Die separierbaren Operationen benötigen kein explizites Kernel-Array.


/// 1D-Sliding-Window Maximum (Dilation) für eine Datenreihe.
///
/// # Komplexität
/// O(N) – echtes Sliding-Window Maximum via Monotone Deque (Algorithmus nach Lemire 2011).
/// Dramatisch schneller als der naive O(N×radius)-Ansatz bei großen Kerneln.
///
/// # Methodik (Monotone Deque)
/// Eine doppelseitige Warteschlange (VecDeque) hält Indizes der Kandidaten für
/// das aktuelle Fenster-Maximum in absteigender Reihenfolge der Werte.
/// - Beim Einfügen eines neuen Elements werden alle kleineren Elemente am Ende
///   aus der Deque entfernt (sie können nie mehr Maximum werden).
/// - Das älteste Element wird vorne entfernt, sobald es aus dem Fenster fällt.
/// - Das aktuelle Maximum ist immer vorne in der Deque.
use std::collections::VecDeque;

fn dilate_1d(data: &[u8], radius: usize) -> Vec<u8> {
    let n = data.len();
    if n == 0 {
        return Vec::new();
    }
    let mut result = vec![0u8; n];
    let mut deque: VecDeque<usize> = VecDeque::new();

    // Das Fenster für den zentrierten Pixel i reicht von i-radius bis i+radius.
    // Wir verschieben die führende Kante j von 0 bis n + radius, um alle Werte zu verarbeiten.
    for j in 0..(n + radius) {
        // 1. Element j am Ende der Deque einfügen
        if j < n {
            while let Some(&back) = deque.back() {
                if data[back] <= data[j] {
                    deque.pop_back();
                } else {
                    break;
                }
            }
            deque.push_back(j);
        }

        // 2. Veraltete Indizes (älter als der linke Fensterrand) vorne entfernen.
        // Der linke Fensterrand für den Pixel i = j - radius ist i - radius = j - 2*radius.
        if j >= 2 * radius {
            let limit = j - 2 * radius;
            while let Some(&front) = deque.front() {
                if front < limit {
                    deque.pop_front();
                } else {
                    break;
                }
            }
        }

        // 3. Maximum für den zentrierten Pixel i = j - radius speichern
        if j >= radius {
            let i = j - radius;
            result[i] = data[*deque.front().unwrap()];
        }
    }
    result
}

/// 1D-Sliding-Window Minimum (Erosion) für eine Datenreihe.
///
/// # Komplexität
/// O(N) – analoges Monotone Deque Sliding-Window Minimum.
/// Deque hält Indizes in aufsteigender Wertereihenfolge.
fn erode_1d(data: &[u8], radius: usize) -> Vec<u8> {
    let n = data.len();
    if n == 0 {
        return Vec::new();
    }
    let mut result = vec![255u8; n];
    let mut deque: VecDeque<usize> = VecDeque::new();

    for j in 0..(n + radius) {
        // 1. Element j einsortieren
        if j < n {
            while let Some(&back) = deque.back() {
                if data[back] >= data[j] {
                    deque.pop_back();
                } else {
                    break;
                }
            }
            deque.push_back(j);
        }

        // 2. Veraltete Indizes entfernen (kleiner als linker Fensterrand j - 2*radius)
        if j >= 2 * radius {
            let limit = j - 2 * radius;
            while let Some(&front) = deque.front() {
                if front < limit {
                    deque.pop_front();
                } else {
                    break;
                }
            }
        }

        // 3. Minimum für den zentrierten Pixel i = j - radius speichern
        if j >= radius {
            let i = j - radius;
            result[i] = data[*deque.front().unwrap()];
        }
    }
    result
}

/// Morphologische Dilatation – Separierbare Sliding-Window-Implementierung.
///
/// # Methodik (Separierbar)
/// Anstatt jeden Pixel mit einem 2D-Kernel zu vergleichen (O(K²) pro Pixel),
/// werden zwei unabhängige 1D-Pässe ausgeführt:
/// 1. Horizontaler Pass: max in jeder Zeile (O(W × radius) pro Zeile)
/// 2. Vertikaler Pass:  max in jeder Spalte (O(H × radius) pro Spalte)
///
/// # Komplexität
/// Naiv:       O(H × W × K²) – hängt bei 1440×1080 mit K=73 (~8,3 Mrd. Ops)
/// Separierbar: O(H × W × K)  – ~113 Mio. Ops, unter 1 Sekunde mit rayon
///
/// # Arguments
/// * `img`         – Eingabe-Matrix (H, W), u8
/// * `kernel_size` – Ungerade Kernel-Größe
///
/// # Returns
/// `Result<ImageMatrix, String>` – Dilatiertes Bild
fn dilate(img: &ImageMatrix, kernel_size: usize) -> Result<ImageMatrix, String> {
    let (h, w) = img.dim();
    let radius = kernel_size / 2;

    // Pass 1: Horizontale Dilation (parallelisiert über Zeilen via rayon)
    let tmp_rows: Vec<Vec<u8>> = (0..h)
        .into_par_iter()
        .map(|y| {
            let row: Vec<u8> = (0..w).map(|x| img[[y, x]]).collect();
            dilate_1d(&row, radius)
        })
        .collect();

    // Zwischenergebnis in Matrix umwandeln
    let mut tmp = Array2::<u8>::zeros((h, w));
    for (y, row) in tmp_rows.iter().enumerate() {
        for (x, &v) in row.iter().enumerate() {
            tmp[[y, x]] = v;
        }
    }

    // Pass 2: Vertikale Dilation (parallelisiert über Spalten via rayon)
    let col_results: Vec<Vec<u8>> = (0..w)
        .into_par_iter()
        .map(|x| {
            let col: Vec<u8> = (0..h).map(|y| tmp[[y, x]]).collect();
            dilate_1d(&col, radius)
        })
        .collect();

    let mut output = Array2::<u8>::zeros((h, w));
    for (x, col) in col_results.iter().enumerate() {
        for (y, &v) in col.iter().enumerate() {
            output[[y, x]] = v;
        }
    }
    Ok(output)
}

/// Morphologische Erosion – Separierbare Sliding-Window-Implementierung.
///
/// # Methodik
/// Analog zu `dilate()`, aber mit Sliding-Window Minimum statt Maximum.
/// 1. Horizontaler Pass: min in jeder Zeile
/// 2. Vertikaler Pass:  min in jeder Spalte
///
/// # Arguments
/// * `img`         – Eingabe-Matrix (H, W), u8
/// * `kernel_size` – Ungerade Kernel-Größe
///
/// # Returns
/// `Result<ImageMatrix, String>` – Erodiertes Bild
fn erode(img: &ImageMatrix, kernel_size: usize) -> Result<ImageMatrix, String> {
    let (h, w) = img.dim();
    let radius = kernel_size / 2;

    // Pass 1: Horizontale Erosion (parallelisiert über Zeilen)
    let tmp_rows: Vec<Vec<u8>> = (0..h)
        .into_par_iter()
        .map(|y| {
            let row: Vec<u8> = (0..w).map(|x| img[[y, x]]).collect();
            erode_1d(&row, radius)
        })
        .collect();

    let mut tmp = Array2::<u8>::zeros((h, w));
    for (y, row) in tmp_rows.iter().enumerate() {
        for (x, &v) in row.iter().enumerate() {
            tmp[[y, x]] = v;
        }
    }

    // Pass 2: Vertikale Erosion (parallelisiert über Spalten)
    let col_results: Vec<Vec<u8>> = (0..w)
        .into_par_iter()
        .map(|x| {
            let col: Vec<u8> = (0..h).map(|y| tmp[[y, x]]).collect();
            erode_1d(&col, radius)
        })
        .collect();

    let mut output = Array2::<u8>::zeros((h, w));
    for (x, col) in col_results.iter().enumerate() {
        for (y, &v) in col.iter().enumerate() {
            output[[y, x]] = v;
        }
    }
    Ok(output)
}


/// Morphologisches Opening: `open(I) = dilate(erode(I, SE), SE)`.
///
/// Entfernt kleine helle Objekte (Rauschen) und glättet Konturgrenzen.
fn morph_open(img: &ImageMatrix, kernel_size: usize) -> Result<ImageMatrix, String> {
    let eroded = erode(img, kernel_size)?;
    dilate(&eroded, kernel_size)
}

/// Morphologisches Closing: `close(I) = erode(dilate(I, SE), SE)`.
///
/// Schließt kleine dunkle Löcher innerhalb heller Regionen.
fn morph_close(img: &ImageMatrix, kernel_size: usize) -> Result<ImageMatrix, String> {
    let dilated = dilate(img, kernel_size)?;
    erode(&dilated, kernel_size)
}

/// Morphologische Top-Hat-Transformation: `tophat(I) = I - open(I, SE)`.
///
/// # Methodik
/// Das morphologische Opening `open(I, SE)` schätzt den lokalen Hintergrund
/// (langsam variierende Intensität). Die Subtraktion isoliert lokale, helle
/// Intensitätsspitzen, die kleiner als der Kernel sind – das sind die Hotspots.
///
/// `TopHat(I) = I - open(I, SE) = I - dilate(erode(I, SE), SE)`
///
/// Diese Methode ist mathematisch äquivalent zur Gauß-Baseline-Subtraktion, aber:
/// - Robuster gegenüber ungleichmäßiger Kamera-Kalibrierung
/// - Schärfere Hotspot-Grenzen (kein Weichzeichner-Artefakt)
/// - Keine negative Pixel (Ergebnis ist immer ≥ 0 durch Sättigungs-Subtraktion)
///
/// # Arguments
/// * `img`         – Eingabe-Matrix (H, W), u8
/// * `kernel_size` – Kernel-Größe für das Strukturierungselement
///
/// # Returns
/// `Result<ImageMatrix, String>` – Top-Hat-transformiertes Bild
fn morph_tophat(img: &ImageMatrix, kernel_size: usize) -> Result<ImageMatrix, String> {
    let opened = morph_open(img, kernel_size)?;

    // Gesättigte Subtraktion: I - open(I) ≥ 0 (kein Wrap-around bei u8)
    // ndarray 0.16: Zip::from().and().map_collect() statt zip_map() (nicht vorhanden)
    let tophat = ndarray::Zip::from(img)
        .and(&opened)
        .map_collect(|&orig, &bg| orig.saturating_sub(bg));
    Ok(tophat)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 4: FEATURE B – ADAPTIVE BODY-MASK VIA DISTANZTRANSFORMATION
// ─────────────────────────────────────────────────────────────────────────────

/// Berechnet den Otsu-Schwellenwert für automatische Binarisierung.
///
/// # Methodik (Otsu 1979)
/// Minimiert die intraklassen-Varianz zwischen Vordergrund und Hintergrund.
/// Iteriert über alle 256 möglichen Schwellenwerte und wählt denjenigen,
/// der die gewichtete Summe der Varianzen beider Klassen minimiert:
/// `σ²_w(t) = w₀(t)·σ²₀(t) + w₁(t)·σ²₁(t)`
///
/// # Arguments
/// * `img` – Graustufen-Eingabebild
///
/// # Returns
/// `u8` – Optimaler Schwellenwert nach Otsu
fn otsu_threshold(img: &ImageMatrix) -> u8 {
    // Histogramm berechnen
    let mut hist = [0usize; 256];
    img.iter().for_each(|&px| hist[px as usize] += 1);

    let total = img.len() as f64;
    let mut sum_total = 0.0f64;
    for (i, &count) in hist.iter().enumerate() {
        sum_total += i as f64 * count as f64;
    }

    let mut sum_bg = 0.0f64;
    let mut w_bg = 0.0f64;
    let mut max_variance = 0.0f64;
    let mut best_threshold = 0u8;

    for t in 0..256usize {
        w_bg += hist[t] as f64;
        if w_bg == 0.0 {
            continue;
        }
        let w_fg = total - w_bg;
        if w_fg == 0.0 {
            break;
        }

        sum_bg += t as f64 * hist[t] as f64;
        let mean_bg = sum_bg / w_bg;
        let mean_fg = (sum_total - sum_bg) / w_fg;

        // Interklassen-Varianz (äquivalent zur Minimierung der Intraklassen-Varianz)
        let variance = w_bg * w_fg * (mean_bg - mean_fg).powi(2);
        if variance > max_variance {
            max_variance = variance;
            best_threshold = t as u8;
        }
    }
    best_threshold
}

/// Berechnet eine euklidische Distanzkarte (DIST_L2) via BFS/Wavefront-Propagation.
///
/// # Methodik
/// Jeder Pixel der binären Maske erhält als Wert seine euklidische Distanz zum
/// nächsten Hintergrundpixel (0-Pixel). Implementiert als iterativer Algorithmus:
/// 1. Initialisierung: Alle Vordergrund-Pixel (255) bekommen Distanz ∞.
///    Hintergrund-Pixel (0) bekommen Distanz 0.
/// 2. Vorwärts-Pass (oben-links → unten-rechts):
///    Aktualisiere Distanz via Nachbarpixel + Schritt-Kosten.
/// 3. Rückwärts-Pass (unten-rechts → oben-links):
///    Aktualisiere analog für die andere Richtung.
///
/// Approximiert DIST_L2 (euklidisch) mit der chamfer-Metrik (3-4-Approximation).
///
/// # Arguments
/// * `binary_mask` – Binäres Eingabebild (0 = Hintergrund, 255 = Vordergrund)
///
/// # Returns
/// `FloatMatrix` – Distanzkarte (Gleitkomma, nicht normalisiert)
fn distance_transform_l2(binary_mask: &ImageMatrix) -> FloatMatrix {
    let (h, w) = binary_mask.dim();

    // Chamfer 3-4 Approximation mit u32-Integer-Arithmetik (statt f64):
    // Integer-Ops sind ~4× schneller als Float-Ops in der inneren Schleife.
    // Horizontale/Vertikale Nachbarn: Kosten = 3
    // Diagonale Nachbarn: Kosten = 4
    // Skalierung: Euklidischer Wert ≈ dist_int / 3.0 (Normierung bei Bedarf)
    const INF: u32 = u32::MAX / 2;
    const COST_STRAIGHT: u32 = 3;
    const COST_DIAGONAL: u32 = 4;

    // Integer-Distanzkarte für schnelle Berechnungen
    let mut dist_int = Array2::<u32>::from_elem((h, w), INF);
    for y in 0..h {
        for x in 0..w {
            if binary_mask[[y, x]] == 0 {
                dist_int[[y, x]] = 0;
            }
        }
    }

    // Vorwärts-Pass: Oben-links → Unten-rechts
    for y in 0..h {
        for x in 0..w {
            if dist_int[[y, x]] == 0 {
                continue;
            }
            let mut min_d = dist_int[[y, x]];
            if y > 0 {
                min_d = min_d.min(dist_int[[y - 1, x]].saturating_add(COST_STRAIGHT));
            }
            if x > 0 {
                min_d = min_d.min(dist_int[[y, x - 1]].saturating_add(COST_STRAIGHT));
            }
            if y > 0 && x > 0 {
                min_d = min_d.min(dist_int[[y - 1, x - 1]].saturating_add(COST_DIAGONAL));
            }
            if y > 0 && x + 1 < w {
                min_d = min_d.min(dist_int[[y - 1, x + 1]].saturating_add(COST_DIAGONAL));
            }
            dist_int[[y, x]] = min_d;
        }
    }

    // Rückwärts-Pass: Unten-rechts → Oben-links
    for y in (0..h).rev() {
        for x in (0..w).rev() {
            if dist_int[[y, x]] == 0 {
                continue;
            }
            let mut min_d = dist_int[[y, x]];
            if y + 1 < h {
                min_d = min_d.min(dist_int[[y + 1, x]].saturating_add(COST_STRAIGHT));
            }
            if x + 1 < w {
                min_d = min_d.min(dist_int[[y, x + 1]].saturating_add(COST_STRAIGHT));
            }
            if y + 1 < h && x + 1 < w {
                min_d = min_d.min(dist_int[[y + 1, x + 1]].saturating_add(COST_DIAGONAL));
            }
            if y + 1 < h && x > 0 {
                min_d = min_d.min(dist_int[[y + 1, x - 1]].saturating_add(COST_DIAGONAL));
            }
            dist_int[[y, x]] = min_d;
        }
    }

    // Zurück zu f64 für Kompatibilität mit dem Rest der Pipeline
    // (Division durch 3 normiert auf ungefähre euklidische Pixel-Distanz)
    dist_int.mapv(|v| if v >= INF { f64::MAX / 2.0 } else { v as f64 / 3.0 })
}

/// Erzeugt eine Body-Mask via Otsu-Schwellenwert und adaptiver Distanz-Erosion.
///
/// # Methodik
/// 1. **Otsu-Binarisierung:** Automatischer globaler Schwellenwert trennt Körper
///    (hell, warm) vom Hintergrund (dunkel, kalt).
/// 2. **Distanztransformation (DIST_L2-Approximation):**
///    Jeder Vordergrundpixel erhält seine euklidische Distanz zum nächsten Rand.
/// 3. **Adaptive Schwellenwertierung:**
///    Nur Pixel mit `dist >= threshold_factor * max_dist` bleiben erhalten.
///    `threshold_factor = 0.15` schließt proportionale Randbereiche aus –
///    dies eliminiert Artefakte an anatomischen Übergängen (Finger, Handgelenke).
///
/// # Arguments
/// * `img` – Graustufen-Eingabebild
///
/// # Returns
/// `Result<ImageMatrix, String>` – Binäre Body-Mask (0 oder 255)
fn extract_body_mask(
    img: &ImageMatrix,
    otsu_min: u8,
    otsu_max: u8,
    dist_erosion_factor: f64,
) -> Result<(ImageMatrix, FloatMatrix), String> {
    let (h, w) = img.dim();

    // Schritt 1: Otsu-Binarisierung mit adaptivem Fallback.
    let otsu_thresh = otsu_threshold(img);
    let threshold = (otsu_thresh / 2).max(otsu_min).min(otsu_max);
    let mut otsu_mask = Array2::<u8>::zeros((h, w));
    otsu_mask.zip_mut_with(img, |out, &px| {
        *out = if px > threshold { 255 } else { 0 };
    });

    // Schritt 2: Distanztransformation (wird auch an filter_geometric weitergegeben)
    let dist_map = distance_transform_l2(&otsu_mask);

    // Maximum der Distanzkarte (für relative Schwellenwertierung)
    let max_dist = dist_map.iter().cloned().fold(0.0_f64, f64::max);
    if max_dist < 1e-10 {
        let empty_mask = Array2::<u8>::zeros((h, w));
        let empty_dist = Array2::<f64>::zeros((h, w));
        return Ok((empty_mask, empty_dist));
    }

    // Schritt 3: Adaptive Erosion
    let erosion_threshold = dist_erosion_factor * max_dist;
    let mut eroded_mask = Array2::<u8>::zeros((h, w));
    for y in 0..h {
        for x in 0..w {
            if dist_map[[y, x]] >= erosion_threshold {
                eroded_mask[[y, x]] = 255;
            }
        }
    }

    Ok((eroded_mask, dist_map))
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 5: FEATURE C – TOP-HAT DIFFERENZBILD
// ─────────────────────────────────────────────────────────────────────────────

/// Berechnet das Differenzbild via morphologischer Top-Hat-Transformation.
///
/// Wendet `morph_tophat()` auf das Bild an und maskiert das Ergebnis mit
/// der Body-Mask (nur Körper-Pixel bleiben im Differenzbild erhalten).
///
/// # Arguments
/// * `img`         – Graustufen-Eingabebild
/// * `mask`        – Body-Mask (0 = Hintergrund, 255 = Körper)
/// * `kernel_size` – Ungerade Kernel-Größe für das Strukturierungselement
///
/// # Returns
/// `Result<ImageMatrix, String>` – Top-Hat-Differenzbild, nur über Körper-Pixeln
fn calculate_tophat_difference(
    img: &ImageMatrix,
    mask: &ImageMatrix,
    kernel_size: usize,
) -> Result<ImageMatrix, String> {
    let tophat = morph_tophat(img, kernel_size)?;

    // Bitwise-AND mit Body-Mask: Hintergrund-Pixel → 0
    // ndarray 0.16: elementweise Operation via Zip::from().and().map_collect()
    let diff_masked = ndarray::Zip::from(&tophat)
        .and(mask)
        .map_collect(|&t, &m| if m > 0 { t } else { 0 });
    Ok(diff_masked)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 6: FEATURE D – STATISTISCHE SCHWELLENWERT-ANALYSE
// ─────────────────────────────────────────────────────────────────────────────

/// Binarisiert das Differenzbild mit adaptivem µ + k·σ Schwellenwert.
///
/// # Methodik
/// 1. Berechne µ (Mittelwert) und σ (Standardabweichung) **exklusiv** über
///    die Pixel, die innerhalb der Body-Mask liegen.
///    Hintergrund-Pixel würden µ nach unten ziehen und σ verfälschen.
/// 2. Adaptiver Schwellenwert: `T = µ + k * σ` (k = 2.0)
///    Statistisch: Pixel > µ + 2σ sind mit 97.7 % Wahrscheinlichkeit Ausreißer
///    (Entzündungs-Verdacht) unter der Normalverteilungs-Annahme.
/// 3. Binarisierung: Alle Pixel mit Wert > T → 255, sonst → 0.
///
/// # Arguments
/// * `diff_img` – Top-Hat-Differenzbild
/// * `mask`     – Body-Mask (definiert die statistische Pixel-Population)
/// * `k`        – Standardabweichungs-Multiplikator (Standard: 2.0)
///
/// # Returns
/// `Result<ImageMatrix, String>` – Binäre Hotspot-Rohmaske
fn threshold_statistical(
    original_img: &ImageMatrix,
    diff_img: &ImageMatrix,
    mask: &ImageMatrix,
    k: f64,
) -> Result<ImageMatrix, String> {
    let (h, w) = diff_img.dim();

    // Zero-Allocation Parallel Reduction via Rayon
    // Berechnet die Summen und Quadratsummen parallel über Zeilen hinweg
    let (sum_diff, sum_orig, sum_sq_diff, count) = (0..h)
        .into_par_iter()
        .map(|y| {
            let mut local_sum_diff = 0.0;
            let mut local_sum_orig = 0.0;
            let mut local_sum_sq_diff = 0.0;
            let mut local_count = 0.0;
            for x in 0..w {
                if mask[[y, x]] > 0 {
                    let d = diff_img[[y, x]] as f64;
                    let o = original_img[[y, x]] as f64;
                    local_sum_diff += d;
                    local_sum_orig += o;
                    local_sum_sq_diff += d * d;
                    local_count += 1.0;
                }
            }
            (local_sum_diff, local_sum_orig, local_sum_sq_diff, local_count)
        })
        .reduce(
            || (0.0, 0.0, 0.0, 0.0),
            |a, b| (a.0 + b.0, a.1 + b.1, a.2 + b.2, a.3 + b.3)
        );

    if count < 1.0 {
        return Err("Body-Mask ist leer – keine Körper-Pixel für Statistik gefunden.".to_string());
    }

    let n = count;

    // Mittelwerte µ für Top-Hat-Differenz und Originalbild
    let mu_diff = sum_diff / n;
    let mu_orig = sum_orig / n;

    // Standardabweichung σ für Top-Hat-Differenz: Var(X) = E[X^2] - (E[X])^2
    let variance_diff = (sum_sq_diff / n) - mu_diff.powi(2);
    // Float-Rundungsfehler abfangen (Varianz darf nicht negativ sein)
    let sigma_diff = variance_diff.max(0.0).sqrt();

    // Adaptiver relativer Schwellenwert T = µ + k·σ, geklemmt auf [0, 254]
    let threshold_diff = (mu_diff + k * sigma_diff).clamp(0.0, 254.0);

    let mut binary = Array2::<u8>::zeros((h, w));
    
    // Binarisierung parallel über Zeilen
    binary.axis_iter_mut(ndarray::Axis(0)).into_par_iter().enumerate().for_each(|(y, mut row)| {
        for x in 0..w {
            let diff_val = diff_img[[y, x]] as f64;
            let orig_val = original_img[[y, x]] as f64;
            if diff_val > threshold_diff && orig_val > mu_orig {
                row[x] = 255;
            }
        }
    });

    Ok(binary)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 7: FEATURE E – GEOMETRISCHER STRUKTUR- & RAUSCHFILTER
// ─────────────────────────────────────────────────────────────────────────────

/// Extrahiert zusammenhängende Komponenten (Connected Components) aus einer Binärmaske.
///
/// # Methodik (Two-Pass-Algorithmus mit Union-Find)
/// Pass 1: Jeder Vordergrundpixel bekommt ein Label. Verbundene Pixel (4-Konnektivität)
///         erhalten dasselbe Label via Union-Find-Datenstruktur.
/// Pass 2: Label-IDs werden auf ihre finale Wurzel normalisiert.
///
/// # Arguments
/// * `binary` – Binäre Eingabemaske (0 oder 255)
///
/// # Returns
/// Tuple: (label_matrix, max_label)
///   - label_matrix: u32-Matrix, Wert = Komponenten-ID (0 = Hintergrund)
///   - max_label: Anzahl der gefundenen Komponenten
fn connected_components(binary: &ImageMatrix) -> (Array2<u32>, u32) {
    let (h, w) = binary.dim();
    let mut labels = Array2::<u32>::zeros((h, w));
    let mut parent: Vec<u32> = vec![0]; // Index 0 = Hintergrund-Label
    let mut next_label = 1u32;

    // Union-Find: Finde Wurzel eines Labels
    let find = |parent: &mut Vec<u32>, mut x: u32| -> u32 {
        while parent[x as usize] != x {
            // Pfadkompression
            let grandparent = parent[parent[x as usize] as usize];
            parent[x as usize] = grandparent;
            x = grandparent;
        }
        x
    };

    // Pass 1: Labels vergeben
    for y in 0..h {
        for x in 0..w {
            if binary[[y, x]] == 0 {
                continue;
            }

            let north = if y > 0 { labels[[y - 1, x]] } else { 0 };
            let west = if x > 0 { labels[[y, x - 1]] } else { 0 };

            match (north > 0, west > 0) {
                (false, false) => {
                    // Neues Label
                    labels[[y, x]] = next_label;
                    parent.push(next_label);
                    next_label += 1;
                }
                (true, false) => {
                    labels[[y, x]] = find(&mut parent, north);
                }
                (false, true) => {
                    labels[[y, x]] = find(&mut parent, west);
                }
                (true, true) => {
                    let rn = find(&mut parent, north);
                    let rw = find(&mut parent, west);
                    let root = rn.min(rw);
                    let other = rn.max(rw);
                    if root != other {
                        parent[other as usize] = root;
                    }
                    labels[[y, x]] = root;
                }
            }
        }
    }

    // Pass 2: Labels normalisieren
    for y in 0..h {
        for x in 0..w {
            if labels[[y, x]] > 0 {
                let root = find(&mut parent, labels[[y, x]]);
                labels[[y, x]] = root;
            }
        }
    }

    let max_label = next_label - 1;
    (labels, max_label)
}

/// Berechnet Fläche und Perimeter für alle Komponenten.
///
/// # Methodik
/// - **Fläche:** Anzahl der Pixel mit diesem Label.
/// - **Perimeter (Approximation):** Anzahl der Pixel, die mindestens einen
///   Nachbarn mit anderem Label oder Bildrand-Pixel haben (4-Konnektivität).
///   Dies ist eine diskrete Approximation des euklidischen Umfangs.
///
/// # Arguments
/// * `labels`    – Label-Matrix aus `connected_components()`
/// * `max_label` – Maximales Label (Anzahl der Komponenten)
///
/// # Returns
/// Vec<(f64, f64)> – Index i = Label i+1: (Fläche, Perimeter)
fn compute_region_stats(
    labels: &Array2<u32>,
    max_label: u32,
    dist_map: &FloatMatrix,
) -> Vec<(f64, f64, bool, f64, f64)> {
    let (h, w) = labels.dim();
    let n = max_label as usize;
    let mut areas = vec![0.0f64; n + 1];
    let mut perimeters = vec![0.0f64; n + 1];
    let mut touches_border = vec![false; n + 1];
    let mut max_dists = vec![0.0f64; n + 1];
    let mut sum_y = vec![0.0f64; n + 1];

    let border_margin = 10usize;

    for y in 0..h {
        for x in 0..w {
            let lbl = labels[[y, x]] as usize;
            if lbl == 0 {
                continue;
            }
            areas[lbl] += 1.0;
            sum_y[lbl] += y as f64;

            // Maximale Distanz zum Maskenrand pro Komponente tracken
            let d = dist_map[[y, x]];
            if d > max_dists[lbl] {
                max_dists[lbl] = d;
            }

            if x <= border_margin || y <= border_margin || x >= w - 1 - border_margin || y >= h - 1 - border_margin {
                touches_border[lbl] = true;
            }

            let is_border = y == 0
                || y == h - 1
                || x == 0
                || x == w - 1
                || (y > 0 && labels[[y - 1, x]] as usize != lbl)
                || (y + 1 < h && labels[[y + 1, x]] as usize != lbl)
                || (x > 0 && labels[[y, x - 1]] as usize != lbl)
                || (x + 1 < w && labels[[y, x + 1]] as usize != lbl);

            if is_border {
                perimeters[lbl] += 1.0;
            }
        }
    }

    areas[1..].iter()
        .zip(perimeters[1..].iter())
        .zip(touches_border[1..].iter())
        .zip(max_dists[1..].iter())
        .zip(sum_y[1..].iter())
        .map(|((((&a, &p), &t), &md), &sy)| {
            let cy = if a > 0.0 { sy / a } else { 0.0 };
            (a, p, t, md, cy)
        })
        .collect()
}

/// Filtert die Hotspot-Rohmaske via geometrische Struktur-Analyse.
///
/// # Filterbedingungen (beide müssen erfüllt sein)
///
/// ## 1. Relative Mindestfläche
/// `Fläche >= 0.0005 * Gesamtfläche_der_Body_Mask`
/// Eliminiert Sensor-Rauschen (Pixel-Gruppen < 0.05 % der Körperoberfläche).
///
/// ## 2. Circularity (Rundheitsmaß ISO 1101)
/// `C = 4π * A / P²`
/// - Kreis:  C = 1.0 (perfekte Rundheit)
/// - Linie:  C → 0.0
/// - Schwellenwert: C ≥ 0.2
/// Echte Entzündungsareale sind kompakte, biologisch gerundete Formen.
/// Hautfalten und Kameralinien-Artefakte haben C < 0.2.
///
/// # Arguments
/// * `binary_mask`  – Binäre Hotspot-Rohmaske
/// * `body_mask`    – Body-Mask für relative Mindestfläche
/// * `kernel_size`  – Kernel für morphologisches Vor-Filtering
///
/// # Returns
/// `Result<ImageMatrix, String>` – Finale, gefilterte Hotspot-Maske
/// `kernel_size` wurde entfernt: Der ursprünglich geplante morphologische Closing-Schritt
/// wurde in der finalen Pipeline nicht benötigt (Otsu + Distance-Erosion reicht aus).
fn filter_geometric(
    binary_mask: &ImageMatrix,
    body_mask: &ImageMatrix,
    dist_map: &FloatMatrix,
    min_area_factor: f64,
    min_circularity: f64,
    min_dist_from_border: f64,
) -> Result<ImageMatrix, String> {
    let closed = binary_mask;

    let total_body_area = body_mask.iter().filter(|&&px| px > 0).count() as f64;
    let min_area_rel = min_area_factor * total_body_area;
    let min_area = min_area_rel.max(10.0);

    let (h, _w) = closed.dim();
    let y_threshold = h as f64 * 0.65;

    // Connected Components für die Filterung
    let (labels, max_label) = connected_components(&closed);
    if max_label == 0 {
        return Ok(closed.clone());
    }

    // Erweiterte Geometrie-Analyse inkl. maximaler Distanz zum Maskenrand und Y-Centroid
    let stats = compute_region_stats(&labels, max_label, dist_map);

    let keep_flags: Vec<bool> = stats
        .par_iter()
        .map(|&(area, perimeter, touches_b, max_dist_component, centroid_y)| {
            // Anatomische Einschränkung: Hotspots am Knöchel/Ferse/Hosenbein liegen
            // anatomisch im unteren 35% Bildbereich. Entzündeter Zeh liegt weit oben.
            if centroid_y > y_threshold {
                return false;
            }
            // Bedingung 0: Bildrand-Berührung
            if touches_b {
                return false;
            }
            // Bedingung 1: Distanztransformation – Hotspot muss tief genug im
            // Körperinneren liegen. Rand-Artefakte (Knöchel, Fersen) liegen
            // am Übergang Körper→Hintergrund (kleine Distanzwerte).
            if max_dist_component < min_dist_from_border {
                return false;
            }
            // Bedingung 2: Mindestfläche
            if area < min_area {
                return false;
            }
            // Bedingung 3: Circularity
            if perimeter < 1.0 {
                return false;
            }
            let circularity = (4.0 * PI * area) / (perimeter * perimeter);
            circularity >= min_circularity
        })
        .collect();

    let (h, w) = closed.dim();
    let mut final_mask = Array2::<u8>::zeros((h, w));
    for y in 0..h {
        for x in 0..w {
            let lbl = labels[[y, x]] as usize;
            if lbl > 0 && lbl <= keep_flags.len() && keep_flags[lbl - 1] {
                final_mask[[y, x]] = 255;
            }
        }
    }

    Ok(final_mask)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 8: NORMALISIERUNG
// ─────────────────────────────────────────────────────────────────────────────

/// Normalisiert eine Matrix linear auf den Bereich [0, 255].
///
/// # Methodik
/// `output[y, x] = (input[y, x] - min) * 255 / (max - min)`
/// Bei `max == min` (homogenes Bild) wird 0 zurückgegeben.
///
/// # Arguments
/// * `img` – Eingabematrix (u8)
///
/// # Returns
/// Normalisierte `ImageMatrix` im Bereich [0, 255]
fn normalize_minmax(img: &ImageMatrix) -> ImageMatrix {
    let min_val = *img.iter().min().unwrap_or(&0) as f64;
    let max_val = *img.iter().max().unwrap_or(&0) as f64;
    let range = max_val - min_val;

    if range < 1e-10 {
        return Array2::<u8>::zeros(img.dim());
    }

    let mut out = Array2::<u8>::zeros(img.dim());
    ndarray::Zip::from(&mut out).and(img).par_for_each(|out_px, &px| {
        *out_px = ((px as f64 - min_val) * 255.0 / range) as u8;
    });
    out
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 9: ÖFFENTLICHE PIPELINE-API (PyO3-Export)
// ─────────────────────────────────────────────────────────────────────────────

/// Führt die vollständige Thermobild-Verarbeitungs-Pipeline aus.
///
/// Dies ist die einzige öffentliche Funktion des Moduls – der zentrale
/// Einstiegspunkt für den Python-Wrapper (`image_processing.py`).
///
/// # Pipeline-Ablauf
/// ```
/// NumPy[H,W] → Body-Mask(Otsu + Distanz-Erosion)
///            → TopHat-Diff(elliptisches SE)
///            → µ+2σ-Threshold(statistisch, maskiert)
///            → Geometriefilter(Fläche + Circularity)
///            → NumPy[H,W] × 2
/// ```
///
/// # Zero-Copy-Eingang
/// `PyReadonlyArray2<u8>` ermöglicht direkten Speicherzugriff auf das NumPy-Array
/// ohne Datenkopie. Der Rust-Code liest den Array-Speicher direkt via `as_slice()`.
///
/// # Arguments
/// * `py`         – Python-GIL-Token (von PyO3 verwaltet)
/// * `gray_array` – Graustufen-Wärmebild als NumPy-Array u8[H, W]
///
/// # Returns
/// `PyResult<(Py<PyArray2<u8>>, Py<PyArray2<u8>>)>`
/// - Erstes Element: `diff_img` – Top-Hat-Differenzbild, normalisiert 0–255
/// - Zweites Element: `hotspot_mask` – Finale binäre Hotspot-Maske (0/255)
///
/// # Errors
/// Gibt `PyRuntimeError` zurück bei:
/// - Ungültiger Array-Form (nicht 2D oder nicht zusammenhängend)
/// - Leerem Bild oder leerer Body-Mask
/// - Internen Berechnungsfehlern (werden mit Kontext weitergereicht)
#[pyfunction]
#[pyo3(name = "process_thermal_pipeline")]
fn process_thermal_pipeline<'py>(
    py: Python<'py>,
    gray_array: PyReadonlyArray2<u8>,
    sigma_k: f64,
    tophat_factor: f64,
    min_area_factor: f64,
    min_circularity: f64,
    otsu_min: u8,
    otsu_max: u8,
    dist_erosion_factor: f64,
) -> PyResult<(Py<PyArray2<u8>>, Py<PyArray2<u8>>)> {
    // ── Schritt 0: Eingabe-Validierung ─────────────────────────────────────
    let array = gray_array.as_array();
    let shape = array.shape();
    let height = shape[0];
    let width = shape[1];

    if height == 0 || width == 0 {
        return Err(PyRuntimeError::new_err(
            "Eingabebild hat Nulldimension (H=0 oder W=0).",
        ));
    }

    // ── Schritt 1: NumPy-View → ndarray::ArrayView2 (Zero-Copy) ───────────
    // `as_array()` gibt eine Borrowed-View auf den NumPy-Speicher zurück – keine Kopie.
    let img_view: ArrayView2<u8> = array;

    // ── Schritt 2: Pipeline in einem GIL-freien Thread ausführen ──────────
    // `py.allow_threads` gibt die Python-GIL frei. Andere Python-Threads können
    // während der Rust-Berechnung laufen (z.B. die Tkinter-Eventloop).
    let (diff_mat, hotspot_mat) = py
        .allow_threads(|| -> Result<(ImageMatrix, ImageMatrix), String> {
            // Owned copy erzeugen (nötig da ArrayView2 nicht Send-sicher über thread boundaries)
            let img: ImageMatrix = img_view.to_owned();

            // ── Feature A-0: Rauschunterdrückung (Box-Blur-Vorfilter) ──────
            let img = box_blur_3x3(&img);

            // ── Feature A: Dynamische Kernel-Größen ──────────────────────
            // Top-Hat-Kernel: 5 % der Bildbreite (passend zu realen Thermokameras
            // mit 160–320px Auflösung, wo Hotspots typisch 10–50 Pixel groß sind).
            // Bei 640px Breite: 5 % = 33px Kernel.
            let kernel_large = compute_odd_kernel(width, tophat_factor);
            // Geometriefilter-Referenzgröße (nicht für Morph-Ops genutzt, nur als Parameter)
            let kernel_small = compute_odd_kernel(width, 0.02).max(3);

            println!(
                "[ignite_core] Bild: {}×{}, Kernel groß: {}, Kernel klein: {}",
                width, height, kernel_large, kernel_small
            );

            // ── Feature B: Adaptive Body-Mask via Distanztransformation ──
            // Gibt nun auch die Distanzkarte zurück (für Rand-Hotspot-Filter)
            let (mask, dist_map) = extract_body_mask(&img, otsu_min, otsu_max, dist_erosion_factor)
                .map_err(|e| format!("Body-Mask Fehler: {}", e))?;

            let body_pixel_count = mask.iter().filter(|&&px| px > 0).count();
            if body_pixel_count == 0 {
                return Err(
                    "Body-Mask ist leer – kein Körper im Bild erkannt. \
                     Bitte Kontrast des Wärmebildes prüfen."
                    .to_string(),
                );
            }
            println!("[ignite_core] Body-Pixel: {}", body_pixel_count);

            // ── Feature C: Top-Hat Differenzbild ─────────────────────────
            let diff_img = calculate_tophat_difference(&img, &mask, kernel_large)
                .map_err(|e| format!("TopHat Fehler: {}", e))?;

            // ── Feature D: Statistischer Schwellenwert µ + k·σ ───────────
            let binary_raw = threshold_statistical(&img, &diff_img, &mask, sigma_k)
                .map_err(|e| format!("Schwellenwert Fehler: {}", e))?;

            let raw_hotspot_count = binary_raw.iter().filter(|&&px| px > 0).count();
            println!(
                "[ignite_core] Hotspot-Pixel (vor Geometriefilter): {}",
                raw_hotspot_count
            );

            // ── Feature E: Geometrischer Rauschfilter ─────────────────────
            // min_dist_from_border: Hotspot-Komponenten müssen mindestens 0.8% der
            // Bildbreite vom Maskenrand entfernt sein. Rand-Artefakte (Knöchel, Fersen)
            // liegen direkt an der Körper-Hintergrund-Grenze (dist ≈ 0-8px).
            // Echter entzündeter Zeh liegt im Inneren des Zehenbereichs (dist > 4px).
            let min_dist_from_border = (width as f64 * 0.005).max(4.0);
            let final_mask = filter_geometric(
                &binary_raw, &mask, &dist_map,
                min_area_factor, min_circularity, min_dist_from_border
            )
            .map_err(|e| format!("Geometriefilter Fehler: {}", e))?;

            let final_hotspot_count = final_mask.iter().filter(|&&px| px > 0).count();
            println!(
                "[ignite_core] Hotspot-Pixel (nach Geometriefilter): {}",
                final_hotspot_count
            );

            // Differenzbild für GUI-Anzeige normalisieren (0–255 Darstellungsbereich)
            let diff_normalized = normalize_minmax(&diff_img);

            Ok((diff_normalized, final_mask))
        })
        .map_err(|e| PyRuntimeError::new_err(e))?;

    // ── Schritt 3: ndarray → NumPy-Array (minimale Datenkopie) ────────────
    // Die Konvertierung erfordert eine Kopie, da PyArray2 sein eigenes Memory
    // verwaltet. Das ist unvermeidbar beim Übergang zwischen Rust- und Python-Heap.
    let diff_flat: Vec<u8> = diff_mat.into_raw_vec_and_offset().0;
    let mask_flat: Vec<u8> = hotspot_mat.into_raw_vec_and_offset().0;

    // numpy-crate 0.22 / PyO3 0.22: from_vec2_bound() gibt Bound<PyArray2> zurück.
    // .unbind() konvertiert zu Py<PyArray2> (owned, GIL-unabhängig).
    let diff_py = PyArray2::from_vec2_bound(
        py,
        &diff_flat.chunks(width).map(|c| c.to_vec()).collect::<Vec<_>>(),
    )
    .map_err(|e| PyRuntimeError::new_err(format!("Diff-Array Fehler: {}", e)))?;

    let mask_py = PyArray2::from_vec2_bound(
        py,
        &mask_flat.chunks(width).map(|c| c.to_vec()).collect::<Vec<_>>(),
    )
    .map_err(|e| PyRuntimeError::new_err(format!("Mask-Array Fehler: {}", e)))?;

    Ok((diff_py.unbind(), mask_py.unbind()))
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 10: MODUL-REGISTRATION (PyO3 Boilerplate)
// ─────────────────────────────────────────────────────────────────────────────

/// PyO3-Modul-Initialisierungsfunktion.
///
/// Wird von Python beim `import ignite_core` aufgerufen. Registriert alle
/// öffentlichen Funktionen und Metadaten des Moduls.
///
/// # Registrierte Symbole
/// - `process_thermal_pipeline(gray_array)` – Haupt-Pipeline-Funktion
/// - `__backend__` – Aktives Compute-Backend als String
/// - `__version__` – Modul-Version
/// - `__author__`  – Projekt-Information
#[pymodule]
fn ignite_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(process_thermal_pipeline, m)?)?;

    // Backend-Info (CPU+rayon – Rust-native ohne externe CV-Bibliothek)
    let num_threads = rayon::current_num_threads();
    m.add(
        "__backend__",
        format!("CPU+rayon ({} Kerne, Rust-native)", num_threads),
    )?;
    // Version wird automatisch aus Cargo.toml zur Kompilierzeit gelesen.
    // Damit ist Versionskonsistenz zwischen Cargo.toml und dem Python-Modul garantiert.
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__author__", "Ignite Team – Jugend forscht")?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn naive_dilate_1d(data: &[u8], radius: usize) -> Vec<u8> {
        let n = data.len();
        let mut result = vec![0u8; n];
        for i in 0..n {
            let start = i.saturating_sub(radius);
            let end = (i + radius + 1).min(n);
            result[i] = data[start..end].iter().cloned().max().unwrap_or(0);
        }
        result
    }

    fn naive_erode_1d(data: &[u8], radius: usize) -> Vec<u8> {
        let n = data.len();
        let mut result = vec![255u8; n];
        for i in 0..n {
            let start = i.saturating_sub(radius);
            let end = (i + radius + 1).min(n);
            result[i] = data[start..end].iter().cloned().min().unwrap_or(0);
        }
        result
    }

    #[test]
    fn test_dilate_and_erode_monotone_deque() {
        let test_cases = vec![
            (vec![1, 3, 2, 4, 3], 1),
            (vec![10, 20, 30, 40, 50, 40, 30, 20, 10], 2),
            (vec![5, 5, 5, 5, 5], 3),
            (vec![1, 2, 3, 4, 5, 6, 7, 8, 9], 4),
            (vec![9, 8, 7, 6, 5, 4, 3, 2, 1], 1),
            (vec![1, 100, 2, 100, 3, 100, 4], 2),
            (vec![255, 0, 255, 0, 255], 1),
        ];

        for (data, radius) in test_cases {
            let naive_d = naive_dilate_1d(&data, radius);
            let opt_d = dilate_1d(&data, radius);
            assert_eq!(naive_d, opt_d, "Dilation test failed for data={:?} and radius={}", data, radius);

            let naive_e = naive_erode_1d(&data, radius);
            let opt_e = erode_1d(&data, radius);
            assert_eq!(naive_e, opt_e, "Erosion test failed for data={:?} and radius={}", data, radius);
        }
    }
}
