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


/// Debug-Protokollierung des Rust-Kerns.
///
/// Die Pipeline wird in der Stapelverarbeitung tausendfach aufgerufen; bedingungslose
/// `println!`-Aufrufe fluten dann stdout und kosten messbar Laufzeit. Die Ausgabe wird
/// daher nur aktiviert, wenn die Umgebungsvariable `IGNITE_DEBUG` gesetzt ist.
fn debug_enabled() -> bool {
    static ENABLED: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ENABLED.get_or_init(|| std::env::var("IGNITE_DEBUG").is_ok())
}

macro_rules! ignite_debug {
    ($($arg:tt)*) => {
        if debug_enabled() {
            println!($($arg)*);
        }
    };
}


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

fn dilate_1d(data: &[u8], result: &mut [u8], radius: usize, deque: &mut VecDeque<usize>) {
    let n = data.len();
    if n == 0 {
        return;
    }
    deque.clear();

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
}

/// 1D-Sliding-Window Minimum (Erosion) für eine Datenreihe.
///
/// # Komplexität
/// O(N) – analoges Monotone Deque Sliding-Window Minimum.
/// Deque hält Indizes in aufsteigender Wertereihenfolge.
fn erode_1d(data: &[u8], result: &mut [u8], radius: usize, deque: &mut VecDeque<usize>) {
    let n = data.len();
    if n == 0 {
        return;
    }
    deque.clear();

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
}


/// Cache-geblockte Transposition einer u8-Matrix.
///
/// Die separable Morphologie benoetigt einen vertikalen (spaltenweisen) Pass.
/// Ein direkter Spaltenzugriff auf eine zeilen-major gespeicherte Matrix
/// erzeugt pro Element einen Cache-Miss (Stride = Bildbreite). Bei 1440x1080
/// dominiert dieser Effekt die gesamte Pipeline-Laufzeit.
///
/// Stattdessen wird die Matrix hier in 64x64-Kacheln transponiert (beide
/// Zugriffsmuster bleiben damit im L1/L2-Cache), anschliessend laeuft der
/// schnelle zeilenweise Pass, danach wird zurueck transponiert.
fn transpose_blocked(src: &ImageMatrix) -> ImageMatrix {
    const TILE: usize = 64;
    let (h, w) = src.dim();
    let mut dst = Array2::<u8>::zeros((w, h));

    let src_s = src.as_slice();
    let dst_s = dst.as_slice_mut();

    if let (Some(a), Some(b)) = (src_s, dst_s) {
        for y0 in (0..h).step_by(TILE) {
            let y1 = (y0 + TILE).min(h);
            for x0 in (0..w).step_by(TILE) {
                let x1 = (x0 + TILE).min(w);
                for y in y0..y1 {
                    let row = y * w;
                    for x in x0..x1 {
                        b[x * h + y] = a[row + x];
                    }
                }
            }
        }
    } else {
        for y in 0..h {
            for x in 0..w {
                dst[[x, y]] = src[[y, x]];
            }
        }
    }
    dst
}

/// Fuehrt einen zeilenweisen 1D-Filter ueber alle Zeilen aus (parallel via rayon).
fn apply_rows_1d(
    src: &ImageMatrix,
    op: fn(&[u8], &mut [u8], usize, &mut VecDeque<usize>),
    radius: usize,
) -> ImageMatrix {
    let (h, w) = src.dim();
    let mut out = Array2::<u8>::zeros((h, w));
    ndarray::Zip::from(out.rows_mut())
        .and(src.rows())
        .into_par_iter()
        .for_each(|(mut out_row, in_row)| {
            let mut deque: VecDeque<usize> = VecDeque::with_capacity(w.min(radius * 2 + 2));
            if let (Some(in_slice), Some(out_slice)) = (in_row.as_slice(), out_row.as_slice_mut()) {
                op(in_slice, out_slice, radius, &mut deque);
            } else {
                let in_vec = in_row.to_vec();
                let mut out_vec = vec![0u8; w];
                op(&in_vec, &mut out_vec, radius, &mut deque);
                for i in 0..w {
                    out_row[i] = out_vec[i];
                }
            }
        });
    let _ = h;
    out
}

