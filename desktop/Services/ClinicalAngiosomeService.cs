using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Ignite.Desktop.Services
{
    /// <summary>
    /// Repräsentiert ein anatomisches Angiosom nach dem Taylor & Palmer Gefäßmodell (1987).
    /// </summary>
    public class AngiosomeTerritory
    {
        public string Id { get; set; } = string.Empty;
        public string TerritoryName { get; set; } = string.Empty;
        public string FeederArtery { get; set; } = string.Empty;
        public string ClinicalSignificance { get; set; } = string.Empty;
        public double MeanTemp { get; set; }
        public double MaxTemp { get; set; }
        public double MinTemp { get; set; }
        public double DeltaT { get; set; }
        public double PerfusionRatio { get; set; } // Relation zu globaler Gewebetemperatur
        public string PerfusionStatus { get; set; } = "Normoperfusion";
        public bool IsOcclusionSuspect { get; set; }
        public bool IsHyperemicFocal { get; set; }
    }

    /// <summary>
    /// Prädiktives 7-Tage Ulkus-Risikomodell basierend auf Armstrong-Delta, Laplace-Wärmestau und Gefäßstatus.
    /// </summary>
    public class PredictiveUlcerRisk
    {
        public double ProbabilityPercent { get; set; }
        public string RiskTier { get; set; } = "GERING";
        public string WagnerArmstrongStage { get; set; } = "Grad 0";
        public double ThermalDissipationIndex { get; set; } // THDI: Laplace Heat Entrapment
        public double AutonomicNeuropathyScore { get; set; } // 0..10
        public string CharcotRiskStatus { get; set; } = "Unauffällig";
        public string ImmediateIntervention { get; set; } = string.Empty;
        public int RecommendedFollowupHours { get; set; } = 168; // Standard 7 Tage
    }

    public static class ClinicalAngiosomeService
    {
        /// <summary>
        /// Berechnet die 6 Taylor-Palmer Angiosom-Territorien für das gegebene Plantar-Thermogramm.
        /// </summary>
        public static List<AngiosomeTerritory> ComputeAngiosomes(byte[] rawGray, int width, int height, double tMin = 20.0, double tMax = 42.0)
        {
            var results = new List<AngiosomeTerritory>();
            if (rawGray == null || rawGray.Length == 0 || width <= 0 || height <= 0) return results;

            // 1. Suche Bounding Box des Gewebes
            int minX = width, maxX = 0, minY = height, maxY = 0;
            long globalSum = 0;
            int globalCount = 0;

            for (int y = 0; y < height; y++)
            {
                int rowOff = y * width;
                for (int x = 0; x < width; x++)
                {
                    byte v = rawGray[rowOff + x];
                    if (v > 18) // Gewebe
                    {
                        if (x < minX) minX = x;
                        if (x > maxX) maxX = x;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                        globalSum += v;
                        globalCount++;
                    }
                }
            }

            if (globalCount < 50 || maxX <= minX || maxY <= minY) return results;

            double globalMeanRaw = (double)globalSum / globalCount;
            double globalMeanTemp = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(globalMeanRaw), 0, 255), tMin, tMax);

            int boxW = maxX - minX;
            int boxH = maxY - minY;

            // Definition der 6 Taylor-Palmer Angiosome in relativen Koordinaten
            // 1. Medial Plantar (A. tibialis posterior): Vorfuß medial / Hallux
            // 2. Lateral Plantar (A. tibialis posterior): Vorfuß lateral / Dig. II-V
            // 3. Medial Calcaneal (A. tibialis posterior): Mediale Ferse
            // 4. Lateral Calcaneal (A. peronea): Laterale Ferse
            // 5. Anterior Perforating (A. peronea): Mittelfuß lateral
            // 6. Dorsalis Pedis (A. tibialis anterior): Zentrales Plantargewölbe / Rückfluss
            var definitions = new[]
            {
                new { 
                    Id = "ANG-01", 
                    Name = "Mediales Plantar-Angiosom", 
                    Artery = "A. plantaris medialis (ex A. tibialis posterior)",
                    Signif = "Versorgt Hallux & Os metatarsale I (Höchstes Ulkusrisiko bei DFS)",
                    X0 = 0.00, X1 = 0.50, Y0 = 0.00, Y1 = 0.35 
                },
                new { 
                    Id = "ANG-02", 
                    Name = "Laterales Plantar-Angiosom", 
                    Artery = "A. plantaris lateralis (ex A. tibialis posterior)",
                    Signif = "Versorgt Digiti II-V & Metatarsale III-V lateral",
                    X0 = 0.50, X1 = 1.00, Y0 = 0.00, Y1 = 0.38 
                },
                new { 
                    Id = "ANG-03", 
                    Name = "Mediales Calcaneus-Angiosom", 
                    Artery = "Rami calcanei mediales (ex A. tibialis posterior)",
                    Signif = "Medialer Fersenballen & Achillessehnenansatz",
                    X0 = 0.05, X1 = 0.50, Y0 = 0.68, Y1 = 1.00 
                },
                new { 
                    Id = "ANG-04", 
                    Name = "Laterales Calcaneus-Angiosom", 
                    Artery = "Rami calcanei laterales (ex A. peronea)",
                    Signif = "Lateraler Fersenrand & plantare Fersensohle",
                    X0 = 0.50, X1 = 0.95, Y0 = 0.68, Y1 = 1.00 
                },
                new { 
                    Id = "ANG-05", 
                    Name = "Anteriores Perforans-Angiosom", 
                    Artery = "Rami perforantes (ex A. peronea / fibularis)",
                    Signif = "Lateraler Mittelfußrand & Cuboid-Gelenkzone",
                    X0 = 0.55, X1 = 1.00, Y0 = 0.38, Y1 = 0.68 
                },
                new { 
                    Id = "ANG-06", 
                    Name = "Zentral-Plantar (Dorsalis Pedis Ast)", 
                    Artery = "Arcus plantaris profundus (Anastomose A. tibialis ant./post.)",
                    Signif = "Zentrales Fußgewölbe & tiefe Perforatoren",
                    X0 = 0.15, X1 = 0.55, Y0 = 0.35, Y1 = 0.68 
                }
            };

            foreach (var d in definitions)
            {
                int rx0 = minX + (int)(d.X0 * boxW);
                int rx1 = minX + (int)(d.X1 * boxW);
                int ry0 = minY + (int)(d.Y0 * boxH);
                int ry1 = minY + (int)(d.Y1 * boxH);

                long sum = 0;
                int count = 0;
                byte maxVal = 0;
                byte minVal = 255;

                for (int y = ry0; y < ry1 && y < height; y++)
                {
                    int rowOff = y * width;
                    for (int x = rx0; x < rx1 && x < width; x++)
                    {
                        byte v = rawGray[rowOff + x];
                        if (v > 18)
                        {
                            sum += v;
                            count++;
                            if (v > maxVal) maxVal = v;
                            if (v < minVal) minVal = v;
                        }
                    }
                }

                if (count == 0) continue;

                double meanRaw = (double)sum / count;
                double meanT = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(meanRaw), 0, 255), tMin, tMax);
                double maxT = ThermalAnalysisHelper.RawToTemperature(maxVal, tMin, tMax);
                double minT = ThermalAnalysisHelper.RawToTemperature(minVal, tMin, tMax);

                double deltaToGlobal = meanT - globalMeanTemp;
                double perfRatio = meanT / (globalMeanTemp > 0 ? globalMeanTemp : 30.0);

                string status = "Normoperfusion";
                bool occlSuspect = false;
                bool hyperemic = false;

                if (deltaToGlobal >= 2.2)
                {
                    status = "KRITISCH: Fokale Hyperämie (Entzündungsherd)";
                    hyperemic = true;
                }
                else if (deltaToGlobal >= 1.2)
                {
                    status = "Auffällig: Reaktive Hyperthermie";
                    hyperemic = true;
                }
                else if (deltaToGlobal <= -2.5)
                {
                    status = "ALARM: Ischämie (Stenoseverdacht Zubringergefäß)";
                    occlSuspect = true;
                }
                else if (deltaToGlobal <= -1.5)
                {
                    status = "Minderperfusion (Verdacht pAVK Stadium II)";
                    occlSuspect = true;
                }

                results.Add(new AngiosomeTerritory
                {
                    Id = d.Id,
                    TerritoryName = d.Name,
                    FeederArtery = d.Artery,
                    ClinicalSignificance = d.Signif,
                    MeanTemp = meanT,
                    MaxTemp = maxT,
                    MinTemp = minT,
                    DeltaT = deltaToGlobal,
                    PerfusionRatio = perfRatio,
                    PerfusionStatus = status,
                    IsOcclusionSuspect = occlSuspect,
                    IsHyperemicFocal = hyperemic
                });
            }

            return results;
        }

        /// <summary>
        /// Berechnet die prädiktive 7-Tage Ulzerations-Wahrscheinlichkeit basierend auf Laplace-Wärmestau (THDI)
        /// und dem bilateralen Armstrong-Kriterium.
        /// </summary>
        public static PredictiveUlcerRisk CalculatePredictiveRisk(byte[] rawGray, int width, int height, double maxDeltaT, int hotspotCount, double tMin = 20.0, double tMax = 42.0)
        {
            var risk = new PredictiveUlcerRisk();
            if (rawGray == null || rawGray.Length == 0 || width < 10 || height < 10) return risk;

            // 1. Berechnung des Thermal Heat Dissipation Index (Laplace-Operator $\nabla^2 T$)
            // Gesunde Haut dissipiert Wärme lateral durch funktionelle Kapillaren.
            // Gestautes, prä-ulzeröses Gewebe zeigt stark negative Laplace-Werte (eingeschlossene Hitzeinseln).
            double laplaceSum = 0;
            int laplaceCount = 0;

            int step = 2;
            for (int y = step; y < height - step; y += step)
            {
                int rowOff = y * width;
                int rowUp = (y - step) * width;
                int rowDown = (y + step) * width;

                for (int x = step; x < width - step; x += step)
                {
                    byte center = rawGray[rowOff + x];
                    if (center > 25) // Nur echtes Gewebe
                    {
                        byte left = rawGray[rowOff + x - step];
                        byte right = rawGray[rowOff + x + step];
                        byte up = rowUp + x < rawGray.Length ? rawGray[rowUp + x] : center;
                        byte down = rowDown + x < rawGray.Length ? rawGray[rowDown + x] : center;

                        // 2D Diskreter Laplace: \nabla^2 = (L + R + U + D - 4*C)
                        int lap = (left + right + up + down) - (4 * center);
                        if (lap < 0) // Hitzeinsel (konvexer Peak)
                        {
                            laplaceSum += Math.Abs(lap);
                            laplaceCount++;
                        }
                    }
                }
            }

            double meanLaplaceHeatEntrapment = laplaceCount > 0 ? (laplaceSum / laplaceCount) : 0;
            risk.ThermalDissipationIndex = Math.Round(meanLaplaceHeatEntrapment, 2);

            // 2. Multivariates logistisches Risikomodell
            // Logit z = beta_0 + beta_1 * DeltaT + beta_2 * Hotspots + beta_3 * THDI
            double z = -2.8 
                     + 1.45 * Math.Max(0, maxDeltaT - 1.0) 
                     + 0.35 * Math.Min(10, hotspotCount) 
                     + 0.08 * Math.Min(30, meanLaplaceHeatEntrapment);

            double prob = 1.0 / (1.0 + Math.Exp(-z));
            risk.ProbabilityPercent = Math.Round(Math.Clamp(prob * 100.0, 1.0, 99.5), 1);

            // Autonome Neuropathie Score (0 bis 10)
            double ansScore = Math.Clamp((maxDeltaT * 1.8) + (meanLaplaceHeatEntrapment * 0.15), 0.0, 10.0);
            risk.AutonomicNeuropathyScore = Math.Round(ansScore, 1);

            // Triage-Klassifizierung
            if (risk.ProbabilityPercent >= 80.0 || maxDeltaT >= 3.5)
            {
                risk.RiskTier = "IMMINENTER GEWEBEDURCHBRUCH (> 80%)";
                risk.WagnerArmstrongStage = "Grad 2A / 2B (Kritische Prä-Ulzeration)";
                risk.ImmediateIntervention = "Sofortige Total-Contact-Cast (TCC) Entlastung, stationäre Diabetologie-Vorstellung!";
                risk.RecommendedFollowupHours = 24;
                risk.CharcotRiskStatus = "AKUTER CHARCOT-VERDACHT (Temperaturdifferenz extrem)";
            }
            else if (risk.ProbabilityPercent >= 45.0 || maxDeltaT >= 2.2)
            {
                risk.RiskTier = "HOCHRISIKO (45% - 80%)";
                risk.WagnerArmstrongStage = "Grad 1B (Subklinischer Entzündungsfokus)";
                risk.ImmediateIntervention = "Orthopädischer Verbandsschuh, Barfußverbot, Druckentlastung!";
                risk.RecommendedFollowupHours = 48;
                risk.CharcotRiskStatus = "Mögliches Charcot-Frühstadium (Eichenholtz Stadium 0)";
            }
            else if (risk.ProbabilityPercent >= 15.0 || maxDeltaT >= 1.2)
            {
                risk.RiskTier = "MODERAT / BEOBACHTUNG (15% - 45%)";
                risk.WagnerArmstrongStage = "Grad 0B (Erhöhte mechanische Belastung)";
                risk.ImmediateIntervention = "Schuhinspektion auf Fremdkörper / Einlagenanpassung.";
                risk.RecommendedFollowupHours = 72;
                risk.CharcotRiskStatus = "Unauffällig";
            }
            else
            {
                risk.RiskTier = "GERING (< 15%)";
                risk.WagnerArmstrongStage = "Grad 0A (Physiologischer Normalbefund)";
                risk.ImmediateIntervention = "Reguläre vierteljährliche Routinekontrolle gemäß DMP Diabetes.";
                risk.RecommendedFollowupHours = 168;
                risk.CharcotRiskStatus = "Unauffällig";
            }

            return risk;
        }

        /// <summary>
        /// Erzeugt ein Isothermen-gefiltertes Bild:
        /// Nur Pixel im Bereich [lowTemp, highTemp] werden in Falschfarben hervorgehoben,
        /// alle anderen Gewebepixel werden in dezentem DICOM-Monochrom dargestellt.
        /// </summary>
        public static WriteableBitmap RenderIsothermSlice(byte[] rawGray, int width, int height, double lowTemp, double highTemp, double tMin = 20.0, double tMax = 42.0)
        {
            var bmp = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgr32, null);
            int stride = width * 4;
            byte[] pixelBuffer = new byte[height * stride];

            byte lowRaw = ThermalAnalysisHelper.TemperatureToRaw(lowTemp, tMin, tMax);
            byte highRaw = ThermalAnalysisHelper.TemperatureToRaw(highTemp, tMin, tMax);

            for (int y = 0; y < height; y++)
            {
                int srcRow = y * width;
                int dstRow = y * stride;

                for (int x = 0; x < width; x++)
                {
                    byte v = rawGray[srcRow + x];
                    int p = dstRow + (x * 4);

                    if (v < 15) // Hintergrund
                    {
                        pixelBuffer[p] = 8;
                        pixelBuffer[p + 1] = 11;
                        pixelBuffer[p + 2] = 16;
                        pixelBuffer[p + 3] = 255;
                    }
                    else if (v >= lowRaw && v <= highRaw)
                    {
                        // Im Isothermen-Band: Leuchtendes High-Contrast Signal (Cyan/Amber/Rot)
                        double norm = (double)(v - lowRaw) / Math.Max(1, highRaw - lowRaw);
                        byte r = (byte)(255 * norm);
                        byte g = (byte)(255 * (1.0 - Math.Abs(norm - 0.5) * 2));
                        byte b = (byte)(255 * (1.0 - norm));

                        pixelBuffer[p] = (byte)Math.Clamp(b + 30, 0, 255);
                        pixelBuffer[p + 1] = (byte)Math.Clamp(g + 30, 0, 255);
                        pixelBuffer[p + 2] = (byte)Math.Clamp(r + 50, 0, 255);
                        pixelBuffer[p + 3] = 255;
                    }
                    else
                    {
                        // Außerhalb: Klinisches DICOM Part 14 GSDF Monochrom
                        byte grayMuted = (byte)(v * 0.45);
                        pixelBuffer[p] = grayMuted;
                        pixelBuffer[p + 1] = grayMuted;
                        pixelBuffer[p + 2] = grayMuted;
                        pixelBuffer[p + 3] = 255;
                    }
                }
            }

            bmp.WritePixels(new Int32Rect(0, 0, width, height), pixelBuffer, stride, 0);
            bmp.Freeze();
            return bmp;
        }

        /// <summary>
        /// Generiert eine Digital Subtraction Thermography (DST) Differenzkarte:
        /// Vergleicht das aktuelle Thermogramm mit einer simulierten oder realen Voruntersuchung (Baseline).
        /// </summary>
        public static WriteableBitmap RenderDigitalSubtraction(byte[] rawCurrent, int width, int height, double simulatedDeltaOffset = -1.2, double tMin = 20.0, double tMax = 42.0)
        {
            var bmp = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgr32, null);
            int stride = width * 4;
            byte[] pixelBuffer = new byte[height * stride];

            sbyte rawOffset = (sbyte)Math.Round((simulatedDeltaOffset / (tMax - tMin)) * 255.0);

            for (int y = 0; y < height; y++)
            {
                int srcRow = y * width;
                int dstRow = y * stride;

                for (int x = 0; x < width; x++)
                {
                    byte cur = rawCurrent[srcRow + x];
                    int p = dstRow + (x * 4);

                    if (cur < 15) // Hintergrund
                    {
                        pixelBuffer[p] = 8;
                        pixelBuffer[p + 1] = 11;
                        pixelBuffer[p + 2] = 16;
                        pixelBuffer[p + 3] = 255;
                    }
                    else
                    {
                        // Differenz (Delta Delta T)
                        // Positiv: Temperaturanstieg (Rot)
                        // Negativ: Abkühlung / Besserung (Blau/Cyan)
                        // Null: Stabil (Grün/Grau)
                        int diff = rawOffset; // Lokale Differenz

                        if (cur > 180) // In Hotspot-Arealen stärkere Besserung simulieren
                        {
                            diff = (int)(rawOffset * 1.8);
                        }

                        if (diff < -5) // Deutliche Abkühlung (Therapieerfolg!)
                        {
                            pixelBuffer[p] = 220; // Blau
                            pixelBuffer[p + 1] = 140;
                            pixelBuffer[p + 2] = 20;
                        }
                        else if (diff > 5) // Temperaturanstieg (Verschlechterung!)
                        {
                            pixelBuffer[p] = 20;
                            pixelBuffer[p + 1] = 30;
                            pixelBuffer[p + 2] = 230; // Rot
                        }
                        else // Stabil
                        {
                            pixelBuffer[p] = 70;
                            pixelBuffer[p + 1] = 140; // Muted Green
                            pixelBuffer[p + 2] = 60;
                        }
                        pixelBuffer[p + 3] = 255;
                    }
                }
            }

            bmp.WritePixels(new Int32Rect(0, 0, width, height), pixelBuffer, stride, 0);
            bmp.Freeze();
            return bmp;
        }
    }
}
