using System;
using System.Windows;

namespace Ignite.Desktop.Services
{
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

    /// <summary>
    /// Orthopädischer Winkelmessdienst für Fußdeformitäten (Hallux Valgus HVA / Intermetatarsal-Winkel IMA).
    /// </summary>
    public static class OrthopedicGoniometerService
    {
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
    }
}
