using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Microsoft.Win32;
using Ignite.Desktop.Models;
using Ignite.Desktop.Services;

namespace Ignite.Desktop
{
    public enum ActiveCanvasTool
    {
        PanZoom,
        RoiSelection,
        ThermalProfile,
        PointProbe,
        WindowLevelDrag
    }

    public partial class MainWindow : Window
    {
        private readonly EngineService _engineService;
        private readonly DatabaseService _dbService;

        private string? _currentImagePath;
        private string? _contralateralImagePath;
        private BitmapSource? _originalBitmap;
        private byte[]? _rawGrayPixels;
        private int _rawWidth = 0;
        private int _rawHeight = 0;
        private AnalysisResult? _latestResult;
        private ColorPalette _activePalette = ColorPalette.Ironbow;
        private double _currentZoom = 1.0;
        private string _activePatientId = "ANON-DEMO";

        // Active Tool Mode
        private ActiveCanvasTool _activeTool = ActiveCanvasTool.PanZoom;

        // Vascular & Window/Level State
        private byte[]? _cachedVeinPixels = null;
        private double _windowWidth = 255.0;
        private double _windowCenter = 127.5;
        private double _veinOpacity = 0.85;
        private byte _veinThreshold = 20;
        private VeinRenderMode _veinRenderMode = VeinRenderMode.FluorescentCyan;
        private bool _enableVeinOverlay = true;

        // Interactive ROI Rubberband Selection
        private bool _isSelectingROI = false;
        private Point _roiStartPoint;
        private System.Windows.Shapes.Rectangle? _roiSelectionRect;
        private int[]? _currentROI = null; // [minX, minY, maxX, maxY]

        // Interactive Thermal Profile Line T(s)
        private bool _isDrawingProfile = false;
        private Point _profileStartPoint;
        private Point _profileEndPoint;
        private ThermalProfileStats? _activeProfileStats;

        // Clinical Point Probes (P1, P2, ...)
        private readonly List<ThermalProbePoint> _probePoints = new();

        // Window/Level Drag State
        private bool _isDraggingWL = false;
        private Point _wlStartPoint;
        private double _wlStartWidth;
        private double _wlStartCenter;

        // Pan State (Middle-click, Right-click or Pan tool)
        private bool _isPanning = false;
        private Point _panStartMouse;
        private double _panStartHScroll;
        private double _panStartVScroll;

        // Viewport Synchronization
        private bool _syncViewports = true;
        private bool _isSyncingScroll = false;
        private bool _showMinMaxTracker = true;

        // Filmstrip Gallery
        private readonly List<string> _filmstripFiles = new();
        private int _activeFilmstripIndex = -1;

        public MainWindow()
        {
            InitializeComponent();
            _engineService = new EngineService();
            _dbService = new DatabaseService();

            _activePatientId = _dbService.EnsurePatient("Patient_001_Demo");
            PatientIdText.Text = $"PATIENT: {_activePatientId}";

            LoadDefaultLuaRule();
            RefreshAuditGrid();
            InitializeFilmstripGallery();
            UpdateToolInstructions();

            // Load initial demo image from test-data if available
            TryLoadInitialDemoImage();
        }

        // --- Filmstrip Case Gallery Initialization ---
        private void InitializeFilmstripGallery()
        {
            try
            {
                PanelFilmstrip.Children.Clear();
                _filmstripFiles.Clear();

                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(baseDir, "..", "..", "..", "..", "test-data"));
                if (!Directory.Exists(testDir))
                {
                    testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(baseDir, "test-data"));
                }
                if (!Directory.Exists(testDir))
                {
                    testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(Directory.GetCurrentDirectory(), "test-data"));
                }

