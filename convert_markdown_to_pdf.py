"""
convert_markdown_to_pdf.py
Erzeugt eine hochwertige PDF-Datei aus der Markdown-Datei unter Nutzung von Pandoc und Google Chrome headless.
"""

import os
import subprocess
import sys

pandoc_bin = r"C:\Users\jonan\AppData\Local\Microsoft\WinGet\Packages\JohnMacFarlane.Pandoc_Microsoft.Winget.Source_8wekyb3d8bbwe\pandoc-3.10\pandoc.exe"
chrome_bin = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

md_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.md"
html_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.html"
pdf_file = "SCHRIFTLICHE_ARBEIT_JUGEND_FORSCHT.pdf"

# CSS Styling exakt nach dem Jugend forscht Leitfaden
custom_css = """
@page {
    size: A4;
    margin: 2.5cm 2.5cm 2.0cm 2.5cm;
}

body {
    font-family: 'Segoe UI', Arial, 'DejaVu Sans', sans-serif;
    font-size: 11pt;
    line-height: 1.5;
    color: #1E293B;
    background-color: #FFFFFF;
}

h1 {
    font-size: 18pt;
    font-weight: bold;
    color: #0F172A;
    border-bottom: 2px solid #6366F1;
    padding-bottom: 4px;
    margin-top: 24px;
    margin-bottom: 12px;
    page-break-before: always;
}

h1:first-of-type {
    page-break-before: avoid;
}

h2 {
    font-size: 14pt;
    font-weight: bold;
    color: #334155;
    margin-top: 18px;
    margin-bottom: 8px;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    color: #475569;
    margin-top: 14px;
    margin-bottom: 6px;
}

p {
    margin-bottom: 10px;
    text-align: justify;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 14px;
    margin-bottom: 16px;
    font-size: 10pt;
}

th, td {
    border: 1px solid #CBD5E1;
    padding: 8px 10px;
    text-align: left;
}

th {
    background-color: #F1F5F9;
    font-weight: bold;
    color: #0F172A;
}

tr:nth-child(even) {
    background-color: #F8FAFC;
}

img {
    max-width: 90%;
    height: auto;
    display: block;
    margin: 16px auto;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

p img {
    margin: 16px auto;
}

em {
    font-style: italic;
    color: #475569;
}

blockquote {
    border-left: 4px solid #6366F1;
    padding-left: 12px;
    margin-left: 0;
    color: #475569;
    background-color: #F8FAFC;
    padding-top: 6px;
    padding-bottom: 6px;
}

code {
    background-color: #F1F5F9;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: Consolas, monospace;
    font-size: 9.5pt;
}

pre code {
    display: block;
    padding: 10px;
    overflow-x: auto;
    line-height: 1.4;
}
"""

css_filename = "jufo_paper_style.css"
with open(css_filename, "w", encoding="utf-8") as f:
    f.write(custom_css)

print("[1/3] Konvertiere Markdown nach HTML via Pandoc...")
cmd_pandoc = [
    pandoc_bin,
    md_file,
    "-o", html_file,
    "--standalone",
    "--mathjax",
    "--css=" + css_filename,
    "--metadata", "title=IGNITE Schriftliche Arbeit Jugend forscht 2026"
]

res_pandoc = subprocess.run(cmd_pandoc, capture_output=True, text=True)
if res_pandoc.returncode != 0:
    print("[!] Fehler bei Pandoc HTML Konvertierung:")
    print(res_pandoc.stderr)
    sys.exit(1)

print("[2/3] Erzeuge finale PDF-Datei via Chrome Headless...")
cmd_chrome = [
    chrome_bin,
    "--headless",
    "--disable-gpu",
    "--print-to-pdf=" + os.path.abspath(pdf_file),
    "--no-pdf-header-footer",
    os.path.abspath(html_file)
]

res_chrome = subprocess.run(cmd_chrome, capture_output=True, text=True)
if res_chrome.returncode != 0:
    print("[!] Fehler bei Chrome PDF Erzeugung:")
    print(res_chrome.stderr)
    sys.exit(1)

print(f"[3/3] Erfolgreich! PDF wurde erstellt: {os.path.abspath(pdf_file)}")