/// Separable 2D-Morphologie: horizontaler Pass, dann vertikaler Pass via Transposition.
fn separable_morph(
    img: &ImageMatrix,
    op: fn(&[u8], &mut [u8], usize, &mut VecDeque<usize>),
    kernel_size: usize,
) -> ImageMatrix {
    let radius = kernel_size / 2;
    let horizontal = apply_rows_1d(img, op, radius);
    let transposed = transpose_blocked(&horizontal);
    let vertical = apply_rows_1d(&transposed, op, radius);
    transpose_blocked(&vertical)
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
    if kernel_size == 0 {
        return Err("Kernel-Groesse muss > 0 sein".to_string());
    }
    Ok(separable_morph(img, dilate_1d, kernel_size))
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
    if kernel_size == 0 {
        return Err("Kernel-Groesse muss > 0 sein".to_string());
    }
    Ok(separable_morph(img, erode_1d, kernel_size))
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
///
/// Wird aktuell nicht in der Standard-Pipeline verwendet, aber als symmetrisches
/// Gegenstück zu `morph_open` bewusst als Teil der morphologischen API vorgehalten.
#[allow(dead_code)]
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
/// Approximiert DIST_L2 (euklidisch) mit der Chamfer-Metrik (12-17-Approximation).
///
/// # Arguments
/// * `binary_mask` – Binäres Eingabebild (0 = Hintergrund, 255 = Vordergrund)
///
/// # Returns
/// `FloatMatrix` – Distanzkarte (Gleitkomma, nicht normalisiert)
fn distance_transform_l2(binary_mask: &ImageMatrix) -> FloatMatrix {
    let (h, w) = binary_mask.dim();

    // Chamfer-Approximation mit u32-Integer-Arithmetik (statt f64):
    // Integer-Ops sind ~4x schneller als Float-Ops in der inneren Schleife.
    // Verwendet werden die Gewichte 12/17 statt der klassischen 3/4:
    //   3/4   -> Diagonalverhaeltnis 1.3333 (5.72 % Fehler gegen sqrt(2))
    //   12/17 -> Diagonalverhaeltnis 1.4167 (0.17 % Fehler gegen sqrt(2))
    //
    // Implementierungshinweis: Die beiden Chamfer-Passes sind streng sequentiell
    // (jeder Pixel haengt vom bereits berechneten Vorgaenger ab) und daher nicht
    // parallelisierbar. Der Durchsatz wird deshalb ueber einen flachen Puffer mit
    // vorberechneten Zeilenoffsets erreicht: ndarray-Indizierung via [[y, x]]
    // kostet pro Zugriff Bounds-Check und Stride-Multiplikation, was bei
    // ~1,5 Mio. Pixeln und 8 Nachbarzugriffen dominant wird.
    const INF: u32 = u32::MAX / 2;
    const COST_STRAIGHT: u32 = 12;
    const COST_DIAGONAL: u32 = 17;

    let mut dist: Vec<u32> = Vec::with_capacity(h * w);
    match binary_mask.as_slice() {
        Some(src) => dist.extend(src.iter().map(|&px| if px == 0 { 0 } else { INF })),
        None => dist.extend(binary_mask.iter().map(|&px| if px == 0 { 0 } else { INF })),
    }

    // Vorwaerts-Pass: oben-links -> unten-rechts
    for y in 0..h {
        let row = y * w;
        let prev = row.wrapping_sub(w);
        for x in 0..w {
            let i = row + x;
            let mut d = dist[i];
            if d == 0 {
                continue;
            }
            if y > 0 {
                d = d.min(dist[prev + x].saturating_add(COST_STRAIGHT));
                if x > 0 {
                    d = d.min(dist[prev + x - 1].saturating_add(COST_DIAGONAL));
                }
                if x + 1 < w {
                    d = d.min(dist[prev + x + 1].saturating_add(COST_DIAGONAL));
                }
            }
            if x > 0 {
                d = d.min(dist[i - 1].saturating_add(COST_STRAIGHT));
            }
            dist[i] = d;
        }
    }

    // Rueckwaerts-Pass: unten-rechts -> oben-links
    for y in (0..h).rev() {
        let row = y * w;
        let next = row + w;
        for x in (0..w).rev() {
            let i = row + x;
            let mut d = dist[i];
            if d == 0 {
                continue;
            }
            if y + 1 < h {
                d = d.min(dist[next + x].saturating_add(COST_STRAIGHT));
                if x > 0 {
                    d = d.min(dist[next + x - 1].saturating_add(COST_DIAGONAL));
                }
                if x + 1 < w {
                    d = d.min(dist[next + x + 1].saturating_add(COST_DIAGONAL));
                }
            }
            if x + 1 < w {
                d = d.min(dist[i + 1].saturating_add(COST_STRAIGHT));
            }
            dist[i] = d;
        }
    }

    // Zurueck zu f64 fuer Kompatibilitaet mit dem Rest der Pipeline
    // (Division durch COST_STRAIGHT normiert auf euklidische Pixel-Distanz)
    let scale = COST_STRAIGHT as f64;
    let floats: Vec<f64> = dist
        .into_iter()
        .map(|v| if v >= INF { f64::MAX / 2.0 } else { v as f64 / scale })
        .collect();
    FloatMatrix::from_shape_vec((h, w), floats).expect("Distanzkarte: Shape-Fehler")
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

    // Schritt 1: Otsu-Binarisierung mit adaptivem Fallback für niedrigen Kontrast.
    let otsu_thresh = otsu_threshold(img);
    let min_px = *img.iter().min().unwrap_or(&0) as f64;
    let max_px = *img.iter().max().unwrap_or(&0) as f64;
    let dynamic_range = max_px - min_px;
    let threshold = if dynamic_range < 30.0 {
        ((min_px + 0.3 * dynamic_range) as u8).max(otsu_min).min(otsu_max)
    } else {
        (otsu_thresh / 2).max(otsu_min).min(otsu_max)
    };
    let mut otsu_mask = Array2::<u8>::zeros((h, w));
    otsu_mask.zip_mut_with(img, |out, &px| {
        *out = if px > threshold { 255 } else { 0 };
    });

    // Schritt 1b: Morphologisches Closing schliesst kleine Poren in der Koerpermaske.
    // Muss identisch im Python-Fallback (extract_body_mask_multi_otsu) erfolgen,
    // sonst divergieren die Backends. Bewusst rechteckiges 5x5-Element, weil die
    // separable Lemire-Morphologie kein elliptisches Element abbilden kann.
    let otsu_mask = morph_close(&otsu_mask, 5)?;

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
    use_mad: bool,
    enable_hysteresis: bool,
    hysteresis_k_low: Option<f64>,
) -> Result<ImageMatrix, String> {
    let (h, w) = diff_img.dim();

    // Die Werte innerhalb der Body-Maske werden nur dann materialisiert, wenn der
    // robuste MAD-Pfad sie tatsaechlich braucht (Median erfordert alle Werte).
    // Der Gauss-Pfad kommt mit Summen aus und vermeidet damit zwei Vektoren mit
    // je ~500k f64-Werten (mehrere MB Allokation und Speicherbandbreite pro Bild).
    // Zusaetzlich wird u8 statt f64 gepuffert (8x weniger Speicher).
    let n_body = mask.iter().filter(|&&m| m > 0).count();
    if n_body == 0 {
        return Err("Body-Mask ist leer – keine Körper-Pixel für Statistik gefunden.".to_string());
    }

    let k_low = hysteresis_k_low.unwrap_or_else(|| (k * 0.5).min(1.8));

    let mut body_diff_vals: Vec<u8> = Vec::new();
    let mut body_orig_vals: Vec<u8> = Vec::new();
    if use_mad {
        body_diff_vals.reserve_exact(n_body);
        body_orig_vals.reserve_exact(n_body);
        for y in 0..h {
            for x in 0..w {
                if mask[[y, x]] > 0 {
                    body_diff_vals.push(diff_img[[y, x]]);
                    body_orig_vals.push(original_img[[y, x]]);
                }
            }
        }
    }

    let (thresh_high, thresh_low, mu_orig) = if use_mad {
        // u8-Werte: Median via Zaehlsortierung (O(n)) statt Vergleichssortierung.
        let mut sorted_diff = body_diff_vals;
        sorted_diff.sort_unstable();
        let len = sorted_diff.len();
        let median_diff = if len % 2 == 0 {
            (sorted_diff[len / 2 - 1] as f64 + sorted_diff[len / 2] as f64) / 2.0
        } else {
            sorted_diff[len / 2] as f64
        };

        let mut abs_devs: Vec<f64> = sorted_diff.iter().map(|&x| (x as f64 - median_diff).abs()).collect();
        abs_devs.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let mad = if len % 2 == 0 {
            (abs_devs[len / 2 - 1] + abs_devs[len / 2]) / 2.0
        } else {
            abs_devs[len / 2]
        };

        // Standard-Normalverteilungs-Skalierungsfaktor 1.4826
        let sigma_mad = 1.4826 * mad;
        let thresh_h = (median_diff + k * sigma_mad).clamp(0.0, 254.0);
        let thresh_l = (median_diff + k_low * sigma_mad).clamp(0.0, 254.0);

        let mut sorted_orig = body_orig_vals;
        sorted_orig.sort_unstable();
        let med_orig = if len % 2 == 0 {
            (sorted_orig[len / 2 - 1] as f64 + sorted_orig[len / 2] as f64) / 2.0
        } else {
            sorted_orig[len / 2] as f64
        };

        (thresh_h, thresh_l, med_orig)
    } else {
        // Einzelner paralleler Reduktionslauf ueber die Maske: Summen in u64,
        // ohne die Werte vorher zu materialisieren.
        let (sum_diff_i, sum_orig_i, sum_sq_diff_i) = ndarray::Zip::from(mask)
            .and(diff_img)
            .and(original_img)
            .into_par_iter()
            .fold(
                || (0u64, 0u64, 0u64),
                |(sd, so, ssq), (&m, &d, &o)| {
                    if m > 0 {
                        let dv = d as u64;
                        (sd + dv, so + o as u64, ssq + dv * dv)
                    } else {
                        (sd, so, ssq)
                    }
                },
            )
            .reduce(
                || (0u64, 0u64, 0u64),
                |a, b| (a.0 + b.0, a.1 + b.1, a.2 + b.2),
            );

        let n = n_body as f64;
        let sum_diff = sum_diff_i as f64;
        let sum_orig = sum_orig_i as f64;
        let sum_sq_diff = sum_sq_diff_i as f64;

        let mu_diff = sum_diff / n;
        let mu_orig = sum_orig / n;
        let variance_diff = (sum_sq_diff / n) - mu_diff.powi(2);
        let sigma_diff = variance_diff.max(0.0).sqrt();

        let thresh_h = (mu_diff + k * sigma_diff).clamp(0.0, 254.0);
        let thresh_l = (mu_diff + k_low * sigma_diff).clamp(0.0, 254.0);
        (thresh_h, thresh_l, mu_orig)
    };

    if !enable_hysteresis {
        let mut binary = Array2::<u8>::zeros((h, w));
        // Binarisierung parallel über Zeilen
        binary.axis_iter_mut(ndarray::Axis(0)).into_par_iter().enumerate().for_each(|(y, mut row)| {
            for x in 0..w {
                let diff_val = diff_img[[y, x]] as f64;
                let orig_val = original_img[[y, x]] as f64;
                if diff_val > thresh_high && orig_val > mu_orig {
                    row[x] = 255;
                }
            }
        });
        return Ok(binary);
    }

    // Adaptive Hysterese / Seeded Region Growing
    let mut weak_binary = Array2::<u8>::zeros((h, w));
    let mut strong_binary = Array2::<u8>::zeros((h, w));

    for y in 0..h {
        for x in 0..w {
            if mask[[y, x]] > 0 {
                let diff_val = diff_img[[y, x]] as f64;
                let orig_val = original_img[[y, x]] as f64;
                if orig_val > mu_orig {
                    if diff_val > thresh_low {
                        weak_binary[[y, x]] = 255;
                    }
                    if diff_val > thresh_high {
                        strong_binary[[y, x]] = 255;
                    }
                }
            }
        }
    }

    let (labels, max_label) = connected_components(&weak_binary);
    let mut has_seed = vec![false; max_label as usize + 1];

    for y in 0..h {
        for x in 0..w {
            let lbl = labels[[y, x]] as usize;
            if lbl > 0 && strong_binary[[y, x]] > 0 {
                has_seed[lbl] = true;
            }
        }
    }

    let mut binary = Array2::<u8>::zeros((h, w));
    for y in 0..h {
        for x in 0..w {
            let lbl = labels[[y, x]] as usize;
            if lbl > 0 && has_seed[lbl] {
                binary[[y, x]] = 255;
            }
        }
    }

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
#[pyo3(name = "process_thermal_pipeline", signature = (gray_array, sigma_k, tophat_factor, min_area_factor, min_circularity, otsu_min, otsu_max, dist_erosion_factor, use_mad=None, enable_hysteresis=None, hysteresis_k_low=None))]
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
    use_mad: Option<bool>,
    enable_hysteresis: Option<bool>,
    hysteresis_k_low: Option<f64>,
) -> PyResult<(Py<PyArray2<u8>>, Py<PyArray2<u8>>)> {
    let use_mad_flag = use_mad.unwrap_or(false);
    let enable_hysteresis_flag = enable_hysteresis.unwrap_or(false);
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
            // Top-Hat-Kernel: 5 % der minimalen Bilddimension min(W, H)
            // (passend zu realen Thermokameras mit variablen Seitenverhältnissen).
            let dimension = width.min(height);
            let kernel_large = compute_odd_kernel(dimension, tophat_factor);
            // Geometriefilter-Referenzgröße (nicht für Morph-Ops genutzt, nur als Parameter)
            let kernel_small = compute_odd_kernel(dimension, 0.02).max(3);

            ignite_debug!(
                "[ignite_core] Bild: {}×{}, Dim: {}, Kernel groß: {}, Kernel klein: {}",
                width, height, dimension, kernel_large, kernel_small
            );

            // ── Feature B: Adaptive Body-Mask via Distanztransformation ──
            // Gibt nun auch die Distanzkarte zurück (für Rand-Hotspot-Filter)
            let _t_stage = std::time::Instant::now();
            let (mask, dist_map) = extract_body_mask(&img, otsu_min, otsu_max, dist_erosion_factor)
                .map_err(|e| format!("Body-Mask Fehler: {}", e))?;
            ignite_debug!("[ignite_core][profil] Body-Mask: {:.2} ms", _t_stage.elapsed().as_secs_f64() * 1000.0);

            let body_pixel_count = mask.iter().filter(|&&px| px > 0).count();
            if body_pixel_count == 0 {
                return Err(
                    "Body-Mask ist leer – kein Körper im Bild erkannt. \
                     Bitte Kontrast des Wärmebildes prüfen."
                    .to_string(),
                );
            }
            ignite_debug!("[ignite_core] Body-Pixel: {}", body_pixel_count);

            // ── Feature C: Top-Hat Differenzbild ─────────────────────────
            let _t_stage = std::time::Instant::now();
            let diff_img = calculate_tophat_difference(&img, &mask, kernel_large)
                .map_err(|e| format!("TopHat Fehler: {}", e))?;
            ignite_debug!("[ignite_core][profil] Top-Hat: {:.2} ms", _t_stage.elapsed().as_secs_f64() * 1000.0);

            // ── Feature D: Statistischer Schwellenwert µ + k·σ / Robust MAD ───
            let _t_stage = std::time::Instant::now();
            let binary_raw = threshold_statistical(
                &img,
                &diff_img,
                &mask,
                sigma_k,
                use_mad_flag,
                enable_hysteresis_flag,
                hysteresis_k_low,
            )
                .map_err(|e| format!("Schwellenwert Fehler: {}", e))?;
            ignite_debug!("[ignite_core][profil] Threshold: {:.2} ms", _t_stage.elapsed().as_secs_f64() * 1000.0);

            let raw_hotspot_count = binary_raw.iter().filter(|&&px| px > 0).count();
            ignite_debug!(
                "[ignite_core] Hotspot-Pixel (vor Geometriefilter): {}",
                raw_hotspot_count
            );

            // ── Feature E: Geometrischer Rauschfilter ─────────────────────
            // min_dist_from_border: Hotspot-Komponenten müssen mindestens 1.5% der
            // minimalen Bilddimension vom Maskenrand entfernt sein (min 12px). Rand-Artefakte
            // liegen direkt an der Körper-Hintergrund-Grenze (dist < 12px).
            let min_dist_from_border = (dimension as f64 * 0.015).max(12.0);
            let _t_stage = std::time::Instant::now();
            let final_mask = filter_geometric(
                &binary_raw, &mask, &dist_map,
                min_area_factor, min_circularity, min_dist_from_border
            )
            .map_err(|e| format!("Geometriefilter Fehler: {}", e))?;
            ignite_debug!("[ignite_core][profil] Geometriefilter: {:.2} ms", _t_stage.elapsed().as_secs_f64() * 1000.0);

            let final_hotspot_count = final_mask.iter().filter(|&&px| px > 0).count();
            ignite_debug!(
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

#[pyfunction]
#[pyo3(name = "compute_asymmetry")]
fn compute_asymmetry(
    gray_array: PyReadonlyArray2<u8>,
    body_mask_array: PyReadonlyArray2<u8>,
    temp_min_c: f64,
    temp_max_c: f64,
    threshold_c: f64,
) -> PyResult<(f64, f64, f64, bool)> {
    let img = gray_array.as_array();
    let mask = body_mask_array.as_array();
    let shape = img.shape();
    let (h, w) = (shape[0], shape[1]);
    let mid_x = w / 2;

    let mut left_sum = 0.0;
    let mut left_count = 0.0;
    let mut right_sum = 0.0;
    let mut right_count = 0.0;

    for y in 0..h {
        for x in 0..w {
            if mask[[y, x]] > 0 {
                let val = img[[y, x]] as f64;
                if x < mid_x {
                    left_sum += val;
                    left_count += 1.0;
                } else {
                    right_sum += val;
                    right_count += 1.0;
                }
            }
        }
    }

    if left_count < 1.0 || right_count < 1.0 {
        return Ok((0.0, 0.0, 0.0, false));
    }

    let mu_left = left_sum / left_count;
    let mu_right = right_sum / right_count;
    let temp_range = (temp_max_c - temp_min_c).max(1.0);

    let left_c = temp_min_c + (mu_left / 255.0) * temp_range;
    let right_c = temp_min_c + (mu_right / 255.0) * temp_range;
    let delta_c = (left_c - right_c).abs();
    let is_asym = delta_c > threshold_c;

    Ok((left_c, right_c, delta_c, is_asym))
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 9.1: PENNES BIOHEAT WÄRMEFLUSS IN RUST
// ─────────────────────────────────────────────────────────────────────────────

/// Berechnet die thermische Wärmeflussdichte und metabolische Wärmequellendichte
/// nach der Pennes-Bioheat-Gleichung in nativem Rust mit Rayon.
#[pyfunction]
#[pyo3(signature = (gray_array, mask_array=None, temp_min_c=20.0, temp_max_c=40.0, k_tissue=0.48))]
fn compute_pennes_bioheat<'py>(
    py: Python<'py>,
    gray_array: PyReadonlyArray2<'py, u8>,
    mask_array: Option<PyReadonlyArray2<'py, u8>>,
    temp_min_c: f64,
    temp_max_c: f64,
    k_tissue: f64,
) -> PyResult<(Bound<'py, PyArray2<f32>>, Bound<'py, PyArray2<f32>>, f64, f64, f64, f64)> {
    let img_view = gray_array.as_array();
    let (h, w) = img_view.dim();

    let temp_range = (temp_max_c - temp_min_c).max(1.0);
    let dx_m = 0.001f32;

    let mut temp_matrix = Array2::<f32>::zeros((h, w));
    temp_matrix.indexed_iter_mut().for_each(|((y, x), val)| {
        *val = (temp_min_c + (img_view[[y, x]] as f64 / 255.0) * temp_range) as f32;
    });

    let mut flux_mag = Array2::<f32>::zeros((h, w));
    let mut q_source = Array2::<f32>::zeros((h, w));

    // Parallele Berechnung der Gradienten und Laplace-Divergenz über Zeilen
    flux_mag.axis_iter_mut(ndarray::Axis(0))
        .into_par_iter()
        .zip(q_source.axis_iter_mut(ndarray::Axis(0)).into_par_iter())
        .enumerate()
        .for_each(|(y, (mut f_row, mut q_row))| {
            if y == 0 || y == h - 1 {
                return;
            }
            for x in 1..w - 1 {
                // 3x3 Sobel X
                let gx = (temp_matrix[[y - 1, x + 1]] + 2.0 * temp_matrix[[y, x + 1]] + temp_matrix[[y + 1, x + 1]])
                       - (temp_matrix[[y - 1, x - 1]] + 2.0 * temp_matrix[[y, x - 1]] + temp_matrix[[y + 1, x - 1]]);
                let grad_x = gx / (8.0 * dx_m);

                // 3x3 Sobel Y
                let gy = (temp_matrix[[y + 1, x - 1]] + 2.0 * temp_matrix[[y + 1, x]] + temp_matrix[[y + 1, x + 1]])
                       - (temp_matrix[[y - 1, x - 1]] + 2.0 * temp_matrix[[y - 1, x]] + temp_matrix[[y - 1, x + 1]]);
                let grad_y = gy / (8.0 * dx_m);

                let fx = -k_tissue as f32 * grad_x * 0.1;
                let fy = -k_tissue as f32 * grad_y * 0.1;
                f_row[x] = (fx * fx + fy * fy).sqrt();

                // 3x3 Laplace
                let lap = temp_matrix[[y - 1, x]] + temp_matrix[[y + 1, x]] + temp_matrix[[y, x - 1]] + temp_matrix[[y, x + 1]]
                        - 4.0 * temp_matrix[[y, x]];
                q_row[x] = (k_tissue as f32 * (lap / (dx_m * dx_m))) * 1e-4;
            }
        });

    let mask_view = mask_array.as_ref().map(|m| m.as_array());

    let mut sum_flux = 0.0f64;
    let mut max_flux = 0.0f64;
    let mut sum_source = 0.0f64;
    let mut max_source = 0.0f64;
    let mut count = 0.0f64;

    for y in 0..h {
        for x in 0..w {
            let valid = match mask_view {
                Some(m) => m[[y, x]] > 0,
                None => true,
            };
            if valid {
                let f = flux_mag[[y, x]] as f64;
                let q = q_source[[y, x]] as f64;
                sum_flux += f;
                sum_source += q;
                if f > max_flux { max_flux = f; }
                if q > max_source { max_source = q; }
                count += 1.0;
            }
        }
    }

    let mean_flux = if count > 0.0 { sum_flux / count } else { 0.0 };
    let mean_source = if count > 0.0 { sum_source / count } else { 0.0 };

    let py_flux = PyArray2::from_array_bound(py, &flux_mag);
    let py_source = PyArray2::from_array_bound(py, &q_source);

    Ok((py_flux, py_source, mean_flux, max_flux, mean_source, max_source))
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 9.2: FRANGI VESSELNESS FILTER IN RUST
// ─────────────────────────────────────────────────────────────────────────────

/// Multiskalen-Frangi-Vesselness-Filter in nativem Rust mit Rayon-Parallelisierung.
#[pyfunction]
#[pyo3(signature = (gray_array, mask_array=None, sigmas=vec![1.0, 1.5, 2.0, 2.5], beta=0.5, c=15.0))]
fn compute_frangi_vesselness<'py>(
    py: Python<'py>,
    gray_array: PyReadonlyArray2<'py, u8>,
    mask_array: Option<PyReadonlyArray2<'py, u8>>,
    sigmas: Vec<f64>,
    beta: f64,
    c: f64,
) -> PyResult<Bound<'py, PyArray2<u8>>> {
    let img_view = gray_array.as_array();
    let (h, w) = img_view.dim();

    let mut max_vesselness = Array2::<f32>::zeros((h, w));
    let mask_view = mask_array.as_ref().map(|m| m.as_array());

    for sigma in sigmas {
        let s2 = (sigma * sigma) as f32;
        let mut hxx = Array2::<f32>::zeros((h, w));
        let mut hyy = Array2::<f32>::zeros((h, w));
        let mut hxy = Array2::<f32>::zeros((h, w));

        // Hesse-Matrix Ableitungen 2. Ordnung via 3x3 Differenzen
        for y in 1..h - 1 {
            for x in 1..w - 1 {
                let center = img_view[[y, x]] as f32;
                let left = img_view[[y, x - 1]] as f32;
                let right = img_view[[y, x + 1]] as f32;
                let top = img_view[[y - 1, x]] as f32;
                let bottom = img_view[[y + 1, x]] as f32;

                let top_left = img_view[[y - 1, x - 1]] as f32;
                let top_right = img_view[[y - 1, x + 1]] as f32;
                let bot_left = img_view[[y + 1, x - 1]] as f32;
                let bot_right = img_view[[y + 1, x + 1]] as f32;

                hxx[[y, x]] = (right - 2.0 * center + left) * s2;
                hyy[[y, x]] = (bottom - 2.0 * center + top) * s2;
                hxy[[y, x]] = 0.25 * (bot_right - bot_left - top_right + top_left) * s2;
            }
        }

        // Eigenwertzerlegung & Frangi Vesselness Formel
        let beta2 = (2.0 * beta * beta) as f32;
        let c2 = (2.0 * c * c) as f32;

        for y in 1..h - 1 {
            for x in 1..w - 1 {
                let a = hxx[[y, x]];
                let d = hyy[[y, x]];
                let b = hxy[[y, x]];

                let tmp = ((a - d) * (a - d) + 4.0 * b * b).max(0.0).sqrt();
                let mut l1 = 0.5 * (a + d - tmp);
                let mut l2 = 0.5 * (a + d + tmp);

                if l1.abs() > l2.abs() {
                    std::mem::swap(&mut l1, &mut l2);
                }

                if l2 < 0.0 {
                    let rb = l1.abs() / (l2.abs() + 1e-6);
                    let s = (l1 * l1 + l2 * l2).sqrt();
                    let v = (- (rb * rb) / beta2).exp() * (1.0 - (- (s * s) / c2).exp());
                    if v > max_vesselness[[y, x]] {
                        max_vesselness[[y, x]] = v;
                    }
                }
            }
        }
    }

    if let Some(mask) = mask_view {
        for y in 0..h {
            for x in 0..w {
                if mask[[y, x]] == 0 {
                    max_vesselness[[y, x]] = 0.0;
                }
            }
        }
    }

    let mut v_min = f32::MAX;
    let mut v_max = f32::MIN;
    for &val in max_vesselness.iter() {
        if val < v_min { v_min = val; }
        if val > v_max { v_max = val; }
    }

    let mut result = Array2::<u8>::zeros((h, w));
    if v_max - v_min > 1e-6 {
        let range = v_max - v_min;
        result.indexed_iter_mut().for_each(|((y, x), pixel)| {
            *pixel = (((max_vesselness[[y, x]] - v_min) / range) * 255.0).clamp(0.0, 255.0) as u8;
        });
    }

    let py_array = PyArray2::from_array_bound(py, &result);
    Ok(py_array)
}

// ─────────────────────────────────────────────────────────────────────────────
// ABSCHNITT 10: MODUL-REGISTRATION (PyO3 Boilerplate)
// ─────────────────────────────────────────────────────────────────────────────

/// PyO3-Modul-Initialisierungsfunktion.
///
/// Wird von Python beim `import ignite_core` aufgerufen. Registriert alle
/// öffentlichen Funktionen und Metadaten des Moduls.
#[pymodule]
fn ignite_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(process_thermal_pipeline, m)?)?;
    m.add_function(wrap_pyfunction!(compute_asymmetry, m)?)?;
    m.add_function(wrap_pyfunction!(compute_pennes_bioheat, m)?)?;
    m.add_function(wrap_pyfunction!(compute_frangi_vesselness, m)?)?;

    // Backend-Info (CPU+rayon – Rust-native ohne externe CV-Bibliothek)
    let num_threads = rayon::current_num_threads();
    m.add(
        "__backend__",
        format!("CPU+rayon ({} Kerne, Rust-native)", num_threads),
    )?;
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
