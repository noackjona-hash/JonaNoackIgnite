"""
compile_latex_pdf.py
Erzeugt eine reine LaTeX-Datei (.tex) aus der Markdown-Datei via Pandoc und kompiliert diese mit pdflatex.
"""

import os
import subprocess
import sys

pandoc_bin = r"C:\Users\jonan\AppData\Local\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-3.10\pandoc.exe"
pdflatex_bin = r"C:\Users\jonan\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"

md_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md"
tex_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.tex"
pdf_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.pdf"

# 1. Konvertierung von Markdown nach LaTeX (.tex)
print("[1/3] Konvertiere Markdown nach LaTeX (.tex) via Pandoc...")
cmd_pandoc = [
    pandoc_bin,
    md_file,
    "-o", tex_file,
    "--standalone",
    "--citeproc",
    "-V", "geometry:margin=2.5cm",
    "-V", "fontsize=11pt",
    "-V", "document-class=article"
]

res_pandoc = subprocess.run(cmd_pandoc, capture_output=True, text=True)
if res_pandoc.returncode != 0:
    print("[!] Fehler bei Pandoc TeX-Erzeugung:")
    print(res_pandoc.stderr)
    sys.exit(1)

print("[+] LaTeX-Datei erfolgreich generiert:", os.path.abspath(tex_file))

# 2. Kompilierung der .tex Datei mit pdflatex im nonstopmode
print("[2/3] Kompiliere .tex-Datei mit pdflatex...")
env = os.environ.copy()
miktex_bin_dir = r"C:\Users\jonan\AppData\Local\Programs\MiKTeX\miktex\bin\x64"
env["PATH"] = miktex_bin_dir + os.pathsep + env.get("PATH", "")

cmd_pdflatex = [
    pdflatex_bin,
    "-interaction=nonstopmode",
    "-halt-on-error",
    tex_file
]

res_tex1 = subprocess.run(cmd_pdflatex, capture_output=True, text=True, env=env)
# Zweiter Durchlauf für Seitenzahlen & Inhaltsverzeichnis
res_tex2 = subprocess.run(cmd_pdflatex, capture_output=True, text=True, env=env)

if os.path.exists(pdf_file):
    print(f"[3/3] Erfolgreich! PDF wurde via pdflatex erstellt: {os.path.abspath(pdf_file)}")
    print("PDF-Größe:", os.path.getsize(pdf_file), "Bytes")
else:
    print("[!] pdflatex Kompilierungsausgabe:")
    print(res_tex1.stdout[-1000:] if res_tex1.stdout else "Keine Ausgabe")
    print(res_tex1.stderr[-1000:] if res_tex1.stderr else "Kein Stderr")
