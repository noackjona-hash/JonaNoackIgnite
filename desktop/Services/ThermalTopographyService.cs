using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Ignite.Desktop.Services
{
    public class ThermalHistogramData
    {
        public int[] Bins { get; set; } = new int[256];
        public int MaxBinCount { get; set; }
        public int TotalTissuePixels { get; set; }
        public double MinTemp { get; set; }
        public double MaxTemp { get; set; }
        public double MeanTemp { get; set; }
        public double MedianTemp { get; set; }
        public double MadTemp { get; set; }
        public double OutlierThresholdTemp { get; set; }
        public byte OutlierThresholdRaw { get; set; }
    }

    public class AnatomicalZoneMetric
    {
        public string ZoneName { get; set; } = string.Empty;
        public string AnatomicalLocation { get; set; } = string.Empty;
        public double MeanTempLeft { get; set; }
        public double MeanTempRight { get; set; }
        public double DeltaT { get; set; }
        public bool IsCritical { get; set; }
        public string RiskAssessment { get; set; } = string.Empty;
    }

    public static class ThermalTopographyService
    {
        public static ThermalHistogramData ComputeHistogram(byte[] rawGray, int width, int height, double kFactor = 3.0, double tMin = 20.0, double tMax = 42.0)
        {
            var data = new ThermalHistogramData();
            if (rawGray == null || rawGray.Length == 0) return data;

            int[] bins = new int[256];
            int tissuePixels = 0;
            long sumRaw = 0;
            byte minRaw = 255;
            byte maxRaw = 0;

            for (int i = 0; i < rawGray.Length; i++)
            {
                byte v = rawGray[i];
                if (v > 15) // Tissue threshold (exclude dark background)
                {
                    bins[v]++;
                    tissuePixels++;
                    sumRaw += v;
                    if (v < minRaw) minRaw = v;
                    if (v > maxRaw) maxRaw = v;
                }
            }

            data.Bins = bins;
            data.TotalTissuePixels = tissuePixels;

            int maxCount = 0;
            for (int i = 0; i < 256; i++)
            {
                if (bins[i] > maxCount) maxCount = bins[i];
            }
            data.MaxBinCount = maxCount;

            if (tissuePixels > 0)
            {
                data.MinTemp = ThermalAnalysisHelper.RawToTemperature(minRaw, tMin, tMax);
                data.MaxTemp = ThermalAnalysisHelper.RawToTemperature(maxRaw, tMin, tMax);
                double meanRaw = (double)sumRaw / tissuePixels;
                data.MeanTemp = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(meanRaw), 0, 255), tMin, tMax);

                // Compute Median
                int half = tissuePixels / 2;
                int accum = 0;
                byte medianRaw = minRaw;
                for (int i = minRaw; i <= maxRaw; i++)
                {
                    accum += bins[i];
                    if (accum >= half)
                    {
                        medianRaw = (byte)i;
                        break;
                    }
                }
                data.MedianTemp = ThermalAnalysisHelper.RawToTemperature(medianRaw, tMin, tMax);

                // Compute MAD (Median Absolute Deviation)
                int[] devBins = new int[256];
                for (int i = 0; i < rawGray.Length; i++)
                {
                    byte v = rawGray[i];
                    if (v > 15)
                    {
                        int dev = Math.Abs(v - medianRaw);
                        devBins[dev]++;
                    }
                }
                int devHalf = tissuePixels / 2;
                int devAccum = 0;
                int madRaw = 0;
                for (int d = 0; d < 256; d++)
                {
                    devAccum += devBins[d];
                    if (devAccum >= devHalf)
                    {
                        madRaw = d;
                        break;
                    }
                }

                double madScale = 1.4826 * madRaw;
                data.MadTemp = (madScale / 255.0) * (tMax - tMin);

                int cutoffRaw = (int)Math.Round(medianRaw + kFactor * madScale);
                data.OutlierThresholdRaw = (byte)Math.Clamp(cutoffRaw, 0, 255);
                data.OutlierThresholdTemp = ThermalAnalysisHelper.RawToTemperature(data.OutlierThresholdRaw, tMin, tMax);
            }

            return data;
        }

        // Generates an Isometric 2.5D Thermal Relief Topographic Map
        // Hot areas are projected upward with pseudo-3D hillshading and altitude color ramps
        public static BitmapSource Generate3DReliefMap(byte[] rawGray, int width, int height, ColorPalette palette, double elevationScale = 0.35)
        {
            if (rawGray == null || width <= 0 || height <= 0)
                throw new ArgumentException("Invalid raw pixel data");

            // Subsample for fast interactive rendering (step 2)
            int step = 2;
            int outW = width;
            int outH = height;

            uint[] outPixels = new uint[outW * outH];
            // Clear to dark obsidian
            for (int i = 0; i < outPixels.Length; i++) outPixels[i] = 0xFF080B12;

            double cos30 = Math.Cos(Math.PI / 6.0);
            double sin30 = Math.Sin(Math.PI / 6.0);

            // Shading directional light from top-left (dx = -1, dy = -1, dz = 1.5)
            for (int y = 1; y < height - 1; y += step)
            {
                int rowOff = y * width;
                for (int x = 1; x < width - 1; x += step)
                {
                    byte v = rawGray[rowOff + x];
                    if (v <= 15) continue; // Skip cold background

                    // Surface normal via central differences
                    double dzdx = (rawGray[rowOff + x + 1] - rawGray[rowOff + x - 1]) * 0.5;
                    double dzdy = (rawGray[(y + 1) * width + x] - rawGray[(y - 1) * width + x]) * 0.5;

                    // Diffuse lighting intensity
                    double nx = -dzdx * 0.15;
                    double ny = -dzdy * 0.15;
                    double nz = 1.0;
                    double len = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                    nx /= len; ny /= len; nz /= len;

                    // Light source (-0.57, -0.57, 0.57)
                    double dot = Math.Max(0.2, (nx * (-0.57) + ny * (-0.57) + nz * 0.57));

                    // Elevation offset
                    int elevation = (int)Math.Round((v - 15) * elevationScale);
                    int projX = x;
                    int projY = Math.Clamp(y - elevation, 0, outH - 1);

                    // Color from palette
                    uint baseColor = GetPaletteColor(v, palette);
                    byte r = (byte)((baseColor >> 16) & 0xFF);
                    byte g = (byte)((baseColor >> 8) & 0xFF);
                    byte b = (byte)(baseColor & 0xFF);

                    // Apply hillshading illumination
                    byte shadedR = (byte)Math.Clamp((int)(r * dot * 1.3), 0, 255);
                    byte shadedG = (byte)Math.Clamp((int)(g * dot * 1.3), 0, 255);
                    byte shadedB = (byte)Math.Clamp((int)(b * dot * 1.3), 0, 255);

                    uint shadedCol = (uint)((255 << 24) | (shadedR << 16) | (shadedG << 8) | shadedB);

                    // Draw a 2x2 footprint for smooth volume
                    for (int dy = 0; dy < step && (projY + dy) < outH; dy++)
                    {
                        int pRow = (projY + dy) * outW;
                        for (int dx = 0; dx < step && (projX + dx) < outW; dx++)
                        {
                            outPixels[pRow + projX + dx] = shadedCol;
                        }
                    }
                }
            }

            var bmp = new WriteableBitmap(outW, outH, 96, 96, PixelFormats.Bgra32, null);
            bmp.WritePixels(new Int32Rect(0, 0, outW, outH), outPixels, outW * 4, 0);
            bmp.Freeze();
            return bmp;
        }

        private static uint GetPaletteColor(byte val, ColorPalette palette)
        {
            double t = val / 255.0;
            if (palette == ColorPalette.Inferno)
            {
                byte r = (byte)Math.Min(255, Math.Max(0, 255 * (t * 1.5)));
                byte g = (byte)Math.Min(255, Math.Max(0, 255 * (Math.Pow(t, 2) * 1.2)));
                byte b = (byte)Math.Min(255, Math.Max(0, 255 * (Math.Pow(t, 3) * 1.5)));
                return (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }
            if (palette == ColorPalette.Rainbow)
            {
                byte r = (byte)(Math.Sin(t * Math.PI - Math.PI / 2) * 127 + 128);
                byte g = (byte)(Math.Sin(t * Math.PI) * 255);
                byte b = (byte)(Math.Cos(t * Math.PI / 2) * 255);
                return (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }

            // Default Ironbow
            if (t < 0.2) return (uint)((255 << 24) | ((int)(t / 0.2 * 30) << 16) | (int)(t / 0.2 * 128));
            if (t < 0.4) return (uint)((255 << 24) | ((int)(30 + ((t - 0.2) / 0.2) * 130) << 16) | 128);
            if (t < 0.7) return (uint)((255 << 24) | (220 << 16) | ((int)(((t - 0.4) / 0.3) * 150) << 8));
            if (t < 0.9) return (uint)((255 << 24) | (255 << 16) | ((int)(150 + ((t - 0.7) / 0.2) * 95) << 8));
            return (uint)((255 << 24) | (255 << 16) | (255 << 8) | (int)(((t - 0.9) / 0.1) * 255));
        }

        // Computes Armstrong 5-Zone Clinical Anatomical Foot Breakdown
        public static List<AnatomicalZoneMetric> ComputeAnatomicalZones(byte[] rawGray, int width, int height)
        {
            var list = new List<AnatomicalZoneMetric>();
            if (rawGray == null || width <= 0 || height <= 0) return list;

            int midX = width / 2;

            // Define 5 clinical zones along vertical axis:
            // 1. Hallux & Digiti (Top 0% - 22%)
            // 2. Metatarsal Heads I-II Medial (22% - 42%, Medial)
            // 3. Metatarsal Heads III-V Lateral (22% - 42%, Lateral)
            // 4. Plantar Arch / Midfoot (42% - 70%)
            // 5. Calcaneus / Heel (70% - 95%)

            var zones = new (string Name, string Loc, double y0, double y1, double xRel0, double xRel1)[]
            {
                ("Zone 1: Hallux & Digiti", "Großzehe & Zehenkuppen (distal)", 0.05, 0.25, 0.1, 0.9),
                ("Zone 2: Metatarsale I-II", "Ballen medial (hohe Druckbelastung)", 0.25, 0.45, 0.4, 0.9),
                ("Zone 3: Metatarsale III-V", "Ballen lateral", 0.25, 0.45, 0.1, 0.45),
                ("Zone 4: Plantargewölbe", "Mittelfuß / Fußinnenwölbung", 0.45, 0.72, 0.15, 0.85),
                ("Zone 5: Calcaneus", "Fersenkissen (proximal)", 0.72, 0.95, 0.2, 0.8)
            };

            foreach (var z in zones)
            {
                int rY0 = (int)(z.y0 * height);
                int rY1 = (int)(z.y1 * height);

                // Sample Left Limb (x: 0 to midX)
                long leftSum = 0; int leftCount = 0;
                int leftX0 = (int)(z.xRel0 * midX);
                int leftX1 = (int)(z.xRel1 * midX);

                for (int y = rY0; y < rY1; y++)
                {
                    int off = y * width;
                    for (int x = leftX0; x < leftX1; x++)
                    {
                        byte v = rawGray[off + x];
                        if (v > 15) { leftSum += v; leftCount++; }
                    }
                }

                // Sample Right Limb (x: midX to width)
                long rightSum = 0; int rightCount = 0;
                int rightX0 = midX + (int)(z.xRel0 * (width - midX));
                int rightX1 = midX + (int)(z.xRel1 * (width - midX));

                for (int y = rY0; y < rY1; y++)
                {
                    int off = y * width;
                    for (int x = rightX0; x < rightX1; x++)
                    {
                        byte v = rawGray[off + x];
                        if (v > 15) { rightSum += v; rightCount++; }
                    }
                }

                double leftT = leftCount > 0 ? ThermalAnalysisHelper.RawToTemperature((byte)(leftSum / leftCount)) : 30.0;
                double rightT = rightCount > 0 ? ThermalAnalysisHelper.RawToTemperature((byte)(rightSum / rightCount)) : 30.0;

                double dt = Math.Round(Math.Abs(leftT - rightT), 1);
                bool crit = dt >= 2.2;

                list.Add(new AnatomicalZoneMetric
                {
                    ZoneName = z.Name,
                    AnatomicalLocation = z.Loc,
                    MeanTempLeft = Math.Round(leftT, 1),
                    MeanTempRight = Math.Round(rightT, 1),
                    DeltaT = dt,
                    IsCritical = crit,
                    RiskAssessment = crit ? "⚠️ PATHOLOGISCH (ΔT ≥ 2.2 K) — Hohes Ulkusrisiko" : "✅ PHYSIOLOGISCH NORMAL"
                });
            }

            return list;
        }
    }
}