                if (Directory.Exists(testDir))
                {
                    var files = Directory.GetFiles(testDir, "*.jpeg")
                        .Concat(Directory.GetFiles(testDir, "*.jpg"))
                        .Concat(Directory.GetFiles(testDir, "*.png"))
                        .OrderBy(f => ExtractNaturalNumber(System.IO.Path.GetFileName(f)))
                        .ToList();

                    _filmstripFiles.AddRange(files);
                    TxtFilmstripCount.Text = $" ({_filmstripFiles.Count} Patientenfälle)";

                    for (int i = 0; i < _filmstripFiles.Count; i++)
                    {
                        string filePath = _filmstripFiles[i];
                        int caseIndex = i;

                        var card = new Border
                        {
                            Background = (Brush)FindResource("SurfaceCardBrush"),
                            BorderBrush = (Brush)FindResource("BorderBrush"),
                            BorderThickness = new Thickness(1),
                            CornerRadius = new CornerRadius(4),
                            Margin = new Thickness(3, 2, 3, 2),
                            Padding = new Thickness(4),
                            Cursor = Cursors.Hand,
                            Tag = caseIndex,
                            Width = 92
                        };

                        var stack = new StackPanel { Orientation = Orientation.Vertical, HorizontalAlignment = HorizontalAlignment.Center };

                        // Fast low-res thumbnail decoder
                        var bmp = new BitmapImage();
                        bmp.BeginInit();
                        bmp.UriSource = new Uri(filePath);
                        bmp.DecodePixelWidth = 84;
                        bmp.CacheOption = BitmapCacheOption.OnLoad;
                        bmp.EndInit();
                        bmp.Freeze();

                        var img = new Image
                        {
                            Source = bmp,
                            Width = 84,
                            Height = 58,
                            Stretch = Stretch.UniformToFill
                        };

                        var lbl = new TextBlock
                        {
                            Text = $"Fall #{caseIndex + 1:D2}",
                            FontSize = 9.5,
                            FontWeight = FontWeights.Bold,
                            Foreground = Brushes.White,
                            HorizontalAlignment = HorizontalAlignment.Center,
                            Margin = new Thickness(0, 3, 0, 0)
                        };

                        stack.Children.Add(img);
                        stack.Children.Add(lbl);
                        card.Child = stack;

                        card.MouseEnter += (s, e) =>
                        {
                            if (card.Tag is int idx && idx != _activeFilmstripIndex)
                                card.BorderBrush = (Brush)FindResource("MedicalBlueBrush");
                        };
                        card.MouseLeave += (s, e) =>
                        {
                            if (card.Tag is int idx && idx != _activeFilmstripIndex)
                                card.BorderBrush = (Brush)FindResource("BorderBrush");
                        };
                        card.MouseDown += (s, e) =>
                        {
                            LoadFilmstripCase(caseIndex);
                        };

                        PanelFilmstrip.Children.Add(card);
                    }
                }
            }
            catch { }
        }

        private static int ExtractNaturalNumber(string name)
        {
            var match = Regex.Match(name, @"\d+");
            return match.Success && int.TryParse(match.Value, out int n) ? n : 0;
        }

        private void LoadFilmstripCase(int index)
        {
            if (index >= 0 && index < _filmstripFiles.Count)
            {
                _activeFilmstripIndex = index;
                HighlightActiveFilmstripCard();
                LoadImage(_filmstripFiles[index]);
            }
        }

        private void HighlightActiveFilmstripCard()
        {
            for (int i = 0; i < PanelFilmstrip.Children.Count; i++)
            {
                if (PanelFilmstrip.Children[i] is Border card)
                {
                    if (i == _activeFilmstripIndex)
                    {
                        card.BorderBrush = (Brush)FindResource("CyanBrush");
                        card.BorderThickness = new Thickness(2);
                        card.Background = new SolidColorBrush(Color.FromArgb(50, 0, 229, 255));
                    }
                    else
                    {
                        card.BorderBrush = (Brush)FindResource("BorderBrush");
                        card.BorderThickness = new Thickness(1);
                        card.Background = (Brush)FindResource("SurfaceCardBrush");
                    }
                }
            }
        }

        private void BtnToggleFilmstrip_Click(object sender, RoutedEventArgs e)
        {
            if (ScrollFilmstrip.Visibility == Visibility.Visible)
            {
                ScrollFilmstrip.Visibility = Visibility.Collapsed;
                BtnToggleFilmstrip.Content = "▲ Einblenden";
            }
            else
            {
                ScrollFilmstrip.Visibility = Visibility.Visible;
                BtnToggleFilmstrip.Content = "▼ Ausblenden";
            }
        }

        private void TryLoadInitialDemoImage()
        {
            if (_filmstripFiles.Count > 0)
            {
                LoadFilmstripCase(0);
            }
            else
            {
                string baseDir = AppDomain.CurrentDomain.BaseDirectory;
                string testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(baseDir, "..", "..", "..", "..", "test-data"));
                if (!Directory.Exists(testDir))
                {
                    testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(baseDir, "test-data"));
                }
                if (!Directory.Exists(testDir))
                {
                    testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(Directory.GetCurrentDirectory(), "test-data"));
                }
                if (Directory.Exists(testDir))
                {
                    var files = Directory.GetFiles(testDir, "*.jpeg");
                    if (files.Length > 0)
                    {
                        LoadImage(files[0]);
                    }
                }
            }
        }

        private void LoadDefaultLuaRule()
        {
            string rulePath = System.IO.Path.GetFullPath(System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "rules", "armstrong_criteria.lua"));
            if (File.Exists(rulePath))
            {
                TxtLuaCode.Text = File.ReadAllText(rulePath);
            }
            else
            {
                TxtLuaCode.Text = @"function evaluate_hotspot(hotspot, stats)
    local delta_t = hotspot.max_val - stats.orig_median
    if delta_t >= 22.0 and hotspot.circularity >= 0.12 then
        return {
            risk_level = 'CRITICAL',
            recommendation = 'Pathologischer Entzündungsherd (Armstrong Delta T >= 2.2 K). Sofortige Druckentlastung indiziert.',
            score = 9.5
        }
    elseif delta_t >= 12.0 then
        return {
            risk_level = 'MODERATE',
            recommendation = 'Gewebeerwärmung. Nachkontrolle in 48 Stunden.',
            score = 5.5
        }
    else
        return {
            risk_level = 'BENIGN',
            recommendation = 'Physiologische Variation.',
            score = 1.0
        }
    end
end";
            }
        }

        // --- Core Image Loading & Radiometry Setup ---
        private void LoadImage(string path)
        {
            try
            {
                _currentImagePath = path;
                _currentROI = null;
                _cachedVeinPixels = null;
                _activeProfileStats = null;
                OverlayOriginalCanvas.Children.Clear();
                OverlayResultCanvas.Children.Clear();

                // Match filmstrip highlight
                int idx = _filmstripFiles.IndexOf(path);
                if (idx >= 0)
                {
                    _activeFilmstripIndex = idx;
                    HighlightActiveFilmstripCard();
                }

                // Load calibrated color bitmap AND raw gray pixels
                var cal = PaletteService.LoadCalibratedImage(path, _activePalette, _windowWidth, _windowCenter);
                _originalBitmap = cal.coloredBitmap;
                _rawGrayPixels = cal.rawGray;
                _rawWidth = cal.width;
                _rawHeight = cal.height;

                ImgOriginal.Source = _originalBitmap;
                OverlayOriginalCanvas.Width = _rawWidth;
                OverlayOriginalCanvas.Height = _rawHeight;
                OverlayResultCanvas.Width = _rawWidth;
                OverlayResultCanvas.Height = _rawHeight;

                StatusText.Text = $"Thermogramm geladen: {System.IO.Path.GetFileName(path)} ({_rawWidth}x{_rawHeight} Radiometrie-Matrix).";

                UpdateHudReadouts();
                RedrawInteractiveOverlays();
                _ = RunPipelineAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Laden des Bildes: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // --- Drag & Drop Support ---
        private void Window_DragOver(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                e.Effects = DragDropEffects.Copy;
            }
            else
            {
                e.Effects = DragDropEffects.None;
            }
            e.Handled = true;
        }

        private void Window_Drop(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                string[] files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (files != null && files.Length > 0)
                {
                    string file = files[0];
                    string ext = System.IO.Path.GetExtension(file).ToLowerInvariant();
                    if (ext == ".jpeg" || ext == ".jpg" || ext == ".png" || ext == ".bmp" || ext == ".tiff")
                    {
                        LoadImage(file);
                    }
                    else
                    {
                        MessageBox.Show("Bitte ein gültiges Wärmebild (.jpeg, .png, .bmp) ablegen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    }
                }
            }
        }

        // --- Analysis Pipeline Execution ---
        private async Task RunPipelineAsync()
        {
            if (string.IsNullOrEmpty(_currentImagePath) || !File.Exists(_currentImagePath))
                return;

            AnalysisProgressBar.Visibility = Visibility.Visible;
            StatusText.Text = "Berechne diagnostische Bildverarbeitung in Go (AVX2-beschleunigt)...";

            double kFactor = SliderK.Value;
            double kernelFactor = SliderKernel.Value;
            string mode = ComboThresholdMode.SelectedIndex == 1 ? "GAUSSIAN" : "MAD";
            bool vascular = ChkFrangi.IsChecked == true;
            bool perfusion = ChkPerfusion.IsChecked == true;

            try
            {
                var result = await _engineService.RunAnalysisAsync(_currentImagePath, kFactor, kernelFactor, mode, vascular, perfusion, _currentROI);
                if (result == null)
                    return;

                result.Hotspots ??= new();
                result.Stats ??= new();
                result.Timing ??= new();

                _latestResult = result;

                // Update UI metrics
                TxtTissuePixels.Text = $"Gewebe-Pixel: {result.TissuePixelCount:N0}";
                TxtHotspotCount.Text = $"Gefundene Herde: {result.TotalHotspots}";
                TxtLatency.Text = $"Rechenzeit: {result.Timing.TotalMs:F1} ms (Top-Hat AVX2: {result.Timing.TopHatMs:F1} ms)";
                EngineTimingText.Text = $"Go Core: {result.Timing.TotalMs:F1} ms (AVX2)";

                // Update Hotspot Table
                GridHotspots.ItemsSource = result.Hotspots;
                if (result.Hotspots.Count > 0)
                {
                    GridHotspots.SelectedIndex = 0;
                }

                // Invalidate cached vein pixels so new ones are loaded
                _cachedVeinPixels = null;

                // Update Perfusion Tab
                if (result.Perfusion != null)
                {
                    string perfStatus = result.Perfusion.Status ?? "NORMAL";
                    TxtPerfusionStatus.Text = $"STATUS: {perfStatus}";
                    TxtPerfusionStatus.Foreground = perfStatus.Contains("CRITICAL") ? Brushes.Red : Brushes.LightGreen;
                    TxtPerfusionDrop.Text = $"Maximaler Gradientenabfall: {result.Perfusion.MaxGradientDrop:F2} K/Zeile";
                    TxtPerfusionDesc.Text = result.Perfusion.Description ?? string.Empty;
                }

                // Render Overlays in Viewport 2
                RenderAnalysisResultOverlay(result, vascular);

                // Log into SQLite database safely
                double maxVal = result.Hotspots.Count > 0 ? result.Hotspots.Max(h => (h?.Region?.MaxVal ?? 0)) - result.Stats.OrigMedian : 0;
                if (_dbService != null && !string.IsNullOrEmpty(_activePatientId) && !string.IsNullOrEmpty(_currentImagePath))
                {
                    _dbService.LogEvaluation(_activePatientId, _currentImagePath, "INFLAMMATION_HOTSPOTS", result.TotalHotspots, maxVal, result.HighestRisk ?? "BENIGN", result.Timing.TotalMs);
                    RefreshAuditGrid();
                }

                StatusText.Text = $"Analyse abgeschlossen: {result.TotalHotspots} Herde gefunden (Status: {result.HighestRisk ?? "OK"}).";
            }
            catch (Exception ex)
            {
                StatusText.Text = $"Fehler bei der Analyse: {ex.Message}";
                MessageBox.Show($"Pipeline-Fehler: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
            finally
            {
                AnalysisProgressBar.Visibility = Visibility.Collapsed;
            }
        }

        private void RenderAnalysisResultOverlay(AnalysisResult result, bool showVeins)
        {
            if (_originalBitmap == null || result == null)
                return;

            int w = _rawWidth > 0 ? _rawWidth : _originalBitmap.PixelWidth;
            int h = _rawHeight > 0 ? _rawHeight : _originalBitmap.PixelHeight;

            BitmapSource baseBmp = _rawGrayPixels != null
                ? PaletteService.ApplyPalette(_rawGrayPixels, w, h, _activePalette, _windowWidth, _windowCenter)
                : PaletteService.ApplyPalette(_originalBitmap, _activePalette, _windowWidth, _windowCenter);

            // Blend vein mask if active
            if (showVeins && _enableVeinOverlay)
            {
                try
                {
                    if (_cachedVeinPixels == null)
                    {
                        string veinMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "vascular_mask.png");
                        if (File.Exists(veinMaskPath))
                        {
                            _cachedVeinPixels = PaletteService.LoadVeinMaskBytes(veinMaskPath, w, h);
                            UpdateVeinMetricsUI();
                        }
                    }

                    if (_cachedVeinPixels != null)
                    {
                        baseBmp = PaletteService.BlendVeinOverlay(baseBmp, _cachedVeinPixels, _veinOpacity, _veinThreshold, _veinRenderMode);
                    }
                }
                catch { }
            }

            ImgResult.Source = baseBmp;

            // Redraw vector annotations
            RedrawInteractiveOverlays();
        }

        private void RefreshResultImageOnly()
        {
            if (_originalBitmap == null) return;
            int w = _rawWidth > 0 ? _rawWidth : _originalBitmap.PixelWidth;
            int h = _rawHeight > 0 ? _rawHeight : _originalBitmap.PixelHeight;

            BitmapSource baseBmp = _rawGrayPixels != null
                ? PaletteService.ApplyPalette(_rawGrayPixels, w, h, _activePalette, _windowWidth, _windowCenter)
                : PaletteService.ApplyPalette(_originalBitmap, _activePalette, _windowWidth, _windowCenter);

            if (_enableVeinOverlay && _cachedVeinPixels != null)
            {
                baseBmp = PaletteService.BlendVeinOverlay(baseBmp, _cachedVeinPixels, _veinOpacity, _veinThreshold, _veinRenderMode);
            }

            ImgResult.Source = baseBmp;
            UpdateHudReadouts();
        }

        // --- Interactive Overlays (Hotspots, Min/Max, Probes, Profile, ROI) ---
        private void RedrawInteractiveOverlays()
        {
            OverlayOriginalCanvas.Children.Clear();
            OverlayResultCanvas.Children.Clear();

            if (_originalBitmap == null) return;
            int w = _rawWidth > 0 ? _rawWidth : _originalBitmap.PixelWidth;
            int h = _rawHeight > 0 ? _rawHeight : _originalBitmap.PixelHeight;

            OverlayOriginalCanvas.Width = w;
            OverlayOriginalCanvas.Height = h;
            OverlayResultCanvas.Width = w;
            OverlayResultCanvas.Height = h;

            // 1. Draw Confirmed Hotspots on Viewport 2
            if (_latestResult?.Hotspots != null)
            {
                double origMed = _latestResult.Stats?.OrigMedian ?? 0;
                foreach (var hspot in _latestResult.Hotspots)
                {
                    if (hspot?.Region == null) continue;
                    var box = hspot.Region.BoundingBox;
                    if (box == null || box.Length < 4) continue;

                    int minX = box[0], minY = box[1], maxX = box[2], maxY = box[3];
                    int bw = maxX - minX, bh = maxY - minY;
                    var risk = hspot.Assessment?.RiskLevel ?? "NORMAL";

                    var rect = new System.Windows.Shapes.Rectangle
                    {
                        Width = Math.Max(bw, 12),
                        Height = Math.Max(bh, 12),
                        Stroke = risk == "CRITICAL" ? new SolidColorBrush(Color.FromRgb(211, 47, 47)) : Brushes.Yellow,
                        StrokeThickness = 2.0,
                        RadiusX = 2,
                        RadiusY = 2,
                        Fill = new SolidColorBrush(Color.FromArgb(35, 211, 47, 47))
                    };
                    Canvas.SetLeft(rect, minX);
                    Canvas.SetTop(rect, minY);
                    OverlayResultCanvas.Children.Add(rect);

                    var crosshairH = new Line { X1 = hspot.Region.CenterX - 7, Y1 = hspot.Region.CenterY, X2 = hspot.Region.CenterX + 7, Y2 = hspot.Region.CenterY, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    var crosshairV = new Line { X1 = hspot.Region.CenterX, Y1 = hspot.Region.CenterY - 7, X2 = hspot.Region.CenterX, Y2 = hspot.Region.CenterY + 7, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    OverlayResultCanvas.Children.Add(crosshairH);
                    OverlayResultCanvas.Children.Add(crosshairV);

                    double deltaT = Math.Round((hspot.Region.MaxVal - origMed) * 0.1, 1);
                    var labelBorder = new Border
                    {
                        Background = new SolidColorBrush(Color.FromArgb(220, 18, 22, 30)),
                        BorderBrush = rect.Stroke,
                        BorderThickness = new Thickness(1),
                        CornerRadius = new CornerRadius(2),
                        Padding = new Thickness(4, 1, 4, 1)
                    };
                    labelBorder.Child = new TextBlock
                    {
                        Text = $"HERD #{hspot.Region.Id} (ΔT = +{deltaT:F1} K) [{risk}]",
                        FontSize = 9.5,
                        FontWeight = FontWeights.Bold,
                        Foreground = Brushes.White
                    };
                    Canvas.SetLeft(labelBorder, minX);
                    Canvas.SetTop(labelBorder, Math.Max(0, minY - 20));
                    OverlayResultCanvas.Children.Add(labelBorder);
                }
            }

            // 2. Draw Global Min/Max Extrema Tracker
            if (_showMinMaxTracker && _rawGrayPixels != null)
            {
                var extrema = ThermalAnalysisHelper.FindExtrema(_rawGrayPixels, w, h, roi: _currentROI);

                // Max Hotspot
                DrawExtremumPin(OverlayResultCanvas, extrema.Max.X, extrema.Max.Y, extrema.Max.Temp, true);
                DrawExtremumPin(OverlayOriginalCanvas, extrema.Max.X, extrema.Max.Y, extrema.Max.Temp, true);

                // Min Coldspot
                DrawExtremumPin(OverlayResultCanvas, extrema.Min.X, extrema.Min.Y, extrema.Min.Temp, false);
                DrawExtremumPin(OverlayOriginalCanvas, extrema.Min.X, extrema.Min.Y, extrema.Min.Temp, false);
            }

            // 3. Draw Active ROI Selection Rectangle (if set)
            if (_currentROI != null && _currentROI.Length >= 4)
            {
                var roiRect = new System.Windows.Shapes.Rectangle
                {
                    Width = Math.Max(0, _currentROI[2] - _currentROI[0]),
                    Height = Math.Max(0, _currentROI[3] - _currentROI[1]),
                    Stroke = Brushes.Cyan,
                    StrokeThickness = 1.5,
                    StrokeDashArray = new DoubleCollection { 4, 2 },
                    Fill = new SolidColorBrush(Color.FromArgb(25, 0, 229, 255))
                };
                Canvas.SetLeft(roiRect, _currentROI[0]);
                Canvas.SetTop(roiRect, _currentROI[1]);
                OverlayOriginalCanvas.Children.Add(roiRect);
            }

            // 4. Draw Thermal Profile Caliper Line
            if (_activeProfileStats != null && _activeProfileStats.Samples.Count >= 2)
            {
                DrawProfileLineVector(OverlayOriginalCanvas);
                DrawProfileLineVector(OverlayResultCanvas);
            }

            // 5. Draw Clinical Point Probes (P1, P2)
            if (_probePoints.Count > 0)
            {
                DrawProbePinsVector(OverlayOriginalCanvas);
                DrawProbePinsVector(OverlayResultCanvas);
            }
        }

        private void DrawExtremumPin(Canvas canvas, int x, int y, double temp, bool isMax)
        {
            var brush = isMax ? new SolidColorBrush(Color.FromRgb(255, 60, 60)) : (Brush)FindResource("CyanBrush");
            var glyph = isMax ? "🔥" : "❄️";
            var text = isMax ? $"MAX: {temp:F1}°C" : $"MIN: {temp:F1}°C";

            var ring = new Ellipse
            {
                Width = 14,
                Height = 14,
                Stroke = brush,
                StrokeThickness = 2.0,
                Fill = new SolidColorBrush(Color.FromArgb(40, isMax ? (byte)255 : (byte)0, isMax ? (byte)60 : (byte)229, isMax ? (byte)60 : (byte)255))
            };
            Canvas.SetLeft(ring, x - 7);
            Canvas.SetTop(ring, y - 7);
            canvas.Children.Add(ring);

            var tag = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(230, 10, 14, 20)),
                BorderBrush = brush,
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(2),
                Padding = new Thickness(4, 1, 4, 1)
            };
            tag.Child = new TextBlock
            {
                Text = $"{glyph} {text}",
                FontSize = 9.5,
                FontWeight = FontWeights.Bold,
                Foreground = brush
            };
            Canvas.SetLeft(tag, x + 9);
            Canvas.SetTop(tag, y - 9);
            canvas.Children.Add(tag);
        }

        private void DrawProfileLineVector(Canvas canvas)
        {
            var line = new Line
            {
                X1 = _profileStartPoint.X,
                Y1 = _profileStartPoint.Y,
                X2 = _profileEndPoint.X,
                Y2 = _profileEndPoint.Y,
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 2.5
            };
            canvas.Children.Add(line);

            // Caliper start and end rings
            var r1 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = (Brush)FindResource("CyanBrush"), StrokeThickness = 1.5 };
            Canvas.SetLeft(r1, _profileStartPoint.X - 4);
            Canvas.SetTop(r1, _profileStartPoint.Y - 4);
            canvas.Children.Add(r1);

            var r2 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = (Brush)FindResource("CyanBrush"), StrokeThickness = 1.5 };
            Canvas.SetLeft(r2, _profileEndPoint.X - 4);
            Canvas.SetTop(r2, _profileEndPoint.Y - 4);
            canvas.Children.Add(r2);

            // Center Callout badge
            double midX = (_profileStartPoint.X + _profileEndPoint.X) / 2.0;
            double midY = (_profileStartPoint.Y + _profileEndPoint.Y) / 2.0;

            var badge = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(230, 12, 16, 24)),
                BorderBrush = (Brush)FindResource("CyanBrush"),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(3),
                Padding = new Thickness(5, 2, 5, 2)
            };
            badge.Child = new TextBlock
            {
                Text = $"📏 T(s): {_activeProfileStats?.MinTemp:F1}°C - {_activeProfileStats?.MaxTemp:F1}°C (L={_activeProfileStats?.TotalLengthPx:F0}px)",
                FontSize = 9.5,
                FontWeight = FontWeights.Bold,
                Foreground = Brushes.White
            };
            Canvas.SetLeft(badge, midX + 6);
            Canvas.SetTop(badge, midY - 18);
            canvas.Children.Add(badge);
        }

        private void DrawProbePinsVector(Canvas canvas)
        {
            for (int i = 0; i < _probePoints.Count; i++)
            {
                var pt = _probePoints[i];
                var brush = i == 0 ? (Brush)FindResource("CyanBrush") : (Brush)FindResource("WarningBrush");

                // Target ring
                var ring = new Ellipse
                {
                    Width = 16,
                    Height = 16,
                    Stroke = brush,
                    StrokeThickness = 2.0,
                    Fill = new SolidColorBrush(Color.FromArgb(40, 255, 255, 255))
                };
                Canvas.SetLeft(ring, pt.Position.X - 8);
                Canvas.SetTop(ring, pt.Position.Y - 8);
                canvas.Children.Add(ring);

                // Center dot
                var dot = new Ellipse { Width = 4, Height = 4, Fill = brush };
                Canvas.SetLeft(dot, pt.Position.X - 2);
                Canvas.SetTop(dot, pt.Position.Y - 2);
                canvas.Children.Add(dot);

                // Badge
                var b = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(235, 12, 16, 24)),
                    BorderBrush = brush,
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(5, 2, 5, 2)
                };
                b.Child = new TextBlock
                {
                    Text = $"{pt.Label}: {pt.Temperature:F1} °C",
                    FontSize = 10,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                Canvas.SetLeft(b, pt.Position.X + 10);
                Canvas.SetTop(b, pt.Position.Y - 14);
                canvas.Children.Add(b);
            }

            // Connecting Caliper line between P1 and P2
            if (_probePoints.Count >= 2)
            {
                var p1 = _probePoints[0].Position;
                var p2 = _probePoints[1].Position;

                double deltaT = Math.Abs(_probePoints[0].Temperature - _probePoints[1].Temperature);
                bool isCrit = deltaT >= 2.2;

                var caliperLine = new Line
                {
                    X1 = p1.X,
                    Y1 = p1.Y,
                    X2 = p2.X,
                    Y2 = p2.Y,
                    Stroke = isCrit ? Brushes.Red : Brushes.LightGreen,
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 4, 3 }
                };
                canvas.Children.Add(caliperLine);

                double midX = (p1.X + p2.X) / 2.0;
                double midY = (p1.Y + p2.Y) / 2.0;

                var badge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(240, isCrit ? (byte)150 : (byte)15, isCrit ? (byte)20 : (byte)60, isCrit ? (byte)20 : (byte)25)),
                    BorderBrush = isCrit ? Brushes.Red : Brushes.LightGreen,
                    BorderThickness = new Thickness(1.5),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(6, 3, 6, 3)
                };
                badge.Child = new TextBlock
                {
                    Text = $"⚖️ ΔT = {deltaT:F1} K {(isCrit ? "[ARMSTRONG ALARM]" : "[NORMAL]")}",
                    FontSize = 10,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                Canvas.SetLeft(badge, midX - 40);
                Canvas.SetTop(badge, midY - 22);
                canvas.Children.Add(badge);
            }
        }

        // --- Interactive Segmented Tool Switching ---
        private void ToolRadio_Checked(object sender, RoutedEventArgs e)
        {
            if (RbToolPan == null) return;

            if (RbToolPan.IsChecked == true) _activeTool = ActiveCanvasTool.PanZoom;
            else if (RbToolRoi.IsChecked == true) _activeTool = ActiveCanvasTool.RoiSelection;
            else if (RbToolProfile.IsChecked == true) _activeTool = ActiveCanvasTool.ThermalProfile;
            else if (RbToolProbe.IsChecked == true) _activeTool = ActiveCanvasTool.PointProbe;
            else if (RbToolWL.IsChecked == true) _activeTool = ActiveCanvasTool.WindowLevelDrag;

            UpdateToolInstructions();
        }

        private void UpdateToolInstructions()
        {
            if (StatusText == null || CanvasOriginal == null || CanvasResult == null) return;

            switch (_activeTool)
            {
                case ActiveCanvasTool.PanZoom:
                    StatusText.Text = "Werkzeug: Pan & Zoom | Ziehen Sie mit linker oder rechter Maustaste zum Verschieben, Mausrad zum Zoomen.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Mausrad = Zoom | Ziehen = Verschieben";
                    CanvasOriginal.Cursor = Cursors.Hand;
                    CanvasResult.Cursor = Cursors.Hand;
                    break;
                case ActiveCanvasTool.RoiSelection:
                    StatusText.Text = "Werkzeug: ROI Fokus | Ziehen Sie ein Rechteck über ein interessierendes Gewebeareal (z. B. Großzehe).";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Rechteck ziehen = Bereich wählen";
                    CanvasOriginal.Cursor = Cursors.Cross;
                    CanvasResult.Cursor = Cursors.Cross;
                    break;
                case ActiveCanvasTool.ThermalProfile:
                    StatusText.Text = "Werkzeug: Schnittprofil T(s) | Ziehen Sie eine Linie über das Gewebe zur Erzeugung des Temperaturdiagramms.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Linie ziehen = Schnittprofil analysieren";
                    CanvasOriginal.Cursor = Cursors.Pen;
                    CanvasResult.Cursor = Cursors.Pen;
                    break;
                case ActiveCanvasTool.PointProbe:
                    StatusText.Text = "Werkzeug: Punktsonden P₁-P₂ | Klicken Sie nacheinander auf zwei Stellen für den bilateralen Armstrong-Vergleich.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Klick = Messpunkt setzen (Armstrong ΔT)";
                    CanvasOriginal.Cursor = Cursors.Cross;
                    CanvasResult.Cursor = Cursors.Cross;
                    break;
                case ActiveCanvasTool.WindowLevelDrag:
                    StatusText.Text = "Werkzeug: W/L Ziehen | Linke Maustaste gedrückt halten und ziehen (horizontal = Kontrast, vertikal = Helligkeit).";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Ziehen = DICOM Fensterung (W/L)";
                    CanvasOriginal.Cursor = Cursors.SizeAll;
                    CanvasResult.Cursor = Cursors.SizeAll;
                    break;
            }
        }

        // --- Mouse Events for Viewports (Pan, ROI, Profile, Probes, W/L) ---
        private void ViewportOriginal_MouseDown(object sender, MouseButtonEventArgs e) => HandleViewportMouseDown(CanvasOriginal, ScrollOriginal, e);
        private void ViewportResult_MouseDown(object sender, MouseButtonEventArgs e) => HandleViewportMouseDown(CanvasResult, ScrollResult, e);

        private void HandleViewportMouseDown(Grid canvas, ScrollViewer scroller, MouseButtonEventArgs e)
        {
            if (_originalBitmap == null) return;
            Point pos = e.GetPosition(canvas);

            // Right or Middle button ALWAYS initiates Panning
            if (e.RightButton == MouseButtonState.Pressed || e.MiddleButton == MouseButtonState.Pressed)
            {
                StartPanning(pos, scroller, canvas);
                return;
            }

            if (e.LeftButton == MouseButtonState.Pressed)
            {
                switch (_activeTool)
                {
                    case ActiveCanvasTool.PanZoom:
                        StartPanning(pos, scroller, canvas);
                        break;

                    case ActiveCanvasTool.RoiSelection:
                        _isSelectingROI = true;
                        _roiStartPoint = pos;
                        if (_roiSelectionRect == null)
                        {
                            _roiSelectionRect = new System.Windows.Shapes.Rectangle
                            {
                                Stroke = Brushes.Cyan,
                                StrokeThickness = 1.5,
                                StrokeDashArray = new DoubleCollection { 4, 2 },
                                Fill = new SolidColorBrush(Color.FromArgb(30, 0, 229, 255))
                            };
                            OverlayOriginalCanvas.Children.Add(_roiSelectionRect);
                        }
                        _roiSelectionRect.Visibility = Visibility.Visible;
                        Canvas.SetLeft(_roiSelectionRect, pos.X);
                        Canvas.SetTop(_roiSelectionRect, pos.Y);
                        _roiSelectionRect.Width = 0;
                        _roiSelectionRect.Height = 0;
                        canvas.CaptureMouse();
                        break;

                    case ActiveCanvasTool.ThermalProfile:
                        _isDrawingProfile = true;
                        _profileStartPoint = pos;
                        _profileEndPoint = pos;
                        canvas.CaptureMouse();
                        break;

                    case ActiveCanvasTool.PointProbe:
                        PlaceProbePoint(pos);
                        break;

                    case ActiveCanvasTool.WindowLevelDrag:
                        _isDraggingWL = true;
                        _wlStartPoint = e.GetPosition(this);
                        _wlStartWidth = _windowWidth;
                        _wlStartCenter = _windowCenter;
                        canvas.CaptureMouse();
                        break;
                }
            }
        }

        private void StartPanning(Point pos, ScrollViewer scroller, Grid canvas)
        {
            _isPanning = true;
            _panStartMouse = pos;
            _panStartHScroll = scroller.HorizontalOffset;
            _panStartVScroll = scroller.VerticalOffset;
            canvas.CaptureMouse();
        }

        private void ViewportOriginal_MouseMove(object sender, MouseEventArgs e) => HandleViewportMouseMove(CanvasOriginal, ScrollOriginal, e);
        private void ViewportResult_MouseMove(object sender, MouseEventArgs e) => HandleViewportMouseMove(CanvasResult, ScrollResult, e);

        private void HandleViewportMouseMove(Grid canvas, ScrollViewer scroller, MouseEventArgs e)
        {
            Point pos = e.GetPosition(canvas);
            int x = (int)pos.X;
            int y = (int)pos.Y;

            // Radiometric Cursor Readout
            if (_rawGrayPixels != null && x >= 0 && x < _rawWidth && y >= 0 && y < _rawHeight)
            {
                byte val = _rawGrayPixels[y * _rawWidth + x];
                double temp = ThermalAnalysisHelper.RawToTemperature(val);
                CursorCoordsText.Text = $"X: {x}, Y: {y} | Radiometrie: T = {temp:F1}°C (Raw: {val})";
            }

            // Panning
            if (_isPanning)
            {
                double dx = (pos.X - _panStartMouse.X) * _currentZoom;
                double dy = (pos.Y - _panStartMouse.Y) * _currentZoom;
                scroller.ScrollToHorizontalOffset(_panStartHScroll - dx);
                scroller.ScrollToVerticalOffset(_panStartVScroll - dy);
                return;
            }

            // Interactive Window/Level Drag
            if (_isDraggingWL)
            {
                Point curScreen = e.GetPosition(this);
                double dx = curScreen.X - _wlStartPoint.X;
                double dy = curScreen.Y - _wlStartPoint.Y;

                double newW = Math.Clamp(_wlStartWidth + dx * 1.5, 40, 255);
                double newL = Math.Clamp(_wlStartCenter - dy * 1.2, 20, 235);

                SliderWindowWidth.Value = newW;
                SliderWindowLevel.Value = newL;
                return;
            }

            // ROI Rubberband
            if (_isSelectingROI && _roiSelectionRect != null)
            {
                double curX = Math.Max(0, Math.Min(_rawWidth, pos.X));
                double curY = Math.Max(0, Math.Min(_rawHeight, pos.Y));

                double minX = Math.Min(_roiStartPoint.X, curX);
                double minY = Math.Min(_roiStartPoint.Y, curY);
                double rw = Math.Abs(curX - _roiStartPoint.X);
                double rh = Math.Abs(curY - _roiStartPoint.Y);

                Canvas.SetLeft(_roiSelectionRect, minX);
                Canvas.SetTop(_roiSelectionRect, minY);
                _roiSelectionRect.Width = rw;
                _roiSelectionRect.Height = rh;
                return;
            }

            // Thermal Profile Line Rubberband
            if (_isDrawingProfile && _rawGrayPixels != null)
            {
                _profileEndPoint = new Point(Math.Clamp(pos.X, 0, _rawWidth - 1), Math.Clamp(pos.Y, 0, _rawHeight - 1));
                _activeProfileStats = ThermalAnalysisHelper.SampleProfileLine(_rawGrayPixels, _rawWidth, _rawHeight, _profileStartPoint, _profileEndPoint);
                RedrawInteractiveOverlays();
                UpdateProfileUI();
            }
        }

        private void ViewportOriginal_MouseUp(object sender, MouseButtonEventArgs e) => HandleViewportMouseUp(CanvasOriginal, e);
        private void ViewportResult_MouseUp(object sender, MouseButtonEventArgs e) => HandleViewportMouseUp(CanvasResult, e);

        private void HandleViewportMouseUp(Grid canvas, MouseButtonEventArgs e)
        {
            if (_isPanning)
            {
                _isPanning = false;
                canvas.ReleaseMouseCapture();
            }

            if (_isDraggingWL)
            {
                _isDraggingWL = false;
                canvas.ReleaseMouseCapture();
            }

            if (_isSelectingROI && _roiSelectionRect != null)
            {
                _isSelectingROI = false;
                canvas.ReleaseMouseCapture();

                double w = _roiSelectionRect.Width;
                double h = _roiSelectionRect.Height;

                if (w > 20 && h > 20)
                {
                    double minX = Canvas.GetLeft(_roiSelectionRect);
                    double minY = Canvas.GetTop(_roiSelectionRect);
                    _currentROI = new int[] { (int)minX, (int)minY, (int)(minX + w), (int)(minY + h) };
                    StatusText.Text = $"ROI gewählt: [{_currentROI[0]}, {_currentROI[1]} bis {_currentROI[2]}, {_currentROI[3]}]. Berechne...";
                    _ = RunPipelineAsync();
                }
            }

            if (_isDrawingProfile)
            {
                _isDrawingProfile = false;
                canvas.ReleaseMouseCapture();

                if (_activeProfileStats != null && _activeProfileStats.Samples.Count >= 2)
                {
                    InspectorTabs.SelectedItem = TabProfile;
                    RenderProfileGraph(_activeProfileStats);
                    StatusText.Text = $"Schnittprofil erstellt: Pfadlänge {_activeProfileStats.TotalLengthPx:F0} px | T={_activeProfileStats.MinTemp:F1}°C bis {_activeProfileStats.MaxTemp:F1}°C.";
                }
            }
        }

        private void ViewportOriginal_MouseLeave(object sender, MouseEventArgs e) => CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
        private void Viewport_MouseLeave(object sender, MouseEventArgs e) => CursorCoordsText.Text = "X: --, Y: -- | Temp: --";

        // --- Probes Management ---
        private void PlaceProbePoint(Point pos)
        {
            if (_rawGrayPixels == null || _rawWidth == 0 || _rawHeight == 0) return;

            int x = (int)Math.Clamp(pos.X, 0, _rawWidth - 1);
            int y = (int)Math.Clamp(pos.Y, 0, _rawHeight - 1);

            byte val = _rawGrayPixels[y * _rawWidth + x];
            double temp = ThermalAnalysisHelper.RawToTemperature(val);

            // Cycle between P1 and P2 (replace if >= 2)
            if (_probePoints.Count >= 2)
            {
                _probePoints.Clear();
            }

            int id = _probePoints.Count + 1;
            var probe = new ThermalProbePoint
            {
                Id = id,
                Position = new Point(x, y),
                RawVal = val,
                Temperature = temp,
                Label = $"P{id}"
            };
            _probePoints.Add(probe);

            UpdateProbesUI();
            RedrawInteractiveOverlays();

            if (_probePoints.Count >= 2)
            {
                InspectorTabs.SelectedItem = TabProbes;
            }
        }

        private void UpdateProbesUI()
        {
            GridProbes.ItemsSource = null;
            GridProbes.ItemsSource = _probePoints;

            if (_probePoints.Count >= 2)
            {
                var p1 = _probePoints[0];
                var p2 = _probePoints[1];
                var eval = ThermalAnalysisHelper.EvaluateBilateralDelta(p1.Temperature, p2.Temperature);

                TxtProbeDeltaT.Text = $"ΔT = {eval.DeltaT:F1} K";
                TxtProbeAssessment.Text = eval.StatusText;

                if (eval.IsPathologic)
                {
                    BadgeArmstrongState.Background = Brushes.DarkRed;
                    TxtProbeRiskBadge.Text = "PATHOLOGISCH (≥ 2.2 K)";
                    TxtProbeRiskBadge.Foreground = Brushes.White;
                    BorderArmstrongRiskCard.Background = new SolidColorBrush(Color.FromArgb(45, 211, 47, 47));
                    BorderArmstrongRiskCard.BorderBrush = Brushes.Red;

                    FloatingArmstrongBanner.Visibility = Visibility.Visible;
                    TxtFloatingArmstrong.Text = $"ARMSTRONG-ALARM: ΔT = {eval.DeltaT:F1} K (≥ 2.2 K) — Hohes Ulkusrisiko!";
                }
                else
                {
                    BadgeArmstrongState.Background = new SolidColorBrush(Color.FromRgb(20, 50, 25));
                    TxtProbeRiskBadge.Text = "PHYSIOLOGISCH NORMAL";
                    TxtProbeRiskBadge.Foreground = Brushes.LightGreen;
                    BorderArmstrongRiskCard.Background = (Brush)FindResource("SurfaceCardBrush");
                    BorderArmstrongRiskCard.BorderBrush = (Brush)FindResource("BorderBrush");

                    FloatingArmstrongBanner.Visibility = Visibility.Collapsed;
                }
            }
            else
            {
                TxtProbeDeltaT.Text = "ΔT = -- K";
                TxtProbeAssessment.Text = "Klicken Sie auf zwei Stellen für den bilateralen Armstrong-Vergleich.";
                BadgeArmstrongState.Background = (Brush)FindResource("SurfaceCardBrush");
                TxtProbeRiskBadge.Text = "1/2 SONDE GESETZT";
                TxtProbeRiskBadge.Foreground = (Brush)FindResource("CyanBrush");
                FloatingArmstrongBanner.Visibility = Visibility.Collapsed;
            }
        }

        private void BtnResetProbes_Click(object sender, RoutedEventArgs e)
        {
            _probePoints.Clear();
            _activeProfileStats = null;
            UpdateProbesUI();
            CanvasProfileGraph.Children.Clear();
            TxtProfileMinTemp.Text = "-- °C";
            TxtProfileMaxTemp.Text = "-- °C";
            TxtProfileMeanTemp.Text = "-- °C";
            TxtProfileLength.Text = "Pfadlänge: -- px";
            TxtProfileMaxGrad.Text = "Maximaler Gradient |dT/ds|: -- K/px";
            RedrawInteractiveOverlays();
            StatusText.Text = "Messpunkt-Sonden und Schnittprofil zurückgesetzt.";
        }

        // --- Thermal Profile Graph 2D Vector Rendering ---
        private void UpdateProfileUI()
        {
            if (_activeProfileStats == null) return;
            TxtProfileMinTemp.Text = $"{_activeProfileStats.MinTemp:F1} °C";
            TxtProfileMaxTemp.Text = $"{_activeProfileStats.MaxTemp:F1} °C";
            TxtProfileMeanTemp.Text = $"{_activeProfileStats.MeanTemp:F1} °C";
            TxtProfileLength.Text = $"Pfadlänge: {_activeProfileStats.TotalLengthPx:F0} px ({_activeProfileStats.SampleCount} Stützstellen)";
            TxtProfileMaxGrad.Text = $"Maximaler Gradient |dT/ds|: {_activeProfileStats.MaxGradient:F2} K/px";
            RenderProfileGraph(_activeProfileStats);
        }

        private void CanvasProfileGraph_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            if (_activeProfileStats != null)
            {
                RenderProfileGraph(_activeProfileStats);
            }
        }

        private void RenderProfileGraph(ThermalProfileStats stats)
        {
            CanvasProfileGraph.Children.Clear();
            if (stats == null || stats.Samples.Count < 2) return;

            double w = CanvasProfileGraph.ActualWidth > 50 ? CanvasProfileGraph.ActualWidth : 420;
            double h = CanvasProfileGraph.ActualHeight > 50 ? CanvasProfileGraph.ActualHeight : 210;

            double padLeft = 36, padRight = 14, padTop = 18, padBottom = 26;
            double plotW = w - padLeft - padRight;
            double plotH = h - padTop - padBottom;

            // Temperature Axis (20°C to 42°C)
            double tMin = 20.0, tMax = 42.0;

            // Draw Grid Lines & Labels
            for (double t = 20.0; t <= 40.0; t += 5.0)
            {
                double yNorm = (t - tMin) / (tMax - tMin);
                double yScreen = padTop + (1.0 - yNorm) * plotH;

                var gridLine = new Line
                {
                    X1 = padLeft,
                    Y1 = yScreen,
                    X2 = w - padRight,
                    Y2 = yScreen,
                    Stroke = new SolidColorBrush(Color.FromRgb(32, 40, 54)),
                    StrokeThickness = 1.0,
                    StrokeDashArray = new DoubleCollection { 3, 2 }
                };
                CanvasProfileGraph.Children.Add(gridLine);

                var tb = new TextBlock
                {
                    Text = $"{t:F0}°",
                    FontSize = 9,
                    Foreground = (Brush)FindResource("TextMutedBrush"),
                    HorizontalAlignment = HorizontalAlignment.Right
                };
                Canvas.SetLeft(tb, 6);
                Canvas.SetTop(tb, yScreen - 7);
                CanvasProfileGraph.Children.Add(tb);
            }

            // Draw Area Fill under Curve
            var areaPolygon = new Polygon
            {
                Fill = new LinearGradientBrush(
                    Color.FromArgb(90, 0, 229, 255),
                    Color.FromArgb(10, 0, 120, 212),
                    new Point(0, 0),
                    new Point(0, 1))
            };
            areaPolygon.Points.Add(new Point(padLeft, padTop + plotH));

            // Draw Profile Curve
            var polyline = new Polyline
            {
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 2.2,
                StrokeLineJoin = PenLineJoin.Round
            };

            int n = stats.Samples.Count;
            for (int i = 0; i < n; i++)
            {
                var s = stats.Samples[i];
                double xNorm = i / (double)(n - 1);
                double yNorm = Math.Clamp((s.Temperature - tMin) / (tMax - tMin), 0.0, 1.0);

                double sx = padLeft + xNorm * plotW;
                double sy = padTop + (1.0 - yNorm) * plotH;

                var pt = new Point(sx, sy);
                polyline.Points.Add(pt);
                areaPolygon.Points.Add(pt);
            }

            areaPolygon.Points.Add(new Point(padLeft + plotW, padTop + plotH));
            CanvasProfileGraph.Children.Add(areaPolygon);
            CanvasProfileGraph.Children.Add(polyline);

            // Bottom Axis Labels
            var tbStart = new TextBlock { Text = "0 px", FontSize = 9, Foreground = (Brush)FindResource("TextMutedBrush") };
            Canvas.SetLeft(tbStart, padLeft);
            Canvas.SetTop(tbStart, h - 18);
            CanvasProfileGraph.Children.Add(tbStart);

            var tbEnd = new TextBlock { Text = $"{stats.TotalLengthPx:F0} px", FontSize = 9, Foreground = (Brush)FindResource("TextMutedBrush") };
            Canvas.SetLeft(tbEnd, w - padRight - 35);
            Canvas.SetTop(tbEnd, h - 18);
            CanvasProfileGraph.Children.Add(tbEnd);
        }

        private void BtnCopyProfileCsv_Click(object sender, RoutedEventArgs e)
        {
            if (_activeProfileStats == null || _activeProfileStats.Samples.Count == 0)
            {
                MessageBox.Show("Keine Schnittprofildaten vorhanden. Bitte zuerst eine Linie im Bild ziehen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var sb = new StringBuilder();
            sb.AppendLine("Index;X;Y;Distance_px;Temperature_C;Gradient_K_per_px;RawVal");
            foreach (var s in _activeProfileStats.Samples)
            {
                sb.AppendLine($"{s.Index};{s.X};{s.Y};{s.Distance:F2};{s.Temperature:F2};{s.Gradient:F3};{s.RawVal}");
            }

            try
            {
                Clipboard.SetText(sb.ToString());
                StatusText.Text = $"Profildaten ({_activeProfileStats.Samples.Count} Punkte) erfolgreich in Zwischenablage kopiert!";
                MessageBox.Show("Schnittprofildaten erfolgreich als CSV in die Zwischenablage kopiert!", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Kopieren: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // --- Synchronized Scrolling & Mouse Wheel Zoom ---
        private void Viewport_PreviewMouseWheel(object sender, MouseWheelEventArgs e)
        {
            double factor = e.Delta > 0 ? 1.15 : (1.0 / 1.15);
            double newZoom = Math.Clamp(_currentZoom * factor, 0.25, 6.0);
            if (Math.Abs(newZoom - _currentZoom) > 0.001)
            {
                _currentZoom = newZoom;
                ApplyZoom();
            }
            e.Handled = true;
        }

        private void ScrollOriginal_ScrollChanged(object sender, ScrollChangedEventArgs e)
        {
            if (_syncViewports && !_isSyncingScroll && ScrollResult != null)
            {
                _isSyncingScroll = true;
                ScrollResult.ScrollToHorizontalOffset(e.HorizontalOffset);
                ScrollResult.ScrollToVerticalOffset(e.VerticalOffset);
                _isSyncingScroll = false;
            }
        }

        private void ScrollResult_ScrollChanged(object sender, ScrollChangedEventArgs e)
        {
            if (_syncViewports && !_isSyncingScroll && ScrollOriginal != null)
            {
                _isSyncingScroll = true;
                ScrollOriginal.ScrollToHorizontalOffset(e.HorizontalOffset);
                ScrollOriginal.ScrollToVerticalOffset(e.VerticalOffset);
                _isSyncingScroll = false;
            }
        }

        private void ApplyZoom()
        {
            var st = new ScaleTransform(_currentZoom, _currentZoom);
            CanvasOriginal.LayoutTransform = st;
            CanvasResult.LayoutTransform = st;
            UpdateHudReadouts();
        }

        private void BtnZoomIn_Click(object sender, RoutedEventArgs e)
        {
            _currentZoom = Math.Min(6.0, _currentZoom + 0.25);
            ApplyZoom();
        }

        private void BtnZoomOut_Click(object sender, RoutedEventArgs e)
        {
            _currentZoom = Math.Max(0.25, _currentZoom - 0.25);
            ApplyZoom();
        }

        private void BtnZoomReset_Click(object sender, RoutedEventArgs e)
        {
            _currentZoom = 1.0;
            ApplyZoom();
        }

        private void BtnZoomFit_Click(object sender, RoutedEventArgs e)
        {
            if (_rawWidth > 0 && ScrollOriginal != null && ScrollOriginal.ActualWidth > 50)
            {
                double fitX = ScrollOriginal.ActualWidth / _rawWidth;
                double fitY = ScrollOriginal.ActualHeight / _rawHeight;
                _currentZoom = Math.Clamp(Math.Min(fitX, fitY) * 0.95, 0.25, 3.0);
            }
            else
            {
                _currentZoom = 0.5;
            }
            ApplyZoom();
        }

        // --- Clinical Presets ---
        private void ComboPreset_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ComboPreset == null) return;
            switch (ComboPreset.SelectedIndex)
            {
                case 1: // Diabetischer Fuß (Armstrong)
                    ComboPalette.SelectedIndex = 0; // Ironbow
                    RbToolProbe.IsChecked = true;
                    InspectorTabs.SelectedItem = TabProbes;
                    StatusText.Text = "Preset aktiv: Diabetischer Fuß. Setzen Sie Sonden P₁/P₂ oder klicken Sie 'Füße trennen'.";
                    break;

                case 2: // Gefäßstatus / DSA (Frangi)
                    ComboPalette.SelectedIndex = 0;
                    ChkEnableVeinOverlay.IsChecked = true;
                    _enableVeinOverlay = true;
                    ComboVeinRenderMode.SelectedIndex = 1; // PureAngiography
                    InspectorTabs.SelectedItem = TabVascular;
                    RefreshResultImageOnly();
                    StatusText.Text = "Preset aktiv: Reiner Gefäßbaum DSA (Digital Subtraction Angiography).";
                    break;

                case 3: // Akute Entzündung (Top-Hat MAD)
                    ComboPalette.SelectedIndex = 0;
                    SliderK.Value = 3.0;
                    RbToolRoi.IsChecked = true;
                    InspectorTabs.SelectedIndex = 1; // Herde & Befunde
                    StatusText.Text = "Preset aktiv: Fokale Entzündungsdetektion (Top-Hat MAD k=3.0).";
                    break;

                case 4: // Ischämie-Verdacht (Perfusion)
                    ComboPalette.SelectedIndex = 2; // Inferno
                    InspectorTabs.SelectedIndex = 3; // Perfusion
                    StatusText.Text = "Preset aktiv: Longitudinale Perfusion & Temperaturgradient dT/dy.";
                    break;
            }
        }

        private void ChkMinMaxTracker_Click(object sender, RoutedEventArgs e)
        {
            _showMinMaxTracker = ChkMinMaxTracker.IsChecked == true;
            RedrawInteractiveOverlays();
        }

        private void BtnResetROI_Click(object sender, RoutedEventArgs e)
        {
            _currentROI = null;
            if (_roiSelectionRect != null) _roiSelectionRect.Visibility = Visibility.Collapsed;
            StatusText.Text = "ROI zurückgesetzt. Vollbildanalyse aktiv.";
            _ = RunPipelineAsync();
        }

        private async void BtnAutoSplitFeet_Click(object sender, RoutedEventArgs e)
        {
            if (_currentImagePath == null || _originalBitmap == null)
            {
                MessageBox.Show("Bitte zuerst ein Wärmebild öffnen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            AnalysisProgressBar.Visibility = Visibility.Visible;
            StatusText.Text = "Trennt linke und rechte Extremität automatisch und berechnet bilateralen Armstrong-Vergleich...";

            try
            {
                var symRes = await _engineService.RunBilateralSymmetryAsync(_currentImagePath, _currentImagePath);
                if (symRes != null)
                {
                    symRes.Zones ??= new();
                    GridSymmetry.ItemsSource = symRes.Zones;
                    TxtSymmetryAssessment.Text = $"{symRes.OverallStatus ?? "NORMAL"}: {symRes.ClinicalAssessment ?? string.Empty} (Max ΔT = {symRes.MaxDeltaT:F1} K)";
                    InspectorTabs.SelectedIndex = 4; // Switch to bilateral tab
                    StatusText.Text = $"Beide Füße erfolgreich verglichen: Max ΔT = {symRes.MaxDeltaT:F1} K.";
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler bei der Fuß-Trennung: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
            finally
            {
                AnalysisProgressBar.Visibility = Visibility.Collapsed;
            }
        }

        private void BtnToggleVascular_Click(object sender, RoutedEventArgs e)
        {
            ChkFrangi.IsChecked = true;
            _enableVeinOverlay = true;
            if (ChkEnableVeinOverlay != null) ChkEnableVeinOverlay.IsChecked = true;
            InspectorTabs.SelectedItem = TabVascular;

            if (_cachedVeinPixels == null)
            {
                _ = RunPipelineAsync();
            }
            else
            {
                RefreshResultImageOnly();
            }
        }

        private void BtnDSA_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedItem = TabVascular;
            ChkEnableVeinOverlay.IsChecked = true;
            _enableVeinOverlay = true;
            ComboVeinRenderMode.SelectedIndex = 1; // PureAngiography
            RefreshResultImageOnly();
        }

        private void ChkEnableVeinOverlay_Click(object sender, RoutedEventArgs e)
        {
            _enableVeinOverlay = ChkEnableVeinOverlay.IsChecked == true;
            RefreshResultImageOnly();
        }

        private void ComboVeinRenderMode_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ComboVeinRenderMode == null) return;
            _veinRenderMode = ComboVeinRenderMode.SelectedIndex switch
            {
                1 => VeinRenderMode.PureAngiography,
                2 => VeinRenderMode.RoyalCobalt,
                3 => VeinRenderMode.SurgicalGreen,
                _ => VeinRenderMode.FluorescentCyan
            };
            RefreshResultImageOnly();
        }

        private void SliderVeinOpacity_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (TxtVeinOpacity == null || SliderVeinOpacity == null) return;
            _veinOpacity = SliderVeinOpacity.Value;
            TxtVeinOpacity.Text = $"{(_veinOpacity * 100):F0}%";
            RefreshResultImageOnly();
        }

        private void SliderVeinThreshold_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (TxtVeinThreshold == null || SliderVeinThreshold == null) return;
            _veinThreshold = (byte)Math.Round(SliderVeinThreshold.Value);
            TxtVeinThreshold.Text = $"{_veinThreshold}";
            UpdateVeinMetricsUI();
            RefreshResultImageOnly();
        }

        private void BtnRecalcVeins_Click(object sender, RoutedEventArgs e)
        {
            _cachedVeinPixels = null;
            ChkFrangi.IsChecked = true;
            _ = RunPipelineAsync();
        }

        private void UpdateVeinMetricsUI()
        {
            if (_cachedVeinPixels == null || TxtVesselCoverage == null) return;
            int count = 0;
            for (int i = 0; i < _cachedVeinPixels.Length; i++)
            {
                if (_cachedVeinPixels[i] >= _veinThreshold) count++;
            }
            double pct = (double)count / _cachedVeinPixels.Length * 100.0;
            TxtVesselCoverage.Text = $"• Gefäßabdeckung: {pct:F1}% des Gewebes ({count:N0} Vaskulär-Pixel)";
        }

        private void UpdateHudReadouts()
        {
            if (HudVp1BottomLeft != null)
                HudVp1BottomLeft.Text = $"LUT: {_activePalette.ToString().ToUpper()}\nW/L: {_windowWidth:F0} / {_windowCenter:F0}";
            if (HudVp1TopRight != null)
                HudVp1TopRight.Text = $"MATRIX: {_rawWidth}x{_rawHeight}\nZOOM: {(_currentZoom * 100):F0}%";
        }

        // --- Window/Level Sliders ---
        private void SliderWindowWidth_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (TxtWindowWidth == null || SliderWindowWidth == null) return;
            _windowWidth = SliderWindowWidth.Value;
            TxtWindowWidth.Text = $"{_windowWidth:F0}";
            ApplyWindowLevelToViewports();
        }

        private void SliderWindowLevel_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (TxtWindowLevel == null || SliderWindowLevel == null) return;
            _windowCenter = SliderWindowLevel.Value;
            TxtWindowLevel.Text = $"{_windowCenter:F0}";
            ApplyWindowLevelToViewports();
        }

        private void ApplyWindowLevelToViewports()
        {
            if (_rawGrayPixels == null || _rawWidth == 0 || _rawHeight == 0) return;
            _originalBitmap = PaletteService.ApplyPalette(_rawGrayPixels, _rawWidth, _rawHeight, _activePalette, _windowWidth, _windowCenter);
            ImgOriginal.Source = _originalBitmap;
            RefreshResultImageOnly();
        }

        private void BtnWLReset_Click(object sender, RoutedEventArgs e)
        {
            SliderWindowWidth.Value = 255;
            SliderWindowLevel.Value = 128;
        }

        private void BtnWLSoftTissue_Click(object sender, RoutedEventArgs e)
        {
            SliderWindowWidth.Value = 150;
            SliderWindowLevel.Value = 140;
        }

        private void BtnWLHotspot_Click(object sender, RoutedEventArgs e)
        {
            SliderWindowWidth.Value = 100;
            SliderWindowLevel.Value = 190;
        }

        private void ComboPalette_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (ComboPalette == null) return;
            _activePalette = ComboPalette.SelectedIndex switch
            {
                1 => ColorPalette.Rainbow,
                2 => ColorPalette.Inferno,
                3 => ColorPalette.Grayscale,
                _ => ColorPalette.Ironbow
            };

            if (_rawGrayPixels != null && _rawWidth > 0 && _rawHeight > 0)
            {
                _originalBitmap = PaletteService.ApplyPalette(_rawGrayPixels, _rawWidth, _rawHeight, _activePalette, _windowWidth, _windowCenter);
                ImgOriginal.Source = _originalBitmap;
                RefreshResultImageOnly();
                UpdateHudReadouts();
            }
        }

        private void SliderK_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e) { }
        private void SliderKernel_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e) { }

        private void GridHotspots_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (GridHotspots.SelectedItem is HotspotSummary sel)
            {
                TxtLuaRecommendation.Text = $"Herd #{sel.Region.Id} [{sel.Assessment.RiskLevel}]: {sel.Assessment.Recommendation}";
            }
        }

        private void BtnResetLua_Click(object sender, RoutedEventArgs e) => LoadDefaultLuaRule();

        private void BtnApplyLua_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string rulePath = System.IO.Path.GetFullPath(System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "rules", "armstrong_criteria.lua"));
                File.WriteAllText(rulePath, TxtLuaCode.Text);
                _dbService.LogAuditAction("UPDATE_LUA_RULE", "Regel 'armstrong_criteria.lua' manuell über Editor aktualisiert.");
                _ = RunPipelineAsync();
                MessageBox.Show("Lua-Regel gespeichert und erfolgreich neu angewendet!", "Erfolg", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Speichern der Regel: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void RefreshAuditGrid()
        {
            try
            {
                var list = _dbService?.GetRecentEvaluations() ?? new();
                GridAudit.ItemsSource = list;
            }
            catch { }
        }

        // --- Menu Items ---
        private void MenuOpenImage_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new OpenFileDialog
            {
                Filter = "Wärmebilder (*.jpeg;*.jpg;*.png)|*.jpeg;*.jpg;*.png|Alle Dateien (*.*)|*.*",
                Title = "Thermografie-Aufnahme öffnen"
            };
            if (dlg.ShowDialog() == true)
            {
                LoadImage(dlg.FileName);
            }
        }

        private void MenuOpenContralateral_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new OpenFileDialog
            {
                Filter = "Wärmebilder (*.jpeg;*.jpg;*.png)|*.jpeg;*.jpg;*.png",
                Title = "Zweites Bild (Gegenseite für Seitenvergleich) öffnen"
            };
            if (dlg.ShowDialog() == true)
            {
                _contralateralImagePath = dlg.FileName;
                _ = RunBilateralSymmetryModeAsync();
            }
        }

        private async Task RunBilateralSymmetryModeAsync()
        {
            if (string.IsNullOrEmpty(_currentImagePath) || string.IsNullOrEmpty(_contralateralImagePath))
            {
                MessageBox.Show("Bitte laden Sie zuerst ein primäres Bild und ein zweites Kontralateral-Bild.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            AnalysisProgressBar.Visibility = Visibility.Visible;
            StatusText.Text = "Berechne bilateralen Seitenvergleich (Armstrong-Kriterien)...";
            try
            {
                var symRes = await _engineService.RunBilateralSymmetryAsync(_currentImagePath, _contralateralImagePath);
                if (symRes != null)
                {
                    symRes.Zones ??= new();
                    GridSymmetry.ItemsSource = symRes.Zones;
                    TxtSymmetryAssessment.Text = $"{symRes.OverallStatus ?? "NORMAL"}: {symRes.ClinicalAssessment ?? string.Empty} (Max ΔT = {symRes.MaxDeltaT:F1} K)";
                    InspectorTabs.SelectedIndex = 4;
                    StatusText.Text = $"Seitenvergleich abgeschlossen: Max ΔT = {symRes.MaxDeltaT:F1} K";
                }
            }
            finally
            {
                AnalysisProgressBar.Visibility = Visibility.Collapsed;
            }
        }

        private void BtnRunAnalysis_Click(object sender, RoutedEventArgs e) => _ = RunPipelineAsync();

        private void ModeInflammation_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedIndex = 1;
            _ = RunPipelineAsync();
        }

        private void ModeVascular_Click(object sender, RoutedEventArgs e) => BtnToggleVascular_Click(sender, e);
        private void ModePerfusion_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedIndex = 3;
            _ = RunPipelineAsync();
        }
        private void ModeBilateral_Click(object sender, RoutedEventArgs e) => BtnAutoSplitFeet_Click(sender, e);

        private void PaletteIronbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 0;
        private void PaletteRainbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 1;
        private void PaletteInferno_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 2;
        private void PaletteGray_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 3;

        private void MenuAuditLog_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 8;
        private void MenuLuaEditor_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 7;

        private void MenuBenchmark_Click(object sender, RoutedEventArgs e)
        {
            if (_latestResult != null)
            {
                MessageBox.Show(
                    $"Go Core Multithreading & AVX2 Benchmark:\n\n" +
                    $"• Body-Mask (Otsu & Chamfer): {_latestResult.Timing.BodyMaskMs:F2} ms\n" +
                    $"• Top-Hat (AVX2 SIMD): {_latestResult.Timing.TopHatMs:F2} ms\n" +
                    $"• Outlier Threshold (MAD): {_latestResult.Timing.ThresholdMs:F2} ms\n" +
                    $"• Geometrie & Circularity: {_latestResult.Timing.GeometryMs:F2} ms\n" +
                    $"• Frangi Vascular Mapping: {_latestResult.Timing.VascularMs:F2} ms\n" +
                    $"• Perfusion Gradient: {_latestResult.Timing.PerfusionMs:F2} ms\n" +
                    $"• Lua Regel-Evaluation: {_latestResult.Timing.LuaEvalMs:F2} ms\n\n" +
                    $"Gesamtlatenz: {_latestResult.Timing.TotalMs:F2} ms",
                    "Hardware Benchmark", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void MenuExportReport_Click(object sender, RoutedEventArgs e)
        {
            if (_latestResult == null)
            {
                MessageBox.Show("Bitte führen Sie zuerst eine Analyse durch.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var dlg = new SaveFileDialog
            {
                Filter = "HTML Befundbericht (*.html)|*.html|JSON Export (*.json)|*.json",
                FileName = $"Ignite_Befund_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.html"
            };

            if (dlg.ShowDialog() == true)
            {
                string html = $@"
<!DOCTYPE html>
<html>
<head>
    <meta charset='utf-8'/>
    <title>IGNITE Medical Report - {_activePatientId}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f11; color: #e1e1e6; padding: 30px; }}
        h1 {{ color: #007acc; border-bottom: 2px solid #333; padding-bottom: 10px; }}
        .card {{ background: #1c1c1f; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #2d2d33; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ border: 1px solid #333; padding: 10px; text-align: left; }}
        th {{ background: #25252b; color: #4ec9b0; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
        .critical {{ background: #900; color: #fff; }}
        .benign {{ background: #070; color: #fff; }}
    </style>
</head>
<body>
    <h1>IGNITE Medical Imaging Suite - Klinischer Befundbericht</h1>
    <div class='card'>
        <p><strong>Patienten-Hash (DSGVO):</strong> {_activePatientId}</p>
        <p><strong>Untersuchungsdatum:</strong> {DateTime.Now:dd.MM.yyyy HH:mm:ss}</p>
        <p><strong>Bilddatei:</strong> {System.IO.Path.GetFileName(_currentImagePath)}</p>
        <p><strong>Gesamtrisiko:</strong> <span class='badge {(_latestResult.HighestRisk == "CRITICAL" ? "critical" : "benign")}'>{_latestResult.HighestRisk}</span></p>
        <p><strong>Rechenzeit (Go Core + AVX2):</strong> {_latestResult.Timing.TotalMs:F2} ms</p>
    </div>
    <div class='card'>
        <h2>Detektierte Entzündungsherde ({_latestResult.TotalHotspots})</h2>
        <table>
            <tr>
                <th>ID</th><th>Fläche (px)</th><th>Anteil (%)</th><th>Max T</th><th>Zirkularität</th><th>Risikostufe</th><th>Klinische Empfehlung (Lua)</th>
            </tr>
            {string.Join("", _latestResult.Hotspots.Select(h => $@"
            <tr>
                <td>#{h.Region.Id}</td>
                <td>{h.Region.AreaPixels}</td>
                <td>{h.Region.AreaPercent:F2} %</td>
                <td>{h.Region.MaxVal}</td>
                <td>{h.Region.Circularity:F3}</td>
                <td><span class='badge {(h.Assessment.RiskLevel == "CRITICAL" ? "critical" : "benign")}'>{h.Assessment.RiskLevel}</span></td>
                <td>{h.Assessment.Recommendation}</td>
            </tr>"))}
        </table>
    </div>
</body>
</html>";
                File.WriteAllText(dlg.FileName, html);
                _dbService.LogAuditAction("EXPORT_REPORT", $"Befundbericht exportiert nach {dlg.FileName}");
                MessageBox.Show($"Befundbericht erfolgreich gespeichert:\n{dlg.FileName}", "Export abgeschlossen", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void MenuAbout_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show(
                "IGNITE Medical Imaging Suite v5.0.0\n" +
                "Jugend Forscht 2026 - Fachgebiet Arbeitswelt / Informatik\n\n" +
                "Architektur:\n" +
                "• Rechenkern: Go 1.27 + x86_64 AVX2 Vektor-Assembler (Plan 9)\n" +
                "• Desktop-Workstation: C# .NET 10 (WPF)\n" +
                "• Klinische Regel-Engine: Eingebettetes Lua (Armstrong et al. 2007)\n" +
                "• Datenschutz & Audit-Trail: SQLite (DSGVO Art. 30)\n\n" +
                "Entwickelt für die automatisierte thermografische Entzündungs- und Ulkusfrüherkennung.",
                "Über IGNITE", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void MenuDocs_Click(object sender, RoutedEventArgs e)
        {
            string docPath = System.IO.Path.GetFullPath(System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..", "..", "..", "..", "docs", "ALGORITHM.md"));
            if (File.Exists(docPath))
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo { FileName = docPath, UseShellExecute = true });
            }
            else
            {
                MessageBox.Show("Die Dokumentationsdatei ALGORITHM.md befindet sich im Ordner docs/.", "Dokumentation", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void MenuExit_Click(object sender, RoutedEventArgs e)
        {
            Application.Current.Shutdown();
        }
    }
}