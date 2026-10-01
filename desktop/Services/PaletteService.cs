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
        Grayscale
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

        public static BitmapSource ApplyPalette(BitmapSource graySource, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5)
        {
            int width = graySource.PixelWidth;
            int height = graySource.PixelHeight;

            var formatConverted = new FormatConvertedBitmap(graySource, PixelFormats.Gray8, null, 0);
            byte[] grayPixels = new byte[width * height];
            formatConverted.CopyPixels(grayPixels, width, 0);

            uint[] lut = palette switch
            {
                ColorPalette.Rainbow => RainbowLUT,
                ColorPalette.Inferno => InfernoLUT,
                _ => IronbowLUT
            };

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

        public static BitmapSource LoadAndColorize(string imagePath, ColorPalette palette, double windowWidth = 255.0, double windowCenter = 127.5)
        {
            var bi = new BitmapImage();
            bi.BeginInit();
            bi.UriSource = new Uri(Path.GetFullPath(imagePath));
            bi.CacheOption = BitmapCacheOption.OnLoad;
            bi.EndInit();
            bi.Freeze();

            return ApplyPalette(bi, palette, windowWidth, windowCenter);
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
    }

}
