using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Media;

namespace Ignite.Desktop.Services
{
    public class OsteoBoneEntity
    {
        public string Id { get; set; } = string.Empty;
        public string LatinName { get; set; } = string.Empty;
        public string CommonName { get; set; } = string.Empty;
        public string AnatomicalRegion { get; set; } = "Vorfuß";
        public List<List<Point>> RelativePolygons { get; set; } = new();
        
        public double MeanTemp { get; set; }
        public double MaxTemp { get; set; }
        public double MinTemp { get; set; }
        public double DeltaT { get; set; }
        public int PixelCount { get; set; }
        public string RiskLevel { get; set; } = "PHYSIOLOGISCH";
        public string Recommendation { get; set; } = "Keine Entlastungsindikation";
        public Color StressColor { get; set; } = Color.FromRgb(2, 132, 199);
        public Brush StressBrush => new SolidColorBrush(StressColor);
        public Brush StressFillBrush => new SolidColorBrush(Color.FromArgb(55, StressColor.R, StressColor.G, StressColor.B));
    }

    public class GoniometerMeasurement
    {
        public Point Point1 { get; set; } // MT-I Schaft
        public Point Point2 { get; set; } // MTP-I Gelenkzentrum (Scheitelpunkt)
        public Point Point3 { get; set; } // Hallux Endglied
        public double AngleDegrees { get; set; }
        public double RawAngle { get; set; }
        public string Classification { get; set; } = "Physiologisch";
        public string SeverityGrade { get; set; } = "Grad 0";
        public string ClinicalIndication { get; set; } = "Keine operative Indikation";
        public bool IsPathologic { get; set; }
    }

    public class OsteoThermalMatrixReport
    {
        public List<OsteoBoneEntity> Bones { get; set; } = new();
        public double GlobalBaselineTemp { get; set; }
        public double MaxBoneTemp { get; set; }
        public OsteoBoneEntity? HighestRiskBone { get; set; }
        public double CharcotInflammatoryIndex { get; set; }
        public string CharcotRiskStatus { get; set; } = "Unauffällig";
        public GoniometerMeasurement? Goniometer { get; set; }
        public int TotalBonesSampled { get; set; }
    }

    public static class OsteoThermalService
    {
        public static List<OsteoBoneEntity> CreateStandardFootSkeletonEntities()
        {
            var list = new List<OsteoBoneEntity>();

            // --- 1. OS METATARSALE I & MTP-I GELENK ---
            list.Add(new OsteoBoneEntity
            {
                Id = "MT1",
                LatinName = "Os metatarsale I (MTP-I)",
                CommonName = "1. Mittelfußknochen & Grundgelenk",
                AnatomicalRegion = "Vorfuß (Hauptlastzone I)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(46, -97), new(48, -85), new(39, -70), new(37, -35), new(40, -18), new(20, -18), new(22, -35), new(22, -70), new(19, -85), new(21, -97) }
                }
            });

