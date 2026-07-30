"""
benchmark_annotator.py – Ground-Truth-Annotierungstool für IGNITE (Vollbild).

Tastenkombinationen:
  LMB / Drag              – Entzündung einzeichnen
  RMB / Drag              – Radierer
  Strg + Scroll           – Zoom
  + / -  oder KP_+/KP_-  – Zoom rein/raus
  0                       – Ansicht auf Bild anpassen (Fit)
  Mitteltaste + Drag      – Bild verschieben (Pan)
  Leertaste + LMB-Drag    – Bild verschieben (Pan, Alternative)
  Pfeiltasten             – Bild verschieben (langsam)
  Scroll (ohne Strg)      – Pinselgröße
  [ / ]                   – Pinselgröße kleiner/größer
  Strg + Z                – Rückgängig (Undo)
  Enter / N               – Nächstes Bild speichern & weiter
  S                       – Bild überspringen
  C / Entf                – Annotation löschen
  F11                     – Vollbild umschalten
  Escape                  – Vollbild beenden
"""

import os
import sys
import json
import math
import datetime
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import cv2

import image_processing
import dataset_evaluator

# ── Pfade ─────────────────────────────────────────────────────────────────────
TEST_DATA_DIR = "test-data"
OUTPUT_DIR    = "ignite_steps_output"
GT_DIR        = os.path.join(TEST_DATA_DIR, "ground_truth")
RESULTS_FILE  = os.path.join(OUTPUT_DIR, "benchmark_real_annotated.json")

# ── Konstanten ────────────────────────────────────────────────────────────────
BRUSH_DEF, BRUSH_MIN, BRUSH_MAX = 18, 3, 120
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP   = 0.05, 16.0, 1.25
MAX_UNDO                         = 25
BG                               = (17, 17, 27)


def sorted_images(folder: str) -> list[str]:
    exts = {".jpeg", ".jpg", ".png"}
    return sorted(f for f in os.listdir(folder)
                  if os.path.splitext(f)[1].lower() in exts)


