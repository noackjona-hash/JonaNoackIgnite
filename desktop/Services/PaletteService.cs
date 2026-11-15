using System;
using System.IO;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace Ignite.Desktop.Services
{
    public enum ColorPalette
    {
        Ironbow,
        Rainbow,
        Inferno,
        Grayscale,
        Viridis,
        Turbo,
        ArcticIschemia
    }

    public enum VeinRenderMode
    {
        FluorescentCyan,   // Glowing Cyan (#00E5FF) on thermal image
        RoyalCobalt,       // Deep Cobalt Blue (#1E88E5)
        SurgicalGreen,     // ICG Fluorescence Green (#00E676)
        PureAngiography    // Digital Subtraction Angiography (Black background, luminous vessels)
    }

    public static class PaletteService
    {
        private static readonly uint[] IronbowLUT = GenerateIronbowLUT();
        private static readonly uint[] RainbowLUT = GenerateRainbowLUT();
        private static readonly uint[] InfernoLUT = GenerateInfernoLUT();
        private static readonly uint[] ViridisLUT = GenerateViridisLUT();
        private static readonly uint[] TurboLUT = GenerateTurboLUT();
        private static readonly uint[] ArcticIschemiaLUT = GenerateArcticIschemiaLUT();

        private static uint[] GenerateGradientLUT((double pos, byte r, byte g, byte b)[] stops)
        {
            var lut = new uint[256];
            for (int i = 0; i < 256; i++)
            {
                double t = i / 255.0;
                int seg = 0;
                while (seg < stops.Length - 2 && t > stops[seg + 1].pos)
                    seg++;

                var s0 = stops[seg];
                var s1 = stops[seg + 1];
                double span = Math.Max(1e-6, s1.pos - s0.pos);
                double f = Math.Clamp((t - s0.pos) / span, 0.0, 1.0);

                byte r = (byte)Math.Clamp((int)Math.Round(s0.r + (s1.r - s0.r) * f), 0, 255);
                byte g = (byte)Math.Clamp((int)Math.Round(s0.g + (s1.g - s0.g) * f), 0, 255);
                byte b = (byte)Math.Clamp((int)Math.Round(s0.b + (s1.b - s0.b) * f), 0, 255);
                lut[i] = (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }
            return lut;
        }

        private static uint[] GenerateViridisLUT() => GenerateGradientLUT(new (double, byte, byte, byte)[]
        {
            (0.00, 0x44, 0x01, 0x54),
            (0.25, 0x3B, 0x52, 0x8B),
            (0.50, 0x21, 0x91, 0x8C),
            (0.75, 0x5E, 0xC9, 0x62),
            (1.00, 0xFD, 0xE7, 0x25)
        });

        private static uint[] GenerateTurboLUT() => GenerateGradientLUT(new (double, byte, byte, byte)[]
        {
            (0.00, 0x30, 0x12, 0x3B),
            (0.17, 0x46, 0x85, 0xFA),
            (0.34, 0x1A, 0xE4, 0xB6),
            (0.52, 0xA4, 0xFC, 0x3C),
            (0.70, 0xFA, 0xBA, 0x39),
            (0.86, 0xE4, 0x46, 0x0A),
            (1.00, 0x7A, 0x04, 0x03)
        });

        private static uint[] GenerateArcticIschemiaLUT() => GenerateGradientLUT(new (double, byte, byte, byte)[]
        {
            (0.00, 0x00, 0xF0, 0xFF), // Luminous hypothermic ice-cyan
            (0.20, 0x0E, 0xA5, 0xE9),
            (0.38, 0x02, 0x84, 0xC7), // Medical ischemia cobalt boundary
            (0.40, 0x33, 0x41, 0x55), // Normothermic muted slate
            (0.74, 0x64, 0x74, 0x8B),
            (0.76, 0xF5, 0x9E, 0x0B), // Hyperthermic amber transition
            (1.00, 0xEF, 0x44, 0x44)  // Focal inflammatory coral/crimson
        });

        private static uint[] GenerateIronbowLUT()
        {
            var lut = new uint[256];
            for (int i = 0; i < 256; i++)
            {
                double t = i / 255.0;
                byte r, g, b;
                if (t < 0.2)
                {
                    r = (byte)(t / 0.2 * 30);
                    g = 0;
                    b = (byte)(t / 0.2 * 128);
                }
                else if (t < 0.4)
                {
                    double s = (t - 0.2) / 0.2;
                    r = (byte)(30 + s * 130);
                    g = 0;
                    b = (byte)(128 + s * 50);
                }
                else if (t < 0.7)
                {
                    double s = (t - 0.4) / 0.3;
                    r = (byte)(160 + s * 95);
                    g = (byte)(s * 150);
                    b = (byte)(178 * (1.0 - s));
                }
                else if (t < 0.9)
                {
                    double s = (t - 0.7) / 0.2;
                    r = 255;
                    g = (byte)(150 + s * 95);
                    b = 0;
                }
                else
                {
                    double s = (t - 0.9) / 0.1;
                    r = 255;
                    g = (byte)(245 + s * 10);
                    b = (byte)(s * 255);
                }
                lut[i] = (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }
            return lut;
        }

        private static uint[] GenerateRainbowLUT()
        {
            var lut = new uint[256];
            for (int i = 0; i < 256; i++)
            {
                double t = i / 255.0;
                byte r = (byte)(Math.Sin(t * Math.PI - Math.PI / 2) * 127 + 128);
                byte g = (byte)(Math.Sin(t * Math.PI) * 255);
                byte b = (byte)(Math.Cos(t * Math.PI / 2) * 255);
                lut[i] = (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }
            return lut;
        }

        private static uint[] GenerateInfernoLUT()
        {
            var lut = new uint[256];
            for (int i = 0; i < 256; i++)
            {
                double t = i / 255.0;
                byte r = (byte)Math.Min(255, Math.Max(0, 255 * (t * 1.5)));
                byte g = (byte)Math.Min(255, Math.Max(0, 255 * (Math.Pow(t, 2) * 1.2)));
                byte b = (byte)Math.Min(255, Math.Max(0, 255 * (Math.Pow(t, 3) * 1.5)));
                lut[i] = (uint)((255 << 24) | (r << 16) | (g << 8) | b);
            }
            return lut;
        }

        private static uint[] SelectLut(ColorPalette palette) => palette switch
        {
            ColorPalette.Rainbow => RainbowLUT,
            ColorPalette.Inferno => InfernoLUT,
            ColorPalette.Viridis => ViridisLUT,
            ColorPalette.Turbo => TurboLUT,
            ColorPalette.ArcticIschemia => ArcticIschemiaLUT,
            _ => IronbowLUT
        };

        public static uint GetBgraColorForValue(byte val, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5, bool invertLut = false)
        {
            double wMin = windowCenter - (windowWidth / 2.0);
            double wMax = windowCenter + (windowWidth / 2.0);
            if (wMax <= wMin) wMax = wMin + 1.0;

            double scaled = (val - wMin) / (wMax - wMin) * 255.0;
            int clamped = Math.Clamp((int)Math.Round(scaled), 0, 255);
            if (invertLut) clamped = 255 - clamped;

            if (palette == ColorPalette.Grayscale)
            {
                byte g = (byte)clamped;
                return (uint)((255 << 24) | (g << 16) | (g << 8) | g);
            }
            return SelectLut(palette)[clamped];
        }

        public static BitmapSource ApplyPalette(BitmapSource graySource, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5, bool invertLut = false)
        {
            int width = graySource.PixelWidth;
            int height = graySource.PixelHeight;

            var formatConverted = new FormatConvertedBitmap(graySource, PixelFormats.Gray8, null, 0);
            byte[] grayPixels = new byte[width * height];
            formatConverted.CopyPixels(grayPixels, width, 0);

            return ApplyPalette(grayPixels, width, height, palette, windowWidth, windowCenter, invertLut);
        }

        public static BitmapSource ApplyPalette(byte[] grayPixels, int width, int height, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5, bool invertLut = false)
        {
            uint[] lut = SelectLut(palette);

            double wMin = windowCenter - (windowWidth / 2.0);
            double wMax = windowCenter + (windowWidth / 2.0);
            if (wMax <= wMin) wMax = wMin + 1.0;

            uint[] coloredPixels = new uint[width * height];
            for (int i = 0; i < grayPixels.Length; i++)
            {
                byte val = grayPixels[i];
                // Apply window/level scaling
                double scaled = (val - wMin) / (wMax - wMin) * 255.0;
                int clamped = Math.Clamp((int)Math.Round(scaled), 0, 255);
                if (invertLut) clamped = 255 - clamped;

                if (palette == ColorPalette.Grayscale)
                {
                    byte g = (byte)clamped;
                    coloredPixels[i] = (uint)((255 << 24) | (g << 16) | (g << 8) | g);
                }
                else
                {
                    coloredPixels[i] = lut[clamped];
                }
            }

            var coloredBitmap = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgra32, null);
            coloredBitmap.WritePixels(new System.Windows.Int32Rect(0, 0, width, height), coloredPixels, width * 4, 0);
            coloredBitmap.Freeze();
            return coloredBitmap;
        }

        public static (BitmapSource coloredBitmap, byte[] rawGray, int width, int height) LoadCalibratedImage(
            string imagePath, 
            ColorPalette palette, 
            double windowWidth = 255.0, 
            double windowCenter = 127.5,
            bool invertLut = false)
        {
            var bi = new BitmapImage();
            bi.BeginInit();
            bi.UriSource = new Uri(Path.GetFullPath(imagePath));
            bi.CacheOption = BitmapCacheOption.OnLoad;
            bi.EndInit();
            bi.Freeze();

            int width = bi.PixelWidth;
            int height = bi.PixelHeight;

            var formatConverted = new FormatConvertedBitmap(bi, PixelFormats.Gray8, null, 0);
            byte[] grayPixels = new byte[width * height];
            formatConverted.CopyPixels(grayPixels, width, 0);

            var colored = ApplyPalette(grayPixels, width, height, palette, windowWidth, windowCenter, invertLut);
            return (colored, grayPixels, width, height);
        }

        public static BitmapSource LoadAndColorize(string imagePath, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5, bool invertLut = false)
        {
            var res = LoadCalibratedImage(imagePath, palette, windowWidth, windowCenter, invertLut);
            return res.coloredBitmap;
        }

        // Fast in-memory cache of vein mask bytes for instant real-time slider updates
        public static byte[]? LoadVeinMaskBytes(string veinMaskPath, int targetWidth, int targetHeight)
        {
            if (string.IsNullOrEmpty(veinMaskPath) || !File.Exists(veinMaskPath))
                return null;

            try
            {
                byte[] raw = File.ReadAllBytes(veinMaskPath);
                if (raw.Length == 0) return null;

                var veinImg = new BitmapImage();
                using (var ms = new MemoryStream(raw))
                {
                    veinImg.BeginInit();
                    veinImg.CacheOption = BitmapCacheOption.OnLoad;
                    veinImg.StreamSource = ms;
                    veinImg.EndInit();
                    veinImg.Freeze();
                }

                BitmapSource processedVein = veinImg;
                if (veinImg.PixelWidth != targetWidth || veinImg.PixelHeight != targetHeight)
                {
                    var scaleTransform = new ScaleTransform((double)targetWidth / veinImg.PixelWidth, (double)targetHeight / veinImg.PixelHeight);
                    processedVein = new TransformedBitmap(veinImg, scaleTransform);
                }

                var veinGray = new FormatConvertedBitmap(processedVein, PixelFormats.Gray8, null, 0);
                byte[] pixels = new byte[targetWidth * targetHeight];
                veinGray.CopyPixels(pixels, targetWidth, 0);
                return pixels;
            }
            catch
            {
                return null;
            }
        }

        // Blends a detected vascular/vein mask with customizable opacity, sensitivity threshold and clinical color modes
        public static BitmapSource BlendVeinOverlay(
            BitmapSource baseSource, 
            byte[] veinPixels, 
            double opacity = 0.85, 
            byte threshold = 20, 
            VeinRenderMode renderMode = VeinRenderMode.FluorescentCyan)
        {
            if (baseSource == null || veinPixels == null)
                return baseSource!;

            try
            {
                int w = baseSource.PixelWidth;
                int h = baseSource.PixelHeight;

                if (veinPixels.Length != w * h)
                    return baseSource;

                var baseBgra = new FormatConvertedBitmap(baseSource, PixelFormats.Bgra32, null, 0);
                uint[] basePixels = new uint[w * h];
                baseBgra.CopyPixels(basePixels, w * 4, 0);

                uint[] output = new uint[w * h];

                // Target tint color based on mode
                byte targetR = 0, targetG = 229, targetB = 255; // Fluorescent Cyan default
                if (renderMode == VeinRenderMode.RoyalCobalt)
                {
                    targetR = 30; targetG = 136; targetB = 229; // Medical Blue
                }
                else if (renderMode == VeinRenderMode.SurgicalGreen)
                {
                    targetR = 0; targetG = 230; targetB = 118; // ICG Green
                }

                bool isDSA = (renderMode == VeinRenderMode.PureAngiography);

                for (int i = 0; i < basePixels.Length; i++)
                {
                    byte v = veinPixels[i];

                    if (isDSA)
                    {
                        // Digital Subtraction Angiography: black background with luminous vessels
                        if (v >= threshold)
                        {
                            double norm = (v - threshold) / (double)(255 - threshold);
                            byte lum = (byte)Math.Clamp((int)(norm * 255), 0, 255);
                            output[i] = (uint)((255 << 24) | (lum << 16) | (lum << 8) | 255); // Ice-white vascular lum
                        }
                        else
                        {
                            output[i] = 0xFF080B10; // Dark background
                        }
                        continue;
                    }

                    if (v >= threshold)
                    {
                        double strength = (v - threshold) / (double)(255 - threshold);
                        double alpha = Math.Clamp(strength * opacity * 1.4, 0.0, 1.0);

                        uint orig = basePixels[i];
                        byte ob = (byte)(orig & 0xFF);
                        byte og = (byte)((orig >> 8) & 0xFF);
                        byte or = (byte)((orig >> 16) & 0xFF);

                        // High-contrast additive & alpha blend
                        byte nb = (byte)Math.Clamp(ob * (1.0 - alpha) + targetB * alpha, 0, 255);
                        byte ng = (byte)Math.Clamp(og * (1.0 - alpha) + targetG * alpha, 0, 255);
                        byte nr = (byte)Math.Clamp(or * (1.0 - alpha) + targetR * alpha, 0, 255);

                        output[i] = (uint)((255 << 24) | (nr << 16) | (ng << 8) | nb);
                    }
                    else
                    {
                        output[i] = basePixels[i];
                    }
                }

                var res = new WriteableBitmap(w, h, 96, 96, PixelFormats.Bgra32, null);
                res.WritePixels(new System.Windows.Int32Rect(0, 0, w, h), output, w * 4, 0);
                res.Freeze();
                return res;
            }
            catch
            {
                return baseSource;
            }
        }

        // Backward compatibility overload
        public static BitmapSource BlendVeinOverlay(BitmapSource baseSource, string veinMaskPath)
        {
            if (baseSource == null || string.IsNullOrEmpty(veinMaskPath) || !File.Exists(veinMaskPath))
                return baseSource!;

            var bytes = LoadVeinMaskBytes(veinMaskPath, baseSource.PixelWidth, baseSource.PixelHeight);
            if (bytes == null) return baseSource;

            return BlendVeinOverlay(baseSource, bytes, 0.85, 20, VeinRenderMode.FluorescentCyan);
        }

        // Generates clinical finding image with dimmed anatomical context, isolating confirmed inflammatory hotspots and vascular tree
        public static BitmapSource CreateIsolatedFindingBitmap(
            byte[] grayPixels, 
            int width, 
            int height, 
            ColorPalette palette, 
            byte threshold = 180, 
            byte[]? veinPixels = null, 
            bool showVeins = true,
            double windowWidth = 255.0,
            double windowCenter = 127.5,
            bool invertLut = false,
            byte[]? hotspotMaskPixels = null)
        {
            uint[] lut = SelectLut(palette);

            double wMin = windowCenter - (windowWidth / 2.0);
            double wMax = windowCenter + (windowWidth / 2.0);
            if (wMax <= wMin) wMax = wMin + 1.0;

            bool hasMaskArray = hotspotMaskPixels != null && hotspotMaskPixels.Length == grayPixels.Length;
            bool hasExplicitMask = false;
            if (hasMaskArray)
            {
                for (int k = 0; k < hotspotMaskPixels!.Length; k++)
                {
                    if (hotspotMaskPixels[k] > 0)
                    {
                        hasExplicitMask = true;
                        break;
                    }
                }
            }

            uint[] output = new uint[width * height];

            for (int i = 0; i < grayPixels.Length; i++)
            {
                byte val = grayPixels[i];
                bool isHotspot = hasMaskArray ? (hotspotMaskPixels![i] > 0) : (val >= threshold);

                if (isHotspot)
                {
                    double scaled = (val - wMin) / (wMax - wMin) * 255.0;
                    int clamped = Math.Clamp((int)Math.Round(scaled), 0, 255);
                    if (invertLut) clamped = 255 - clamped;

                    if (palette == ColorPalette.Grayscale)
                    {
                        byte g = (byte)clamped;
                        output[i] = (uint)((255 << 24) | (g << 16) | (g << 8) | g);
                    }
                    else
                    {
                        uint lutCol = lut[clamped];
                        if (hasExplicitMask)
                        {
                            // Warm clinical red/amber inflammation highlight blend so even cooler acral lesions stand out
                            byte lb = (byte)(lutCol & 0xFF);
                            byte lg = (byte)((lutCol >> 8) & 0xFF);
                            byte lr = (byte)((lutCol >> 16) & 0xFF);
                            byte rr = (byte)Math.Clamp((int)(lr * 0.55 + 255 * 0.45), 0, 255);
                            byte rg = (byte)Math.Clamp((int)(lg * 0.55 + 90 * 0.45), 0, 255);
                            byte rb = (byte)Math.Clamp((int)(lb * 0.55 + 20 * 0.45), 0, 255);
                            output[i] = (uint)((255 << 24) | (rr << 16) | (rg << 8) | rb);
                        }
                        else
                        {
                            output[i] = lutCol;
                        }
                    }
                }
                else
                {
                    // Dimmed 38% anatomical grayscale context so the clinician sees exact foot/toe landmarks
                    byte dim = (byte)Math.Clamp((int)Math.Round(val * 0.38), 0, 255);
                    if (showVeins && veinPixels != null && i < veinPixels.Length && veinPixels[i] > 25)
                    {
                        double strength = Math.Clamp((veinPixels[i] - 25) / 230.0, 0.0, 1.0);
                        byte r = (byte)Math.Clamp((int)(dim * (1.0 - strength)), 0, 255);
                        byte g = (byte)Math.Clamp((int)(dim * (1.0 - strength) + 229 * strength), 0, 255);
                        byte b = (byte)Math.Clamp((int)(dim * (1.0 - strength) + 255 * strength), 0, 255);
                        output[i] = (uint)((255 << 24) | (r << 16) | (g << 8) | b);
                    }
                    else
                    {
                        output[i] = (uint)((255 << 24) | (dim << 16) | (dim << 8) | dim);
                    }
                }
            }

            var bmp = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgra32, null);
            bmp.WritePixels(new System.Windows.Int32Rect(0, 0, width, height), output, width * 4, 0);
            bmp.Freeze();
            return bmp;
        }
    }

}
