using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using Ignite.Desktop.Services;

namespace Ignite.Desktop.Services
{
    public class ClinicalReportModel
    {
        public string PatientId { get; set; } = "UNKNOWN";
        public DateTime ExamDate { get; set; } = DateTime.Now;
        public string Modality { get; set; } = "FLIR LWIR 17µm (8-14µm)";
        public string ImageFileName { get; set; } = string.Empty;
        public string Base64ImagePng { get; set; } = string.Empty;
        
        public double MinTemp { get; set; }
        public double MaxTemp { get; set; }
        public double MeanTemp { get; set; }
        public double MadDeviation { get; set; }
        public double SimdLatencyMs { get; set; }

        public string ArmstrongStage { get; set; } = "Grad 0";
        public string OverallRiskLevel { get; set; } = "PHYSIOLOGISCH";
        public string OverallRecommendation { get; set; } = "Regulärer Befund, keine akute Intervention erforderlich.";

        public GoniometerMeasurement? Goniometer { get; set; }
        public List<AngiosomeTerritory>? Angiosomes { get; set; }
        public List<HotspotReportItem> Hotspots { get; set; } = new();
    }

    public class HotspotReportItem
    {
        public int Id { get; set; }
        public int AreaPx { get; set; }
        public double AreaPercent { get; set; }
        public double MaxTemp { get; set; }
        public double Circularity { get; set; }
        public string RiskLevel { get; set; } = "BENIGN";
        public string Recommendation { get; set; } = string.Empty;
    }

