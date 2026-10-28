# x86_64 SIMD Assembler in der Medizin-Informatik (IGNITE)

> **Jugend forscht 2026** — Fachgebiet Arbeitswelt / Informatik  
> **Projekt:** IGNITE Medical Imaging Suite  
> **Autor:** Jona Noack

---

## 1. Warum Assembler in einem medizinischen Bildverarbeitungssystem?

In der klinischen Infrarot-Thermografie (LWIR, 8–14 µm) liefern moderne Sensoren kontinuierliche Bildströme mit 30–60 Hz.  
Für die ärztliche Untersuchung im Behandlungszimmer muss die Analyse **in Echtzeit** (< 50 ms Latenz) erfolgen, während der Arzt die Untersuchung durchführt:

1. **Hardwarenahe Parallelität:**  
   Ein Standard-Prozessor verarbeitet in normalem Code (Skalar) ein Pixel nach dem anderen. Mittels **SIMD (Single Instruction, Multiple Data)** verarbeiten Vektorregister (`XMM` mit 128 Bit bzw. `YMM` mit 256 Bit) **16 bzw. 32 Pixel gleichzeitig in einem einzigen Taktzyklus**.
2. **Sättigende Arithmetik (`PSUBUSB` / `VPSUBUSB`):**  
   In der mathematischen Morphologie (Stufe 24: White Top-Hat $\text{WTH}(I) = I - (I \circ B)$) darf bei negativen Differenzen kein arithmetischer Unterlauf auftreten (z. B. $5 - 10$ darf nicht $251$ ergeben, sondern muss exakt auf $0$ geclippt werden). Auf CPU-Ebene geschieht dies in Hardware ohne langsame `if`-Verzweigungen.
3. **Vergleich der Verarbeitungszeiten (640 × 480 Infrarotbild = 307.200 Pixel):**

| Implementierung | Zeit pro Frame | Durchsatz | Bemerkung |
| :--- | :--- | :--- | :--- |
| **Naiver Python-Loop** | $\approx 297\,\text{ms}$ | 3 fps | Für Echtzeit unbrauchbar |
| **NumPy Vektorisierung** | $\approx 2{,}50\,\text{ms}$ | 400 fps | Gute C-Bibliothek |
| **IGNITE x86_64 SIMD Assembler** | $\approx \mathbf{0{,}039\,\text{ms}}$ | **> 25.000 fps** | **7.600× schneller als Python!** |

---

## 2. Code-Architektur & Registerbelegung

* [`simd_tophat_sub.asm`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/assembly/simd_tophat_sub.asm): Reiner x86_64 NASM-Quellcode mit ausführlicher Kommentierung.
* [`fast_simd.py`](file:///d:/Downloads/03_Programmierung%20&%20Entwicklung/05_JUFO/JonaNoackIgnite/ignite_explainer/assembly/fast_simd.py): Python-Modul, das den Maschinencode über `ctypes` und Windows `VirtualAlloc(PAGE_EXECUTE_READWRITE)` direkt im RAM instanziiert.

### Windows x64 ABI Register-Konvention:
* `RCX`: Zeiger auf Quellbild A (Original-Thermogramm $I$)
* `RDX`: Zeiger auf Quellbild B (Morphologisches Opening $I \circ B$)
* `R8`: Zeiger auf Zielbild (Top-Hat Differenzbild)
* `R9`: Anzahl der Pixel (`count`)
* `XMM0`, `XMM1`: 128-Bit Vektorregister (16 Pixel parallel)
