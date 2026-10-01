using System;
using System.Collections.Generic;
using System.Windows;

namespace Ignite.Desktop.Services
{
    public class ThermalProfileSample
    {
        public int Index { get; set; }
        public int X { get; set; }
        public int Y { get; set; }
        public double Distance { get; set; }
        public double Temperature { get; set; }
        public double Gradient { get; set; }
        public byte RawVal { get; set; }
    }

    public class ThermalProfileStats
    {
        public double MinTemp { get; set; }
        public double MaxTemp { get; set; }
        public double MeanTemp { get; set; }
        public double MaxGradient { get; set; }
        public double TotalLengthPx { get; set; }
        public int SampleCount { get; set; }
        public List<ThermalProfileSample> Samples { get; set; } = new();
    }

    public class ThermalProbePoint
    {
        public int Id { get; set; }
        public Point Position { get; set; }
        public byte RawVal { get; set; }
        public double Temperature { get; set; }
        public string Label { get; set; } = string.Empty;
    }

    public static class ThermalAnalysisHelper
    {
        public const double DefaultTMin = 20.0;
        public const double DefaultTMax = 42.0;

        public static double RawToTemperature(byte val, double tMin = DefaultTMin, double tMax = DefaultTMax)
        {
            return tMin + (val / 255.0) * (tMax - tMin);
        }

        public static byte TemperatureToRaw(double temp, double tMin = DefaultTMin, double tMax = DefaultTMax)
        {
            if (tMax <= tMin) return 0;
            double norm = (temp - tMin) / (tMax - tMin);
            return (byte)Math.Clamp((int)Math.Round(norm * 255.0), 0, 255);
        }

        public static ThermalProfileStats SampleProfileLine(
            byte[] rawGray,
            int width,
            int height,
            Point p1,
            Point p2,
            double tMin = DefaultTMin,
            double tMax = DefaultTMax)
        {
            var stats = new ThermalProfileStats();
            if (rawGray == null || rawGray.Length != width * height)
                return stats;

            double dx = p2.X - p1.X;
            double dy = p2.Y - p1.Y;
            double distance = Math.Sqrt(dx * dx + dy * dy);
            stats.TotalLengthPx = distance;

            int steps = Math.Max(2, (int)Math.Ceiling(distance));
            double minT = double.MaxValue;
            double maxT = double.MinValue;
            double sumT = 0.0;
            double maxGrad = 0.0;

            ThermalProfileSample? prevSample = null;

            for (int i = 0; i <= steps; i++)
            {
                double t = i / (double)steps;
                int x = (int)Math.Clamp(Math.Round(p1.X + t * dx), 0, width - 1);
                int y = (int)Math.Clamp(Math.Round(p1.Y + t * dy), 0, height - 1);

                byte raw = rawGray[y * width + x];
                double temp = RawToTemperature(raw, tMin, tMax);

                double dist = t * distance;
                double grad = 0.0;

                if (prevSample != null)
                {
                    double dDist = dist - prevSample.Distance;
                    if (dDist > 0.001)
                    {
                        grad = Math.Abs(temp - prevSample.Temperature) / dDist;
                        if (grad > maxGrad) maxGrad = grad;
                    }
                }

                if (temp < minT) minT = temp;
                if (temp > maxT) maxT = temp;
                sumT += temp;

                var sample = new ThermalProfileSample
                {
                    Index = i,
                    X = x,
                    Y = y,
                    Distance = dist,
                    Temperature = temp,
                    Gradient = grad,
                    RawVal = raw
                };
                stats.Samples.Add(sample);
                prevSample = sample;
            }

            stats.SampleCount = stats.Samples.Count;
            stats.MinTemp = stats.SampleCount > 0 ? minT : 0;
            stats.MaxTemp = stats.SampleCount > 0 ? maxT : 0;
            stats.MeanTemp = stats.SampleCount > 0 ? sumT / stats.SampleCount : 0;
            stats.MaxGradient = maxGrad;

            return stats;
        }

        public static ((int X, int Y, double Temp) Min, (int X, int Y, double Temp) Max) FindExtrema(
            byte[] rawGray,
            int width,
            int height,
            double tMin = DefaultTMin,
            double tMax = DefaultTMax,
            int[]? roi = null)
        {
            if (rawGray == null || rawGray.Length != width * height)
                return ((0, 0, 0), (0, 0, 0));

            int x0 = 0, y0 = 0, x1 = width, y1 = height;
            if (roi != null && roi.Length >= 4)
            {
                x0 = Math.Clamp(roi[0], 0, width);
                y0 = Math.Clamp(roi[1], 0, height);
                x1 = Math.Clamp(roi[2], 0, width);
                y1 = Math.Clamp(roi[3], 0, height);
            }

            byte minVal = 255;
            byte maxVal = 0;
            int minX = x0, minY = y0;
            int maxX = x0, maxY = y0;

            for (int y = y0; y < y1; y++)
            {
                int rowOff = y * width;
                for (int x = x0; x < x1; x++)
                {
                    byte v = rawGray[rowOff + x];
                    // Ignore extreme black background noise (< 15) for min calculation if possible
                    if (v > 15 && v < minVal)
                    {
                        minVal = v;
                        minX = x;
                        minY = y;
                    }
                    if (v > maxVal)
                    {
                        maxVal = v;
                        maxX = x;
                        maxY = y;
                    }
                }
            }

            if (minVal == 255 && maxVal == 0)
            {
                return ((0, 0, tMin), (0, 0, tMax));
            }

            return (
                (minX, minY, RawToTemperature(minVal, tMin, tMax)),
                (maxX, maxY, RawToTemperature(maxVal, tMin, tMax))
            );
        }

        public static (double DeltaT, bool IsPathologic, string StatusText) EvaluateBilateralDelta(double t1, double t2)
        {
            double delta = Math.Round(Math.Abs(t1 - t2), 2);
            bool isPathologic = delta >= 2.2;
            string text = isPathologic
                ? $"⚠️ PATHOLOGISCH: ΔT = {delta:F1} K (≥ 2.2 K Armstrong-Kriterium). Hohes Ulkus-/Entzündungsrisiko!"
                : $"✅ PHYSIOLOGISCH: ΔT = {delta:F1} K (< 2.2 K). Keine pathologische Hyperthermie-Asymmetrie.";

            return (delta, isPathologic, text);
        }
    }
}