            // --- 2. DIGITUS I (HALLUX PHALANGEN) ---
            list.Add(new OsteoBoneEntity
            {
                Id = "DIG1",
                LatinName = "Phalanges hallucis I",
                CommonName = "Großzehe (Grund- & Endglied)",
                AnatomicalRegion = "Zehenstrahl I",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(37, -190), new(48, -172), new(46, -154), new(27, -154), new(25, -172) },
                    new() { new(44, -147), new(40, -125), new(45, -104), new(26, -104), new(30, -125), new(26, -147) }
                }
            });

            // --- 3. OS METATARSALE II ---
            list.Add(new OsteoBoneEntity
            {
                Id = "MT2",
                LatinName = "Os metatarsale II (MTP-II)",
                CommonName = "2. Mittelfußknochen (Transferzone)",
                AnatomicalRegion = "Vorfuß (Lastzone II)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(17, -102), new(15, -60), new(15, -18), new(7, -18), new(7, -60), new(7, -102) }
                }
            });

            // --- 4. DIGITUS II (PHALANGEN II) ---
            list.Add(new OsteoBoneEntity
            {
                Id = "DIG2",
                LatinName = "Phalanges digiti II",
                CommonName = "2. Zehe (Zehenkuppe & Mittelglied)",
                AnatomicalRegion = "Zehenstrahl II",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(14, -180), new(17, -168), new(17, -158), new(9, -158), new(9, -168) },
                    new() { new(16, -152), new(17, -140), new(9, -140), new(9, -152) },
                    new() { new(17, -135), new(15, -120), new(17, -108), new(8, -108), new(9, -120), new(8, -135) }
                }
            });

            // --- 5. OS METATARSALE III ---
            list.Add(new OsteoBoneEntity
            {
                Id = "MT3",
                LatinName = "Os metatarsale III (MTP-III)",
                CommonName = "3. Mittelfußknochen",
                AnatomicalRegion = "Vorfuß (Zentral)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(-3, -98), new(-4, -58), new(-4, -16), new(-13, -16), new(-12, -58), new(-13, -98) }
                }
            });

            // --- 6. OS METATARSALE IV ---
            list.Add(new OsteoBoneEntity
            {
                Id = "MT4",
                LatinName = "Os metatarsale IV (MTP-IV)",
                CommonName = "4. Mittelfußknochen",
                AnatomicalRegion = "Vorfuß (Lateral)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(-22, -94), new(-24, -54), new(-24, -14), new(-34, -14), new(-34, -54), new(-33, -94) }
                }
            });

            // --- 7. OS METATARSALE V & TUBEROSITAS ---
            list.Add(new OsteoBoneEntity
            {
                Id = "MT5",
                LatinName = "Os metatarsale V (MTP-V)",
                CommonName = "5. Mittelfußknochen & Tuberositas",
                AnatomicalRegion = "Vorfuß (Laterale Lastsäule)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(-42, -88), new(-46, -50), new(-47, -10), new(-64, -20), new(-65, -35), new(-56, -55), new(-53, -88) }
                }
            });

            // --- 8. TARSUS MEDIALIS (OSSA CUNEIFORMIA & NAVICULARE - CHARCOT ZONE) ---
            list.Add(new OsteoBoneEntity
            {
                Id = "TARS_MED",
                LatinName = "Ossa cuneiformia & Os naviculare",
                CommonName = "Mediale Fußwurzel (Kahnbein & Keilbeine)",
                AnatomicalRegion = "Mittelfuß (Charcot-Prädilektion)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(37, -14), new(39, 12), new(19, 12), new(18, -14) },
                    new() { new(15, -14), new(15, 10), new(4, 10), new(5, -14) },
                    new() { new(35, 16), new(34, 44), new(-9, 44), new(-11, 16) }
                }
            });

            // --- 9. TARSUS LATERALIS (OS CUBOIDEUM & CUNEIFORME III) ---
            list.Add(new OsteoBoneEntity
            {
                Id = "TARS_LAT",
                LatinName = "Os cuboideum & Cuneiforme lat.",
                CommonName = "Laterale Fußwurzel (Würfelbein)",
                AnatomicalRegion = "Mittelfuß (Laterale Säule)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(2, -12), new(2, 12), new(-14, 12), new(-13, -12) },
                    new() { new(-18, -10), new(-15, 32), new(-45, 32), new(-50, -10) }
                }
            });

            // --- 10. TALUS ---
            list.Add(new OsteoBoneEntity
            {
                Id = "TAL",
                LatinName = "Talus",
                CommonName = "Sprungbein (Oberes Sprunggelenk)",
                AnatomicalRegion = "Rückfuß (Gelenkachse)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(25, 48), new(24, 85), new(-18, 85), new(-14, 48) }
                }
            });

            // --- 11. CALCANEUS ---
            list.Add(new OsteoBoneEntity
            {
                Id = "CALC",
                LatinName = "Calcaneus",
                CommonName = "Fersenbein (Tuber calcanei)",
                AnatomicalRegion = "Rückfuß (Plantarer Fersensporn)",
                RelativePolygons = new List<List<Point>>
                {
                    new() { new(18, 88), new(14, 160), new(-32, 160), new(-34, 88) }
                }
            });

            return list;
        }

        /// <summary>
        /// Führt die radiometrische Beprobung aller anatomischen Knochen- und Gelenkstrukturen durch.
        /// </summary>
        public static OsteoThermalMatrixReport ComputeOsteoThermalMatrix(
            byte[] rawGray,
            int width,
            int height,
            double cx,
            double cy,
            double scale,
            bool isLeftFoot,
            double tMin = 20.0,
            double tMax = 42.0)
        {
            var report = new OsteoThermalMatrixReport();
            if (rawGray == null || rawGray.Length == 0 || width <= 0 || height <= 0)
                return report;

            // 1. Globale Fuß-Baseline bestimmen (Tissue Pixels > 20)
            long globalSum = 0;
            int globalCount = 0;
            for (int i = 0; i < rawGray.Length; i++)
            {
                byte b = rawGray[i];
                if (b > 20) // Tissue mask threshold
                {
                    globalSum += b;
                    globalCount++;
                }
            }
            double globalMeanByte = globalCount > 0 ? (double)globalSum / globalCount : 128.0;
            report.GlobalBaselineTemp = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp(globalMeanByte, 0, 255), tMin, tMax);

            var bones = CreateStandardFootSkeletonEntities();
            double sign = isLeftFoot ? -1.0 : 1.0;

            Point TransformPt(Point rp) => new Point(cx + (rp.X * scale * sign), cy + (rp.Y * scale));

            double maxOverallTemp = double.MinValue;
            OsteoBoneEntity? highestBone = null;
            double tarsusMean = 0;
            int tarsusCount = 0;
            double calcaneusMean = 0;

            foreach (var bone in bones)
            {
                long boneSum = 0;
                int boneCount = 0;
                byte boneMin = 255;
                byte boneMax = 0;

                foreach (var poly in bone.RelativePolygons)
                {
                    if (poly.Count < 3) continue;

                    // Konvertiere in absolute Bildkoordinaten
                    var absPts = poly.Select(TransformPt).ToList();

                    // Bounding Box des Polygons
                    double bMinX = absPts.Min(p => p.X);
                    double bMaxX = absPts.Max(p => p.X);
                    double bMinY = absPts.Min(p => p.Y);
                    double bMaxY = absPts.Max(p => p.Y);

                    int x0 = Math.Clamp((int)Math.Floor(bMinX), 0, width - 1);
                    int x1 = Math.Clamp((int)Math.Ceiling(bMaxX), 0, width - 1);
                    int y0 = Math.Clamp((int)Math.Floor(bMinY), 0, height - 1);
                    int y1 = Math.Clamp((int)Math.Ceiling(bMaxY), 0, height - 1);

                    for (int y = y0; y <= y1; y++)
                    {
                        int rowOff = y * width;
                        for (int x = x0; x <= x1; x++)
                        {
                            var testPt = new Point(x + 0.5, y + 0.5);
                            if (IsPointInPolygon(absPts, testPt))
                            {
                                byte val = rawGray[rowOff + x];
                                boneSum += val;
                                boneCount++;
                                if (val < boneMin) boneMin = val;
                                if (val > boneMax) boneMax = val;
                            }
                        }
                    }
                }

                bone.PixelCount = boneCount;
                if (boneCount > 0)
                {
                    double avgRaw = (double)boneSum / boneCount;
                    bone.MeanTemp = Math.Round(ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp(avgRaw, 0, 255), tMin, tMax), 1);
                    bone.MaxTemp = Math.Round(ThermalAnalysisHelper.RawToTemperature(boneMax, tMin, tMax), 1);
                    bone.MinTemp = Math.Round(ThermalAnalysisHelper.RawToTemperature(boneMin, tMin, tMax), 1);
                }
                else
                {
                    bone.MeanTemp = report.GlobalBaselineTemp;
                    bone.MaxTemp = report.GlobalBaselineTemp;
                    bone.MinTemp = report.GlobalBaselineTemp;
                }

                bone.DeltaT = Math.Round(bone.MeanTemp - report.GlobalBaselineTemp, 1);

                // Klinische Einstufung nach IWGDF 2023 & Armstrong Kriterien
                if (bone.DeltaT >= 3.0)
                {
                    bone.RiskLevel = "AKUT KRITISCH (≥ 3.0 K)";
                    bone.Recommendation = "Sofortige Totalentlastung (TCC / Walker), Charcot-/Ulkusausschluss";
                    bone.StressColor = Color.FromRgb(220, 38, 38); // Red-600
                }
                else if (bone.DeltaT >= 2.2)
                {
                    bone.RiskLevel = "ARMSTRONG-ALARM (≥ 2.2 K)";
                    bone.Recommendation = "Druckentlastungsschuh, engmaschige 48h-Kontrolle";
                    bone.StressColor = Color.FromRgb(239, 68, 68); // Red-500
                }
                else if (bone.DeltaT >= 1.2)
                {
                    bone.RiskLevel = "HYPERTHERMIE-STRESS";
                    bone.Recommendation = "Orthopädische Druckverteilungs-Einlage prüfen";
                    bone.StressColor = Color.FromRgb(217, 119, 6); // Amber-600
                }
                else
                {
                    bone.RiskLevel = "PHYSIOLOGISCH NORMAL";
                    bone.Recommendation = "Regulärer Befund, keine Entlastungsindikation";
                    bone.StressColor = Color.FromRgb(2, 132, 199); // Cyan-600
                }

                if (bone.MeanTemp > maxOverallTemp)
                {
                    maxOverallTemp = bone.MeanTemp;
                    highestBone = bone;
                }

                if (bone.Id == "TARS_MED" || bone.Id == "TARS_LAT")
                {
                    tarsusMean += bone.MeanTemp;
                    tarsusCount++;
                }
                else if (bone.Id == "CALC")
                {
                    calcaneusMean = bone.MeanTemp;
                }
            }

            report.Bones = bones;
            report.TotalBonesSampled = bones.Count;
            report.MaxBoneTemp = maxOverallTemp > double.MinValue ? maxOverallTemp : report.GlobalBaselineTemp;
            report.HighestRiskBone = highestBone;

            // 3. Charcot Inflammatory Index (CII)
            if (tarsusCount > 0 && calcaneusMean > 0)
            {
                double avgTarsus = tarsusMean / tarsusCount;
                report.CharcotInflammatoryIndex = Math.Round(avgTarsus - calcaneusMean, 1);
                if (report.CharcotInflammatoryIndex >= 2.2)
                {
                    report.CharcotRiskStatus = "AKUTER CHARCOT-VERDACHT (Eichenholtz 0/1)";
                }
                else if (report.CharcotInflammatoryIndex >= 1.2)
                {
                    report.CharcotRiskStatus = "Mäßige Mittelfuß-Reizung (Beobachtung)";
                }
                else
                {
                    report.CharcotRiskStatus = "Physiologisch (Kein Charcot-Anhalt)";
                }
            }

            return report;
        }

        /// <summary>
        /// Berechnet den orthopädischen Hallux-Valgus-Winkel (HVA) oder Intermetatarsal-Winkel (IMA) über 3 Messpunkte.
        /// </summary>
        public static GoniometerMeasurement CalculateGoniometer(Point p1, Point p2, Point p3)
        {
            var meas = new GoniometerMeasurement
            {
                Point1 = p1,
                Point2 = p2,
                Point3 = p3
            };

            // Vektoren ausgehend vom Scheitelpunkt P2 (MTP-I Gelenkzentrum)
            double uX = p1.X - p2.X;
            double uY = p1.Y - p2.Y;
            double vX = p3.X - p2.X;
            double vY = p3.Y - p2.Y;

            double lenU = Math.Sqrt(uX * uX + uY * uY);
            double lenV = Math.Sqrt(vX * vX + vY * vY);

            if (lenU < 1.0 || lenV < 1.0)
            {
                meas.AngleDegrees = 0;
                meas.Classification = "Ungültige Messpunkte (zu geringer Abstand)";
                return meas;
            }

            double dot = (uX * vX + uY * vY) / (lenU * lenV);
            dot = Math.Clamp(dot, -1.0, 1.0);

            double angleRad = Math.Acos(dot);
            double angleDeg = angleRad * (180.0 / Math.PI);
            meas.RawAngle = Math.Round(angleDeg, 1);

            // In der Orthopädie wird der Abweichungswinkel vom geraden Strahl (180°) als Hallux Valgus Winkel definiert
            double hva = Math.Abs(180.0 - angleDeg);
            meas.AngleDegrees = Math.Round(hva, 1);

            if (hva < 15.0)
            {
                meas.Classification = "Normalbefund / Physiologische Zehenachse";
                meas.SeverityGrade = "Grad 0 (Normal)";
                meas.ClinicalIndication = "Keine Therapieindikation, physiologische Ausrichtung";
                meas.IsPathologic = false;
            }
            else if (hva <= 20.0)
            {
                meas.Classification = "Leichte Hallux-Valgus-Fehlstellung";
                meas.SeverityGrade = "Grad I (Leicht)";
                meas.ClinicalIndication = "Konservative Therapie: Hallux-Valgus-Schiene / Zehenspreizer, Fußgymnastik";
                meas.IsPathologic = true;
            }
            else if (hva <= 39.0)
            {
                meas.Classification = "Mäßiggradiger Hallux Valgus";
                meas.SeverityGrade = "Grad II (Mäßig)";
                meas.ClinicalIndication = "Operative Indikation: Distale Metatarsale-Osteotomie (Chevron / Austin / Scarf)";
                meas.IsPathologic = true;
            }
            else
            {
                meas.Classification = "Schwere Hallux-Valgus-Deformität";
                meas.SeverityGrade = "Grad III (Schwer)";
                meas.ClinicalIndication = "Operative Indikation: Basisosteotomie oder TMT-1-Arthrodese (Lapidus-Operation)";
                meas.IsPathologic = true;
            }

            return meas;
        }

        /// <summary>
        /// Standard Point-in-Polygon Ray Casting Algorithmus.
        /// </summary>
        private static bool IsPointInPolygon(List<Point> polygon, Point point)
        {
            bool isInside = false;
            int n = polygon.Count;
            for (int i = 0, j = n - 1; i < n; j = i++)
            {
                if (((polygon[i].Y > point.Y) != (polygon[j].Y > point.Y)) &&
                    (point.X < (polygon[j].X - polygon[i].X) * (point.Y - polygon[i].Y) / (polygon[j].Y - polygon[i].Y) + polygon[i].X))
                {
                    isInside = !isInside;
                }
            }
            return isInside;
        }
    }
}
