# -*- coding: utf-8 -*-
"""gui/services/dynamic_perfusion_service.py – Dynamic Thermal Perfusion & Cold Stress Recovery Analysis.

Implements clinical cold-stress challenge & dynamic rewarming evaluation:
- Pennes-Newton Bioheat exponential reperfusion model:
  T(t) = T_inf - (T_inf - T_0) * exp(-k * t)
- Estimation of Perfusion Recovery Rate (k) and Half-Recovery Time (t_1/2)
- Clinical vascular risk classification (Physiological vs Diabetic Microangiopathy vs Severe Ischemia)
- Synthetic Cold Challenge frame-sequence generator for testing and demonstration
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np


class DynamicPerfusionService:
    """Service zur Modellierung und Quantifizierung thermischer Wiedererwärmungskinetiken."""

    @classmethod
    def fit_rewarming_curve(
        cls,
        time_seconds: np.ndarray,
        temperatures: np.ndarray,
        t_asymptote: Optional[float] = None
    ) -> Dict[str, Any]:
        """Fittet das exponentielle Wiedererwärmungsmodell an Zeitreihendaten an."""
        t_arr = np.asarray(time_seconds, dtype=np.float64)
        temp_arr = np.asarray(temperatures, dtype=np.float64)

        if len(t_arr) < 3 or len(temp_arr) != len(t_arr):
            raise ValueError("Mindestens 3 Datenpunkte für eine Wiedererwärmungskurve erforderlich.")

        t0 = float(temp_arr[0])
        t_max_observed = float(np.max(temp_arr))

        # Asymptote schätzen falls nicht vorgegeben
        if t_asymptote is None:
            t_inf = max(t_max_observed + 0.2, t0 + 0.5)
        else:
            t_inf = max(float(t_asymptote), t_max_observed + 0.05)

        # Robuste Optimierung via Grid-Search / Lineare Regression im transformierten Raum:
        # ln((T_inf - T(t)) / (T_inf - T_0)) = -k * t
        diff = t_inf - temp_arr
        diff = np.maximum(diff, 1e-4)  # Numerische Stabilität
        denom = max(t_inf - t0, 1e-4)

        y_trans = np.log(diff / denom)

        # Regressiere y = -k * t (ohne Offset oder mit kleinem Offset)
        # k = - (sum(t * y) / sum(t^2))
        t_nonzero = t_arr[t_arr > 0]
        y_nonzero = y_trans[t_arr > 0]

        if len(t_nonzero) > 0 and np.sum(t_nonzero**2) > 0:
            k = - float(np.sum(t_nonzero * y_nonzero) / np.sum(t_nonzero**2))
            k = max(1e-5, min(k, 0.5))  # Physikalische Grenzen für k in s^-1
        else:
            k = 0.01

        # Fitted curve
        fitted_temps = t_inf - (t_inf - t0) * np.exp(-k * t_arr)

        # Bestimmtheitsmaß R²
        ss_res = np.sum((temp_arr - fitted_temps)**2)
        ss_tot = np.sum((temp_arr - np.mean(temp_arr))**2)
        r_squared = 1.0 - (ss_res / (ss_tot + 1e-8))
        r_squared = max(0.0, min(1.0, float(r_squared)))

        # Halbwertszeit der Reperfusion (t_1/2 in s)
        half_recovery_time_s = math.log(2.0) / k if k > 0 else 999.0
        k_min = k * 60.0  # k in min^-1 für medizinische Interpretation

        # Klinische Klassifikation nach vaskulären Reperfusionsstandards
        # (z. B. Raynaud / Diabetische Mikroangiopathie Kriterien)
        if k_min >= 0.40:
            classification = "Physiologisch (Intakte Mikrozirkulation)"
            risk_level = "Normal"
            color_hex = "#16A34A"  # Grün
        elif k_min >= 0.20:
            classification = "Verzögert (Verdacht auf diabetische Mikroangiopathie)"
            risk_level = "Mäßig"
            color_hex = "#D97706"  # Bernstein
        else:
            classification = "Kritisch verlangsamt (Schwere pAVK / Neurovaskuläre Störung)"
            risk_level = "Hoch"
            color_hex = "#DC2626"  # Rot

        return {
            "t0_c": round(t0, 2),
            "t_inf_c": round(t_inf, 2),
            "k_rate_s": round(k, 5),
            "k_rate_min": round(k_min, 3),
            "half_time_s": round(half_recovery_time_s, 1),
            "r_squared": round(r_squared, 4),
            "classification": classification,
            "risk_level": risk_level,
            "color_hex": color_hex,
            "time_seconds": t_arr.tolist(),
            "measured_temps": temp_arr.tolist(),
            "fitted_temps": fitted_temps.tolist()
        }

    @classmethod
    def simulate_cold_stress_sequence(
        cls,
        baseline_img: np.ndarray,
        body_mask: Optional[np.ndarray] = None,
        num_frames: int = 10,
        total_time_s: float = 180.0,
        ischemic_center: Optional[Tuple[int, int]] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[float]]:
        """
        Erzeugt eine synthetische Kälteprovokations-Bildsequenz für Tests & Live-Demos.
        
        Rückgabe:
        - frame_sequence: np.ndarray der Form (num_frames, H, W) mit 8-Bit Werten
        - time_points: np.ndarray mit Zeitpunkten in Sekunden [0, t_1, ..., total_time_s]
        - mean_temps: Liste der mittleren Gewebetemperaturen über die Zeit
        """
        h, w = baseline_img.shape[:2]
        mask = body_mask if body_mask is not None else (baseline_img > 30).astype(np.uint8) * 255
        time_points = np.linspace(0.0, total_time_s, num_frames)

        # Baseline Ausgangszustand
        t_base = baseline_img.astype(np.float32)

        # Kältereiz zu Beginn (z. B. Abkühlung um 5-8°C)
        cold_drop = np.random.uniform(5.0, 8.0, size=(h, w)).astype(np.float32)
        cold_start = np.clip(t_base - (cold_drop * 6.0), 20.0, 255.0)

        # Falls Ischämie-Zentrum definiert, verlangsamt sich dort die Wiedererwärmung
        k_map = np.full((h, w), 0.025, dtype=np.float32)  # Normal ~1.5 min^-1
        if ischemic_center is not None:
            cy, cx = ischemic_center
            y_coords, x_coords = np.ogrid[:h, :w]
            dist = np.sqrt((x_coords - cx)**2 + (y_coords - cy)**2)
            ischemic_factor = np.exp(-(dist**2) / (2 * (max(h, w) * 0.15)**2))
            k_map = k_map * (1.0 - 0.75 * ischemic_factor)  # Deutlich verzögert

        frames = []
        mean_temps = []

        for t in time_points:
            # T(t) = T_base - (T_base - T_cold) * exp(-k * t)
            frame_t = t_base - (t_base - cold_start) * np.exp(-k_map * t)
            # Rauschen hinzufügen (±0.5 Graylevel)
            noise = np.random.normal(0, 0.4, (h, w)).astype(np.float32)
            frame_t = np.clip(frame_t + noise, 0, 255).astype(np.uint8)

            # Nur innerhalb der Gewebemaske
            frame_t = np.where(mask > 0, frame_t, 0).astype(np.uint8)
            frames.append(frame_t)

            tissue_px = frame_t[mask > 0]
            mean_c = 20.0 + (float(np.mean(tissue_px)) / 255.0) * 20.0 if len(tissue_px) > 0 else 20.0
            mean_temps.append(round(mean_c, 2))

        return np.array(frames, dtype=np.uint8), time_points, mean_temps
