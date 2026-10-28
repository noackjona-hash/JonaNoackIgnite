# -*- coding: utf-8 -*-
"""context.py — Datenstrukturen und Pipeline-Kontext für IGNITE.

Jugend forscht 2026 — Jona Noack
IGNITE Medical Imaging Suite

Enthält:
- PipelineConfig: Konfigurierbare Schwellenwerte und medizinische Parameter
- StepResult: Metadaten und Diagnose-Telemetrie einer einzelnen Stufe
- PipelineContext: Zentraler Zustandsspeicher für alle 42 Stufen
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import numpy as np


@dataclass
class PipelineConfig:
    """Klinische Konfigurationsparameter nach DIN EN ISO 13485 & IWGDF."""
    # Morphologie
    kernel_factor: float = 0.05        # Morphologischer Kernradius (5% der minimalen Bilddimension)
    margin_factor: float = 0.005       # Randabstand-Erosion (0.5% schützt distale Zehenkuppen)
    
    # Statistik & Outlier-Erkennung
    k_factor: float = 3.0              # Hampel-MAD Multiplikator (Standard k=3.0 für 99.7% Konfidenz)
    threshold_mode: str = "MAD"        # "MAD" (Median Absolute Deviation) oder "GAUSSIAN"
    min_temp_floor: float = 20.0       # Minimaler biologischer Temperaturboden in °C
    
    # Geometrische Filterung & Artefaktausschluss
    min_area_fraction: float = 0.0003  # Minimale Hotspot-Fläche (0.03% der Fußgewebefläche)
    min_circularity: float = 0.08      # Minimale Zirkularität (C = 4*pi*A / P^2) zum Ausschluss von Venen
    border_exclusion_px: int = 15      # Randabstand zum Sensorrand in Pixeln
    
    # Klinische Leitlinien
    armstrong_threshold_k: float = 2.2 # Armstrong-Kriterium: Delta_T >= 2.2 K = Ulkusprädiktor
    moderate_threshold_k: float = 1.2  # Frühe biomechanische Warnschwelle (1.2 K bis 2.1 K)
    enable_3d_correction: bool = True  # 3D-Winkelkorrektur zur Eliminierung von Randabkühlung


@dataclass
class StepResult:
    """Dokumentation und Metriken einer einzelnen Berechnungsstufe (1 bis 42)."""
    step_number: int                   # 1 bis 42
    phase_number: int                  # 1 bis 7
    phase_name: str                    # Name der klinischen Phase
    name: str                          # Kurztitel der Stufe
    description: str                   # Ausführliche medizinisch-technische Erklärung
    formula: str                       # Mathematische Formel (LaTeX)
    duration_ms: float                 # Ausführungszeit in Millisekunden
    metrics: Dict[str, Any]            # Gemessene Kennzahlen (Temperatur, Pixel, Schwellen)
    image_filename: str                # Dateiname des exportierten Bildes in exports/
    json_filename: str                 # Dateiname der JSON-Metadaten


@dataclass
class HotspotRegion:
    """Ein segmentierter und biophysikalisch charakterisierter Entzündungsherd."""
    region_id: int
    center_x: int
    center_y: int
    bbox: Tuple[int, int, int, int]    # (x, y, w, h)
    area_px: int
    circularity: float
    aspect_ratio: float
    t_max: float                       # Maximaltemperatur im Herd (°C)
    t_mean: float                      # Mittlere Temperatur (°C)
    edge_gradient: float               # Perifokaler Randgradient dT/dr
    halo_delta_t: float                # Temperaturdifferenz zum umgebenden Halo (K)
    laplace_divergence: float          # 2D-Laplace Divergenz
    contra_delta: float = 0.0          # Kontralaterale Temperaturdifferenz zum homologen Ort (K)
    is_vascular: bool = False          # Wurde durch Frangi als Gefäß identifiziert?
    classification: str = "BENIGN"     # "BENIGN", "MODERATE", "CRITICAL"
    clinical_note: str = ""


@dataclass
class PipelineContext:
    """Zentraler Zustand der Pipeline mit allen Zwischenergebnissen."""
    config: PipelineConfig = field(default_factory=PipelineConfig)
    
    # Phase I: Sensor & Radiometrie
    raw_bgr: Optional[np.ndarray] = None
    raw_gray: Optional[np.ndarray] = None
    temp_celsius: Optional[np.ndarray] = None
    bad_pixel_mask: Optional[np.ndarray] = None
    filtered_temp: Optional[np.ndarray] = None
    pitch_mm_per_px: float = 0.6
    
    # Phase II: Anatomische Gewebesegmentierung
    otsu_threshold: int = 0
    raw_body_mask: Optional[np.ndarray] = None
    cleaned_body_mask: Optional[np.ndarray] = None
    distance_field: Optional[np.ndarray] = None
    eroded_body_mask: Optional[np.ndarray] = None
    tissue_pixel_count: int = 0
    
    # Phase III: 3D-Modell & Winkelkompensation
    depth_map_3d: Optional[np.ndarray] = None
    normal_map_3d: Optional[np.ndarray] = None
    cosine_view_angle: Optional[np.ndarray] = None
    emissivity_map: Optional[np.ndarray] = None
    temp_3d_corrected: Optional[np.ndarray] = None
    
    # Phase IV: Morphologische Top-Hat Extraktion
    kernel_radius_px: int = 15
    structuring_element: Optional[np.ndarray] = None
    eroded_img: Optional[np.ndarray] = None
    opened_img: Optional[np.ndarray] = None
    tophat_diff: Optional[np.ndarray] = None
    backend_used: str = "CPU"
    
    # Phase V: Statistische Schwellwertbildung
    tissue_histogram: Optional[np.ndarray] = None
    tissue_median: float = 0.0
    tissue_mad: float = 0.0
    tissue_sigma: float = 0.0
    outlier_threshold_tau: float = 0.0
    outlier_mask: Optional[np.ndarray] = None
    
    # Phase VI: Geometrie & Gefäßdifferenzierung
    raw_hotspot_regions: List[HotspotRegion] = field(default_factory=list)
    hessian_l1: Optional[np.ndarray] = None
    hessian_l2: Optional[np.ndarray] = None
    frangi_vesselness: Optional[np.ndarray] = None
    filtered_hotspots: List[HotspotRegion] = field(default_factory=list)
    confirmed_pathology_hotspots: List[HotspotRegion] = field(default_factory=list)
    
    # Phase VII: Biophysik, Armstrong & Triage
    bilateral_split: Optional[Tuple[np.ndarray, np.ndarray]] = None
    delta_t_contralateral: float = 0.0
    overall_triage_level: str = "BENIGN"
    triage_headline: str = "Physiologische Normotemperatur"
    
    # Protokoll aller Stufen
    step_results: List[StepResult] = field(default_factory=list)
