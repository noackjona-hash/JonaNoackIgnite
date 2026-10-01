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

        public static BitmapSource ApplyPalette(BitmapSource graySource, ColorPalette palette)
        {
            if (palette == ColorPalette.Grayscale)
            {
                return graySource;
            }

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

            uint[] coloredPixels = new uint[width * height];
            for (int i = 0; i < grayPixels.Length; i++)
            {
                coloredPixels[i] = lut[grayPixels[i]];
            }

            var coloredBitmap = new WriteableBitmap(width, height, 96, 96, PixelFormats.Bgra32, null);
            coloredBitmap.WritePixels(new System.Windows.Int32Rect(0, 0, width, height), coloredPixels, width * 4, 0);
            coloredBitmap.Freeze();
            return coloredBitmap;
        }

        public static BitmapSource LoadAndColorize(string imagePath, ColorPalette palette)
        {
            var bi = new BitmapImage();
            bi.BeginInit();
            bi.UriSource = new Uri(Path.GetFullPath(imagePath));
            bi.CacheOption = BitmapCacheOption.OnLoad;
            bi.EndInit();
            bi.Freeze();

            return ApplyPalette(bi, palette);
        }
    }
}
