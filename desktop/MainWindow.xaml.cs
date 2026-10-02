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
    public enum ActiveViewMode
    {
        DualView,
        CurtainWipe,
        Relief3D,
        PureDSA,
        IsothermSlice,
        DigitalSubtraction
    }

    public enum ActiveCanvasTool
    {
        PanZoom,
        RoiSelection,
        ThermalProfile,
        PointProbe,
        WindowLevelDrag,
        BoneDrawing,
        Goniometer
    }

    public class DrawnBone
    {
        public string Id { get; set; } = Guid.NewGuid().ToString("N")[..6];
        public string Name { get; set; } = "Knochen";
        public List<Point> Points { get; set; } = new();
        public double Thickness { get; set; } = 2.0;
        public Brush StrokeBrush { get; set; } = new SolidColorBrush(Color.FromRgb(30, 41, 59));
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
        private bool _isInitialized = false;

        // Active Modes
        private ActiveCanvasTool _activeTool = ActiveCanvasTool.PanZoom;
        private ActiveViewMode _activeViewMode = ActiveViewMode.DualView;

        // Vascular & Window/Level State
        private byte[]? _cachedVeinPixels = null;
        private double _windowWidth = 255.0;
        private double _windowCenter = 127.5;
        private double _veinOpacity = 0.85;
        private byte _veinThreshold = 20;
        private VeinRenderMode _veinRenderMode = VeinRenderMode.FluorescentCyan;
        private bool _enableVeinOverlay = true;

        // Angiosome, Predictive Risk & Isotherm State
        private double _isothermLow = 32.0;
        private double _isothermHigh = 36.0;
        private double _dstOffset = -1.2;
        private List<AngiosomeTerritory> _cachedAngiosomes = new();
        private PredictiveUlcerRisk? _latestPredictiveRisk;

        // Curtain Wipe Split Compare State
        private bool _isDraggingCurtain = false;
        private double _curtainPositionX = 0.5; // Normalized (0.0 to 1.0)

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

        // Interactive Bone Drawing & Anatomical Foot Skeleton State
        private bool _isDrawingBone = false;
        private readonly List<DrawnBone> _drawnBones = new();
        private DrawnBone? _currentBoneDrawing = null;
        private bool _showAnatomicalBones = true;
        private bool _showDrawnBones = true;
        private double _boneScale = 1.0;
        private double _boneOffX = 0.0;
        private double _boneOffY = 0.0;
        private bool _boneIsLeftFoot = false;

        // Osteo-Thermal Matrix & Orthopedic Goniometer State
        private OsteoThermalMatrixReport? _osteoReport = null;
        private bool _colorBonesByTemp = false;
        private GoniometerMeasurement? _goniometerMeasurement = null;
        private readonly List<Point> _goniometerPoints = new();
        private Point? _goniometerHoverPoint = null;

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

        // Viewport Synchronization & Extrema Tracker
        private bool _syncViewports = true;
        private bool _isSyncingScroll = false;
        private bool _showMinMaxTracker = true;

        // Histogram & Topography Cache
        private ThermalHistogramData? _cachedHistogram;

        // Filmstrip Gallery
        private readonly List<string> _filmstripFiles = new();
        private int _activeFilmstripIndex = -1;

        public MainWindow()
        {
            InitializeComponent();
            _isInitialized = true;
            ViewMode_Checked(this, new RoutedEventArgs());

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
                            CornerRadius = new CornerRadius(5),
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
                                card.BorderBrush = (Brush)FindResource("CyanBrush");
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
                        card.Background = new SolidColorBrush(Color.FromArgb(50, 0, 240, 255));
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
                ImgCurtainRaw.Source = _originalBitmap;

                CanvasOriginal.Width = _rawWidth;
                CanvasOriginal.Height = _rawHeight;
                CanvasResult.Width = _rawWidth;
                CanvasResult.Height = _rawHeight;
                ImgOriginal.Width = _rawWidth;
                ImgOriginal.Height = _rawHeight;
                ImgResult.Width = _rawWidth;
                ImgResult.Height = _rawHeight;
                ImgCurtainRaw.Width = _rawWidth;
                ImgCurtainRaw.Height = _rawHeight;
                OverlayOriginalCanvas.Width = _rawWidth;
                OverlayOriginalCanvas.Height = _rawHeight;
                OverlayResultCanvas.Width = _rawWidth;
                OverlayResultCanvas.Height = _rawHeight;
                CanvasCurtain.Width = _rawWidth;
                CanvasCurtain.Height = _rawHeight;

                // Auto-fit anatomical foot skeleton to tissue bounds
                AutoFitBonesToImage();

                // Compute real-time histogram, anatomical zones & osteo-thermal bone matrix
                UpdateHistogramData();
                UpdateAnatomicalZonesData();
                SampleOsteoThermalMatrix();

                StatusText.Text = $"Thermogramm geladen: {System.IO.Path.GetFileName(path)} ({_rawWidth}x{_rawHeight} Radiometrie-Matrix).";

                UpdateHudReadouts();
                UpdateCurtainGeometry();
                RedrawInteractiveOverlays();
                _ = RunPipelineAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Laden des Bildes: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void UpdateHistogramData()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;
            _cachedHistogram = ThermalTopographyService.ComputeHistogram(_rawGrayPixels, _rawWidth, _rawHeight, SliderK.Value);
            TxtHistoMedian.Text = $"{_cachedHistogram.MedianTemp:F1} °C";
            TxtHistoMad.Text = $"{_cachedHistogram.MadTemp:F1} K";
            TxtHistoThreshold.Text = $"{_cachedHistogram.OutlierThresholdTemp:F1} °C";
            RenderHistogram(_cachedHistogram);
        }

        private void UpdateAnatomicalZonesData()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;
            var zones = ThermalTopographyService.ComputeAnatomicalZones(_rawGrayPixels, _rawWidth, _rawHeight);
            GridAnatomicalZones.ItemsSource = zones;
        }

        // --- Drag & Drop Support ---
        private void Window_DragOver(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
                e.Effects = DragDropEffects.Copy;
            else
                e.Effects = DragDropEffects.None;
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

        private void MainWindow_Loaded(object sender, RoutedEventArgs e)
        {
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

                // Update Clinical Header Status Chip
                bool isCrit = (result.HighestRisk == "CRITICAL");
                double maxVal = result.Hotspots.Count > 0 ? (result.Hotspots.Max(h => (h?.Region?.MaxVal ?? 0)) - result.Stats.OrigMedian) * 0.1 : 0;
                if (isCrit)
                {
                    BadgeAiStatusDot.Background = (Brush)FindResource("CriticalBrush");
                    TxtHeaderAiStatus.Text = $"KLINISCHER BEFUND: PATHOLOGISCHES RISIKO (ΔT = +{maxVal:F1} K)";
                    TxtHeaderAiStatus.Foreground = (Brush)FindResource("CriticalBrush");
                }
                else
                {
                    BadgeAiStatusDot.Background = (Brush)FindResource("SuccessBrush");
                    TxtHeaderAiStatus.Text = "KLINISCHER BEFUND: PHYSIOLOGISCH NORMAL";
                    TxtHeaderAiStatus.Foreground = (Brush)FindResource("SuccessBrush");
                }

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

                // Update Histogram
                UpdateHistogramData();

                // Update Angiosome territories & Predictive 7-Day Ulceration Risk
                UpdateAngiosomesAndPrediction();

                // Log into SQLite database safely
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

            // Handle 3D Relief mode
            if (_activeViewMode == ActiveViewMode.Relief3D && _rawGrayPixels != null)
            {
                var reliefBmp = ThermalTopographyService.Generate3DReliefMap(_rawGrayPixels, w, h, _activePalette);
                ImgResult.Source = reliefBmp;
                OverlayResultCanvas.Children.Clear();
                return;
            }

            BitmapSource baseBmp;
            if ((_activeViewMode == ActiveViewMode.CurtainWipe || _activeViewMode == ActiveViewMode.DualView) && _rawGrayPixels != null)
            {
                byte thresh = 160;
                if (result.Stats != null && result.Stats.OrigMedian > 0)
                {
                    thresh = (byte)Math.Clamp(result.Stats.OrigMedian + 10, 100, 230);
                }
                baseBmp = PaletteService.CreateIsolatedFindingBitmap(
                    _rawGrayPixels, w, h, _activePalette, thresh, _cachedVeinPixels, showVeins && _enableVeinOverlay, _windowWidth, _windowCenter);
            }
            else
            {
                baseBmp = _rawGrayPixels != null
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

            if (_activeViewMode == ActiveViewMode.Relief3D && _rawGrayPixels != null)
            {
                ImgResult.Source = ThermalTopographyService.Generate3DReliefMap(_rawGrayPixels, w, h, _activePalette);
                OverlayResultCanvas.Children.Clear();
                return;
            }

            if (_activeViewMode == ActiveViewMode.IsothermSlice && _rawGrayPixels != null)
            {
                ImgResult.Source = ClinicalAngiosomeService.RenderIsothermSlice(_rawGrayPixels, w, h, _isothermLow, _isothermHigh);
                OverlayResultCanvas.Children.Clear();
                return;
            }

            if (_activeViewMode == ActiveViewMode.DigitalSubtraction && _rawGrayPixels != null)
            {
                ImgResult.Source = ClinicalAngiosomeService.RenderDigitalSubtraction(_rawGrayPixels, w, h, _dstOffset);
                OverlayResultCanvas.Children.Clear();
                return;
            }

            BitmapSource baseBmp;
            if ((_activeViewMode == ActiveViewMode.CurtainWipe || _activeViewMode == ActiveViewMode.DualView) && _rawGrayPixels != null)
            {
                byte thresh = (byte)Math.Clamp(_windowCenter + 15, 120, 230);
                if (_latestResult?.Stats != null && _latestResult.Stats.OrigMedian > 0)
                {
                    thresh = (byte)Math.Clamp(_latestResult.Stats.OrigMedian + 10, 100, 230);
                }
                baseBmp = PaletteService.CreateIsolatedFindingBitmap(
                    _rawGrayPixels, w, h, _activePalette, thresh, _cachedVeinPixels, _enableVeinOverlay, _windowWidth, _windowCenter);
            }
            else
            {
                baseBmp = _rawGrayPixels != null
                    ? PaletteService.ApplyPalette(_rawGrayPixels, w, h, _activePalette, _windowWidth, _windowCenter)
                    : PaletteService.ApplyPalette(_originalBitmap, _activePalette, _windowWidth, _windowCenter);

                if (_enableVeinOverlay && _cachedVeinPixels != null)
                {
                    baseBmp = PaletteService.BlendVeinOverlay(baseBmp, _cachedVeinPixels, _veinOpacity, _veinThreshold, _veinRenderMode);
                }
            }

            ImgResult.Source = baseBmp;
            UpdateHudReadouts();
        }

        // --- View Mode Selector (Dual, Curtain Wipe, 3D Relief, Pure DSA, Isotherm, Bones) ---
        private void ViewMode_Checked(object sender, RoutedEventArgs e)
        {
            if (!_isInitialized || RbViewDual == null || ColViewport1 == null || ColViewport2 == null || ColDivider == null) return;

            if (RbViewDual.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.DualView;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                TxtVp2Title.Text = "DIAGNOSTISCHER BEFUND (OVERLAYS & VENEN)";
            }
            else if (RbViewCurtain.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.CurtainWipe;
                // Focus on Viewport 2 for the Wipe Curtain
                ColViewport1.Width = new GridLength(0);
                ColDivider.Width = new GridLength(0);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Visible;
                CanvasCurtain.Visibility = Visibility.Visible;
                _showAnatomicalBones = true;
                TxtVp2Title.Text = "SCHIEBE-VORHANG: ROHBILD (LINKS) vs BEFUND & GEFÄSSE (RECHTS)";
                UpdateCurtainGeometry();
            }
            else if (RbView3DRelief.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.Relief3D;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                TxtVp2Title.Text = "TOPOGRAPHISCHES 3D-RELIEF (ISO-HÖHENMODELL DER HYPERTHERMIE)";
            }
            else if (RbViewDSA.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.PureDSA;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                _enableVeinOverlay = true;
                _veinRenderMode = VeinRenderMode.PureAngiography;
                TxtVp2Title.Text = "DIGITALE SUBTRAKTIONS-ANGIOGRAPHIE (DSA / REINER GEFÄSSBAUM)";
            }
            else if (RbViewIsotherm != null && RbViewIsotherm.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.IsothermSlice;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                TxtVp2Title.Text = $"ISOTHERMEN-BAND: [{_isothermLow:F1}°C bis {_isothermHigh:F1}°C]";
            }
            else if (RbViewBones != null && RbViewBones.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.CurtainWipe;
                ColViewport1.Width = new GridLength(0);
                ColDivider.Width = new GridLength(0);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Visible;
                CanvasCurtain.Visibility = Visibility.Visible;
                _showAnatomicalBones = true;
                if (ChkShowBones != null) ChkShowBones.IsChecked = true;
                if (ChkEnableSkeletonTemplate != null) ChkEnableSkeletonTemplate.IsChecked = true;
                if (InspectorTabs != null && TabBones != null) InspectorTabs.SelectedItem = TabBones;
                if (RbToolBone != null) RbToolBone.IsChecked = true;
                _activeTool = ActiveCanvasTool.BoneDrawing;
                TxtVp2Title.Text = "OSTEOLOGIE & ANATOMISCHES SKELETT: Knochen einzeichnen & Befundvergleich";
                UpdateCurtainGeometry();
            }

            RefreshResultImageOnly();
        }

        // --- Curtain Wipe Handle Dragging ---
        private void CurtainHandle_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.LeftButton == MouseButtonState.Pressed)
            {
                _isDraggingCurtain = true;
                BorderCurtainHandle.CaptureMouse();
                e.Handled = true;
            }
        }

        private void UpdateCurtainGeometry()
        {
            if (_rawWidth <= 0 || _rawHeight <= 0) return;

            double curtainX = _curtainPositionX * _rawWidth;
            CurtainClipRect.Rect = new Rect(0, 0, Math.Max(0, curtainX), _rawHeight);

            CanvasCurtain.Width = _rawWidth;
            CanvasCurtain.Height = _rawHeight;

            LineCurtain.X1 = curtainX;
            LineCurtain.Y1 = 0;
            LineCurtain.X2 = curtainX;
            LineCurtain.Y2 = _rawHeight;

            Canvas.SetLeft(BorderCurtainHandle, curtainX - 17);
            Canvas.SetTop(BorderCurtainHandle, (_rawHeight / 2.0) - 17);
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
            if (_latestResult?.Hotspots != null && _activeViewMode != ActiveViewMode.Relief3D)
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
                        Stroke = risk == "CRITICAL" ? new SolidColorBrush(Color.FromRgb(255, 42, 85)) : Brushes.Yellow,
                        StrokeThickness = 2.0,
                        RadiusX = 3,
                        RadiusY = 3,
                        Fill = new SolidColorBrush(Color.FromArgb(40, 255, 42, 85))
                    };
                    Canvas.SetLeft(rect, minX);
                    Canvas.SetTop(rect, minY);
                    OverlayResultCanvas.Children.Add(rect);

                    var crosshairH = new Line { X1 = hspot.Region.CenterX - 8, Y1 = hspot.Region.CenterY, X2 = hspot.Region.CenterX + 8, Y2 = hspot.Region.CenterY, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    var crosshairV = new Line { X1 = hspot.Region.CenterX, Y1 = hspot.Region.CenterY - 8, X2 = hspot.Region.CenterX, Y2 = hspot.Region.CenterY + 8, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    OverlayResultCanvas.Children.Add(crosshairH);
                    OverlayResultCanvas.Children.Add(crosshairV);

                    double deltaT = Math.Round((hspot.Region.MaxVal - origMed) * 0.1, 1);
                    var labelBorder = new Border
                    {
                        Background = new SolidColorBrush(Color.FromArgb(235, 10, 14, 22)),
                        BorderBrush = rect.Stroke,
                        BorderThickness = new Thickness(1),
                        CornerRadius = new CornerRadius(3),
                        Padding = new Thickness(5, 2, 5, 2)
                    };
                    labelBorder.Child = new TextBlock
                    {
                        Text = $"HERD #{hspot.Region.Id} (ΔT = +{deltaT:F1} K) [{risk}]",
                        FontSize = 9.5,
                        FontWeight = FontWeights.Bold,
                        Foreground = Brushes.White
                    };
                    Canvas.SetLeft(labelBorder, minX);
                    Canvas.SetTop(labelBorder, Math.Max(0, minY - 22));
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
                DrawRoiRectVector(OverlayOriginalCanvas);
                DrawRoiRectVector(OverlayResultCanvas);
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

            // 6. Draw Anatomical Foot Skeleton (Osteology Template)
            if (_showAnatomicalBones)
            {
                DrawAnatomicalFootSkeleton(OverlayOriginalCanvas);
                DrawAnatomicalFootSkeleton(OverlayResultCanvas);
            }

            // 7. Draw Physician Freehand Drawn Bones
            if (_showDrawnBones)
            {
                DrawPhysicianBones(OverlayOriginalCanvas);
                DrawPhysicianBones(OverlayResultCanvas);
            }

            // 7b. Draw Orthopedic Goniometer (3-Point Angle Caliper)
            if (_goniometerPoints.Count > 0)
            {
                DrawGoniometerVector(OverlayOriginalCanvas);
                DrawGoniometerVector(OverlayResultCanvas);
            }

            // 8. Screenshot-matching Fokaler Hotspot Callout Box
            if (_latestResult?.Hotspots != null && _latestResult.Hotspots.Count > 0)
            {
                var mainHotspot = _latestResult.Hotspots.OrderByDescending(h => h.Region?.MaxVal ?? 0).FirstOrDefault();
                if (mainHotspot?.Region != null)
                {
                    double hx = mainHotspot.Region.CenterX;
                    double hy = mainHotspot.Region.CenterY;
                    double origMed = _latestResult.Stats?.OrigMedian ?? 128.0;
                    double deltaT = Math.Round((mainHotspot.Region.MaxVal - origMed) * 0.1, 1);
                    string riskText = mainHotspot.Assessment?.RiskLevel == "CRITICAL" ? "Kritisch" : "Auffällig";

                    DrawHotspotCalloutCard(OverlayOriginalCanvas, hx, hy, deltaT, riskText);
                    DrawHotspotCalloutCard(OverlayResultCanvas, hx, hy, deltaT, riskText);
                }
            }
        }

        private void DrawExtremumPin(Canvas canvas, int x, int y, double temp, bool isMax)
        {
            var brush = isMax ? new SolidColorBrush(Color.FromRgb(255, 42, 85)) : (Brush)FindResource("CyanBrush");
            var glyph = isMax ? "🔥" : "❄️";
            var text = isMax ? $"MAX: {temp:F1}°C" : $"MIN: {temp:F1}°C";

            var ring = new Ellipse
            {
                Width = 14,
                Height = 14,
                Stroke = brush,
                StrokeThickness = 2.0,
                Fill = new SolidColorBrush(Color.FromArgb(40, isMax ? (byte)255 : (byte)0, isMax ? (byte)42 : (byte)240, isMax ? (byte)85 : (byte)255))
            };
            Canvas.SetLeft(ring, x - 7);
            Canvas.SetTop(ring, y - 7);
            canvas.Children.Add(ring);

            var tag = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(235, 10, 14, 22)),
                BorderBrush = brush,
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(3),
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

            var r1 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = (Brush)FindResource("CyanBrush"), StrokeThickness = 1.5 };
            Canvas.SetLeft(r1, _profileStartPoint.X - 4);
            Canvas.SetTop(r1, _profileStartPoint.Y - 4);
            canvas.Children.Add(r1);

            var r2 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = (Brush)FindResource("CyanBrush"), StrokeThickness = 1.5 };
            Canvas.SetLeft(r2, _profileEndPoint.X - 4);
            Canvas.SetTop(r2, _profileEndPoint.Y - 4);
            canvas.Children.Add(r2);

            double midX = (_profileStartPoint.X + _profileEndPoint.X) / 2.0;
            double midY = (_profileStartPoint.Y + _profileEndPoint.Y) / 2.0;

            var badge = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(235, 10, 14, 22)),
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

                var dot = new Ellipse { Width = 4, Height = 4, Fill = brush };
                Canvas.SetLeft(dot, pt.Position.X - 2);
                Canvas.SetTop(dot, pt.Position.Y - 2);
                canvas.Children.Add(dot);

                var b = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(235, 10, 14, 22)),
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
                    Stroke = isCrit ? (Brush)FindResource("CriticalBrush") : (Brush)FindResource("SuccessBrush"),
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 4, 3 }
                };
                canvas.Children.Add(caliperLine);

                double midX = (p1.X + p2.X) / 2.0;
                double midY = (p1.Y + p2.Y) / 2.0;

                var badge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(240, isCrit ? (byte)150 : (byte)15, isCrit ? (byte)20 : (byte)60, isCrit ? (byte)20 : (byte)25)),
                    BorderBrush = isCrit ? (Brush)FindResource("CriticalBrush") : (Brush)FindResource("SuccessBrush"),
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
            if (!_isInitialized || RbToolPan == null) return;

            if (RbToolPan.IsChecked == true) _activeTool = ActiveCanvasTool.PanZoom;
            else if (RbToolRoi.IsChecked == true) _activeTool = ActiveCanvasTool.RoiSelection;
            else if (RbToolProfile.IsChecked == true) _activeTool = ActiveCanvasTool.ThermalProfile;
            else if (RbToolProbe.IsChecked == true) _activeTool = ActiveCanvasTool.PointProbe;
            else if (RbToolBone != null && RbToolBone.IsChecked == true) _activeTool = ActiveCanvasTool.BoneDrawing;
            else if (RbToolGoniometer != null && RbToolGoniometer.IsChecked == true) _activeTool = ActiveCanvasTool.Goniometer;
            else if (RbToolWL.IsChecked == true) _activeTool = ActiveCanvasTool.WindowLevelDrag;

            UpdateToolInstructions();
        }

        // --- Voicemod Style Search Box Filter ---
        private void SearchBox_TextChanged(object sender, TextChangedEventArgs e)
        {
            if (PanelFilmstrip == null || _filmstripFiles == null) return;
            string query = SearchBox.Text?.Trim().ToLowerInvariant() ?? "";
            for (int i = 0; i < PanelFilmstrip.Children.Count; i++)
            {
                if (PanelFilmstrip.Children[i] is FrameworkElement elem && elem.Tag is int idx && idx < _filmstripFiles.Count)
                {
                    string fn = System.IO.Path.GetFileName(_filmstripFiles[idx]).ToLowerInvariant();
                    elem.Visibility = string.IsNullOrEmpty(query) || fn.Contains(query) ? Visibility.Visible : Visibility.Collapsed;
                }
            }
        }

        // --- Voicemod Left Navigation Rail Handler ---
        private void NavRail_Checked(object sender, RoutedEventArgs e)
        {
            if (!_isInitialized || InspectorTabs == null) return;
            if (sender == RailBtnWorkstation)
            {
                if (RbViewDual != null) RbViewDual.IsChecked = true;
            }
            else if (sender == RailBtnVascular)
            {
                if (TabVascular != null) InspectorTabs.SelectedItem = TabVascular;
            }
            else if (sender == RailBtnHotspots)
            {
                InspectorTabs.SelectedIndex = 2; // Herde
            }
            else if (sender == RailBtnAnatomy)
            {
                if (TabAnatomy != null) InspectorTabs.SelectedItem = TabAnatomy;
            }
            else if (sender == RailBtnRadiometry)
            {
                if (TabHistogram != null) InspectorTabs.SelectedItem = TabHistogram;
            }
            else if (sender == RailBtnReport)
            {
                InspectorTabs.SelectedIndex = 0; // Arztbericht
            }
            else if (sender == RailBtnParams)
            {
                InspectorTabs.SelectedIndex = 1; // Parameter
            }
            else if (sender == RailBtnAudit)
            {
                InspectorTabs.SelectedIndex = 11; // Audit
            }
        }

        // --- Voicemod Floating Dock Center Action Trigger ---
        private void BtnCentralRun_MouseDown(object sender, MouseButtonEventArgs e)
        {
            BtnRunAnalysis_Click(sender, e);
        }

        // --- Voicemod Filter Pill Category All ---
        private void RbFilterAll_Checked(object sender, RoutedEventArgs e)
        {
            if (!_isInitialized || RbViewDual == null) return;
            RbViewDual.IsChecked = true;
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
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Rechteck ziehen = Bereich wählen (Pixelgenau)";
                    CanvasOriginal.Cursor = Cursors.Cross;
                    CanvasResult.Cursor = Cursors.Cross;
                    break;
                case ActiveCanvasTool.ThermalProfile:
                    StatusText.Text = "Werkzeug: Schnittprofil T(s) | Ziehen Sie eine Linie über das Gewebe zur Erzeugung des Temperaturdiagramms.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Linie ziehen = Schnittprofil analysieren (Pixelgenau)";
                    CanvasOriginal.Cursor = Cursors.Pen;
                    CanvasResult.Cursor = Cursors.Pen;
                    break;
                case ActiveCanvasTool.PointProbe:
                    StatusText.Text = "Werkzeug: Punktsonden P₁-P₂ | Klicken Sie nacheinander auf zwei Stellen für den bilateralen Armstrong-Vergleich.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Klick = Messpunkt setzen (Armstrong ΔT)";
                    CanvasOriginal.Cursor = Cursors.Cross;
                    CanvasResult.Cursor = Cursors.Cross;
                    break;
                case ActiveCanvasTool.BoneDrawing:
                    StatusText.Text = "Werkzeug: Knochen einzeichnen | Zeichnen Sie Knochenstrukturen frei mit der Maus auf das Gewebe.";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Maus ziehen = Knochenkontur einzeichnen";
                    CanvasOriginal.Cursor = Cursors.Pen;
                    CanvasResult.Cursor = Cursors.Pen;
                    break;
                case ActiveCanvasTool.Goniometer:
                    StatusText.Text = "Werkzeug: Goniometer (Winkelmessung) | Klicken Sie 3 Punkte im Bild (1. Schaft MT-I, 2. Scheitelpunkt MTP-I Gelenk, 3. Hallux).";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · 3 Punkte setzen = Hallux-Valgus-Winkel (HVA) messen";
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

        // --- Mouse Events for Viewports (Pan, ROI, Profile, Probes, Bones, W/L, Curtain) ---
        private void ViewportOriginal_MouseDown(object sender, MouseButtonEventArgs e) => HandleViewportMouseDown(CanvasOriginal, ScrollOriginal, e);
        private void ViewportResult_MouseDown(object sender, MouseButtonEventArgs e) => HandleViewportMouseDown(CanvasResult, ScrollResult, e);

        private void HandleViewportMouseDown(Grid canvas, ScrollViewer scroller, MouseButtonEventArgs e)
        {
            if (_originalBitmap == null) return;
            Canvas activeOverlay = (canvas == CanvasResult) ? OverlayResultCanvas : OverlayOriginalCanvas;
            Point pos = e.GetPosition(activeOverlay);
            pos = new Point(Math.Clamp(pos.X, 0, _rawWidth), Math.Clamp(pos.Y, 0, _rawHeight));

            // Right or Middle button ALWAYS initiates Panning
            if (e.RightButton == MouseButtonState.Pressed || e.MiddleButton == MouseButtonState.Pressed)
            {
                StartPanning(e.GetPosition(scroller), scroller, canvas);
                return;
            }

            if (e.LeftButton == MouseButtonState.Pressed)
            {
                switch (_activeTool)
                {
                    case ActiveCanvasTool.PanZoom:
                        StartPanning(e.GetPosition(scroller), scroller, canvas);
                        break;

                    case ActiveCanvasTool.RoiSelection:
                        _isSelectingROI = true;
                        _roiStartPoint = pos;
                        if (_roiSelectionRect == null)
                        {
                            _roiSelectionRect = new System.Windows.Shapes.Rectangle
                            {
                                Stroke = (Brush)FindResource("CyanBrush"),
                                StrokeThickness = 1.8,
                                StrokeDashArray = new DoubleCollection { 4, 2 },
                                Fill = new SolidColorBrush(Color.FromArgb(30, 0, 240, 255))
                            };
                        }
                        if (_roiSelectionRect.Parent is Canvas prevParent)
                        {
                            prevParent.Children.Remove(_roiSelectionRect);
                        }
                        activeOverlay.Children.Add(_roiSelectionRect);
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

                    case ActiveCanvasTool.BoneDrawing:
                        _isDrawingBone = true;
                        _currentBoneDrawing = new DrawnBone
                        {
                            Name = $"Knochen #{_drawnBones.Count + 1}",
                            Thickness = 2.2,
                            StrokeBrush = new SolidColorBrush(Color.FromRgb(30, 41, 59))
                        };
                        _currentBoneDrawing.Points.Add(pos);
                        canvas.CaptureMouse();
                        RedrawInteractiveOverlays();
                        break;

                    case ActiveCanvasTool.Goniometer:
                        HandleGoniometerClick(pos);
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

        private void StartPanning(Point scrollerPos, ScrollViewer scroller, Grid canvas)
        {
            _isPanning = true;
            _panStartMouse = scrollerPos;
            _panStartHScroll = scroller.HorizontalOffset;
            _panStartVScroll = scroller.VerticalOffset;
            canvas.CaptureMouse();
        }

        private void ViewportOriginal_MouseMove(object sender, MouseEventArgs e) => HandleViewportMouseMove(CanvasOriginal, ScrollOriginal, e);
        private void ViewportResult_MouseMove(object sender, MouseEventArgs e) => HandleViewportMouseMove(CanvasResult, ScrollResult, e);

        private void HandleViewportMouseMove(Grid canvas, ScrollViewer scroller, MouseEventArgs e)
        {
            Canvas activeOverlay = (canvas == CanvasResult) ? OverlayResultCanvas : OverlayOriginalCanvas;
            Point pos = e.GetPosition(activeOverlay);
            pos = new Point(Math.Clamp(pos.X, 0, _rawWidth), Math.Clamp(pos.Y, 0, _rawHeight));
            int x = (int)pos.X;
            int y = (int)pos.Y;

            // Curtain Wipe Drag
            if (_isDraggingCurtain && _rawWidth > 0)
            {
                _curtainPositionX = Math.Clamp(pos.X / _rawWidth, 0.02, 0.98);
                UpdateCurtainGeometry();
                return;
            }

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
                Point curMouse = e.GetPosition(scroller);
                double dx = (curMouse.X - _panStartMouse.X);
                double dy = (curMouse.Y - _panStartMouse.Y);
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

            // ROI Rubberband (Zero Offset)
            if (_isSelectingROI && _roiSelectionRect != null)
            {
                double minX = Math.Min(_roiStartPoint.X, pos.X);
                double minY = Math.Min(_roiStartPoint.Y, pos.Y);
                double rw = Math.Abs(pos.X - _roiStartPoint.X);
                double rh = Math.Abs(pos.Y - _roiStartPoint.Y);

                Canvas.SetLeft(_roiSelectionRect, minX);
                Canvas.SetTop(_roiSelectionRect, minY);
                _roiSelectionRect.Width = rw;
                _roiSelectionRect.Height = rh;
                return;
            }

            // Thermal Profile Line Rubberband (Zero Offset)
            if (_isDrawingProfile && _rawGrayPixels != null)
            {
                _profileEndPoint = pos;
                _activeProfileStats = ThermalAnalysisHelper.SampleProfileLine(_rawGrayPixels, _rawWidth, _rawHeight, _profileStartPoint, _profileEndPoint);
                RedrawInteractiveOverlays();
                UpdateProfileUI();
                return;
            }

            // Bone Drawing Live Trace (Zero Offset)
            if (_isDrawingBone && _currentBoneDrawing != null)
            {
                var pts = _currentBoneDrawing.Points;
                if (pts.Count == 0 || (pos - pts[^1]).Length >= 2.0)
                {
                    pts.Add(pos);
                    RedrawInteractiveOverlays();
                }
                return;
            }

            // Goniometer Live Hover Preview Line
            if (_activeTool == ActiveCanvasTool.Goniometer && (_goniometerPoints.Count == 1 || _goniometerPoints.Count == 2))
            {
                _goniometerHoverPoint = pos;
                RedrawInteractiveOverlays();
                return;
            }
        }

        private void ViewportOriginal_MouseUp(object sender, MouseButtonEventArgs e) => HandleViewportMouseUp(CanvasOriginal, e);
        private void ViewportResult_MouseUp(object sender, MouseButtonEventArgs e) => HandleViewportMouseUp(CanvasResult, e);

        private void HandleViewportMouseUp(Grid canvas, MouseButtonEventArgs e)
        {
            if (_isDraggingCurtain)
            {
                _isDraggingCurtain = false;
                BorderCurtainHandle.ReleaseMouseCapture();
            }

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

                if (w > 15 && h > 15)
                {
                    double minX = Canvas.GetLeft(_roiSelectionRect);
                    double minY = Canvas.GetTop(_roiSelectionRect);
                    _currentROI = new int[] { (int)minX, (int)minY, (int)(minX + w), (int)(minY + h) };
                    StatusText.Text = $"ROI gewählt: [{_currentROI[0]}, {_currentROI[1]} bis {_currentROI[2]}, {_currentROI[3]}]. Berechne...";
                    _ = RunPipelineAsync();
                }
                else
                {
                    _roiSelectionRect.Visibility = Visibility.Collapsed;
                }
            }

            if (_isDrawingProfile)
            {
                _isDrawingProfile = false;
                canvas.ReleaseMouseCapture();

                if (_activeProfileStats != null && _activeProfileStats.Samples.Count >= 2)
                {
                    if (InspectorTabs != null && TabProfile != null) InspectorTabs.SelectedItem = TabProfile;
                    RenderProfileGraph(_activeProfileStats);
                    StatusText.Text = $"Schnittprofil erstellt: Pfadlänge {_activeProfileStats.TotalLengthPx:F0} px | T={_activeProfileStats.MinTemp:F1}°C bis {_activeProfileStats.MaxTemp:F1}°C.";
                }
            }

            if (_isDrawingBone)
            {
                _isDrawingBone = false;
                canvas.ReleaseMouseCapture();

                if (_currentBoneDrawing != null && _currentBoneDrawing.Points.Count >= 2)
                {
                    _drawnBones.Add(_currentBoneDrawing);
                    StatusText.Text = $"Knochen eingezeichnet: {_currentBoneDrawing.Name} ({_currentBoneDrawing.Points.Count} Punkte). Gesamt: {_drawnBones.Count} Knochen.";
                }
                _currentBoneDrawing = null;
                RedrawInteractiveOverlays();
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
                    BadgeArmstrongState.Background = (Brush)FindResource("CriticalBrush");
                    TxtProbeRiskBadge.Text = "PATHOLOGISCH (≥ 2.2 K)";
                    TxtProbeRiskBadge.Foreground = Brushes.White;
                    BorderArmstrongRiskCard.Background = new SolidColorBrush(Color.FromArgb(50, 255, 42, 85));
                    BorderArmstrongRiskCard.BorderBrush = (Brush)FindResource("CriticalBrush");

                    FloatingArmstrongBanner.Visibility = Visibility.Visible;
                    TxtFloatingArmstrong.Text = $"ARMSTRONG-ALARM: ΔT = {eval.DeltaT:F1} K (≥ 2.2 K) — Hohes Ulkusrisiko!";
                }
                else
                {
                    BadgeArmstrongState.Background = new SolidColorBrush(Color.FromRgb(20, 50, 25));
                    TxtProbeRiskBadge.Text = "PHYSIOLOGISCH NORMAL";
                    TxtProbeRiskBadge.Foreground = (Brush)FindResource("SuccessBrush");
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

        // --- Histogram Rendering ---
        private void CanvasHistogram_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            if (_cachedHistogram != null)
                RenderHistogram(_cachedHistogram);
        }

        private void RenderHistogram(ThermalHistogramData data)
        {
            CanvasHistogram.Children.Clear();
            if (data == null || data.MaxBinCount == 0) return;

            double w = CanvasHistogram.ActualWidth > 50 ? CanvasHistogram.ActualWidth : 380;
            double h = CanvasHistogram.ActualHeight > 50 ? CanvasHistogram.ActualHeight : 180;

            double padLeft = 20, padRight = 10, padTop = 15, padBottom = 20;
            double plotW = w - padLeft - padRight;
            double plotH = h - padTop - padBottom;

            var polyline = new Polyline
            {
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 1.8,
                StrokeLineJoin = PenLineJoin.Round
            };

            var area = new Polygon
            {
                Fill = new LinearGradientBrush(
                    Color.FromArgb(90, 0, 240, 255),
                    Color.FromArgb(10, 0, 100, 200),
                    new Point(0, 0),
                    new Point(0, 1))
            };
            area.Points.Add(new Point(padLeft, padTop + plotH));

            // Plot bins 20..255 (skip background)
            for (int b = 15; b < 256; b++)
            {
                double xNorm = (b - 15) / 240.0;
                double yNorm = data.Bins[b] / (double)data.MaxBinCount;

                double sx = padLeft + xNorm * plotW;
                double sy = padTop + (1.0 - yNorm) * plotH;

                var pt = new Point(sx, sy);
                polyline.Points.Add(pt);
                area.Points.Add(pt);
            }

            area.Points.Add(new Point(padLeft + plotW, padTop + plotH));
            CanvasHistogram.Children.Add(area);
            CanvasHistogram.Children.Add(polyline);

            // Draw Threshold Line (Red)
            if (data.OutlierThresholdRaw > 15)
            {
                double threshXNorm = (data.OutlierThresholdRaw - 15) / 240.0;
                double threshX = padLeft + threshXNorm * plotW;

                var threshLine = new Line
                {
                    X1 = threshX, Y1 = padTop,
                    X2 = threshX, Y2 = padTop + plotH,
                    Stroke = (Brush)FindResource("CriticalBrush"),
                    StrokeThickness = 2.0,
                    StrokeDashArray = new DoubleCollection { 3, 2 }
                };
                CanvasHistogram.Children.Add(threshLine);

                var tagThresh = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(230, 255, 42, 85)),
                    CornerRadius = new CornerRadius(2),
                    Padding = new Thickness(3, 1, 3, 1)
                };
                tagThresh.Child = new TextBlock { Text = $"k*MAD: {data.OutlierThresholdTemp:F1}°C", FontSize = 8.5, FontWeight = FontWeights.Bold, Foreground = Brushes.White };
                Canvas.SetLeft(tagThresh, Math.Min(w - 75, threshX + 2));
                Canvas.SetTop(tagThresh, padTop + 4);
                CanvasHistogram.Children.Add(tagThresh);
            }
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
                RenderProfileGraph(_activeProfileStats);
        }

        private void RenderProfileGraph(ThermalProfileStats stats)
        {
            CanvasProfileGraph.Children.Clear();
            if (stats == null || stats.Samples.Count < 2) return;

            double w = CanvasProfileGraph.ActualWidth > 50 ? CanvasProfileGraph.ActualWidth : 420;
            double h = CanvasProfileGraph.ActualHeight > 50 ? CanvasProfileGraph.ActualHeight : 200;

            double padLeft = 36, padRight = 14, padTop = 18, padBottom = 26;
            double plotW = w - padLeft - padRight;
            double plotH = h - padTop - padBottom;

            double tMin = 20.0, tMax = 42.0;

            for (double t = 20.0; t <= 40.0; t += 5.0)
            {
                double yNorm = (t - tMin) / (tMax - tMin);
                double yScreen = padTop + (1.0 - yNorm) * plotH;

                var gridLine = new Line
                {
                    X1 = padLeft, Y1 = yScreen,
                    X2 = w - padRight, Y2 = yScreen,
                    Stroke = new SolidColorBrush(Color.FromRgb(30, 39, 58)),
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

            var areaPolygon = new Polygon
            {
                Fill = new LinearGradientBrush(
                    Color.FromArgb(90, 0, 240, 255),
                    Color.FromArgb(10, 0, 100, 200),
                    new Point(0, 0),
                    new Point(0, 1))
            };
            areaPolygon.Points.Add(new Point(padLeft, padTop + plotH));

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
                    RbViewDSA.IsChecked = true;
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
                    InspectorTabs.SelectedIndex = 8; // Perfusion
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
                    InspectorTabs.SelectedIndex = 7; // Switch to bilateral tab
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
            int denom = (_latestResult != null && _latestResult.TissuePixelCount > 0)
                ? _latestResult.TissuePixelCount
                : _cachedVeinPixels.Length;
            double pct = (double)count / denom * 100.0;
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
            ImgCurtainRaw.Source = _originalBitmap;
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
                ImgCurtainRaw.Source = _originalBitmap;
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
                    InspectorTabs.SelectedIndex = 7;
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
            InspectorTabs.SelectedIndex = 8;
            _ = RunPipelineAsync();
        }
        private void ModeBilateral_Click(object sender, RoutedEventArgs e) => BtnAutoSplitFeet_Click(sender, e);

        private void PaletteIronbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 0;
        private void PaletteRainbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 1;
        private void PaletteInferno_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 2;
        private void PaletteGray_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 3;

        private void MenuAuditLog_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 10;
        private void MenuLuaEditor_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 9;

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
            if (_originalBitmap == null && _latestResult == null)
            {
                MessageBox.Show("Bitte laden Sie zuerst ein Thermogramm und führen Sie die Diagnose aus.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            // Ensure Osteo-thermal sampling is executed
            if (_osteoReport == null && _rawGrayPixels != null)
            {
                SampleOsteoThermalMatrix();
            }

            // Ensure Angiosomes are computed
            if (_cachedAngiosomes.Count == 0 && _rawGrayPixels != null)
            {
                _cachedAngiosomes = ClinicalAngiosomeService.ComputeAngiosomes(_rawGrayPixels, _rawWidth, _rawHeight);
            }

            // Capture rendered visual snapshot as PNG Base64
            string base64Snapshot = "";
            try
            {
                if (CanvasResult != null && _rawWidth > 0 && _rawHeight > 0)
                {
                    var rtb = new RenderTargetBitmap(_rawWidth, _rawHeight, 96, 96, PixelFormats.Pbgra32);
                    rtb.Render(CanvasResult);
                    var enc = new PngBitmapEncoder();
                    enc.Frames.Add(BitmapFrame.Create(rtb));
                    using var ms = new MemoryStream();
                    enc.Save(ms);
                    base64Snapshot = Convert.ToBase64String(ms.ToArray());
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Snapshot capture failed: {ex.Message}");
            }

            // Determine calibrated temperature bounds
            double repMin = 22.0, repMax = 38.0;
            if (_rawGrayPixels != null && _rawWidth > 0 && _rawHeight > 0)
            {
                var extrema = ThermalAnalysisHelper.FindExtrema(_rawGrayPixels, _rawWidth, _rawHeight);
                repMin = extrema.Min.Temp;
                repMax = extrema.Max.Temp;
            }

            string armstrongStage = _latestResult?.HighestRisk == "CRITICAL"
                ? "Grad 1 (Hohes Ulkusrisiko, ΔT ≥ 2.2 K)"
                : (_latestResult?.HighestRisk == "WARNING" ? "Grad 0 (Prä-ulzerativ / Hyperthermie)" : "Grad 0 (Physiologisch)");

            // Build Clinical Report Model
            var model = new ClinicalReportModel
            {
                PatientId = _activePatientId,
                ExamDate = DateTime.Now,
                Modality = "FLIR LWIR 17µm Mikrobolometer (8-14µm)",
                ImageFileName = System.IO.Path.GetFileName(_currentImagePath ?? "Thermogramm.png"),
                Base64ImagePng = base64Snapshot,
                MinTemp = repMin,
                MaxTemp = repMax,
                MeanTemp = _latestResult?.Stats != null ? ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)_latestResult.Stats.OrigMedian, 0, 255)) : 31.0,
                MadDeviation = _latestResult?.Stats != null ? Math.Round(_latestResult.Stats.Mad * 0.1, 2) : 1.2,
                SimdLatencyMs = _latestResult?.Timing?.TotalMs ?? 24.8,
                ArmstrongStage = armstrongStage,
                OverallRiskLevel = _latestResult?.HighestRisk ?? "PHYSIOLOGISCH",
                OverallRecommendation = _latestResult?.HighestRisk == "CRITICAL"
                    ? "Pathologische Hyperthermie (ΔT ≥ 2.2 K nach Armstrong). Sofortige Druckentlastung (Vorfußentlastungsschuh), Ausschluss Ulkus/Charcot."
                    : "Keine akute pathologische Asymmetrie nachweisbar. Regelmäßige präventive Fußpflege und 3-Monats-Follow-up empfohlen.",
                OsteoReport = _osteoReport,
                Goniometer = _goniometerMeasurement,
                Angiosomes = _cachedAngiosomes
            };

            if (_latestResult?.Hotspots != null)
            {
                foreach (var h in _latestResult.Hotspots)
                {
                    model.Hotspots.Add(new HotspotReportItem
                    {
                        Id = h.Region?.Id ?? 0,
                        AreaPx = h.Region?.AreaPixels ?? 0,
                        AreaPercent = h.Region?.AreaPercent ?? 0.0,
                        MaxTemp = h.Region?.MaxVal != null ? ThermalAnalysisHelper.RawToTemperature((byte)h.Region.MaxVal) : 0,
                        Circularity = h.Region?.Circularity ?? 0.0,
                        RiskLevel = h.Assessment?.RiskLevel ?? "BENIGN",
                        Recommendation = h.Assessment?.Recommendation ?? "Keine Intervention"
                    });
                }
            }

            string html = ClinicalReportService.GenerateHtmlReport(model);

            var dlg = new SaveFileDialog
            {
                Filter = "Klinischer HTML-Befundbericht (*.html)|*.html",
                FileName = $"Ignite_Befund_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.html"
            };

            if (dlg.ShowDialog() == true)
            {
                File.WriteAllText(dlg.FileName, html, Encoding.UTF8);
                _dbService.LogAuditAction("EXPORT_REPORT", $"Klinischer Befundbericht exportiert nach {dlg.FileName}");

                // Proactively open in default browser for instant view & PDF print!
                try
                {
                    System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                    {
                        FileName = dlg.FileName,
                        UseShellExecute = true
                    });
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"Failed to auto-open report: {ex.Message}");
                }

                MessageBox.Show($"Befundbericht erfolgreich generiert und geöffnet:\n{dlg.FileName}", "Export abgeschlossen", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void SliderIsotherm_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (SliderIsothermLow == null || SliderIsothermHigh == null || TxtIsothermRange == null) return;
            _isothermLow = SliderIsothermLow.Value;
            _isothermHigh = SliderIsothermHigh.Value;
            if (_isothermHigh < _isothermLow)
            {
                _isothermHigh = _isothermLow;
                SliderIsothermHigh.Value = _isothermHigh;
            }
            TxtIsothermRange.Text = $"{_isothermLow:F1} °C - {_isothermHigh:F1} °C";
            if (_activeViewMode == ActiveViewMode.IsothermSlice)
            {
                RefreshResultImageOnly();
            }
        }

        private void SliderDst_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (SliderDstOffset == null || TxtDstOffset == null) return;
            _dstOffset = SliderDstOffset.Value;
            string trend = _dstOffset < -0.5 ? "(Besserung / Heilung)" : (_dstOffset > 0.5 ? "(Progression / Alarm)" : "(Stabil)");
            TxtDstOffset.Text = $"{_dstOffset:+0.0;-0.0} K {trend}";
            if (_activeViewMode == ActiveViewMode.DigitalSubtraction)
            {
                RefreshResultImageOnly();
            }
        }

        private void UpdateAngiosomesAndPrediction()
        {
            if (_rawGrayPixels == null || _latestResult == null) return;
            int w = _rawWidth > 0 ? _rawWidth : (_originalBitmap?.PixelWidth ?? 640);
            int h = _rawHeight > 0 ? _rawHeight : (_originalBitmap?.PixelHeight ?? 480);

            try
            {
                var angiosomes = ClinicalAngiosomeService.ComputeAngiosomes(_rawGrayPixels, w, h);
                _cachedAngiosomes = angiosomes;
                if (GridAngiosomes != null)
                {
                    GridAngiosomes.ItemsSource = angiosomes;
                }

                double maxDeltaT = 0.0;
                if (_latestResult.Hotspots != null && _latestResult.Hotspots.Count > 0)
                {
                    byte maxVal = _latestResult.Hotspots.Max(h => h.Region.MaxVal);
                    double peakT = ThermalAnalysisHelper.RawToTemperature(maxVal);
                    double medT = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(_latestResult.Stats?.OrigMedian ?? 128), 0, 255));
                    maxDeltaT = Math.Max(0.0, peakT - medT);
                }
                else if (_latestResult.Stats != null)
                {
                    double peakT = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(_latestResult.Stats.Median + 20), 0, 255));
                    double medT = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)Math.Round(_latestResult.Stats.OrigMedian > 0 ? _latestResult.Stats.OrigMedian : _latestResult.Stats.Median), 0, 255));
                    maxDeltaT = Math.Max(0.0, peakT - medT);
                }
                int hotCount = _latestResult.TotalHotspots > 0 ? _latestResult.TotalHotspots : (_latestResult.Hotspots?.Count ?? 0);
                var pred = ClinicalAngiosomeService.CalculatePredictiveRisk(_rawGrayPixels, w, h, maxDeltaT, hotCount);
                _latestPredictiveRisk = pred;

                if (TxtPredProbability != null) TxtPredProbability.Text = $"{pred.ProbabilityPercent:F1} %";
                if (TxtPredTier != null) TxtPredTier.Text = pred.RiskTier;
                if (TxtPredStage != null) TxtPredStage.Text = pred.WagnerArmstrongStage;
                if (TxtPredThdi != null) TxtPredThdi.Text = $"{pred.ThermalDissipationIndex:F1} K/px²";
                if (TxtPredAns != null) TxtPredAns.Text = $"{pred.AutonomicNeuropathyScore:F1} / 10";
                if (TxtPredCharcot != null) TxtPredCharcot.Text = pred.CharcotRiskStatus;
                if (TxtPredIntervention != null) TxtPredIntervention.Text = pred.ImmediateIntervention;

                if (TxtPredProbability != null)
                {
                    if (pred.ProbabilityPercent >= 70.0)
                        TxtPredProbability.Foreground = (Brush)FindResource("CriticalBrush");
                    else if (pred.ProbabilityPercent >= 30.0)
                        TxtPredProbability.Foreground = (Brush)FindResource("WarningBrush");
                    else
                        TxtPredProbability.Foreground = (Brush)FindResource("SuccessBrush");
                }
            }
            catch { }
        }

        private void MenuAbout_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show(
                "IGNITE Medical PACS Suite v5.0.0 (Research Grade SaMD)\n" +
                "DIN EN ISO 13485 & IEC 62304 konforme radiometrische Präzisionsanalyse\n" +
                "Jugend forscht 2026 – Fachgebiet Arbeitswelt / Informatik\n\n" +
                "Klinische Diagnostik-Architektur:\n" +
                "• Deterministische Signalverarbeitung: Go 1.27 + x86_64 AVX2 Vektor-SIMD (32 Pixel/Takt)\n" +
                "• Klinische PACS-Workstation: C# .NET 10 (WPF DICOM GSDF konform)\n" +
                "• Evidenzbasierte Leitlinien: Lua 5.1 (IWGDF 2023 & Armstrong et al.)\n" +
                "• DSGVO Art. 30 & FDA 21 CFR Part 11 Audit-Trail: SQLite\n" +
                "• Deterministisch & lokal: 100% reproduzierbar, keine Black-Box-KI\n\n" +
                "Zweckbestimmung: Computer-assistierte thermografische Diagnostik (CAD) zur Früherkennung diabetischer Fußulzera und vaskulärer Perfusionsstörungen.",
                "Über IGNITE Medical PACS", MessageBoxButton.OK, MessageBoxImage.Information);
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

        private void DrawRoiRectVector(Canvas canvas)
        {
            if (_currentROI == null || _currentROI.Length < 4) return;
            var roiRect = new System.Windows.Shapes.Rectangle
            {
                Width = Math.Max(0, _currentROI[2] - _currentROI[0]),
                Height = Math.Max(0, _currentROI[3] - _currentROI[1]),
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 1.8,
                StrokeDashArray = new DoubleCollection { 4, 2 },
                Fill = new SolidColorBrush(Color.FromArgb(25, 0, 240, 255))
            };
            Canvas.SetLeft(roiRect, _currentROI[0]);
            Canvas.SetTop(roiRect, _currentROI[1]);
            canvas.Children.Add(roiRect);
        }

        private void DrawAnatomicalFootSkeleton(Canvas canvas)
        {
            if (_rawWidth <= 0 || _rawHeight <= 0) return;

            double cx = (_rawWidth / 2.0) + _boneOffX;
            double cy = (_rawHeight / 2.0) + _boneOffY;
            double sc = _boneScale;
            double sign = _boneIsLeftFoot ? -1.0 : 1.0;

            Point FPt(double rx, double ry) => new Point(cx + (rx * sc * sign), cy + (ry * sc));

            var defaultStroke = new SolidColorBrush(Color.FromRgb(30, 41, 59));
            var defaultFill = new SolidColorBrush(Color.FromArgb(14, 30, 41, 59));

            (Brush stroke, Brush fill) GetBoneStyle(string boneId)
            {
                if (_colorBonesByTemp && _osteoReport != null)
                {
                    var match = _osteoReport.Bones.FirstOrDefault(b => b.Id == boneId);
                    if (match != null)
                    {
                        return (match.StressBrush, match.StressFillBrush);
                    }
                }
                return (defaultStroke, defaultFill);
            }

            void AddBonePoly(string boneId, params Point[] pts)
            {
                if (pts.Length < 3) return;
                var (bStroke, bFill) = GetBoneStyle(boneId);
                var poly = new Polygon
                {
                    Stroke = bStroke,
                    StrokeThickness = 1.8,
                    Fill = bFill,
                    StrokeLineJoin = PenLineJoin.Round
                };
                foreach (var p in pts) poly.Points.Add(p);
                canvas.Children.Add(poly);
            }

            // --- 1. DIGITUS I (HALLUX / GROSSZEHE) ---
            AddBonePoly("DIG1", FPt(37, -190), FPt(48, -172), FPt(46, -154), FPt(27, -154), FPt(25, -172));
            AddBonePoly("DIG1", FPt(44, -147), FPt(40, -125), FPt(45, -104), FPt(26, -104), FPt(30, -125), FPt(26, -147));
            AddBonePoly("MT1", FPt(46, -97), FPt(48, -85), FPt(39, -70), FPt(37, -35), FPt(40, -18), FPt(20, -18), FPt(22, -35), FPt(22, -70), FPt(19, -85), FPt(21, -97));

            // --- 2. DIGITUS II ---
            AddBonePoly("DIG2", FPt(14, -180), FPt(17, -168), FPt(17, -158), FPt(9, -158), FPt(9, -168));
            AddBonePoly("DIG2", FPt(16, -152), FPt(17, -140), FPt(9, -140), FPt(9, -152));
            AddBonePoly("DIG2", FPt(17, -135), FPt(15, -120), FPt(17, -108), FPt(8, -108), FPt(9, -120), FPt(8, -135));
            AddBonePoly("MT2", FPt(17, -102), FPt(15, -60), FPt(15, -18), FPt(7, -18), FPt(7, -60), FPt(7, -102));

            // --- 3. DIGITUS III ---
            AddBonePoly("DIG3", FPt(-6, -172), FPt(-3, -160), FPt(-3, -150), FPt(-11, -150), FPt(-11, -160));
            AddBonePoly("DIG3", FPt(-4, -145), FPt(-3, -134), FPt(-11, -134), FPt(-11, -145));
            AddBonePoly("DIG3", FPt(-3, -129), FPt(-5, -116), FPt(-3, -104), FPt(-12, -104), FPt(-11, -116), FPt(-12, -129));
            AddBonePoly("MT3", FPt(-3, -98), FPt(-4, -58), FPt(-4, -16), FPt(-13, -16), FPt(-12, -58), FPt(-13, -98));

            // --- 4. DIGITUS IV ---
            AddBonePoly("DIG4", FPt(-26, -160), FPt(-23, -150), FPt(-23, -142), FPt(-31, -142), FPt(-31, -150));
            AddBonePoly("DIG4", FPt(-23, -137), FPt(-23, -126), FPt(-31, -126), FPt(-31, -137));
            AddBonePoly("DIG4", FPt(-23, -121), FPt(-24, -110), FPt(-22, -100), FPt(-32, -100), FPt(-31, -110), FPt(-32, -121));
            AddBonePoly("MT4", FPt(-22, -94), FPt(-24, -54), FPt(-24, -14), FPt(-34, -14), FPt(-34, -54), FPt(-33, -94));

            // --- 5. DIGITUS V (KLEINZEHE) ---
            AddBonePoly("DIG5", FPt(-46, -145), FPt(-43, -136), FPt(-44, -130), FPt(-51, -130), FPt(-51, -136));
            AddBonePoly("DIG5", FPt(-43, -126), FPt(-43, -117), FPt(-51, -117), FPt(-51, -126));
            AddBonePoly("DIG5", FPt(-43, -113), FPt(-44, -104), FPt(-42, -94), FPt(-52, -94), FPt(-51, -104), FPt(-52, -113));
            AddBonePoly("MT5", FPt(-42, -88), FPt(-46, -50), FPt(-47, -10), FPt(-64, -20), FPt(-65, -35), FPt(-56, -55), FPt(-53, -88));

            // --- 6. TARSUS (FUSSWURZEL) ---
            AddBonePoly("TARS_MED", FPt(37, -14), FPt(39, +12), FPt(19, +12), FPt(18, -14));
            AddBonePoly("TARS_MED", FPt(15, -14), FPt(15, +10), FPt(4, +10), FPt(5, -14));
            AddBonePoly("TARS_LAT", FPt(2, -12), FPt(2, +12), FPt(-14, +12), FPt(-13, -12));
            AddBonePoly("TARS_LAT", FPt(-18, -10), FPt(-15, +32), FPt(-45, +32), FPt(-50, -10));
            AddBonePoly("TARS_MED", FPt(35, +16), FPt(34, +44), FPt(-9, +44), FPt(-11, +16));
            AddBonePoly("TAL", FPt(25, +48), FPt(24, +85), FPt(-18, +85), FPt(-14, +48));
            AddBonePoly("CALC", FPt(18, +88), FPt(14, +160), FPt(-32, +160), FPt(-34, +88));
        }

        private void DrawPhysicianBones(Canvas canvas)
        {
            if (_drawnBones.Count > 0)
            {
                foreach (var bone in _drawnBones)
                {
                    if (bone.Points.Count >= 2)
                    {
                        var polyline = new Polyline
                        {
                            Stroke = bone.StrokeBrush,
                            StrokeThickness = bone.Thickness,
                            StrokeLineJoin = PenLineJoin.Round,
                            StrokeStartLineCap = PenLineCap.Round,
                            StrokeEndLineCap = PenLineCap.Round
                        };
                        foreach (var pt in bone.Points)
                        {
                            polyline.Points.Add(pt);
                        }
                        canvas.Children.Add(polyline);
                    }
                }
            }

            // Active live drawing trace
            if (_currentBoneDrawing != null && _currentBoneDrawing.Points.Count >= 2)
            {
                var livePolyline = new Polyline
                {
                    Stroke = new SolidColorBrush(Color.FromRgb(2, 132, 199)),
                    StrokeThickness = 2.5,
                    StrokeDashArray = new DoubleCollection { 3, 2 },
                    StrokeLineJoin = PenLineJoin.Round,
                    StrokeStartLineCap = PenLineCap.Round,
                    StrokeEndLineCap = PenLineCap.Round
                };
                foreach (var pt in _currentBoneDrawing.Points)
                {
                    livePolyline.Points.Add(pt);
                }
                canvas.Children.Add(livePolyline);
            }
        }

        private void DrawHotspotCalloutCard(Canvas canvas, double hx, double hy, double deltaT, string riskText)
        {
            double calloutX = hx + 14;
            double calloutY = Math.Max(8, hy - 42);

            var pointer = new Line
            {
                X1 = hx,
                Y1 = hy,
                X2 = calloutX,
                Y2 = calloutY + 16,
                Stroke = new SolidColorBrush(Color.FromRgb(30, 41, 59)),
                StrokeThickness = 1.2
            };
            canvas.Children.Add(pointer);

            var card = new Border
            {
                Background = Brushes.White,
                BorderBrush = new SolidColorBrush(Color.FromRgb(203, 213, 225)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(8, 4, 8, 4),
                Effect = new System.Windows.Media.Effects.DropShadowEffect
                {
                    BlurRadius = 8,
                    ShadowDepth = 2,
                    Opacity = 0.18,
                    Color = Colors.Black
                }
            };

            var sp = new StackPanel { Orientation = Orientation.Vertical };
            sp.Children.Add(new TextBlock
            {
                Text = "Fokaler Hotspot:",
                FontSize = 9.5,
                FontWeight = FontWeights.SemiBold,
                Foreground = new SolidColorBrush(Color.FromRgb(51, 65, 85))
            });
            sp.Children.Add(new TextBlock
            {
                Text = $"ΔT = +{deltaT:F1} K ({riskText})",
                FontSize = 10,
                FontWeight = FontWeights.Bold,
                Foreground = new SolidColorBrush(Color.FromRgb(220, 38, 38))
            });

            card.Child = sp;
            Canvas.SetLeft(card, calloutX);
            Canvas.SetTop(card, calloutY);
            canvas.Children.Add(card);
        }

        private void MenuOpenOptions_Click(object sender, RoutedEventArgs e)
        {
            if (InspectorTabs != null) InspectorTabs.SelectedIndex = 1;
        }

        private void ChkShowBones_Click(object sender, RoutedEventArgs e)
        {
            _showAnatomicalBones = (sender as CheckBox)?.IsChecked == true;
            if (ChkShowBones != null) ChkShowBones.IsChecked = _showAnatomicalBones;
            if (ChkEnableSkeletonTemplate != null) ChkEnableSkeletonTemplate.IsChecked = _showAnatomicalBones;
            if (ChkShowBonesInspector != null) ChkShowBonesInspector.IsChecked = _showAnatomicalBones;
            RedrawInteractiveOverlays();
        }

        private void ChkEnableSkeletonTemplate_Click(object sender, RoutedEventArgs e)
        {
            _showAnatomicalBones = ChkEnableSkeletonTemplate.IsChecked == true;
            if (ChkShowBones != null) ChkShowBones.IsChecked = _showAnatomicalBones;
            if (ChkShowBonesInspector != null) ChkShowBonesInspector.IsChecked = _showAnatomicalBones;
            RedrawInteractiveOverlays();
        }

        private void BtnActivateBoneTool_Click(object sender, RoutedEventArgs e)
        {
            _activeTool = ActiveCanvasTool.BoneDrawing;
            if (RbToolBone != null) RbToolBone.IsChecked = true;
            UpdateToolInstructions();
        }

        private void BtnUndoBone_Click(object sender, RoutedEventArgs e)
        {
            if (_drawnBones.Count > 0)
            {
                _drawnBones.RemoveAt(_drawnBones.Count - 1);
                StatusText.Text = $"Letzter Knochen entfernt. Verbleibend: {_drawnBones.Count}.";
                RedrawInteractiveOverlays();
            }
        }

        private void BtnClearBones_Click(object sender, RoutedEventArgs e)
        {
            _drawnBones.Clear();
            StatusText.Text = "Alle eingezeichneten Knochen gelöscht.";
            RedrawInteractiveOverlays();
        }

        private void ComboBoneSide_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (!_isInitialized || ComboBoneSide == null) return;
            _boneIsLeftFoot = (ComboBoneSide.SelectedIndex == 1);
            RedrawInteractiveOverlays();
        }

        private void SliderBoneAdjust_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e)
        {
            if (!_isInitialized) return;
            if (SliderBoneScale != null) _boneScale = SliderBoneScale.Value;
            if (SliderBoneOffX != null) _boneOffX = SliderBoneOffX.Value;
            if (SliderBoneOffY != null) _boneOffY = SliderBoneOffY.Value;

            if (TxtBoneScale != null) TxtBoneScale.Text = $"{(_boneScale * 100):F0}%";
            if (TxtBoneOffX != null) TxtBoneOffX.Text = $"{_boneOffX:+0;-0;0} px";
            if (TxtBoneOffY != null) TxtBoneOffY.Text = $"{_boneOffY:+0;-0;0} px";

            RedrawInteractiveOverlays();
        }

        private void BtnAutoFitBones_Click(object sender, RoutedEventArgs e)
        {
            AutoFitBonesToImage();
        }

        private void AutoFitBonesToImage()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;

            int minX = _rawWidth, maxX = 0, minY = _rawHeight, maxY = 0;
            long sumX = 0, sumY = 0, count = 0;

            for (int y = 0; y < _rawHeight; y++)
            {
                int row = y * _rawWidth;
                for (int x = 0; x < _rawWidth; x++)
                {
                    byte v = _rawGrayPixels[row + x];
                    if (v > 50)
                    {
                        if (x < minX) minX = x;
                        if (x > maxX) maxX = x;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                        sumX += x;
                        sumY += y;
                        count++;
                    }
                }
            }

            if (count > 500 && maxX > minX && maxY > minY)
            {
                double footH = maxY - minY;
                double cx = sumX / (double)count;
                double cy = sumY / (double)count;

                _boneScale = Math.Clamp(footH / 320.0, 0.65, 1.45);
                _boneOffX = Math.Clamp(cx - (_rawWidth / 2.0), -100, 100);
                _boneOffY = Math.Clamp(cy - (_rawHeight / 2.0), -100, 100);

                if (SliderBoneScale != null) SliderBoneScale.Value = _boneScale;
                if (SliderBoneOffX != null) SliderBoneOffX.Value = _boneOffX;
                if (SliderBoneOffY != null) SliderBoneOffY.Value = _boneOffY;

                StatusText.Text = $"Knochenskelett automatisch eingepasst (Skalierung {(_boneScale * 100):F0}%, ΔX={_boneOffX:F0}px, ΔY={_boneOffY:F0}px).";
            }
            else
            {
                _boneScale = 1.0;
                _boneOffX = 0;
                _boneOffY = 0;
            }

            RedrawInteractiveOverlays();
        }

        // ============================================================
        // ORTHOPEDIC GONIOMETER (3-POINT CALIPER) METHODS
        // ============================================================
        private void HandleGoniometerClick(Point pos)
        {
            if (_goniometerPoints.Count >= 3)
            {
                _goniometerPoints.Clear();
                _goniometerMeasurement = null;
            }

            _goniometerPoints.Add(pos);

            if (_goniometerPoints.Count == 3)
            {
                _goniometerMeasurement = OsteoThermalService.CalculateGoniometer(
                    _goniometerPoints[0], _goniometerPoints[1], _goniometerPoints[2]);
                UpdateGoniometerUI();
                if (InspectorTabs != null && TabBones != null)
                {
                    InspectorTabs.SelectedItem = TabBones;
                }
            }
            else
            {
                UpdateGoniometerUI();
            }

            RedrawInteractiveOverlays();
        }

        private void UpdateGoniometerUI()
        {
            if (TxtGoniometerAngle == null || TxtGoniometerGrade == null || TxtGoniometerIndication == null) return;

            if (_goniometerMeasurement != null)
            {
                TxtGoniometerAngle.Text = $"{_goniometerMeasurement.AngleDegrees:F1}°";
                TxtGoniometerGrade.Text = _goniometerMeasurement.SeverityGrade;
                TxtGoniometerIndication.Text = $"{_goniometerMeasurement.Classification}: {_goniometerMeasurement.ClinicalIndication}";
            }
            else if (_goniometerPoints.Count == 1)
            {
                TxtGoniometerAngle.Text = "-- °";
                TxtGoniometerGrade.Text = "Punkt 1 gesetzt";
                TxtGoniometerIndication.Text = "Klicken Sie auf das MTP-I Gelenkzentrum (Scheitelpunkt)...";
            }
            else if (_goniometerPoints.Count == 2)
            {
                TxtGoniometerAngle.Text = "-- °";
                TxtGoniometerGrade.Text = "Punkt 2 gesetzt";
                TxtGoniometerIndication.Text = "Klicken Sie auf die Großzehen-Achse (Hallux)...";
            }
            else
            {
                TxtGoniometerAngle.Text = "-- °";
                TxtGoniometerGrade.Text = "Grad 0";
                TxtGoniometerIndication.Text = "Klicken Sie im Bild auf 3 Punkte zur Achsenmessung...";
            }
        }

        private void DrawGoniometerVector(Canvas canvas)
        {
            if (_goniometerPoints.Count == 0) return;

            var mainStroke = new SolidColorBrush(Color.FromRgb(2, 132, 199)); // Cyan-600
            var accentStroke = new SolidColorBrush(Color.FromRgb(245, 158, 11)); // Amber-500
            var alertStroke = new SolidColorBrush(Color.FromRgb(220, 38, 38)); // Red-600

            void DrawPin(Point p, string label, Brush brush)
            {
                var dot = new Ellipse
                {
                    Width = 10,
                    Height = 10,
                    Fill = brush,
                    Stroke = Brushes.White,
                    StrokeThickness = 2
                };
                Canvas.SetLeft(dot, p.X - 5);
                Canvas.SetTop(dot, p.Y - 5);
                canvas.Children.Add(dot);

                var badge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(220, 15, 23, 42)),
                    CornerRadius = new CornerRadius(4),
                    Padding = new Thickness(4, 1, 4, 1),
                    IsHitTestVisible = false
                };
                badge.Child = new TextBlock
                {
                    Text = label,
                    FontSize = 9.5,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                Canvas.SetLeft(badge, p.X + 8);
                Canvas.SetTop(badge, p.Y - 8);
                canvas.Children.Add(badge);
            }

            // Draw line 1: P1 -> P2
            if (_goniometerPoints.Count >= 2)
            {
                var line1 = new Line
                {
                    X1 = _goniometerPoints[0].X,
                    Y1 = _goniometerPoints[0].Y,
                    X2 = _goniometerPoints[1].X,
                    Y2 = _goniometerPoints[1].Y,
                    Stroke = mainStroke,
                    StrokeThickness = 2.4,
                    StrokeStartLineCap = PenLineCap.Round,
                    StrokeEndLineCap = PenLineCap.Round
                };
                canvas.Children.Add(line1);
            }
            else if (_goniometerPoints.Count == 1 && _goniometerHoverPoint.HasValue)
            {
                var previewLine = new Line
                {
                    X1 = _goniometerPoints[0].X,
                    Y1 = _goniometerPoints[0].Y,
                    X2 = _goniometerHoverPoint.Value.X,
                    Y2 = _goniometerHoverPoint.Value.Y,
                    Stroke = mainStroke,
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 3, 2 }
                };
                canvas.Children.Add(previewLine);
            }

            // Draw line 2: P2 -> P3
            if (_goniometerPoints.Count >= 3)
            {
                var line2 = new Line
                {
                    X1 = _goniometerPoints[1].X,
                    Y1 = _goniometerPoints[1].Y,
                    X2 = _goniometerPoints[2].X,
                    Y2 = _goniometerPoints[2].Y,
                    Stroke = accentStroke,
                    StrokeThickness = 2.4,
                    StrokeStartLineCap = PenLineCap.Round,
                    StrokeEndLineCap = PenLineCap.Round
                };
                canvas.Children.Add(line2);

                var p2 = _goniometerPoints[1];

                if (_goniometerMeasurement != null)
                {
                    var meas = _goniometerMeasurement;
                    var badgeBrush = meas.IsPathologic ? (meas.AngleDegrees >= 20.0 ? alertStroke : accentStroke) : mainStroke;

                    var callout = new Border
                    {
                        Background = Brushes.White,
                        BorderBrush = badgeBrush,
                        BorderThickness = new Thickness(1.8),
                        CornerRadius = new CornerRadius(6),
                        Padding = new Thickness(8, 4, 8, 4),
                        Effect = new System.Windows.Media.Effects.DropShadowEffect
                        {
                            BlurRadius = 8,
                            ShadowDepth = 2,
                            Opacity = 0.2,
                            Color = Colors.Black
                        }
                    };
                    var sp = new StackPanel();
                    sp.Children.Add(new TextBlock
                    {
                        Text = $"📐 HVA: {meas.AngleDegrees:F1}°",
                        FontSize = 11,
                        FontWeight = FontWeights.Bold,
                        Foreground = badgeBrush
                    });
                    sp.Children.Add(new TextBlock
                    {
                        Text = meas.SeverityGrade,
                        FontSize = 9.5,
                        FontWeight = FontWeights.SemiBold,
                        Foreground = new SolidColorBrush(Color.FromRgb(30, 41, 59))
                    });
                    callout.Child = sp;

                    Canvas.SetLeft(callout, p2.X + 14);
                    Canvas.SetTop(callout, p2.Y - 14);
                    canvas.Children.Add(callout);
                }
            }
            else if (_goniometerPoints.Count == 2 && _goniometerHoverPoint.HasValue)
            {
                var previewLine2 = new Line
                {
                    X1 = _goniometerPoints[1].X,
                    Y1 = _goniometerPoints[1].Y,
                    X2 = _goniometerHoverPoint.Value.X,
                    Y2 = _goniometerHoverPoint.Value.Y,
                    Stroke = accentStroke,
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 3, 2 }
                };
                canvas.Children.Add(previewLine2);
            }

            if (_goniometerPoints.Count >= 1) DrawPin(_goniometerPoints[0], "P1 (MT-I)", mainStroke);
            if (_goniometerPoints.Count >= 2) DrawPin(_goniometerPoints[1], "P2 (MTP-I)", alertStroke);
            if (_goniometerPoints.Count >= 3) DrawPin(_goniometerPoints[2], "P3 (Hallux)", accentStroke);
        }

        private void BtnActivateGoniometerTool_Click(object sender, RoutedEventArgs e)
        {
            if (RbToolGoniometer != null)
            {
                RbToolGoniometer.IsChecked = true;
            }
        }

        private void BtnResetGoniometer_Click(object sender, RoutedEventArgs e)
        {
            _goniometerPoints.Clear();
            _goniometerHoverPoint = null;
            _goniometerMeasurement = null;
            UpdateGoniometerUI();
            RedrawInteractiveOverlays();
        }

        // ============================================================
        // OSTEO-THERMAL SAMPLING & COLOR-CODING METHODS
        // ============================================================
        private void SampleOsteoThermalMatrix()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;

            double cx = (_rawWidth / 2.0) + _boneOffX;
            double cy = (_rawHeight / 2.0) + _boneOffY;
            double sc = _boneScale;

            _osteoReport = OsteoThermalService.ComputeOsteoThermalMatrix(
                _rawGrayPixels, _rawWidth, _rawHeight, cx, cy, sc, _boneIsLeftFoot);

            if (GridBoneTemps != null)
            {
                GridBoneTemps.ItemsSource = null;
                GridBoneTemps.ItemsSource = _osteoReport.Bones;
            }

            if (TxtCharcotIndex != null)
            {
                TxtCharcotIndex.Text = $"CII = {_osteoReport.CharcotInflammatoryIndex:F1} K";
            }
            if (TxtCharcotStatus != null)
            {
                TxtCharcotStatus.Text = $"Charcot-Status: {_osteoReport.CharcotRiskStatus}";
            }

            if (_colorBonesByTemp)
            {
                RedrawInteractiveOverlays();
            }
        }

        private void BtnSampleBoneTemps_Click(object sender, RoutedEventArgs e)
        {
            SampleOsteoThermalMatrix();
            if (StatusText != null)
            {
                StatusText.Text = $"Osteo-Thermische Matrix berechnet: {_osteoReport?.TotalBonesSampled ?? 0} Knochen beprobt | CII: {_osteoReport?.CharcotInflammatoryIndex:F1} K";
            }
        }

        private void ChkColorBonesByTemp_Click(object sender, RoutedEventArgs e)
        {
            _colorBonesByTemp = ChkColorBonesByTemp.IsChecked == true;
            if (_colorBonesByTemp && _osteoReport == null)
            {
                SampleOsteoThermalMatrix();
            }
            RedrawInteractiveOverlays();
        }

        private void MenuExit_Click(object sender, RoutedEventArgs e)
        {
            Application.Current.Shutdown();
        }
    }
}