class AnnotatorApp:
    # ── Init ──────────────────────────────────────────────────────────────────
    def __init__(self, root: tk.Tk, image_files: list[str]):
        self.root = root
        self.root.title("IGNITE – Annotierungstool")
        self.root.configure(bg="#1e1e2e")
        self.root.attributes("-fullscreen", True)

        self.image_files = image_files
        self.index       = 0
        self.brush_size  = BRUSH_DEF
        self.zoom        = 1.0
        self.pan_x       = 0.0   # viewport-Mitte in Bildkoordinaten
        self.pan_y       = 0.0

        self._drawing       = False
        self._erasing       = False
        self._panning       = False   # Mitteltaste
        self._space_down    = False
        self._space_pan     = False   # LMB-Pan via Leertaste
        self._pan_last      = None
        self._mouse_pos     = (-1, -1)

        self._undo: list[Image.Image]        = []
        self.annotations: dict[str, np.ndarray] = {}
        self.skipped: list[str]                  = []
        self._tk_img                             = None  # GC-Guard

        # Bilddaten (werden in _load_current_image gesetzt)
        self.base_pil:  Image.Image             = None
        self.draw_mask: Image.Image             = None
        self.draw_obj:  ImageDraw.ImageDraw     = None
        self.disp_w = self.disp_h = 1

        self._build_ui()
        self._bind_keys()
        self.root.after(80, self._load_current_image)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg="#181825")
        hdr.pack(fill=tk.X)

        self.lbl_title     = tk.Label(hdr, font=("Segoe UI", 12, "bold"), fg="#cdd6f4", bg="#181825", text="")
        self.lbl_counter   = tk.Label(hdr, font=("Segoe UI", 11),         fg="#89b4fa", bg="#181825", text="")
        self.lbl_zoom      = tk.Label(hdr, font=("Segoe UI", 10),         fg="#a6adc8", bg="#181825", text="Zoom: 100%")
        self.lbl_brush     = tk.Label(hdr, font=("Segoe UI", 10),         fg="#a6adc8", bg="#181825", text=f"Pinsel: {BRUSH_DEF} px")
        self.lbl_annotated = tk.Label(hdr, font=("Segoe UI", 10),         fg="#f38ba8", bg="#181825", text="Keine Annotation")

        self.lbl_title    .pack(side=tk.LEFT,  padx=14, pady=6)
        self.lbl_counter  .pack(side=tk.RIGHT, padx=14)
        self.lbl_zoom     .pack(side=tk.RIGHT, padx=10)
        self.lbl_brush    .pack(side=tk.RIGHT, padx=10)
        self.lbl_annotated.pack(side=tk.RIGHT, padx=10)

        # Canvas
        self.canvas = tk.Canvas(self.root, bg="#11111b", highlightthickness=0, cursor="none")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        c = self.canvas
        c.bind("<ButtonPress-1>",   self._on_lmb_press)
        c.bind("<B1-Motion>",       self._on_lmb_drag)
        c.bind("<ButtonRelease-1>", self._on_lmb_release)
        c.bind("<ButtonPress-3>",   self._on_rmb_press)
        c.bind("<B3-Motion>",       self._on_rmb_drag)
        c.bind("<ButtonRelease-3>", self._on_rmb_release)
        c.bind("<MouseWheel>",      self._on_scroll)
        c.bind("<Button-4>",        self._on_scroll)
        c.bind("<Button-5>",        self._on_scroll)
        c.bind("<ButtonPress-2>",   self._pan_start)
        c.bind("<B2-Motion>",       self._pan_move)
        c.bind("<ButtonRelease-2>", self._pan_end)
        c.bind("<Motion>",          self._on_mouse_move)
        c.bind("<Leave>",           self._on_mouse_leave)
        c.bind("<Configure>",       self._on_canvas_resize)

        # Footer
        ftr = tk.Frame(self.root, bg="#181825")
        ftr.pack(fill=tk.X)

        bs = dict(font=("Segoe UI", 10, "bold"), bd=0, padx=18, pady=7, cursor="hand2", relief=tk.FLAT)
        tk.Button(ftr, text="Löschen  [C]",      bg="#45475a", fg="#cdd6f4",
                  activebackground="#585b70", command=self._clear_mask, **bs).pack(side=tk.LEFT, padx=8, pady=4)
        tk.Button(ftr, text="Überspringen  [S]", bg="#f38ba8", fg="#1e1e2e",
                  activebackground="#eba0ac", command=self._skip,       **bs).pack(side=tk.LEFT, padx=4)

        hints = ("LMB: Malen  ·  RMB: Radierer  ·  Strg+Scroll / +−: Zoom  ·  "
                 "Mitteltaste · Leer+Drag: Pan  ·  Pfeiltasten: Pan  ·  "
                 "[/]: Pinsel  ·  0: Fit  ·  Strg+Z: Undo  ·  F11: Vollbild")
        tk.Label(ftr, text=hints, font=("Segoe UI", 8), fg="#585b70",
                 bg="#181825").pack(side=tk.LEFT, padx=14)

        self.btn_next = tk.Button(ftr, text="Weiter  [Enter]", bg="#a6e3a1", fg="#1e1e2e",
                                  activebackground="#94e2d5", command=self._next, **bs)
        self.btn_next.pack(side=tk.RIGHT, padx=8, pady=4)

    # ── Tastenkombinationen ───────────────────────────────────────────────────
    def _bind_keys(self):
        r = self.root
        r.bind("<Return>",           lambda e: self._next())
        r.bind("n",                  lambda e: self._next())
        r.bind("N",                  lambda e: self._next())
        r.bind("s",                  lambda e: self._skip())
        r.bind("S",                  lambda e: self._skip())
        r.bind("c",                  lambda e: self._clear_mask())
        r.bind("C",                  lambda e: self._clear_mask())
        r.bind("<Delete>",           lambda e: self._clear_mask())
        r.bind("<Control-z>",        lambda e: self._undo_last())
        r.bind("<Control-Z>",        lambda e: self._undo_last())
        r.bind("<F11>",              lambda e: self._toggle_fullscreen())
        r.bind("<Escape>",           lambda e: self._exit_fullscreen())
        # Zoom
        r.bind("plus",               lambda e: self._zoom_center(ZOOM_STEP))
        r.bind("equal",              lambda e: self._zoom_center(ZOOM_STEP))
        r.bind("KP_Add",             lambda e: self._zoom_center(ZOOM_STEP))
        r.bind("minus",              lambda e: self._zoom_center(1 / ZOOM_STEP))
        r.bind("KP_Subtract",        lambda e: self._zoom_center(1 / ZOOM_STEP))
        r.bind("0",                  lambda e: self._fit_view())
        r.bind("KP_0",               lambda e: self._fit_view())
        # Pinselgröße
        r.bind("bracketleft",        lambda e: self._change_brush(-2))
        r.bind("bracketright",       lambda e: self._change_brush(+2))
        # Pan via Pfeiltasten
        r.bind("<Left>",             lambda e: self._pan_by(-30, 0))
        r.bind("<Right>",            lambda e: self._pan_by(+30, 0))
        r.bind("<Up>",               lambda e: self._pan_by(0, -30))
        r.bind("<Down>",             lambda e: self._pan_by(0, +30))
        # Leertaste für Pan-Modus
        r.bind("<KeyPress-space>",   self._space_press)
        r.bind("<KeyRelease-space>", self._space_release)

    # ── Bild laden ────────────────────────────────────────────────────────────
    def _load_current_image(self):
        if self.index >= len(self.image_files):
            self._finish()
            return

        fname = self.image_files[self.index]
        fpath = os.path.join(TEST_DATA_DIR, fname)

        raw        = np.fromfile(fpath, dtype=np.uint8)
        gray       = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
        h, w       = gray.shape[:2]
        self.disp_w, self.disp_h = w, h

        rgb            = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        self.base_pil  = Image.fromarray(rgb)
        self.draw_mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.draw_obj  = ImageDraw.Draw(self.draw_mask)
        self._undo     = []

        self._fit_view()
        self.lbl_title  .config(text=f"📷  {fname}")
        self.lbl_counter.config(text=f"Bild {self.index + 1} / {len(self.image_files)}")
        is_last = (self.index == len(self.image_files) - 1)
        self.btn_next.config(text="Benchmark  [Enter]" if is_last else "Weiter  [Enter]")
        self._update_annotation_label()

    def _update_annotation_label(self):
        px = int(np.sum(np.array(self.draw_mask)[:, :, 3] > 0))
        if px == 0:
            self.lbl_annotated.config(text="Keine Annotation", fg="#f38ba8")
        else:
            self.lbl_annotated.config(text=f"✏️  {px} px annotiert", fg="#a6e3a1")

    # ── Zoom & Pan ────────────────────────────────────────────────────────────
    def _cw_ch(self) -> tuple[int, int]:
        return self.canvas.winfo_width(), self.canvas.winfo_height()

    def _fit_view(self):
        """Passt Zoom an, sodass das gesamte Bild im Canvas sichtbar ist."""
        self.root.update_idletasks()
        cw, ch = self._cw_ch()
        if cw < 2:
            cw = self.root.winfo_width()
            ch = max(1, self.root.winfo_height() - 100)
        self.zoom  = max(ZOOM_MIN, min(ZOOM_MAX, min(cw / self.disp_w, ch / self.disp_h)))
        self.pan_x = self.disp_w / 2.0
        self.pan_y = self.disp_h / 2.0
        self._clamp_pan()
        self._update_hud()
        self._render()

    def _zoom_at(self, factor: float, cx: float, cy: float):
        """Zoom um einen bestimmten Canvas-Punkt (zoom-to-cursor)."""
        ix, iy = self._c2i(cx, cy)
        self.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.zoom * factor))
        cw, ch = self._cw_ch()
        self.pan_x = ix - (cx - cw * 0.5) / self.zoom
        self.pan_y = iy - (cy - ch * 0.5) / self.zoom
        self._clamp_pan()
        self._update_hud()
        self._render()

    def _zoom_center(self, factor: float):
        cw, ch = self._cw_ch()
        self._zoom_at(factor, cw / 2, ch / 2)

    def _pan_by(self, dpx: float, dpy: float):
        self.pan_x += dpx / self.zoom
        self.pan_y += dpy / self.zoom
        self._clamp_pan()
        self._render()

    def _clamp_pan(self):
        cw, ch = self._cw_ch()
        if cw < 2:
            return
        hw = cw / (2 * self.zoom)
        hh = ch / (2 * self.zoom)
        # Bild-Mitte bleibt immer im erlaubten Bereich
        self.pan_x = max(min(hw, self.disp_w / 2),
                         min(max(self.disp_w - hw, self.disp_w / 2), self.pan_x))
        self.pan_y = max(min(hh, self.disp_h / 2),
                         min(max(self.disp_h - hh, self.disp_h / 2), self.pan_y))

    def _c2i(self, cx: float, cy: float) -> tuple[float, float]:
        """Canvas-Pixel → Bild-Pixel (float)."""
        cw, ch = self._cw_ch()
        return (self.pan_x + (cx - cw * 0.5) / self.zoom,
                self.pan_y + (cy - ch * 0.5) / self.zoom)

    def _update_hud(self):
        self.lbl_zoom .config(text=f"Zoom: {int(self.zoom * 100)}%")
        self.lbl_brush.config(text=f"Pinsel: {self.brush_size} px")

    # ── Rendering ─────────────────────────────────────────────────────────────
    def _render(self):
        cw, ch = self._cw_ch()
        if cw < 2 or ch < 2:
            return

        out = Image.new("RGB", (cw, ch), BG)

        half_w = cw * 0.5 / self.zoom
        half_h = ch * 0.5 / self.zoom
        src_l  = self.pan_x - half_w
        src_t  = self.pan_y - half_h
        src_r  = self.pan_x + half_w
        src_b  = self.pan_y + half_h

        cl = max(0.0, src_l)
        ct = max(0.0, src_t)
        cr = min(float(self.disp_w), src_r)
        cb = min(float(self.disp_h), src_b)

        if cr > cl + 0.5 and cb > ct + 0.5:
            box    = (int(cl), int(ct), math.ceil(cr), math.ceil(cb))
            base_c = self.base_pil .crop(box)
            mask_c = self.draw_mask.crop(box)
            comp   = Image.alpha_composite(base_c.convert("RGBA"), mask_c).convert("RGB")
            sw     = max(1, int((cr - cl) * self.zoom))
            sh     = max(1, int((cb - ct) * self.zoom))
            rs     = Image.NEAREST if self.zoom >= 3.0 else Image.BILINEAR
            scaled = comp.resize((sw, sh), rs)
            px     = max(0, int((cl - src_l) * self.zoom))
            py     = max(0, int((ct - src_t) * self.zoom))
            out.paste(scaled, (px, py))

        self._tk_img = ImageTk.PhotoImage(out)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._tk_img)

        # Pinsel-Cursor zeichnen
        mx, my = self._mouse_pos
        if 0 <= mx < cw and 0 <= my < ch and not (self._panning or self._space_pan):
            r_c = max(2.0, self.brush_size * self.zoom)
            col = "#4fc3f7" if self._erasing else "#ff5050"
            self.canvas.create_oval(mx - r_c, my - r_c, mx + r_c, my + r_c,
                                    outline=col, width=1.5)
            self.canvas.create_oval(mx - 2, my - 2, mx + 2, my + 2,
                                    fill=col, outline="")

    def _on_canvas_resize(self, _event):
        self._clamp_pan()
        self._render()

    # ── Maus-Events ───────────────────────────────────────────────────────────
    def _on_mouse_move(self, event):
        self._mouse_pos = (event.x, event.y)
        self._render()

    def _on_mouse_leave(self, _event):
        self._mouse_pos = (-1, -1)
        self._render()

    # LMB
    def _on_lmb_press(self, event):
        if self._space_down:
            self._space_pan = True
            self._pan_start(event)
        else:
            self._push_undo()
            self._drawing = True
            self._paint(event.x, event.y, erase=False)

    def _on_lmb_drag(self, event):
        if self._space_pan:
            self._pan_move(event)
        elif self._drawing:
            self._paint(event.x, event.y, erase=False)

    def _on_lmb_release(self, event):
        if self._space_pan:
            self._pan_end(event)
            self._space_pan = False
        else:
            self._drawing = False
            self._update_annotation_label()

    # RMB
    def _on_rmb_press(self, event):
        self._push_undo()
        self._erasing = True
        self._paint(event.x, event.y, erase=True)

    def _on_rmb_drag(self, event):
        if self._erasing:
            self._paint(event.x, event.y, erase=True)

    def _on_rmb_release(self, _event):
        self._erasing = False
        self._update_annotation_label()

    # Scroll
    def _on_scroll(self, event):
        if event.num == 4:       delta = +1
        elif event.num == 5:     delta = -1
        else:                    delta = +1 if event.delta > 0 else -1

        if event.state & 0x4:   # Strg gedrückt → Zoom
            self._zoom_at(ZOOM_STEP if delta > 0 else 1 / ZOOM_STEP, event.x, event.y)
        else:                    # Pinselgröße
            self._change_brush(delta * 2)

    # Mitteltaste-Pan
    def _pan_start(self, event):
        self._panning  = True
        self._pan_last = (event.x, event.y)
        self.canvas.config(cursor="fleur")

    def _pan_move(self, event):
        if not self._panning or self._pan_last is None:
            return
        dx = event.x - self._pan_last[0]
        dy = event.y - self._pan_last[1]
        self._pan_last = (event.x, event.y)
        self.pan_x -= dx / self.zoom
        self.pan_y -= dy / self.zoom
        self._clamp_pan()
        self._render()

    def _pan_end(self, _event):
        self._panning  = False
        self._pan_last = None
        self.canvas.config(cursor="fleur" if self._space_down else "none")

    # Leertaste
    def _space_press(self, _event):
        if not self._space_down:
            self._space_down = True
            self.canvas.config(cursor="fleur")

    def _space_release(self, _event):
        self._space_down = False
        if not self._panning:
            self.canvas.config(cursor="none")

    # ── Zeichnen ──────────────────────────────────────────────────────────────
    def _paint(self, cx: int, cy: int, erase: bool):
        ix, iy = self._c2i(cx, cy)
        r = float(self.brush_size)

        if erase:
            # Alpha-Kanal via NumPy löschen (PIL unterstützt kein echtes Erase)
            arr = np.array(self.draw_mask)
            Y, X = np.ogrid[:self.disp_h, :self.disp_w]
            arr[(X - ix) ** 2 + (Y - iy) ** 2 <= r ** 2, 3] = 0
            self.draw_mask = Image.fromarray(arr.astype(np.uint8), "RGBA")
            self.draw_obj  = ImageDraw.Draw(self.draw_mask)
        else:
            self.draw_obj.ellipse([ix - r, iy - r, ix + r, iy + r],
                                  fill=(255, 80, 80, 180))
        self._render()

    def _change_brush(self, delta: int):
        self.brush_size = max(BRUSH_MIN, min(BRUSH_MAX, self.brush_size + delta))
        self.lbl_brush.config(text=f"Pinsel: {self.brush_size} px")
        self._render()

    # ── Undo ──────────────────────────────────────────────────────────────────
    def _push_undo(self):
        if len(self._undo) >= MAX_UNDO:
            self._undo.pop(0)
        self._undo.append(self.draw_mask.copy())

    def _undo_last(self):
        if self._undo:
            self.draw_mask = self._undo.pop()
            self.draw_obj  = ImageDraw.Draw(self.draw_mask)
            self._update_annotation_label()
            self._render()

    # ── Annotation löschen ────────────────────────────────────────────────────
    def _clear_mask(self):
        self._push_undo()
        self.draw_mask = Image.new("RGBA", (self.disp_w, self.disp_h), (0, 0, 0, 0))
        self.draw_obj  = ImageDraw.Draw(self.draw_mask)
        self._update_annotation_label()
        self._render()

    # ── Vollbild ──────────────────────────────────────────────────────────────
    def _toggle_fullscreen(self):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))

    def _exit_fullscreen(self):
        self.root.attributes("-fullscreen", False)

    # ── Navigation ────────────────────────────────────────────────────────────
    def _save_current_annotation(self):
        fname = self.image_files[self.index]
        arr   = np.array(self.draw_mask)
        gt    = (arr[:, :, 3] > 0).astype(np.uint8) * 255
        self.annotations[fname] = gt
        os.makedirs(GT_DIR, exist_ok=True)
        base = os.path.splitext(fname)[0]
        cv2.imwrite(os.path.join(GT_DIR, base + "_mask.png"), gt)

    def _next(self):
        self._save_current_annotation()
        self.index += 1
        self._load_current_image()

    def _skip(self):
        self.skipped.append(self.image_files[self.index])
        self.index += 1
        self._load_current_image()

    # ── Benchmark ─────────────────────────────────────────────────────────────
    def _finish(self):
        self.root.withdraw()
        self._run_benchmark()

    def _run_benchmark(self):
        print("\n" + "=" * 60)
        print("  IGNITE – Benchmark mit manuellen Ground-Truth-Masken")
        print("=" * 60)

        results = {}
        agg     = {"dice": [], "iou": [], "sensitivity": [], "specificity": [], "precision": []}

        for fname, gt in self.annotations.items():
            fpath = os.path.join(TEST_DATA_DIR, fname)
            print(f"\n▶  {fname}")
            try:
                img     = image_processing.load_thermal_image(fpath)
                _, pred = image_processing.run_rust_pipeline(img)
                body    = image_processing._extract_body_mask_cpu(img)
                metrics = dataset_evaluator.evaluate_metrics(pred, gt, body)

                results[fname] = {
                    "metrics":       metrics,
                    "annotated_px":  int(np.sum(gt > 0)),
                    "detected_px":   int(np.sum(pred > 0)),
                    "status":        "OK",
                }
                print(f"   Dice={metrics['dice']:.3f}  IoU={metrics['iou']:.3f}  "
                      f"Sens={metrics['sensitivity']:.3f}  Spec={metrics['specificity']:.3f}")
                for k in agg:
                    agg[k].append(metrics[k])
            except Exception as exc:
                results[fname] = {"status": f"Fehler: {exc}"}
                print(f"   Fehler: {exc}")

        summary = {}
        if agg["dice"]:
            summary = {k: round(float(np.mean(v)), 4) for k, v in agg.items()}
            print("\n" + "-" * 60 + "\n  Durchschnitt:")
            for k, v in summary.items():
                print(f"    {k:15s}: {v:.4f}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output = {
            "timestamp":         datetime.datetime.now().isoformat(),
            "annotated_images":  list(self.annotations.keys()),
            "skipped_images":    self.skipped,
            "per_image_results": results,
            "summary_averages":  summary,
        }
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

        print(f"\n✅  Ergebnisse: {RESULTS_FILE}")
        print(f"    Masken:      {GT_DIR}/")
        print("=" * 60)

        self.root.deiconify()
        messagebox.showinfo(
            "Benchmark abgeschlossen",
            f"✅  Fertig!\n\n"
            f"Annotierte Bilder: {len(self.annotations)}\n"
            f"Übersprungen:      {len(self.skipped)}\n\n"
            f"Ø Dice: {summary.get('dice', '–')}   "
            f"Ø IoU: {summary.get('iou', '–')}\n\n"
            f"Ergebnisse:\n{RESULTS_FILE}",
        )
        self.root.destroy()


# ── Einstiegspunkt ────────────────────────────────────────────────────────────
def main():
    if not os.path.isdir(TEST_DATA_DIR):
        sys.exit(f"[Fehler] Ordner '{TEST_DATA_DIR}' nicht gefunden.")
    files = sorted_images(TEST_DATA_DIR)
    if not files:
        sys.exit(f"[Fehler] Keine Bilder in '{TEST_DATA_DIR}'.")
    print(f"[IGNITE Annotator] {len(files)} Bilder gefunden.")
    root = tk.Tk()
    root.resizable(True, True)
    AnnotatorApp(root, files)
    root.mainloop()


if __name__ == "__main__":
    main()