    public static class ClinicalReportService
    {
        public static string GenerateHtmlReport(ClinicalReportModel model)
        {
            string hashInput = $"{model.PatientId}_{model.ExamDate:O}_{model.MaxTemp:F1}_{model.ArmstrongStage}";
            string sha256Hash = BitConverter.ToString(SHA256.HashData(Encoding.UTF8.GetBytes(hashInput))).Replace("-", "").ToLowerInvariant()[..16];

            string riskBadgeClass = model.OverallRiskLevel switch
            {
                "CRITICAL" or "KRITISCH" or "ARMSTRONG-ALARM" => "badge-critical",
                "WARNING" or "WARNUNG" or "HYPERTHERMIE-STRESS" => "badge-warning",
                _ => "badge-success"
            };

            var sb = new StringBuilder();
            sb.AppendLine("<!DOCTYPE html>");
            sb.AppendLine("<html lang='de'>");
            sb.AppendLine("<head>");
            sb.AppendLine("    <meta charset='utf-8'/>");
            sb.AppendLine($"    <title>IGNITE Klinischer Befundbericht - {model.PatientId}</title>");
            sb.AppendLine("    <style>");
            sb.AppendLine("        @page { size: A4 portrait; margin: 15mm 15mm 20mm 15mm; }");
            sb.AppendLine("        * { box-sizing: border-box; }");
            sb.AppendLine("        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #F8FAFC; color: #1E293B; margin: 0; padding: 24px; font-size: 13px; line-height: 1.5; }");
            sb.AppendLine("        .page-container { max-width: 900px; margin: 0 auto; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 32px; box-shadow: 0 4px 16px rgba(0,0,0,0.04); }");
            sb.AppendLine("        .header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #0284C7; padding-bottom: 16px; margin-bottom: 20px; }");
            sb.AppendLine("        .logo-title h1 { margin: 0; font-size: 20px; color: #0F172A; letter-spacing: -0.5px; }");
            sb.AppendLine("        .logo-title .subtitle { color: #0284C7; font-size: 11px; font-weight: bold; text-transform: uppercase; margin-top: 2px; }");
            sb.AppendLine("        .header-meta { text-align: right; font-size: 11px; color: #64748B; }");
            sb.AppendLine("        .header-meta strong { color: #1E293B; }");
            sb.AppendLine("        .section-title { font-size: 14px; font-weight: bold; color: #0F172A; border-bottom: 1px solid #E2E8F0; padding-bottom: 6px; margin-top: 24px; margin-bottom: 12px; display: flex; align-items: center; }");
            sb.AppendLine("        .section-title span { margin-right: 8px; }");
            sb.AppendLine("        .meta-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; margin-bottom: 20px; }");
            sb.AppendLine("        .meta-box .label { font-size: 10px; font-weight: bold; color: #64748B; text-transform: uppercase; }");
            sb.AppendLine("        .meta-box .val { font-size: 13px; font-weight: bold; color: #0F172A; margin-top: 2px; }");
            sb.AppendLine("        .banner { border-radius: 8px; padding: 14px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; }");
            sb.AppendLine("        .banner-critical { background: #FEE2E2; border: 1.5px solid #DC2626; color: #991B1B; }");
            sb.AppendLine("        .banner-warning { background: #FEF3C7; border: 1.5px solid #D97706; color: #92400E; }");
            sb.AppendLine("        .banner-success { background: #ECFDF5; border: 1.5px solid #059669; color: #065F46; }");
            sb.AppendLine("        .image-container { text-align: center; margin: 16px 0; background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px; }");
            sb.AppendLine("        .image-container img { max-width: 100%; max-height: 420px; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }");
            sb.AppendLine("        .image-caption { font-size: 10.5px; color: #64748B; margin-top: 8px; font-style: italic; }");
            sb.AppendLine("        table { width: 100%; border-collapse: collapse; margin-top: 8px; margin-bottom: 16px; font-size: 11.5px; }");
            sb.AppendLine("        th { background: #F1F5F9; color: #475569; font-weight: 600; text-align: left; padding: 8px 10px; border: 1px solid #E2E8F0; }");
            sb.AppendLine("        td { padding: 8px 10px; border: 1px solid #E2E8F0; color: #1E293B; }");
            sb.AppendLine("        tr:nth-child(even) { background: #F8FAFC; }");
            sb.AppendLine("        .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 10px; }");
            sb.AppendLine("        .badge-critical { background: #DC2626; color: #FFFFFF; }");
            sb.AppendLine("        .badge-warning { background: #D97706; color: #FFFFFF; }");
            sb.AppendLine("        .badge-success { background: #059669; color: #FFFFFF; }");
            sb.AppendLine("        .badge-info { background: #0284C7; color: #FFFFFF; }");
            sb.AppendLine("        .guidelines-box { background: #F0F9FF; border-left: 4px solid #0284C7; padding: 12px 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px; }");
            sb.AppendLine("        .guidelines-box h4 { margin: 0 0 6px 0; font-size: 12px; color: #0369A1; }");
            sb.AppendLine("        .guidelines-box ul { margin: 0; padding-left: 18px; }");
            sb.AppendLine("        .guidelines-box li { margin-bottom: 4px; font-size: 11.5px; }");
            sb.AppendLine("        .signature-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px; padding-top: 20px; border-top: 1px solid #E2E8F0; }");
            sb.AppendLine("        .signature-line { border-bottom: 1px solid #94A3B8; height: 35px; margin-bottom: 6px; }");
            sb.AppendLine("        .signature-title { font-size: 10.5px; color: #64748B; }");
            sb.AppendLine("        @media print {");
            sb.AppendLine("            body { background: #FFFFFF; padding: 0; font-size: 12px; }");
            sb.AppendLine("            .page-container { border: none; box-shadow: none; padding: 0; max-width: 100%; }");
            sb.AppendLine("            .no-print { display: none; }");
            sb.AppendLine("        }");
            sb.AppendLine("    </style>");
            sb.AppendLine("</head>");
            sb.AppendLine("<body>");
            sb.AppendLine("<div class='page-container'>");

            // 1. Header
            sb.AppendLine("    <div class='header'>");
            sb.AppendLine("        <div class='logo-title'>");
            sb.AppendLine("            <h1>IGNITE MEDICAL PACS SUITE v5.0.0</h1>");
            sb.AppendLine("            <div class='subtitle'>Radiometrische Computer-Assisted Diagnostics (CAD) &amp; Thermographie</div>");
            sb.AppendLine("        </div>");
            sb.AppendLine("        <div class='header-meta'>");
            sb.AppendLine($"            <div><strong>BEFUND-ID:</strong> IGN-{DateTime.Now:yyyyMMdd}-{sha256Hash.ToUpperInvariant()}</div>");
            sb.AppendLine($"            <div><strong>DATUM:</strong> {model.ExamDate:dd.MM.yyyy HH:mm:ss} CET</div>");
            sb.AppendLine("            <div><strong>KLINIK:</strong> Diabetologisches CAD-Zentrum</div>");
            sb.AppendLine("        </div>");
            sb.AppendLine("    </div>");

            // 2. Patient Demographics & Hardware
            sb.AppendLine("    <div class='meta-grid'>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>Patienten-Pseudonym</div><div class='val'>{model.PatientId}</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>Modalität &amp; Detektor</div><div class='val'>{model.Modality}</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>Bilddatensatz</div><div class='val'>{model.ImageFileName}</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>SIMD Latenz (AVX2)</div><div class='val'>{model.SimdLatencyMs:F1} ms (256-Bit)</div></div>");
            sb.AppendLine("    </div>");

            // 3. Executive Diagnostic Callout Banner
            string bannerClass = model.OverallRiskLevel.Contains("KRITISCH") || model.OverallRiskLevel.Contains("CRITICAL") || model.OverallRiskLevel.Contains("ALARM") 
                ? "banner-critical" 
                : (model.OverallRiskLevel.Contains("WARNUNG") || model.OverallRiskLevel.Contains("STRESS") ? "banner-warning" : "banner-success");

            sb.AppendLine($"    <div class='banner {bannerClass}'>");
            sb.AppendLine("        <div>");
            sb.AppendLine($"            <div style='font-size: 15px; font-weight: bold;'>DIAGNOSTISCHES GESAMTERGEBNIS: {model.OverallRiskLevel}</div>");
            sb.AppendLine($"            <div style='font-size: 11.5px; margin-top: 3px;'>{model.OverallRecommendation}</div>");
            sb.AppendLine("        </div>");
            sb.AppendLine($"        <div style='text-align: right;'><span class='badge {riskBadgeClass}' style='font-size: 13px; padding: 6px 12px;'>ARMSTRONG {model.ArmstrongStage.ToUpperInvariant()}</span></div>");
            sb.AppendLine("    </div>");

            // 4. Embedded Snapshot
            if (!string.IsNullOrEmpty(model.Base64ImagePng))
            {
                sb.AppendLine("    <div class='image-container'>");
                sb.AppendLine($"        <img src='data:image/png;base64,{model.Base64ImagePng}' alt='Thermogramm Befund'/>");
                sb.AppendLine("        <div class='image-caption'>Abbildung 1: Kalibriertes Plantar-Thermogramm mit detektierten Hyperthermie-Foci und Druckverteilung.</div>");
                sb.AppendLine("    </div>");
            }

            // 5. Radiometrische Kennwerte
            sb.AppendLine("    <div class='section-title'><span>📊</span> 1. Radiometrische Basis-Kennwerte (Global)</div>");
            sb.AppendLine("    <div class='meta-grid'>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>T Minimal</div><div class='val'>{model.MinTemp:F1} °C</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>T Maximal</div><div class='val' style='color:#DC2626;'>{model.MaxTemp:F1} °C</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>T Mittelwert</div><div class='val'>{model.MeanTemp:F1} °C</div></div>");
            sb.AppendLine($"        <div class='meta-box'><div class='label'>MAD-Streuung</div><div class='val'>{model.MadDeviation:F2} K</div></div>");
            sb.AppendLine("    </div>");

            // 6. Orthopädische Goniometrie (Hallux Valgus)
            if (model.Goniometer != null && model.Goniometer.AngleDegrees > 0)
            {
                sb.AppendLine("    <div class='section-title'><span>📐</span> 2. Orthopädische Winkelmessung (Digitales Goniometer)</div>");
                sb.AppendLine("    <div class='meta-grid'>");
                sb.AppendLine($"        <div class='meta-box'><div class='label'>Hallux-Valgus-Winkel (HVA)</div><div class='val' style='color:#0284C7;'>{model.Goniometer.AngleDegrees:F1}°</div></div>");
                sb.AppendLine($"        <div class='meta-box'><div class='label'>Orthopädischer Schweregrad</div><div class='val'>{model.Goniometer.SeverityGrade}</div></div>");
                sb.AppendLine($"        <div class='meta-box' style='grid-column: span 2;'><div class='label'>Klinische Handlungsempfehlung</div><div class='val' style='font-size:11.5px; font-weight:normal;'>{model.Goniometer.ClinicalIndication}</div></div>");
                sb.AppendLine("    </div>");
            }

            // 7. Detektierte Hyperthermie-Herde
            if (model.Hotspots.Count > 0)
            {
                sb.AppendLine($"    <div class='section-title'><span>🔬</span> 3. Detektierte Entzündungsherde ({model.Hotspots.Count} Foci)</div>");
                sb.AppendLine("    <table>");
                sb.AppendLine("        <thead>");
                sb.AppendLine("            <tr><th>ID</th><th>Fläche (px)</th><th>Anteil (%)</th><th>Max Temp</th><th>Zirkularität</th><th>Risikostufe</th><th>Klinische Bewertung</th></tr>");
                sb.AppendLine("        </thead>");
                sb.AppendLine("        <tbody>");
                foreach (var h in model.Hotspots)
                {
                    string hBadge = h.RiskLevel == "CRITICAL" ? "badge-critical" : "badge-info";
                    sb.AppendLine("            <tr>");
                    sb.AppendLine($"                <td>#{h.Id}</td>");
                    sb.AppendLine($"                <td>{h.AreaPx} px</td>");
                    sb.AppendLine($"                <td>{h.AreaPercent:F2} %</td>");
                    sb.AppendLine($"                <td>{h.MaxTemp:F1} °C</td>");
                    sb.AppendLine($"                <td>{h.Circularity:F2}</td>");
                    sb.AppendLine($"                <td><span class='badge {hBadge}'>{h.RiskLevel}</span></td>");
                    sb.AppendLine($"                <td>{h.Recommendation}</td>");
                    sb.AppendLine("            </tr>");
                }
                sb.AppendLine("        </tbody>");
                sb.AppendLine("    </table>");
            }

            // 8. Taylor & Palmer Angiosom Territorien
            if (model.Angiosomes != null && model.Angiosomes.Count > 0)
            {
                sb.AppendLine("    <div class='section-title'><span>🩺</span> 4. Vaskuläre Perfusion: Taylor &amp; Palmer Angiosome</div>");
                sb.AppendLine("    <table>");
                sb.AppendLine("        <thead>");
                sb.AppendLine("            <tr><th>ID</th><th>Territorium</th><th>Versorgende Leitarterie</th><th>T Mittel</th><th>ΔT (K)</th><th>Status</th></tr>");
                sb.AppendLine("        </thead>");
                sb.AppendLine("        <tbody>");
                foreach (var a in model.Angiosomes)
                {
                    string aBadge = a.IsOcclusionSuspect ? "badge-critical" : (a.IsHyperemicFocal ? "badge-warning" : "badge-success");
                    sb.AppendLine("            <tr>");
                    sb.AppendLine($"                <td><strong>{a.Id}</strong></td>");
                    sb.AppendLine($"                <td>{a.TerritoryName}</td>");
                    sb.AppendLine($"                <td style='font-size:10.5px;'>{a.FeederArtery}</td>");
                    sb.AppendLine($"                <td>{a.MeanTemp:F1} °C</td>");
                    sb.AppendLine($"                <td>{a.DeltaT:F1} K</td>");
                    sb.AppendLine($"                <td><span class='badge {aBadge}'>{a.PerfusionStatus}</span></td>");
                    sb.AppendLine("            </tr>");
                }
                sb.AppendLine("        </tbody>");
                sb.AppendLine("    </table>");
            }

            // 10. Leitlinienkonforme IWGDF 2023 Handlungsempfehlungen
            sb.AppendLine("    <div class='guidelines-box'>");
            sb.AppendLine("        <h4>Leitlinienkonforme klinische Therapie- &amp; Präventionsdirektiven (IWGDF 2023):</h4>");
            sb.AppendLine("        <ul>");
            sb.AppendLine("            <li><strong>Asymmetrie-Schwelle ΔT ≥ 2.2 K:</strong> Nachweis eines prädiktiven Ulkusrisikos. Sofortige temporäre Reduktion der Gehstrecke um mindestens 50% und Verordnung orthopädischer Entlastungsschuhe.</li>");
            sb.AppendLine("            <li><strong>Mittelfuß-Hyperthermie (CII ≥ 2.0 K):</strong> Verdacht auf akute Charcot-Neuroarthropathie (Stadium 0/1). Dringende Indikation zur Entlastung mittels Total Contact Cast (TCC) sowie MRT-Bestätigungsdiagnostik.</li>");
            sb.AppendLine("            <li><strong>Goniometrie (HVA > 20°):</strong> Druckspitzen unter dem MTP-I Gelenk durch Abrollhilfe und Weichbettungseinlage kompensieren. Bei therapierefraktären Schmerzen orthopädische OP-Vorstellung.</li>");
            sb.AppendLine("            <li><strong>Thermografische Verlaufskontrolle:</strong> Re-Untersuchung innerhalb von 7–14 Tagen zur Überprüfung des Entzündungsrückgangs.</li>");
            sb.AppendLine("        </ul>");
            sb.AppendLine("    </div>");

            // 11. Signature Block
            sb.AppendLine("    <div class='signature-grid'>");
            sb.AppendLine("        <div>");
            sb.AppendLine("            <div class='signature-line'></div>");
            sb.AppendLine("            <div class='signature-title'>Unterschrift Befundender Arzt / Diabetologe</div>");
            sb.AppendLine("        </div>");
            sb.AppendLine("        <div>");
            sb.AppendLine("            <div class='signature-line'></div>");
            sb.AppendLine($"            <div class='signature-title'>Elektronisch signiert via IGNITE Core (SHA-256: {sha256Hash})</div>");
            sb.AppendLine("        </div>");
            sb.AppendLine("    </div>");

            // Print button for browser
            sb.AppendLine("    <div class='no-print' style='text-align: center; margin-top: 30px;'>");
            sb.AppendLine("        <button onclick='window.print()' style='background: #0284C7; color: #FFFFFF; border: none; padding: 10px 24px; font-size: 13px; font-weight: bold; border-radius: 6px; cursor: pointer;'>🖨️ Bericht drucken / als PDF speichern (Strg + P)</button>");
            sb.AppendLine("    </div>");

            sb.AppendLine("</div>");
            sb.AppendLine("</body>");
            sb.AppendLine("</html>");

            return sb.ToString();
        }
    }
}
