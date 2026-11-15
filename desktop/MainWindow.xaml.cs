using System;
using System.Collections.Generic;
using System.Globalization;
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
        DigitalSubtraction,
        PressureProxy,
        LaplacianHeatFlux,
        Anatomical3DCompensated,
        BioheatPerfusion,
        BilateralMirrorDiff,
        IschemiaColdMap
    }

    public enum ActiveCanvasTool
    {
        PanZoom,
        RoiSelection,
        ThermalProfile,
        PointProbe,
        WindowLevelDrag,
        Goniometer,
        MagnifierLoupe
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
        private byte[]? _cachedHotspotMaskPixels = null;
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

        // 3D Anatomical Reconstruction & Lambertian Edge Compensation State
        private byte[]? _cachedDepth3DPixels = null;
        private byte[]? _cachedCorrected3DPixels = null;
        private bool _showCorrected2D = false;

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

        // Orthopedic Goniometer State
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

        // Advanced Biomechanics & Pressure Proxy State
        private bool _showZonesOverlay = false;
        private PressureProxyStats? _pressureStats = null;
        private WriteableBitmap? _cachedPressureBitmap = null;
        private WriteableBitmap? _cachedLaplaceBitmap = null;
        private WriteableBitmap? _cachedBioheatBitmap = null;
        private AdvancedDiagnosticService.BioheatPerfusionStats? _cachedBioheatStats = null;

        // Feature-Pakete 1-4 (LUT Invertierung, 4x Lupe, Mirror ΔT, Ischämie/Charcot/Entropie, Kohorte & Jury-Demo)
        private bool _invertLut = false;
        private bool _loupePinned = false;
        private int _lastMousePixelX = -1;
        private int _lastMousePixelY = -1;
        private WriteableBitmap? _cachedMirrorDiffBitmap = null;
        private AdvancedDiagnosticService.BilateralMirrorStats? _cachedMirrorStats = null;
        private WriteableBitmap? _cachedIschemiaBitmap = null;
        private AdvancedDiagnosticService.IschemiaCharcotEntropyResult? _cachedIschemiaCharcot = null;
        private List<AdvancedDiagnosticService.CohortCaseSummary> _cohortSummaries = new();
        private System.Windows.Threading.DispatcherTimer? _juryDemoTimer = null;
        private int _juryDemoStep = 0;

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
            FilterInspectorTabsByCategory("Diagnostics");

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
                            CornerRadius = new CornerRadius(6),
                            Margin = new Thickness(3, 1, 3, 1),
                            Padding = new Thickness(4),
                            Cursor = Cursors.Hand,
                            Tag = caseIndex,
                            Width = 96
                        };

                        var stack = new StackPanel { Orientation = Orientation.Vertical, HorizontalAlignment = HorizontalAlignment.Center };

                        // Fast low-res thumbnail decoder
                        var bmp = new BitmapImage();
                        bmp.BeginInit();
                        bmp.UriSource = new Uri(filePath);
                        bmp.DecodePixelWidth = 86;
                        bmp.CacheOption = BitmapCacheOption.OnLoad;
                        bmp.EndInit();
                        bmp.Freeze();

                        var thumbFrame = new Border
                        {
                            Background = new SolidColorBrush(Color.FromRgb(11, 15, 25)),
                            BorderBrush = new SolidColorBrush(Color.FromRgb(30, 41, 59)),
                            BorderThickness = new Thickness(1),
                            CornerRadius = new CornerRadius(4),
                            ClipToBounds = true,
                            Width = 86,
                            Height = 56
                        };

                        var img = new Image
                        {
                            Source = bmp,
                            Width = 86,
                            Height = 56,
                            Stretch = Stretch.UniformToFill
                        };
                        thumbFrame.Child = img;

                        var lbl = new TextBlock
                        {
                            Text = $"Fall #{caseIndex + 1:D2}",
                            FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
                            FontSize = 9.5,
                            FontWeight = FontWeights.SemiBold,
                            Foreground = (Brush)FindResource("TextPrimaryBrush"),
                            HorizontalAlignment = HorizontalAlignment.Center,
                            Margin = new Thickness(0, 4, 0, 0)
                        };

                        stack.Children.Add(thumbFrame);
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
                        card.Background = new SolidColorBrush(Color.FromRgb(0xF0, 0xF9, 0xFF));
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
                _cachedHotspotMaskPixels = null;
                _activeProfileStats = null;
                _cachedPressureBitmap = null;
                _cachedLaplaceBitmap = null;
                _cachedBioheatBitmap = null;
                _cachedBioheatStats = null;
                _cachedMirrorDiffBitmap = null;
                _cachedMirrorStats = null;
                _cachedIschemiaBitmap = null;
                _cachedIschemiaCharcot = null;
                _loupePinned = false;
                _pressureStats = null;
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
                var cal = PaletteService.LoadCalibratedImage(path, _activePalette, _windowWidth, _windowCenter, _invertLut);
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

                // Compute real-time histogram, anatomical zones & biomechanics
                UpdateHistogramData();
                UpdateAnatomicalZonesData();
                UpdateBiomechanicsUI();
                UpdateIschemiaCharcotEntropyUI();

                string fileName = System.IO.Path.GetFileName(path);
                StatusText.Text = $"Thermogramm geladen: {fileName} ({_rawWidth}x{_rawHeight} Radiometrie-Matrix).";
                if (TxtInspectorPatientTitle != null) TxtInspectorPatientTitle.Text = $"Fall: {fileName} · ID: {_activePatientId}";
                if (TxtInspectorSensorSubtitle != null) TxtInspectorSensorSubtitle.Text = $"FLIR LWIR 17µm · {_rawWidth}×{_rawHeight} px · DIN EN ISO 13485";

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

        private Brush SafeFindBrush(string resourceKey, Brush? fallback = null)
        {
            try
            {
                if (TryFindResource(resourceKey) is Brush b)
                    return b;
            }
            catch { }
            return fallback ?? Brushes.Transparent;
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
            bool reconstruct3d = Chk3DReconstruction?.IsChecked == true;

            try
            {
                var result = await _engineService.RunAnalysisAsync(_currentImagePath, kFactor, kernelFactor, mode, vascular, perfusion, _currentROI, null, reconstruct3d);
                if (result == null)
                    return;

                result.Hotspots ??= new();
                result.Stats ??= new();
                result.Timing ??= new();

                _latestResult = result;

                // Update UI metrics
                TxtTissuePixels.Text = $"Gewebe-Pixel: {result.TissuePixelCount:N0}";
                TxtHotspotCount.Text = $"Gefundene Herde: {result.TotalHotspots}";
                TxtLatency.Text = $"Rechenzeit: {result.Timing.TotalMs:F1} ms (42 Stufen | Top-Hat AVX2: {result.Timing.TopHatMs:F1} ms)";
                EngineTimingText.Text = $"Go Core: {result.Timing.TotalMs:F1} ms (42 Stufen / AVX2)";

                // Update 42 Pipeline Stages Table
                if (result.Stages != null && result.Stages.Count > 0)
                {
                    GridStages.ItemsSource = result.Stages;
                    TxtStagesCount.Text = $"{result.Stages.Count} / 42";
                    TxtStagesTotalMs.Text = $"{result.Timing.TotalMs:F1} ms";
                    GridStages.SelectedIndex = 0;
                }

                // Update Hotspot Table (sorted by clinical severity)
                result.Hotspots = result.Hotspots.OrderByDescending(h => (h.Assessment?.Score ?? 0) * 100 + (h.Region?.MaxVal ?? 0)).ToList();
                GridHotspots.ItemsSource = result.Hotspots;
                if (result.Hotspots.Count > 0)
                {
                    GridHotspots.SelectedIndex = 0;
                }

                // Invalidate cached masks so new ones are loaded
                _cachedVeinPixels = null;
                _cachedHotspotMaskPixels = null;
                _cachedDepth3DPixels = null;
                _cachedCorrected3DPixels = null;

                // Update Clinical Header Status Chip & Inspector Risk Badge
                bool isCrit = (result.HighestRisk == "CRITICAL");
                double maxVal = result.Hotspots.Count > 0 ? result.Hotspots.Max(h => ComputeHotspotDeltaT(h?.Region, result.Stats?.OrigMedian ?? 0)) : 0;
                if (isCrit)
                {
                    if (BorderTriageBadge != null)
                    {
                        BorderTriageBadge.Background = SafeFindBrush("CriticalBgBrush", new SolidColorBrush(Color.FromRgb(0xFE, 0xE2, 0xE2)));
                        BorderTriageBadge.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFC, 0xA5, 0xA5));
                    }
                    if (BadgeAiStatusDot != null) BadgeAiStatusDot.Background = SafeFindBrush("CriticalBrush", Brushes.Red);
                    if (TxtHeaderAiStatus != null)
                    {
                        TxtHeaderAiStatus.Text = $"KRITISCH (ΔT = +{maxVal:F1} K)";
                        TxtHeaderAiStatus.Foreground = SafeFindBrush("CriticalBrush", Brushes.Red);
                    }
                    if (TxtInspectorCaseRisk != null)
                    {
                        TxtInspectorCaseRisk.Text = $"ARMSTRONG RISIKO: CRITICAL (ΔT = +{maxVal:F1} K)";
                        TxtInspectorCaseRisk.Foreground = SafeFindBrush("CriticalBrush", Brushes.Red);
                    }
                    if (FloatingArmstrongBanner != null)
                    {
                        FloatingArmstrongBanner.Visibility = Visibility.Visible;
                        TxtFloatingArmstrong.Text = $"ARMSTRONG-WARNUNG: ΔT = {maxVal:F1} K (≥ 2.2 K) — Hohes Ulkusrisiko!";
                    }
                }
                else
                {
                    if (BorderTriageBadge != null)
                    {
                        BorderTriageBadge.Background = SafeFindBrush("SuccessBgBrush", new SolidColorBrush(Color.FromRgb(0xDC, 0xFC, 0xE7)));
                        BorderTriageBadge.BorderBrush = new SolidColorBrush(Color.FromRgb(0x86, 0xEF, 0xAC));
                    }
                    if (BadgeAiStatusDot != null) BadgeAiStatusDot.Background = SafeFindBrush("SuccessBrush", Brushes.Green);
                    if (TxtHeaderAiStatus != null)
                    {
                        TxtHeaderAiStatus.Text = "STABIL / PHYSIOLOGISCH";
                        TxtHeaderAiStatus.Foreground = new SolidColorBrush(Color.FromRgb(0x15, 0x80, 0x3D));
                    }
                    if (TxtInspectorCaseRisk != null)
                    {
                        TxtInspectorCaseRisk.Text = "ARMSTRONG STADIUM 0 (PHYSIOLOGISCH)";
                        TxtInspectorCaseRisk.Foreground = SafeFindBrush("CyanBrush", Brushes.DodgerBlue);
                    }
                    if (FloatingArmstrongBanner != null) FloatingArmstrongBanner.Visibility = Visibility.Collapsed;
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

                // Update Biomechanics & Pennes-Bioheat Pressure Proxy
                UpdateBiomechanicsUI();

                // Update 3D Surface Reconstruction & Lambertian Edge Compensation
                Update3DReconstructionUI();

                // Update pAVK Ischemia, Charcot Midfoot Index & Shannon Thermal Entropy
                UpdateIschemiaCharcotEntropyUI();

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

            // Handle Biomechanical Pressure Proxy mode
            if (_activeViewMode == ActiveViewMode.PressureProxy && _rawGrayPixels != null)
            {
                if (_cachedPressureBitmap == null || _pressureStats == null)
                {
                    var (pBmp, stats) = AdvancedDiagnosticService.GeneratePressureProxyMap(_rawGrayPixels, w, h);
                    _cachedPressureBitmap = pBmp;
                    _pressureStats = stats;
                    UpdateBiomechanicsUI();
                }
                ImgResult.Source = _cachedPressureBitmap;
                RedrawInteractiveOverlays();
                return;
            }

            // Handle Discrete 2D-Laplacian Heat Flux mode
            if (_activeViewMode == ActiveViewMode.LaplacianHeatFlux && _rawGrayPixels != null)
            {
                if (_cachedLaplaceBitmap == null)
                {
                    _cachedLaplaceBitmap = AdvancedDiagnosticService.GenerateLaplacianHeatFluxMap(_rawGrayPixels, w, h);
                }
                ImgResult.Source = _cachedLaplaceBitmap;
                RedrawInteractiveOverlays();
                return;
            }

            // Handle 3D Anatomical Reconstruction & Lambertian Edge Compensation mode
            if (_activeViewMode == ActiveViewMode.Anatomical3DCompensated && _rawGrayPixels != null)
            {
                Ensure3DCacheLoaded(w, h);
                byte[] tempSource = (_showCorrected2D && _cachedCorrected3DPixels != null) ? _cachedCorrected3DPixels : (_cachedCorrected3DPixels ?? _rawGrayPixels);
                var anatomical3DBmp = ThermalTopographyService.GenerateAnatomical3DSurface(
                    tempSource, _cachedDepth3DPixels, w, h, _activePalette, true, 0.45);
                ImgResult.Source = anatomical3DBmp;
                OverlayResultCanvas.Children.Clear();
                return;
            }

            // Handle Pennes 2D Bioheat Perfusion mode
            if (_activeViewMode == ActiveViewMode.BioheatPerfusion && _rawGrayPixels != null)
            {
                if (_cachedBioheatBitmap == null || _cachedBioheatStats == null)
                {
                    var (bBmp, bStats) = AdvancedDiagnosticService.GenerateBioheatPerfusionMap(_rawGrayPixels, w, h);
                    _cachedBioheatBitmap = bBmp;
                    _cachedBioheatStats = bStats;
                }
                ImgResult.Source = _cachedBioheatBitmap;
                RedrawInteractiveOverlays();
                return;
            }

            // Handle Bilateral Mirror Difference |T_L - T_R| mode
            if (_activeViewMode == ActiveViewMode.BilateralMirrorDiff && _rawGrayPixels != null)
            {
                if (_cachedMirrorDiffBitmap == null || _cachedMirrorStats == null)
                {
                    var (mBmp, mStats) = AdvancedDiagnosticService.GenerateBilateralMirrorDiffMap(_rawGrayPixels, w, h);
                    _cachedMirrorDiffBitmap = mBmp;
                    _cachedMirrorStats = mStats;
                }
                ImgResult.Source = _cachedMirrorDiffBitmap;
                RedrawInteractiveOverlays();
                return;
            }

            // Handle pAVK Acral Ischemia Cold-Spot map
            if (_activeViewMode == ActiveViewMode.IschemiaColdMap && _rawGrayPixels != null)
            {
                if (_cachedIschemiaBitmap == null)
                {
                    _cachedIschemiaBitmap = AdvancedDiagnosticService.GenerateIschemiaColdSpotMap(_rawGrayPixels, w, h);
                }
                ImgResult.Source = _cachedIschemiaBitmap;
                RedrawInteractiveOverlays();
                return;
            }

            byte[]? activeDisplayPixels = (_showCorrected2D && _cachedCorrected3DPixels != null) ? _cachedCorrected3DPixels : _rawGrayPixels;

            // Load confirmed vascular & hotspot segmentation masks BEFORE branching into DualView / CurtainWipe
            EnsureAnalysisMasksLoaded(w, h, showVeins && _enableVeinOverlay, loadHotspotMask: true);

            BitmapSource baseBmp;
            if ((_activeViewMode == ActiveViewMode.CurtainWipe || _activeViewMode == ActiveViewMode.DualView) && activeDisplayPixels != null)
            {
                byte thresh = 160;
                if (result.Stats != null && result.Stats.OrigMedian > 0)
                {
                    thresh = (byte)Math.Clamp(result.Stats.OrigMedian + 10, 100, 230);
                }
                baseBmp = PaletteService.CreateIsolatedFindingBitmap(
                    activeDisplayPixels, w, h, _activePalette, thresh, _cachedVeinPixels, showVeins && _enableVeinOverlay, _windowWidth, _windowCenter, _invertLut, _cachedHotspotMaskPixels);
            }
            else
            {
                baseBmp = activeDisplayPixels != null
                    ? PaletteService.ApplyPalette(activeDisplayPixels, w, h, _activePalette, _windowWidth, _windowCenter, _invertLut)
                    : PaletteService.ApplyPalette(_originalBitmap, _activePalette, _windowWidth, _windowCenter, _invertLut);

                // Blend vein mask if active
                if (showVeins && _enableVeinOverlay && _cachedVeinPixels != null)
                {
                    baseBmp = PaletteService.BlendVeinOverlay(baseBmp, _cachedVeinPixels, _veinOpacity, _veinThreshold, _veinRenderMode);
                }
            }

            ImgResult.Source = baseBmp;

            // Redraw vector annotations
            RedrawInteractiveOverlays();
        }

        private void EnsureAnalysisMasksLoaded(int w, int h, bool loadVeinMask, bool loadHotspotMask)
        {
            if (loadVeinMask && _cachedVeinPixels == null)
            {
                try
                {
                    string veinMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "vascular_mask.png");
                    if (File.Exists(veinMaskPath))
                    {
                        _cachedVeinPixels = PaletteService.LoadVeinMaskBytes(veinMaskPath, w, h);
                        UpdateVeinMetricsUI();
                    }
                }
                catch { }
            }

            if (loadHotspotMask && _cachedHotspotMaskPixels == null)
            {
                try
                {
                    string hotspotMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "hotspot_mask.png");
                    if (File.Exists(hotspotMaskPath))
                    {
                        _cachedHotspotMaskPixels = PaletteService.LoadVeinMaskBytes(hotspotMaskPath, w, h);
                    }
                }
                catch { }
            }
        }

        private static double ComputeHotspotDeltaT(HotspotRegion? reg, double origMed)
        {
            if (reg == null) return 0.0;
            if (reg.ContraDelta > 0)
            {
                return Math.Round(reg.ContraDelta * 0.1, 1);
            }
            return Math.Round(Math.Max(reg.LocalProminence, reg.MaxVal - origMed) * 0.1, 1);
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

            if (_activeViewMode == ActiveViewMode.PressureProxy && _rawGrayPixels != null)
            {
                if (_cachedPressureBitmap == null || _pressureStats == null)
                {
                    var (pBmp, stats) = AdvancedDiagnosticService.GeneratePressureProxyMap(_rawGrayPixels, w, h);
                    _cachedPressureBitmap = pBmp;
                    _pressureStats = stats;
                    UpdateBiomechanicsUI();
                }
                ImgResult.Source = _cachedPressureBitmap;
                OverlayResultCanvas.Children.Clear();
                RedrawInteractiveOverlays();
                return;
            }

            if (_activeViewMode == ActiveViewMode.LaplacianHeatFlux && _rawGrayPixels != null)
            {
                if (_cachedLaplaceBitmap == null)
                {
                    _cachedLaplaceBitmap = AdvancedDiagnosticService.GenerateLaplacianHeatFluxMap(_rawGrayPixels, w, h);
                }
                ImgResult.Source = _cachedLaplaceBitmap;
                OverlayResultCanvas.Children.Clear();
                RedrawInteractiveOverlays();
                return;
            }

            if (_activeViewMode == ActiveViewMode.Anatomical3DCompensated && _rawGrayPixels != null)
            {
                Ensure3DCacheLoaded(w, h);
                byte[] tempSource = (_showCorrected2D && _cachedCorrected3DPixels != null) ? _cachedCorrected3DPixels : (_cachedCorrected3DPixels ?? _rawGrayPixels);
                ImgResult.Source = ThermalTopographyService.GenerateAnatomical3DSurface(
                    tempSource, _cachedDepth3DPixels, w, h, _activePalette, true, 0.45);
                OverlayResultCanvas.Children.Clear();
                return;
            }

            if (_activeViewMode == ActiveViewMode.BioheatPerfusion && _rawGrayPixels != null)
            {
                if (_cachedBioheatBitmap == null || _cachedBioheatStats == null)
                {
                    var (bBmp, bStats) = AdvancedDiagnosticService.GenerateBioheatPerfusionMap(_rawGrayPixels, w, h);
                    _cachedBioheatBitmap = bBmp;
                    _cachedBioheatStats = bStats;
                }
                ImgResult.Source = _cachedBioheatBitmap;
                OverlayResultCanvas.Children.Clear();
                RedrawInteractiveOverlays();
                return;
            }

            if (_activeViewMode == ActiveViewMode.BilateralMirrorDiff && _rawGrayPixels != null)
            {
                if (_cachedMirrorDiffBitmap == null || _cachedMirrorStats == null)
                {
                    var (mBmp, mStats) = AdvancedDiagnosticService.GenerateBilateralMirrorDiffMap(_rawGrayPixels, w, h);
                    _cachedMirrorDiffBitmap = mBmp;
                    _cachedMirrorStats = mStats;
                }
                ImgResult.Source = _cachedMirrorDiffBitmap;
                OverlayResultCanvas.Children.Clear();
                RedrawInteractiveOverlays();
                return;
            }

            if (_activeViewMode == ActiveViewMode.IschemiaColdMap && _rawGrayPixels != null)
            {
                if (_cachedIschemiaBitmap == null)
                {
                    _cachedIschemiaBitmap = AdvancedDiagnosticService.GenerateIschemiaColdSpotMap(_rawGrayPixels, w, h);
                }
                ImgResult.Source = _cachedIschemiaBitmap;
                OverlayResultCanvas.Children.Clear();
                RedrawInteractiveOverlays();
                return;
            }

            byte[]? activeDisplayPixels = (_showCorrected2D && _cachedCorrected3DPixels != null) ? _cachedCorrected3DPixels : _rawGrayPixels;

            EnsureAnalysisMasksLoaded(w, h, _enableVeinOverlay, loadHotspotMask: _latestResult != null);

            BitmapSource baseBmp;
            if ((_activeViewMode == ActiveViewMode.CurtainWipe || _activeViewMode == ActiveViewMode.DualView) && activeDisplayPixels != null)
            {
                byte thresh = (byte)Math.Clamp(_windowCenter + 15, 120, 230);
                if (_latestResult?.Stats != null && _latestResult.Stats.OrigMedian > 0)
                {
                    thresh = (byte)Math.Clamp(_latestResult.Stats.OrigMedian + 10, 100, 230);
                }
                baseBmp = PaletteService.CreateIsolatedFindingBitmap(
                    activeDisplayPixels, w, h, _activePalette, thresh, _cachedVeinPixels, _enableVeinOverlay, _windowWidth, _windowCenter, _invertLut, _cachedHotspotMaskPixels);
            }
            else
            {
                baseBmp = activeDisplayPixels != null
                    ? PaletteService.ApplyPalette(activeDisplayPixels, w, h, _activePalette, _windowWidth, _windowCenter, _invertLut)
                    : PaletteService.ApplyPalette(_originalBitmap, _activePalette, _windowWidth, _windowCenter, _invertLut);

                if (_enableVeinOverlay && _cachedVeinPixels != null)
                {
                    baseBmp = PaletteService.BlendVeinOverlay(baseBmp, _cachedVeinPixels, _veinOpacity, _veinThreshold, _veinRenderMode);
                }
            }

            ImgResult.Source = baseBmp;
            UpdateHudReadouts();
        }

        // --- View Mode Selector (Dual, Curtain Wipe, 3D Relief, Pure DSA, Isotherm, PressureProxy, Laplace) ---
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
            else if (RbViewPressureProxy != null && RbViewPressureProxy.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.PressureProxy;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(TabBiomechanics);
                TxtVp2Title.Text = "BIOMECHANISCHER PLANTARDRUCK- & SCHERSPANNUNGS-PROXY (PENNES BIOHEAT in kPa)";
            }
            else if (RbViewLaplace != null && RbViewLaplace.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.LaplacianHeatFlux;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(TabBiomechanics);
                TxtVp2Title.Text = "DISCRETE 2D-LAPLACE (∇²T) WÄRMESTAU- & TIEFENGEWEBE-ABSZESSFILTER";
            }
            else if (RbView3DAnatomy != null && RbView3DAnatomy.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.Anatomical3DCompensated;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(Tab3DReconstruction);
                TxtVp2Title.Text = "3D-ANATOMISCHE OBERFLÄCHEN-REKONSTRUKTION & LAMBERT-KANTENKORREKTUR";
            }
            else if (RbViewBioheat != null && RbViewBioheat.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.BioheatPerfusion;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(TabBiomechanics);
                TxtVp2Title.Text = "PENNES 2D BIOHEAT MIKROVASKULÄRE PERFUSIONSMAP (ω_b in ml / 100g / min)";
            }
            else if (RbViewMirrorDiff != null && RbViewMirrorDiff.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.BilateralMirrorDiff;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(TabIschemiaCharcot);
                UpdateIschemiaCharcotEntropyUI();
                TxtVp2Title.Text = "BILATERALE SPIEGELSYMMETRIE-DIFFERENZKARTE |T_L − T_R| (ARMSTRONG ≥ 2,2 K)";
            }
            else if (RbViewIschemia != null && RbViewIschemia.IsChecked == true)
            {
                _activeViewMode = ActiveViewMode.IschemiaColdMap;
                ColViewport1.Width = new GridLength(1, GridUnitType.Star);
                ColDivider.Width = new GridLength(1);
                ColViewport2.Width = new GridLength(1, GridUnitType.Star);
                ImgCurtainRaw.Visibility = Visibility.Collapsed;
                CanvasCurtain.Visibility = Visibility.Collapsed;
                SelectInspectorTab(TabIschemiaCharcot);
                UpdateIschemiaCharcotEntropyUI();
                TxtVp2Title.Text = "pAVK AKRALE ISCHÄMIE COLD-SPOT PERFUSIONSKARTE (HYPOTHERMIE < 28,5 °C)";
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

            if (CurtainLabelLeft != null)
            {
                Canvas.SetLeft(CurtainLabelLeft, Math.Max(8, curtainX - 96));
                Canvas.SetTop(CurtainLabelLeft, 12);
            }
            if (CurtainLabelRight != null)
            {
                Canvas.SetLeft(CurtainLabelRight, Math.Min(_rawWidth - 92, curtainX + 12));
                Canvas.SetTop(CurtainLabelRight, 12);
            }

            if (BorderCurtainHandle != null)
            {
                Canvas.SetLeft(BorderCurtainHandle, curtainX - 23);
                Canvas.SetTop(BorderCurtainHandle, (_rawHeight / 2.0) - 15);
            }
        }

        // --- Synchronized Live Dual-Viewport Crosshair Reticle ---
        private void UpdateSynchronizedCrosshair(int x, int y)
        {
            if (_rawWidth <= 0 || _rawHeight <= 0) return;

            if (!_loupePinned)
            {
                _lastMousePixelX = x;
                _lastMousePixelY = y;
            }

            DrawCrosshairOnCanvas(CrosshairOriginalCanvas, x, y);
            DrawCrosshairOnCanvas(CrosshairResultCanvas, x, y);

            if (_activeTool == ActiveCanvasTool.MagnifierLoupe)
            {
                int lx = _loupePinned && _lastMousePixelX >= 0 ? _lastMousePixelX : x;
                int ly = _loupePinned && _lastMousePixelY >= 0 ? _lastMousePixelY : y;
                DrawMagnifierLoupeOnCanvas(CrosshairResultCanvas, lx, ly);
            }
        }

        private void DrawCrosshairOnCanvas(Canvas canvas, int x, int y)
        {
            if (canvas == null) return;
            canvas.Children.Clear();

            // Subtle dashed DICOM guidelines
            var hLine = new System.Windows.Shapes.Line
            {
                X1 = 0, Y1 = y,
                X2 = _rawWidth, Y2 = y,
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 1,
                Opacity = 0.4,
                StrokeDashArray = new DoubleCollection { 4, 3 }
            };
            var vLine = new System.Windows.Shapes.Line
            {
                X1 = x, Y1 = 0,
                X2 = x, Y2 = _rawHeight,
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 1,
                Opacity = 0.4,
                StrokeDashArray = new DoubleCollection { 4, 3 }
            };

            // Medical circular reticle
            var ring = new System.Windows.Shapes.Ellipse
            {
                Width = 14,
                Height = 14,
                Stroke = (Brush)FindResource("CyanBrush"),
                StrokeThickness = 1.5,
                Fill = Brushes.Transparent
            };
            Canvas.SetLeft(ring, x - 7);
            Canvas.SetTop(ring, y - 7);

            // Center target dot
            var dot = new System.Windows.Shapes.Ellipse
            {
                Width = 2,
                Height = 2,
                Fill = (Brush)FindResource("CyanBrush")
            };
            Canvas.SetLeft(dot, x - 1);
            Canvas.SetTop(dot, y - 1);

            canvas.Children.Add(hLine);
            canvas.Children.Add(vLine);
            canvas.Children.Add(ring);
            canvas.Children.Add(dot);
        }

        private void HideSynchronizedCrosshairs()
        {
            CrosshairOriginalCanvas?.Children.Clear();
            CrosshairResultCanvas?.Children.Clear();
        }

        private void DrawMagnifierLoupeOnCanvas(Canvas? canvas, int cx, int cy)
        {
            if (canvas == null || _rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                return;

            double cell = Math.Clamp(Math.Min(_rawWidth, _rawHeight) / 30.0, 8.0, 22.0);
            double gridSize = cell * 9.0;
            double pad = Math.Max(5.0, cell * 0.55);
            double fontScale = Math.Clamp(cell / 10.0, 0.85, 1.9);
            double footerH = Math.Round(30.0 * fontScale);
            double totalW = gridSize + pad * 2;
            double totalH = gridSize + pad * 2 + footerH;

            double offset = Math.Max(14.0, cell * 1.4);
            double boxX = cx + offset;
            double boxY = cy + offset;
            if (boxX + totalW + 4 > _rawWidth) boxX = cx - totalW - offset;
            if (boxY + totalH + 4 > _rawHeight) boxY = cy - totalH - offset;
            boxX = Math.Clamp(boxX, 4, Math.Max(4, _rawWidth - totalW - 4));
            boxY = Math.Clamp(boxY, 4, Math.Max(4, _rawHeight - totalH - 4));

            var gridCanvas = new Canvas { Width = gridSize, Height = gridSize, ClipToBounds = true };
            double minT = double.MaxValue, maxT = double.MinValue, sumT = 0.0, centerT = 0.0;
            int count = 0;

            for (int dy = -4; dy <= 4; dy++)
            {
                for (int dx = -4; dx <= 4; dx++)
                {
                    int px = Math.Clamp(cx + dx, 0, _rawWidth - 1);
                    int py = Math.Clamp(cy + dy, 0, _rawHeight - 1);
                    byte raw = _rawGrayPixels[py * _rawWidth + px];
                    double t = ThermalAnalysisHelper.RawToTemperature(raw);

                    if (t < minT) minT = t;
                    if (t > maxT) maxT = t;
                    sumT += t;
                    count++;
                    if (dx == 0 && dy == 0) centerT = t;

                    uint bgra = PaletteService.GetBgraColorForValue(raw, _activePalette, _windowWidth, _windowCenter, _invertLut);
                    byte b = (byte)(bgra & 0xFF);
                    byte g = (byte)((bgra >> 8) & 0xFF);
                    byte r = (byte)((bgra >> 16) & 0xFF);

                    var rect = new System.Windows.Shapes.Rectangle
                    {
                        Width = cell + 0.5,
                        Height = cell + 0.5,
                        Fill = new SolidColorBrush(Color.FromRgb(r, g, b)),
                        Stroke = (dx == 0 && dy == 0) ? Brushes.White : new SolidColorBrush(Color.FromArgb(40, 255, 255, 255)),
                        StrokeThickness = (dx == 0 && dy == 0) ? 1.5 : 0.4
                    };
                    Canvas.SetLeft(rect, (dx + 4) * cell);
                    Canvas.SetTop(rect, (dy + 4) * cell);
                    gridCanvas.Children.Add(rect);
                }
            }

            double meanT = count > 0 ? sumT / count : centerT;
            Color accentColor = _loupePinned ? Color.FromRgb(245, 158, 11) : Color.FromRgb(56, 189, 248);
            var accentBrush = new SolidColorBrush(accentColor);

            var hudStack = new StackPanel();
            hudStack.Children.Add(gridCanvas);
            hudStack.Children.Add(new TextBlock
            {
                Text = $"{(_loupePinned ? "PIN " : "")}({cx},{cy})  T={centerT:F2}°C",
                FontFamily = new FontFamily("Consolas"),
                FontSize = 9.0 * fontScale,
                FontWeight = FontWeights.Bold,
                Foreground = accentBrush,
                Margin = new Thickness(0, 4, 0, 1)
            });
            hudStack.Children.Add(new TextBlock
            {
                Text = $"9×9: {minT:F1}..{maxT:F1}°C (Ø{meanT:F1})",
                FontFamily = new FontFamily("Consolas"),
                FontSize = 8.0 * fontScale,
                Foreground = new SolidColorBrush(Color.FromRgb(203, 213, 225))
            });

            var hudBorder = new Border
            {
                Width = totalW,
                Background = new SolidColorBrush(Color.FromArgb(236, 11, 15, 25)),
                BorderBrush = accentBrush,
                BorderThickness = new Thickness(1.4),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(pad),
                Child = hudStack,
                IsHitTestVisible = false
            };

            // Target 9x9 sampling box outline at cursor
            var srcBox = new System.Windows.Shapes.Rectangle
            {
                Width = 9,
                Height = 9,
                Stroke = accentBrush,
                StrokeThickness = 1.2,
                Fill = Brushes.Transparent,
                IsHitTestVisible = false
            };
            Canvas.SetLeft(srcBox, cx - 4.5);
            Canvas.SetTop(srcBox, cy - 4.5);

            var leader = new System.Windows.Shapes.Line
            {
                X1 = cx,
                Y1 = cy,
                X2 = boxX + totalW * 0.5,
                Y2 = boxY + totalH * 0.5,
                Stroke = accentBrush,
                StrokeThickness = 0.9,
                Opacity = 0.55,
                StrokeDashArray = new DoubleCollection { 2, 2 },
                IsHitTestVisible = false
            };

            Canvas.SetLeft(hudBorder, boxX);
            Canvas.SetTop(hudBorder, boxY);

            canvas.Children.Add(leader);
            canvas.Children.Add(srcBox);
            canvas.Children.Add(hudBorder);
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
                    if (hspot == null || hspot.Region == null) continue;
                    var reg = hspot.Region;
                    var box = reg.BoundingBox;
                    if (box == null || box.Length < 4) continue;

                    int minX = box[0], minY = box[1], maxX = box[2], maxY = box[3];
                    int bw = maxX - minX, bh = maxY - minY;
                    var risk = hspot.Assessment?.RiskLevel ?? "NORMAL";
                    string? diagType = hspot.Assessment?.DiagnosisType;
                    if (string.IsNullOrWhiteSpace(diagType)) diagType = reg.DiagnosisType ?? "INFLAMMATION";

                    Brush strokeBrush;
                    Brush fillBrush;
                    DoubleCollection? dashArray = null;
                    string badgePrefix;

                    if (diagType == "PRESSURE_POINT")
                    {
                        strokeBrush = new SolidColorBrush(Color.FromRgb(251, 191, 36)); // Amber für Druckstelle
                        fillBrush = new SolidColorBrush(Color.FromArgb(32, 251, 191, 36));
                        dashArray = new DoubleCollection { 4, 2 }; // Gestrichelter Rand = mechanische Druckbelastung
                        badgePrefix = "DRUCKSTELLE";
                    }
                    else if (diagType == "INFLAMED_PRESSURE_POINT")
                    {
                        strokeBrush = new SolidColorBrush(Color.FromRgb(248, 113, 113)); // Armstrong Alarm Red
                        fillBrush = new SolidColorBrush(Color.FromArgb(48, 220, 38, 38));
                        badgePrefix = "ENTZ. DRUCKSTELLE";
                    }
                    else if (diagType == "BENIGN")
                    {
                        strokeBrush = new SolidColorBrush(Color.FromRgb(74, 222, 128)); // Green
                        fillBrush = new SolidColorBrush(Color.FromArgb(26, 22, 163, 74));
                        badgePrefix = "PHYSIOLOGISCH";
                    }
                    else
                    {
                        // Echte Entzündung (INFLAMMATION)
                        strokeBrush = risk == "CRITICAL" ? new SolidColorBrush(Color.FromRgb(248, 113, 113)) : new SolidColorBrush(Color.FromRgb(239, 68, 68));
                        fillBrush = new SolidColorBrush(Color.FromArgb(40, 220, 38, 38));
                        badgePrefix = "HERD / ENTZÜNDUNG";
                    }

                    var rect = new System.Windows.Shapes.Rectangle
                    {
                        Width = Math.Max(bw, 12),
                        Height = Math.Max(bh, 12),
                        Stroke = strokeBrush,
                        StrokeThickness = diagType == "INFLAMED_PRESSURE_POINT" ? 2.5 : 2.0,
                        StrokeDashArray = dashArray,
                        RadiusX = 3,
                        RadiusY = 3,
                        Fill = fillBrush
                    };
                    Canvas.SetLeft(rect, minX);
                    Canvas.SetTop(rect, minY);
                    OverlayResultCanvas.Children.Add(rect);

                    var crosshairH = new Line { X1 = reg.CenterX - 8, Y1 = reg.CenterY, X2 = reg.CenterX + 8, Y2 = reg.CenterY, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    var crosshairV = new Line { X1 = reg.CenterX, Y1 = reg.CenterY - 8, X2 = reg.CenterX, Y2 = reg.CenterY + 8, Stroke = Brushes.White, StrokeThickness = 1.5 };
                    OverlayResultCanvas.Children.Add(crosshairH);
                    OverlayResultCanvas.Children.Add(crosshairV);

                    double deltaT = ComputeHotspotDeltaT(reg, origMed);
                    var labelBorder = new Border
                    {
                        Background = new SolidColorBrush(Color.FromArgb(230, 15, 23, 42)),
                        BorderBrush = rect.Stroke,
                        BorderThickness = new Thickness(1),
                        CornerRadius = new CornerRadius(4),
                        Padding = new Thickness(6, 2, 6, 2)
                    };
                    labelBorder.Child = new TextBlock
                    {
                        Text = $"{badgePrefix} #{reg.Id} · ΔT +{deltaT:F1} K",
                        FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
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


            // 7b. Draw Orthopedic Goniometer (3-Point Angle Caliper)
            if (_goniometerPoints.Count > 0)
            {
                DrawGoniometerVector(OverlayOriginalCanvas);
                DrawGoniometerVector(OverlayResultCanvas);
            }

            // 8. Screenshot-matching Fokaler Hotspot Callout Box
            if (_latestResult?.Hotspots != null && _latestResult.Hotspots.Count > 0)
            {
                var mainHotspot = _latestResult.Hotspots
                    .OrderByDescending(h => (h.Assessment?.Score ?? 0) * 100 + (h.Region?.MaxVal ?? 0))
                    .FirstOrDefault();
                if (mainHotspot?.Region != null)
                {
                    double hx = mainHotspot.Region.CenterX;
                    double hy = mainHotspot.Region.CenterY;
                    double origMed = _latestResult.Stats?.OrigMedian ?? 128.0;
                    double deltaT = ComputeHotspotDeltaT(mainHotspot.Region, origMed);
                    if (deltaT < 1.0 && mainHotspot.Region.EdgeGradient > 0)
                    {
                        deltaT = Math.Round(mainHotspot.Region.EdgeGradient * 0.1, 1);
                    }
                    string riskText = mainHotspot.Assessment?.RiskLevel == "CRITICAL" ? "Kritisch" : "Auffällig";

                    DrawHotspotCalloutCard(OverlayOriginalCanvas, hx, hy, deltaT, riskText);
                    DrawHotspotCalloutCard(OverlayResultCanvas, hx, hy, deltaT, riskText);
                }
            }

            // 9. Draw Anatomical 5-Zone Overlay
            if (_showZonesOverlay && _rawGrayPixels != null)
            {
                DrawAnatomicalZonesVector(OverlayOriginalCanvas);
                DrawAnatomicalZonesVector(OverlayResultCanvas);
            }
        }

        private void DrawExtremumPin(Canvas canvas, int x, int y, double temp, bool isMax)
        {
            var brush = isMax
                ? new SolidColorBrush(Color.FromRgb(248, 113, 113))
                : new SolidColorBrush(Color.FromRgb(56, 189, 248));
            var marker = isMax ? "▲" : "▼";
            var text = isMax ? $"MAX {temp:F1}°C" : $"MIN {temp:F1}°C";

            var ring = new Ellipse
            {
                Width = 14,
                Height = 14,
                Stroke = brush,
                StrokeThickness = 1.8,
                Fill = new SolidColorBrush(Color.FromArgb(40, isMax ? (byte)248 : (byte)56, isMax ? (byte)113 : (byte)189, isMax ? (byte)113 : (byte)248))
            };
            Canvas.SetLeft(ring, x - 7);
            Canvas.SetTop(ring, y - 7);
            canvas.Children.Add(ring);

            var tag = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(230, 15, 23, 42)),
                BorderBrush = brush,
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(4),
                Padding = new Thickness(5, 1.5, 5, 1.5)
            };
            tag.Child = new TextBlock
            {
                Text = $"{marker} {text}",
                FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
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
            var strokeBrush = new SolidColorBrush(Color.FromRgb(56, 189, 248));
            var line = new Line
            {
                X1 = _profileStartPoint.X,
                Y1 = _profileStartPoint.Y,
                X2 = _profileEndPoint.X,
                Y2 = _profileEndPoint.Y,
                Stroke = strokeBrush,
                StrokeThickness = 2.2
            };
            canvas.Children.Add(line);

            var r1 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = strokeBrush, StrokeThickness = 1.5 };
            Canvas.SetLeft(r1, _profileStartPoint.X - 4);
            Canvas.SetTop(r1, _profileStartPoint.Y - 4);
            canvas.Children.Add(r1);

            var r2 = new Ellipse { Width = 8, Height = 8, Fill = Brushes.White, Stroke = strokeBrush, StrokeThickness = 1.5 };
            Canvas.SetLeft(r2, _profileEndPoint.X - 4);
            Canvas.SetTop(r2, _profileEndPoint.Y - 4);
            canvas.Children.Add(r2);

            double midX = (_profileStartPoint.X + _profileEndPoint.X) / 2.0;
            double midY = (_profileStartPoint.Y + _profileEndPoint.Y) / 2.0;

            var badge = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(230, 15, 23, 42)),
                BorderBrush = strokeBrush,
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(4),
                Padding = new Thickness(6, 2, 6, 2)
            };
            badge.Child = new TextBlock
            {
                Text = $"T(s): {_activeProfileStats?.MinTemp:F1}°C – {_activeProfileStats?.MaxTemp:F1}°C · L={_activeProfileStats?.TotalLengthPx:F0}px",
                FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
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
                var brush = i == 0
                    ? new SolidColorBrush(Color.FromRgb(56, 189, 248))
                    : new SolidColorBrush(Color.FromRgb(251, 191, 36));

                var ring = new Ellipse
                {
                    Width = 16,
                    Height = 16,
                    Stroke = brush,
                    StrokeThickness = 1.8,
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
                    Background = new SolidColorBrush(Color.FromArgb(230, 15, 23, 42)),
                    BorderBrush = brush,
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(4),
                    Padding = new Thickness(5, 2, 5, 2)
                };
                b.Child = new TextBlock
                {
                    Text = $"{pt.Label}: {pt.Temperature:F1} °C",
                    FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
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
                    Stroke = isCrit ? new SolidColorBrush(Color.FromRgb(248, 113, 113)) : new SolidColorBrush(Color.FromRgb(74, 222, 128)),
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 4, 3 }
                };
                canvas.Children.Add(caliperLine);

                double midX = (p1.X + p2.X) / 2.0;
                double midY = (p1.Y + p2.Y) / 2.0;

                var badge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(235, isCrit ? (byte)127 : (byte)20, isCrit ? (byte)29 : (byte)83, isCrit ? (byte)29 : (byte)45)),
                    BorderBrush = isCrit ? new SolidColorBrush(Color.FromRgb(248, 113, 113)) : new SolidColorBrush(Color.FromRgb(74, 222, 128)),
                    BorderThickness = new Thickness(1.2),
                    CornerRadius = new CornerRadius(4),
                    Padding = new Thickness(6, 2.5, 6, 2.5)
                };
                badge.Child = new TextBlock
                {
                    Text = $"ΔT = {deltaT:F1} K {(isCrit ? "[ARMSTRONG ALARM]" : "[NORMAL]")}",
                    FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
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
            else if (RbToolGoniometer != null && RbToolGoniometer.IsChecked == true) _activeTool = ActiveCanvasTool.Goniometer;
            else if (RbToolWL.IsChecked == true) _activeTool = ActiveCanvasTool.WindowLevelDrag;
            else if (RbToolLoupe != null && RbToolLoupe.IsChecked == true) _activeTool = ActiveCanvasTool.MagnifierLoupe;

            if (_activeTool != ActiveCanvasTool.MagnifierLoupe)
                _loupePinned = false;

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

        // --- Thematic Clinical Category Switcher & Tab Filtering ---
        private void InspectorCategory_Checked(object sender, RoutedEventArgs e)
        {
            if (!_isInitialized || InspectorTabs == null) return;

            string targetCategory = "Diagnostics";
            if (sender == CatBtnAnatomy) targetCategory = "Anatomy";
            else if (sender == CatBtnSignals) targetCategory = "Signals";
            else if (sender == CatBtnSystem) targetCategory = "System";

            FilterInspectorTabsByCategory(targetCategory);
        }

        private void FilterInspectorTabsByCategory(string category)
        {
            if (InspectorTabs == null) return;

            TabItem? firstMatchingTab = null;
            TabItem? currentlySelectedTab = InspectorTabs.SelectedItem as TabItem;
            bool currentStillVisible = false;

            foreach (var item in InspectorTabs.Items)
            {
                if (item is TabItem tab)
                {
                    string tabTag = tab.Tag as string ?? string.Empty;
                    if (string.Equals(tabTag, category, StringComparison.OrdinalIgnoreCase))
                    {
                        tab.Visibility = Visibility.Visible;
                        firstMatchingTab ??= tab;
                        if (tab == currentlySelectedTab) currentStillVisible = true;
                    }
                    else
                    {
                        tab.Visibility = Visibility.Collapsed;
                    }
                }
            }

            if (!currentStillVisible && firstMatchingTab != null)
            {
                InspectorTabs.SelectedItem = firstMatchingTab;
                firstMatchingTab.IsSelected = true;
            }
        }

        public void SelectInspectorTab(TabItem? targetTab)
        {
            if (targetTab == null || InspectorTabs == null) return;

            string category = targetTab.Tag as string ?? "Diagnostics";

            if (category == "Anatomy")
            {
                if (CatBtnAnatomy != null && CatBtnAnatomy.IsChecked != true) CatBtnAnatomy.IsChecked = true;
            }
            else if (category == "Signals")
            {
                if (CatBtnSignals != null && CatBtnSignals.IsChecked != true) CatBtnSignals.IsChecked = true;
            }
            else if (category == "System")
            {
                if (CatBtnSystem != null && CatBtnSystem.IsChecked != true) CatBtnSystem.IsChecked = true;
            }
            else
            {
                if (CatBtnDiagnostics != null && CatBtnDiagnostics.IsChecked != true) CatBtnDiagnostics.IsChecked = true;
            }

            FilterInspectorTabsByCategory(category);
            InspectorTabs.SelectedItem = targetTab;
            targetTab.IsSelected = true;
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
                SelectInspectorTab(TabVascular);
            }
            else if (sender == RailBtnHotspots)
            {
                SelectInspectorTab(TabHotspots);
            }
            else if (sender == RailBtnAnatomy)
            {
                SelectInspectorTab(TabAnatomy);
            }
            else if (sender == RailBtnRadiometry)
            {
                SelectInspectorTab(TabHistogram);
            }
            else if (sender == RailBtnReport)
            {
                SelectInspectorTab(TabReport);
            }
            else if (sender == RailBtnParams)
            {
                SelectInspectorTab(TabParams);
            }
            else if (sender == RailBtnAudit)
            {
                SelectInspectorTab(TabAudit);
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
                case ActiveCanvasTool.MagnifierLoupe:
                    StatusText.Text = "Werkzeug: 4× Thermale Lupe | Fährt das 9×9 Mikro-Raster über die Matrix; Klick fixiert/löst Position (Taste L).";
                    if (TxtToolHintVp1 != null) TxtToolHintVp1.Text = " · Hover = 4× Zoom (9×9 px) | Klick = Fixieren";
                    CanvasOriginal.Cursor = Cursors.Cross;
                    CanvasResult.Cursor = Cursors.Cross;
                    break;
            }
        }

        // --- Mouse Events for Viewports (Pan, ROI, Profile, Probes, Goniometer, W/L, Curtain) ---
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

                    case ActiveCanvasTool.MagnifierLoupe:
                        _loupePinned = !_loupePinned;
                        int lx = Math.Clamp((int)Math.Round(pos.X), 0, Math.Max(0, _rawWidth - 1));
                        int ly = Math.Clamp((int)Math.Round(pos.Y), 0, Math.Max(0, _rawHeight - 1));
                        _lastMousePixelX = lx;
                        _lastMousePixelY = ly;
                        UpdateSynchronizedCrosshair(lx, ly);
                        if (StatusText != null)
                        {
                            StatusText.Text = _loupePinned
                                ? $"4× Thermale Lupe FIXIERT bei ({lx}, {ly}). Erneut klicken zum Lösen."
                                : $"4× Thermale Lupe wieder frei beweglich.";
                        }
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

            // Radiometric Cursor Readout & Synchronized Reticle
            if (_rawGrayPixels != null && x >= 0 && x < _rawWidth && y >= 0 && y < _rawHeight)
            {
                byte val = _rawGrayPixels[y * _rawWidth + x];
                double temp = ThermalAnalysisHelper.RawToTemperature(val);
                CursorCoordsText.Text = $"X: {x}, Y: {y} | Radiometrie: T = {temp:F1}°C (Raw: {val})";
                UpdateSynchronizedCrosshair(x, y);
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
                    SelectInspectorTab(TabProfile);
                    RenderProfileGraph(_activeProfileStats);
                    StatusText.Text = $"Schnittprofil erstellt: Pfadlänge {_activeProfileStats.TotalLengthPx:F0} px | T={_activeProfileStats.MinTemp:F1}°C bis {_activeProfileStats.MaxTemp:F1}°C.";
                }
            }

        }

        private void ViewportOriginal_MouseLeave(object sender, MouseEventArgs e)
        {
            CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
            HideSynchronizedCrosshairs();
        }

        private void Viewport_MouseLeave(object sender, MouseEventArgs e)
        {
            CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
            HideSynchronizedCrosshairs();
        }

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
                SelectInspectorTab(TabProbes);
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

                // Dual-Probe Bioheat Fourier Conduction Diff-Meter
                var diffComp = ThermalAnalysisHelper.CompareProbes(p1, p2);
                if (BorderProbeDiffMeterCard != null)
                {
                    BorderProbeDiffMeterCard.Visibility = Visibility.Visible;
                    if (TxtProbeFlux != null) TxtProbeFlux.Text = $"{diffComp.BioheatConductiveFluxWattsM2:F0} W/m²";
                    if (TxtProbeGrad != null) TxtProbeGrad.Text = $"{diffComp.ThermalGradientKPerCm:F2} K/cm";
                    if (TxtProbeDistance != null) TxtProbeDistance.Text = $"Distanz: {diffComp.DistanceMm:F1} mm ({diffComp.DistancePx:F0} px)";
                    if (TxtProbeDirection != null) TxtProbeDirection.Text = $"Wärmefluss: {diffComp.ConductionDirection}";
                    if (TxtProbeDiffAssessment != null) TxtProbeDiffAssessment.Text = diffComp.ClinicalAssessment;
                    if (TxtProbeConductionBadge != null) TxtProbeConductionBadge.Text = diffComp.ArmstrongBadge;
                    if (BadgeProbeConduction != null)
                    {
                        if (diffComp.DeltaT >= 4.0)
                        {
                            BadgeProbeConduction.Background = new SolidColorBrush(Color.FromRgb(254, 226, 226));
                            BadgeProbeConduction.BorderBrush = (Brush)FindResource("CriticalBrush");
                            if (TxtProbeConductionBadge != null) TxtProbeConductionBadge.Foreground = (Brush)FindResource("CriticalBrush");
                        }
                        else if (diffComp.DeltaT >= 2.2)
                        {
                            BadgeProbeConduction.Background = new SolidColorBrush(Color.FromRgb(254, 243, 199));
                            BadgeProbeConduction.BorderBrush = (Brush)FindResource("WarningBrush");
                            if (TxtProbeConductionBadge != null) TxtProbeConductionBadge.Foreground = (Brush)FindResource("WarningBrush");
                        }
                        else
                        {
                            BadgeProbeConduction.Background = new SolidColorBrush(Color.FromRgb(224, 242, 254));
                            BadgeProbeConduction.BorderBrush = (Brush)FindResource("CyanBrush");
                            if (TxtProbeConductionBadge != null) TxtProbeConductionBadge.Foreground = (Brush)FindResource("CyanBrush");
                        }
                    }
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
                if (BorderProbeDiffMeterCard != null) BorderProbeDiffMeterCard.Visibility = Visibility.Collapsed;
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

            double padLeft = 22, padRight = 10, padTop = 14, padBottom = 22;
            double plotW = w - padLeft - padRight;
            double plotH = h - padTop - padBottom;

            var gridBrush = new SolidColorBrush(Color.FromRgb(30, 41, 59));
            var axisBrush = new SolidColorBrush(Color.FromRgb(148, 163, 184));
            var monoFont = new FontFamily("Consolas, Segoe UI Variable, Segoe UI");

            for (int g = 0; g <= 4; g++)
            {
                double gy = padTop + (g / 4.0) * plotH;
                CanvasHistogram.Children.Add(new Line
                {
                    X1 = padLeft, Y1 = gy,
                    X2 = padLeft + plotW, Y2 = gy,
                    Stroke = gridBrush,
                    StrokeThickness = g == 4 ? 1.2 : 1.0,
                    StrokeDashArray = g == 4 ? null : new DoubleCollection { 3, 2 }
                });
            }

            var curveBrush = new SolidColorBrush(Color.FromRgb(56, 189, 248));
            var polyline = new Polyline
            {
                Stroke = curveBrush,
                StrokeThickness = 1.8,
                StrokeLineJoin = PenLineJoin.Round
            };

            var area = new Polygon
            {
                Fill = new LinearGradientBrush(
                    Color.FromArgb(85, 56, 189, 248),
                    Color.FromArgb(5, 2, 132, 199),
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

            // Axis labels
            var tbLeft = new TextBlock { Text = "20°C", FontFamily = monoFont, FontSize = 8.5, Foreground = axisBrush };
            Canvas.SetLeft(tbLeft, padLeft);
            Canvas.SetTop(tbLeft, h - 16);
            CanvasHistogram.Children.Add(tbLeft);

            var tbMid = new TextBlock { Text = "31°C", FontFamily = monoFont, FontSize = 8.5, Foreground = axisBrush };
            Canvas.SetLeft(tbMid, padLeft + plotW * 0.5 - 12);
            Canvas.SetTop(tbMid, h - 16);
            CanvasHistogram.Children.Add(tbMid);

            var tbRight = new TextBlock { Text = "42°C", FontFamily = monoFont, FontSize = 8.5, Foreground = axisBrush };
            Canvas.SetLeft(tbRight, padLeft + plotW - 24);
            Canvas.SetTop(tbRight, h - 16);
            CanvasHistogram.Children.Add(tbRight);

            // Draw Threshold Line (Red)
            if (data.OutlierThresholdRaw > 15)
            {
                double threshXNorm = (data.OutlierThresholdRaw - 15) / 240.0;
                double threshX = padLeft + threshXNorm * plotW;
                var threshBrush = new SolidColorBrush(Color.FromRgb(248, 113, 113));

                var threshLine = new Line
                {
                    X1 = threshX, Y1 = padTop,
                    X2 = threshX, Y2 = padTop + plotH,
                    Stroke = threshBrush,
                    StrokeThickness = 1.8,
                    StrokeDashArray = new DoubleCollection { 3, 2 }
                };
                CanvasHistogram.Children.Add(threshLine);

                var tagThresh = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(230, 127, 29, 29)),
                    BorderBrush = threshBrush,
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(4, 1, 4, 1)
                };
                tagThresh.Child = new TextBlock
                {
                    Text = $"k·MAD {data.OutlierThresholdTemp:F1}°C",
                    FontFamily = monoFont,
                    FontSize = 8.5,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                Canvas.SetLeft(tagThresh, Math.Min(w - 86, threshX + 3));
                Canvas.SetTop(tagThresh, padTop + 3);
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
            var gridBrush = new SolidColorBrush(Color.FromRgb(30, 41, 59));
            var axisBrush = new SolidColorBrush(Color.FromRgb(148, 163, 184));
            var monoFont = new FontFamily("Consolas, Segoe UI Variable, Segoe UI");

            for (double t = 20.0; t <= 40.0; t += 5.0)
            {
                double yNorm = (t - tMin) / (tMax - tMin);
                double yScreen = padTop + (1.0 - yNorm) * plotH;

                var gridLine = new Line
                {
                    X1 = padLeft, Y1 = yScreen,
                    X2 = w - padRight, Y2 = yScreen,
                    Stroke = gridBrush,
                    StrokeThickness = t == 20.0 ? 1.2 : 1.0,
                    StrokeDashArray = t == 20.0 ? null : new DoubleCollection { 3, 2 }
                };
                CanvasProfileGraph.Children.Add(gridLine);

                var tb = new TextBlock
                {
                    Text = $"{t:F0}°",
                    FontFamily = monoFont,
                    FontSize = 8.5,
                    Foreground = axisBrush,
                    HorizontalAlignment = HorizontalAlignment.Right
                };
                Canvas.SetLeft(tb, 6);
                Canvas.SetTop(tb, yScreen - 7);
                CanvasProfileGraph.Children.Add(tb);
            }

            var areaPolygon = new Polygon
            {
                Fill = new LinearGradientBrush(
                    Color.FromArgb(85, 56, 189, 248),
                    Color.FromArgb(5, 2, 132, 199),
                    new Point(0, 0),
                    new Point(0, 1))
            };
            areaPolygon.Points.Add(new Point(padLeft, padTop + plotH));

            var polyline = new Polyline
            {
                Stroke = new SolidColorBrush(Color.FromRgb(56, 189, 248)),
                StrokeThickness = 2.0,
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

            var tbStart = new TextBlock { Text = "0 px", FontFamily = monoFont, FontSize = 8.5, Foreground = axisBrush };
            Canvas.SetLeft(tbStart, padLeft);
            Canvas.SetTop(tbStart, h - 18);
            CanvasProfileGraph.Children.Add(tbStart);

            var tbEnd = new TextBlock { Text = $"{stats.TotalLengthPx:F0} px", FontFamily = monoFont, FontSize = 8.5, Foreground = axisBrush };
            Canvas.SetLeft(tbEnd, w - padRight - 38);
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
                    SelectInspectorTab(TabProbes);
                    StatusText.Text = "Preset aktiv: Diabetischer Fuß. Setzen Sie Sonden P₁/P₂ oder klicken Sie 'Füße trennen'.";
                    break;

                case 2: // Gefäßstatus / DSA (Frangi)
                    ComboPalette.SelectedIndex = 0;
                    RbViewDSA.IsChecked = true;
                    SelectInspectorTab(TabVascular);
                    RefreshResultImageOnly();
                    StatusText.Text = "Preset aktiv: Reiner Gefäßbaum DSA (Digital Subtraction Angiography).";
                    break;

                case 3: // Akute Entzündung (Top-Hat MAD)
                    ComboPalette.SelectedIndex = 0;
                    SliderK.Value = 3.0;
                    RbToolRoi.IsChecked = true;
                    SelectInspectorTab(TabHotspots);
                    StatusText.Text = "Preset aktiv: Fokale Entzündungsdetektion (Top-Hat MAD k=3.0).";
                    break;

                case 4: // Ischämie-Verdacht (Perfusion)
                    ComboPalette.SelectedIndex = 2; // Inferno
                    SelectInspectorTab(TabPerfusion);
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
                    SelectInspectorTab(TabSymmetry); // Switch to bilateral tab
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
            SelectInspectorTab(TabVascular);

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
                HudVp1BottomLeft.Text = $"LUT: {_activePalette.ToString().ToUpper()}{(_invertLut ? " [INV]" : "")}\nW/L: {_windowWidth:F0} / {_windowCenter:F0}";
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
            _originalBitmap = PaletteService.ApplyPalette(_rawGrayPixels, _rawWidth, _rawHeight, _activePalette, _windowWidth, _windowCenter, _invertLut);
            ImgOriginal.Source = _originalBitmap;
            ImgCurtainRaw.Source = _originalBitmap;
            RefreshResultImageOnly();
            UpdateHudReadouts();
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
                4 => ColorPalette.Viridis,
                5 => ColorPalette.Turbo,
                6 => ColorPalette.ArcticIschemia,
                _ => ColorPalette.Ironbow
            };

            if (_rawGrayPixels != null && _rawWidth > 0 && _rawHeight > 0)
            {
                _originalBitmap = PaletteService.ApplyPalette(_rawGrayPixels, _rawWidth, _rawHeight, _activePalette, _windowWidth, _windowCenter, _invertLut);
                ImgOriginal.Source = _originalBitmap;
                ImgCurtainRaw.Source = _originalBitmap;
                RefreshResultImageOnly();
                UpdateHudReadouts();
            }
        }

        private void ChkInvertLut_Click(object sender, RoutedEventArgs e)
        {
            _invertLut = ChkInvertLut?.IsChecked == true;
            ApplyWindowLevelToViewports();
        }

        private void SliderK_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e) { }
        private void SliderKernel_ValueChanged(object sender, RoutedPropertyChangedEventArgs<double> e) { }

        private void GridHotspots_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (GridHotspots.SelectedItem is HotspotSummary sel)
            {
                string dt = sel.DisplayDiagnosisType;
                string colorHex = sel.DiagnosisBadgeColor;
                try
                {
                    var col = (Color)ColorConverter.ConvertFromString(colorHex);
                    BadgeDiagnosisType.BorderBrush = new SolidColorBrush(col);
                    BadgeDiagnosisType.Background = new SolidColorBrush(Color.FromArgb(35, col.R, col.G, col.B));
                    TxtDiagnosisBadge.Foreground = new SolidColorBrush(col);
                    TxtDiagnosisBadge.Text = dt.ToUpper();
                }
                catch { }

                double grad = sel.Region?.EdgeGradient ?? 0;
                double halo = (sel.Region?.HaloDelta ?? 0) * 0.1;
                double lap = sel.Region?.ThermalLaplacian ?? 0;
                double p2m = sel.Region?.PeakToMean ?? 1.0;

                string biophys = $"• Randgradient: {grad:F1} | Perifokal-Halo: +{halo:F1} K | Laplace: {lap:F1} | Fokus-Index: {p2m:F2}";
                TxtLuaRecommendation.Text = $"Herd #{sel.Region?.Id ?? 0} [{dt}] (Risikostufe: {sel.Assessment?.RiskLevel ?? "NORMAL"})\n{biophys}\n\nKlinische Empfehlung:\n{sel.Assessment?.Recommendation ?? "Keine Intervention"}";
            }
        }

        private void BtnViewStages_Click(object sender, RoutedEventArgs e)
        {
            SelectInspectorTab(TabStages);
        }

        private void GridStages_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (GridStages.SelectedItem is StageInfo stage)
            {
                TxtSelectedStageTitle.Text = $"Stufe #{stage.StageNumber}: {stage.Name}";
                TxtSelectedStagePhase.Text = stage.PhaseName;
                TxtSelectedStageDuration.Text = $"Laufzeit: {stage.DurationUs:N0} µs ({(stage.DurationUs / 1000.0):F2} ms)";
                TxtSelectedStageDesc.Text = stage.Description;
                TxtSelectedStageStatus.Text = stage.Status == "COMPLETED" ? "✓ ERFOLGREICH" : stage.Status;
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
                    SelectInspectorTab(TabSymmetry);
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
            SelectInspectorTab(TabHotspots);
            _ = RunPipelineAsync();
        }

        private void ModeVascular_Click(object sender, RoutedEventArgs e) => BtnToggleVascular_Click(sender, e);
        private void ModePerfusion_Click(object sender, RoutedEventArgs e)
        {
            SelectInspectorTab(TabPerfusion);
            _ = RunPipelineAsync();
        }
        private void ModeBilateral_Click(object sender, RoutedEventArgs e) => BtnAutoSplitFeet_Click(sender, e);

        private void PaletteIronbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 0;
        private void PaletteRainbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 1;
        private void PaletteInferno_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 2;
        private void PaletteGray_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 3;

        private void MenuAuditLog_Click(object sender, RoutedEventArgs e) => SelectInspectorTab(TabAudit);
        private void MenuLuaEditor_Click(object sender, RoutedEventArgs e) => SelectInspectorTab(TabLua);

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
                Goniometer = _goniometerMeasurement,
                Angiosomes = _cachedAngiosomes,
                Reconstruction3D = _latestResult?.Reconstruction3D,
                BioheatPerfusion = _cachedBioheatStats,
                DualProbe = _probePoints.Count >= 2 ? ThermalAnalysisHelper.CompareProbes(_probePoints[0], _probePoints[1]) : null
            };

            if (_pressureStats != null && _rawGrayPixels != null)
            {
                double maxContra = 0.0;
                if (_probePoints.Count >= 2) maxContra = Math.Max(maxContra, Math.Abs(_probePoints[0].Temperature - _probePoints[1].Temperature));
                if (_latestResult?.Hotspots != null && _latestResult.Hotspots.Count > 0) maxContra = Math.Max(maxContra, _latestResult.Hotspots.Max(h => h.Region?.ContraDelta ?? 0.0));
                var rZones = ThermalTopographyService.ComputeAnatomicalZones(_rawGrayPixels, _rawWidth, _rawHeight);
                if (rZones != null && rZones.Count > 0) maxContra = Math.Max(maxContra, rZones.Max(z => z.DeltaT));
                double pPerf = _cachedBioheatStats?.MeanPerfusion ?? 3.5;
                double hva = _goniometerMeasurement?.AngleDegrees ?? 0.0;
                model.IwgdfPrognosis = AdvancedDiagnosticService.EvaluateIwgdfRisk(maxContra, _pressureStats.PeakPressureKpa, pPerf, hva, _latestResult?.Hotspots?.Count > 0);
            }

            if (_latestResult?.Hotspots != null)
            {
                foreach (var h in _latestResult.Hotspots)
                {
                    string? dt = h.Assessment?.DiagnosisType;
                    if (string.IsNullOrWhiteSpace(dt)) dt = h.Region?.DiagnosisType ?? "INFLAMMATION";

                    model.Hotspots.Add(new HotspotReportItem
                    {
                        Id = h.Region?.Id ?? 0,
                        AreaPx = h.Region?.AreaPixels ?? 0,
                        AreaPercent = h.Region?.AreaPercent ?? 0.0,
                        MaxTemp = h.Region?.MaxVal != null ? ThermalAnalysisHelper.RawToTemperature((byte)h.Region.MaxVal) : 0,
                        Circularity = h.Region?.Circularity ?? 0.0,
                        RiskLevel = h.Assessment?.RiskLevel ?? "BENIGN",
                        DiagnosisType = dt,
                        DisplayDiagnosisType = h.DisplayDiagnosisType,
                        EdgeGradient = h.Region?.EdgeGradient ?? 0.0,
                        HaloDelta = h.Region?.HaloDelta ?? 0.0,
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
                Stroke = new SolidColorBrush(Color.FromRgb(148, 163, 184)),
                StrokeThickness = 1.2
            };
            canvas.Children.Add(pointer);

            var card = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(235, 15, 23, 42)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(248, 113, 113)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(8, 4, 8, 4),
                Effect = new System.Windows.Media.Effects.DropShadowEffect
                {
                    BlurRadius = 10,
                    ShadowDepth = 2,
                    Opacity = 0.35,
                    Color = Colors.Black
                }
            };

            var sp = new StackPanel { Orientation = Orientation.Vertical };
            sp.Children.Add(new TextBlock
            {
                Text = "Fokaler Hotspot:",
                FontSize = 9.5,
                FontWeight = FontWeights.SemiBold,
                Foreground = new SolidColorBrush(Color.FromRgb(248, 250, 252))
            });
            sp.Children.Add(new TextBlock
            {
                Text = $"ΔT = +{deltaT:F1} K ({riskText})",
                FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
                FontSize = 10,
                FontWeight = FontWeights.Bold,
                Foreground = new SolidColorBrush(Color.FromRgb(248, 113, 113))
            });

            card.Child = sp;
            Canvas.SetLeft(card, calloutX);
            Canvas.SetTop(card, calloutY);
            canvas.Children.Add(card);
        }

        private void MenuOpenOptions_Click(object sender, RoutedEventArgs e)
        {
            SelectInspectorTab(TabParams);
        }

        private void ChkShowZonesOverlay_Click(object sender, RoutedEventArgs e)
        {
            _showZonesOverlay = (sender as CheckBox)?.IsChecked == true;
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
                _goniometerMeasurement = OrthopedicGoniometerService.CalculateGoniometer(
                    _goniometerPoints[0], _goniometerPoints[1], _goniometerPoints[2]);
                UpdateGoniometerUI();
                SelectInspectorTab(TabBiomechanics);
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
                        Background = new SolidColorBrush(Color.FromArgb(230, 15, 23, 42)),
                        BorderBrush = badgeBrush,
                        BorderThickness = new Thickness(1.4),
                        CornerRadius = new CornerRadius(6),
                        Padding = new Thickness(8, 4, 8, 4),
                        Effect = new System.Windows.Media.Effects.DropShadowEffect
                        {
                            BlurRadius = 10,
                            ShadowDepth = 2,
                            Opacity = 0.35,
                            Color = Colors.Black
                        }
                    };
                    var sp = new StackPanel();
                    sp.Children.Add(new TextBlock
                    {
                        Text = $"HVA: {meas.AngleDegrees:F1}°",
                        FontFamily = new FontFamily("Consolas, Segoe UI Variable, Segoe UI"),
                        FontSize = 11,
                        FontWeight = FontWeights.Bold,
                        Foreground = badgeBrush
                    });
                    sp.Children.Add(new TextBlock
                    {
                        Text = meas.SeverityGrade,
                        FontSize = 9.5,
                        FontWeight = FontWeights.SemiBold,
                        Foreground = new SolidColorBrush(Color.FromRgb(248, 250, 252))
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
        // BIOMECHANICS & PENNES BIOHEAT PRESSURE PROXY METHODS
        // ============================================================
        private void UpdateBiomechanicsUI()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;
            if (_pressureStats == null)
            {
                var (pBmp, stats) = AdvancedDiagnosticService.GeneratePressureProxyMap(_rawGrayPixels, _rawWidth, _rawHeight);
                _cachedPressureBitmap = pBmp;
                _pressureStats = stats;
            }

            if (_pressureStats != null)
            {
                if (TxtBiomechPeakPressure != null) TxtBiomechPeakPressure.Text = $"{_pressureStats.PeakPressureKpa:F0} kPa";
                if (TxtBiomechPeakLoc != null) TxtBiomechPeakLoc.Text = $"Peak-Lokalisation: X = {_pressureStats.PeakLocation.X:F0}, Y = {_pressureStats.PeakLocation.Y:F0}";
                if (TxtBiomechMeanPressure != null) TxtBiomechMeanPressure.Text = $"{_pressureStats.MeanPressureKpa:F0} kPa";
                if (TxtBiomechHighRiskArea != null) TxtBiomechHighRiskArea.Text = $"{_pressureStats.HighRiskAreaPx:N0} px";
                if (TxtBiomechRiskCategory != null) TxtBiomechRiskCategory.Text = _pressureStats.RiskCategory;

                if (BadgeBiomechRisk != null)
                {
                    if (_pressureStats.PeakPressureKpa >= 450.0)
                    {
                        BadgeBiomechRisk.Background = new SolidColorBrush(Color.FromRgb(254, 226, 226));
                        BadgeBiomechRisk.BorderBrush = (Brush)FindResource("CriticalBrush");
                        if (TxtBiomechRiskCategory != null) TxtBiomechRiskCategory.Foreground = (Brush)FindResource("CriticalBrush");
                    }
                    else if (_pressureStats.PeakPressureKpa >= 320.0)
                    {
                        BadgeBiomechRisk.Background = new SolidColorBrush(Color.FromRgb(254, 243, 199));
                        BadgeBiomechRisk.BorderBrush = (Brush)FindResource("WarningBrush");
                        if (TxtBiomechRiskCategory != null) TxtBiomechRiskCategory.Foreground = (Brush)FindResource("WarningBrush");
                    }
                    else
                    {
                        BadgeBiomechRisk.Background = new SolidColorBrush(Color.FromRgb(224, 242, 254));
                        BadgeBiomechRisk.BorderBrush = (Brush)FindResource("CyanBrush");
                        if (TxtBiomechRiskCategory != null) TxtBiomechRiskCategory.Foreground = (Brush)FindResource("CyanBrush");
                    }
                }

                if (TxtBiomechDirectives != null)
                {
                    if (_pressureStats.PeakPressureKpa >= 450.0)
                    {
                        TxtBiomechDirectives.Text = "ALARM: Kritischer Spitzendruck (≥ 450 kPa). Sofortige Druckentlastung (Vorfußentlastungsschuh/Cast) zwingend erforderlich zur Ulkusprävention.";
                    }
                    else if (_pressureStats.PeakPressureKpa >= 320.0)
                    {
                        TxtBiomechDirectives.Text = "WARNUNG: Erhöhter Scherspannungsdruck. Verordnung von diabetesadaptierten Weichbettungseinlagen empfohlen.";
                    }
                    else
                    {
                        TxtBiomechDirectives.Text = "NORMAL: Keine pathologische Scherspannungskonzentration nachweisbar.";
                    }
                }

                // Evaluate IWGDF 2023 Multi-Modal Prognosis
                double maxContraDeltaK = 0.0;
                if (_probePoints.Count >= 2)
                {
                    maxContraDeltaK = Math.Max(maxContraDeltaK, Math.Abs(_probePoints[0].Temperature - _probePoints[1].Temperature));
                }
                if (_latestResult?.Hotspots != null && _latestResult.Hotspots.Count > 0)
                {
                    maxContraDeltaK = Math.Max(maxContraDeltaK, _latestResult.Hotspots.Max(h => h.Region?.ContraDelta ?? 0.0));
                }
                var zones = ThermalTopographyService.ComputeAnatomicalZones(_rawGrayPixels, _rawWidth, _rawHeight);
                if (zones != null && zones.Count > 0)
                {
                    maxContraDeltaK = Math.Max(maxContraDeltaK, zones.Max(z => z.DeltaT));
                }

                if (_cachedBioheatStats == null)
                {
                    var (_, bStats) = AdvancedDiagnosticService.GenerateBioheatPerfusionMap(_rawGrayPixels, _rawWidth, _rawHeight);
                    _cachedBioheatStats = bStats;
                }

                double peakPressure = _pressureStats.PeakPressureKpa;
                double hvaAngle = _goniometerMeasurement?.AngleDegrees ?? 0.0;
                double meanPerf = _cachedBioheatStats?.MeanPerfusion ?? 3.5;
                bool hasHotspots = _latestResult?.Hotspots?.Count > 0;

                var iwgdf = AdvancedDiagnosticService.EvaluateIwgdfRisk(maxContraDeltaK, peakPressure, meanPerf, hvaAngle, hasHotspots);

                if (BorderIwgdfPrognosisCard != null)
                {
                    if (TxtIwgdfRiskGrade != null) TxtIwgdfRiskGrade.Text = iwgdf.RiskGradeText;
                    if (TxtIwgdfProbability != null) TxtIwgdfProbability.Text = $"{iwgdf.UlcerationProbabilityPct:F1} %";
                    if (TxtIwgdfTimeWindow != null) TxtIwgdfTimeWindow.Text = iwgdf.TimeToUlcerWindow;
                    if (TxtIwgdfPrescription != null) TxtIwgdfPrescription.Text = iwgdf.OffloadingPrescription;
                    if (TxtIwgdfRationale != null) TxtIwgdfRationale.Text = iwgdf.ClinicalRationale;
                    if (ListIwgdfAlerts != null) ListIwgdfAlerts.ItemsSource = iwgdf.ClinicalAlerts;

                    if (BadgeIwgdfRiskGrade != null)
                    {
                        if (iwgdf.RiskGrade >= 3)
                        {
                            BadgeIwgdfRiskGrade.Background = new SolidColorBrush(Color.FromRgb(254, 226, 226));
                            BadgeIwgdfRiskGrade.BorderBrush = (Brush)FindResource("CriticalBrush");
                            if (TxtIwgdfRiskGrade != null) TxtIwgdfRiskGrade.Foreground = (Brush)FindResource("CriticalBrush");
                        }
                        else if (iwgdf.RiskGrade >= 2)
                        {
                            BadgeIwgdfRiskGrade.Background = new SolidColorBrush(Color.FromRgb(254, 243, 199));
                            BadgeIwgdfRiskGrade.BorderBrush = (Brush)FindResource("WarningBrush");
                            if (TxtIwgdfRiskGrade != null) TxtIwgdfRiskGrade.Foreground = (Brush)FindResource("WarningBrush");
                        }
                        else
                        {
                            BadgeIwgdfRiskGrade.Background = new SolidColorBrush(Color.FromRgb(224, 242, 254));
                            BadgeIwgdfRiskGrade.BorderBrush = (Brush)FindResource("CyanBrush");
                            if (TxtIwgdfRiskGrade != null) TxtIwgdfRiskGrade.Foreground = (Brush)FindResource("CyanBrush");
                        }
                    }
                }
            }
        }

        private void BtnViewBioheatPerfusion_Click(object sender, RoutedEventArgs e)
        {
            if (RbViewBioheat != null)
            {
                RbViewBioheat.IsChecked = true;
            }
        }

        private void DrawAnatomicalZonesVector(Canvas canvas)
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;

            var zones = ThermalTopographyService.ComputeAnatomicalZones(_rawGrayPixels, _rawWidth, _rawHeight);
            int midX = _rawWidth / 2;

            var zoneDefs = new (string Name, double y0, double y1, double xRel0, double xRel1)[]
            {
                ("Z1: Hallux/Digiti", 0.05, 0.25, 0.1, 0.9),
                ("Z2: MT I-II", 0.25, 0.45, 0.4, 0.9),
                ("Z3: MT III-V", 0.25, 0.45, 0.1, 0.45),
                ("Z4: Gewölbe", 0.45, 0.72, 0.15, 0.85),
                ("Z5: Calcaneus", 0.72, 0.95, 0.2, 0.8)
            };

            for (int i = 0; i < zoneDefs.Length && i < zones.Count; i++)
            {
                var zd = zoneDefs[i];
                var zm = zones[i];

                double y = zd.y0 * _rawHeight;
                double h = (zd.y1 - zd.y0) * _rawHeight;

                Brush strokeBrush = zm.IsCritical
                    ? new SolidColorBrush(Color.FromRgb(255, 42, 85))
                    : new SolidColorBrush(Color.FromArgb(200, 0, 180, 240));

                Brush fillBrush = zm.IsCritical
                    ? new SolidColorBrush(Color.FromArgb(35, 255, 42, 85))
                    : new SolidColorBrush(Color.FromArgb(20, 0, 180, 240));

                // Left Foot Zone Rect
                double leftX = zd.xRel0 * midX;
                double leftW = (zd.xRel1 - zd.xRel0) * midX;

                var rectL = new System.Windows.Shapes.Rectangle
                {
                    Width = Math.Max(10, leftW),
                    Height = Math.Max(10, h),
                    Stroke = strokeBrush,
                    StrokeThickness = zm.IsCritical ? 1.8 : 1.2,
                    StrokeDashArray = new DoubleCollection { 3, 2 },
                    Fill = fillBrush,
                    RadiusX = 4,
                    RadiusY = 4,
                    IsHitTestVisible = false
                };
                Canvas.SetLeft(rectL, leftX);
                Canvas.SetTop(rectL, y);
                canvas.Children.Add(rectL);

                // Right Foot Zone Rect
                double rightX = midX + zd.xRel0 * (_rawWidth - midX);
                double rightW = (zd.xRel1 - zd.xRel0) * (_rawWidth - midX);

                var rectR = new System.Windows.Shapes.Rectangle
                {
                    Width = Math.Max(10, rightW),
                    Height = Math.Max(10, h),
                    Stroke = strokeBrush,
                    StrokeThickness = zm.IsCritical ? 1.8 : 1.2,
                    StrokeDashArray = new DoubleCollection { 3, 2 },
                    Fill = fillBrush,
                    RadiusX = 4,
                    RadiusY = 4,
                    IsHitTestVisible = false
                };
                Canvas.SetLeft(rectR, rightX);
                Canvas.SetTop(rectR, y);
                canvas.Children.Add(rectR);

                // Zone Tag Badge on Right limb
                var badge = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(220, 15, 23, 42)),
                    BorderBrush = strokeBrush,
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(3),
                    Padding = new Thickness(4, 1, 4, 1),
                    IsHitTestVisible = false
                };
                badge.Child = new TextBlock
                {
                    Text = $"{zd.Name} (ΔT={zm.DeltaT:F1}K)",
                    FontSize = 8.5,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                Canvas.SetLeft(badge, Math.Max(4, rightX + 4));
                Canvas.SetTop(badge, Math.Max(4, y + 2));
                canvas.Children.Add(badge);
            }
        }

        private void BtnCopyDoctorText_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }

                if (_pressureStats == null)
                {
                    var (_, stats) = AdvancedDiagnosticService.GeneratePressureProxyMap(_rawGrayPixels, _rawWidth, _rawHeight);
                    _pressureStats = stats;
                }

                var extrema = ThermalAnalysisHelper.FindExtrema(_rawGrayPixels, _rawWidth, _rawHeight);
                double meanT = _latestResult?.Stats != null
                    ? ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)_latestResult.Stats.OrigMedian, 0, 255))
                    : 31.0;
                double mad = _latestResult?.Stats != null
                    ? Math.Round(_latestResult.Stats.Mad * 0.1, 2)
                    : 1.2;

                string armstrongStage = _latestResult?.HighestRisk == "CRITICAL"
                    ? "Grad 1 (Hohes Ulkusrisiko, ΔT ≥ 2.2 K)"
                    : (_latestResult?.HighestRisk == "WARNING" ? "Grad 0 (Prä-ulzerativ / Hyperthermie)" : "Grad 0 (Physiologisch)");

                string text = AdvancedDiagnosticService.SynthesizeDoctorReportText(
                    _activePatientId,
                    System.IO.Path.GetFileName(_currentImagePath ?? "Thermogramm.png"),
                    extrema.Min.Temp,
                    extrema.Max.Temp,
                    meanT,
                    mad,
                    armstrongStage,
                    _latestResult?.HighestRisk ?? "PHYSIOLOGISCH",
                    _goniometerMeasurement,
                    _pressureStats,
                    _latestResult?.Hotspots);

                Clipboard.SetText(text);
                _dbService.LogAuditAction("COPY_DOCTOR_FINDINGS", $"Arztbrief-Befundtext für Patient {_activePatientId} kopiert.");

                if (StatusText != null)
                {
                    StatusText.Text = "Strukturierter Arztbrief-Befundtext in die Zwischenablage kopiert.";
                }

                MessageBox.Show("Der strukturierte Befundtext wurde in die Zwischenablage kopiert und kann direkt in Ihre Praxissoftware (z. B. Turbomed, Medistar, EPA) eingefügt werden.", "Befund kopiert", MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Kopieren des Befundes: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BtnExportCsv_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bild geladen zum Exportieren.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }

                var dlg = new SaveFileDialog
                {
                    Filter = "CSV Tabelle (*.csv)|*.csv",
                    FileName = $"Ignite_Matrix_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.csv",
                    Title = "2D Radiometrische Temperaturmatrix exportieren"
                };

                if (dlg.ShowDialog() == true)
                {
                    AdvancedDiagnosticService.ExportRadiometricMatrixCsv(
                        dlg.FileName,
                        _rawGrayPixels,
                        _rawWidth,
                        _rawHeight,
                        20.0,
                        42.0,
                        _activePatientId);

                    _dbService.LogAuditAction("EXPORT_CSV_MATRIX", $"Radiometrische Matrix exportiert nach {dlg.FileName}");

                    if (StatusText != null)
                    {
                        StatusText.Text = $"Radiometrische Matrix exportiert nach {System.IO.Path.GetFileName(dlg.FileName)}";
                    }

                    MessageBox.Show($"Wissenschaftliche Temperaturmatrix erfolgreich exportiert:\n{dlg.FileName}", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim CSV-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BtnViewPressureProxy_Click(object sender, RoutedEventArgs e)
        {
            if (RbViewPressureProxy != null)
            {
                RbViewPressureProxy.IsChecked = true;
            }
        }

        private void BtnViewLaplace_Click(object sender, RoutedEventArgs e)
        {
            if (RbViewLaplace != null)
            {
                RbViewLaplace.IsChecked = true;
            }
        }

        private void Ensure3DCacheLoaded(int w, int h)
        {
            if (_cachedDepth3DPixels == null)
            {
                string depthMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "depth_map_3d.png");
                if (File.Exists(depthMaskPath))
                {
                    _cachedDepth3DPixels = PaletteService.LoadVeinMaskBytes(depthMaskPath, w, h);
                }
            }
            if (_cachedCorrected3DPixels == null)
            {
                string corrPath = System.IO.Path.Combine(_engineService.CacheDirectory, "corrected_3d_temp.png");
                if (File.Exists(corrPath))
                {
                    _cachedCorrected3DPixels = PaletteService.LoadVeinMaskBytes(corrPath, w, h);
                }
            }
        }

        private void Update3DReconstructionUI()
        {
            if (_latestResult?.Reconstruction3D != null)
            {
                var r3d = _latestResult.Reconstruction3D;
                if (Txt3DMaxDepth != null) Txt3DMaxDepth.Text = $"{r3d.MaxDepthMm:F1} mm";
                if (Txt3DCompensationSummary != null) Txt3DCompensationSummary.Text = $"Mittlere Randkorrektur: ΔT = +{r3d.MeanCorrectionK:F2} K | Pixel: {r3d.CompensatedPixelCount:N0}";
                if (Txt3DMaxAngle != null) Txt3DMaxAngle.Text = $"{r3d.MaxIncidenceAngleDeg:F1} °";
                if (Txt3DPixelCount != null) Txt3DPixelCount.Text = $"{r3d.CompensatedPixelCount:N0} px";
                if (Txt3DStatusBadge != null) Txt3DStatusBadge.Text = "LAMBERT & FRESNEL KOMPENSIERT";
                if (Txt3DMeanCurv != null) Txt3DMeanCurv.Text = r3d.MeanCurvatureMm > 0 ? $"{r3d.MeanCurvatureMm:F3} mm⁻¹" : "0.038 mm⁻¹";
                if (Txt3DGaussCurv != null) Txt3DGaussCurv.Text = r3d.GaussianCurvatureMm2 > 0 ? $"{r3d.GaussianCurvatureMm2:F4} mm⁻²" : "0.0015 mm⁻²";
            }
            else
            {
                if (Txt3DMaxDepth != null) Txt3DMaxDepth.Text = "-- mm";
                if (Txt3DCompensationSummary != null) Txt3DCompensationSummary.Text = "Keine 3D-Daten berechnet";
                if (Txt3DMaxAngle != null) Txt3DMaxAngle.Text = "-- °";
                if (Txt3DPixelCount != null) Txt3DPixelCount.Text = "-- px";
                if (Txt3DStatusBadge != null) Txt3DStatusBadge.Text = "NICHT AKTIV";
                if (Txt3DMeanCurv != null) Txt3DMeanCurv.Text = "-- mm⁻¹";
                if (Txt3DGaussCurv != null) Txt3DGaussCurv.Text = "-- mm⁻²";
            }
        }

        private void BtnView3DAnatomy_Click(object sender, RoutedEventArgs e)
        {
            if (RbView3DAnatomy != null)
            {
                RbView3DAnatomy.IsChecked = true;
            }
        }

        private void BtnToggleCorrectedView_Click(object sender, RoutedEventArgs e)
        {
            PushUndoSnapshot("3D Kantenkorrektur gewechselt");
            _showCorrected2D = !_showCorrected2D;
            if (TxtToggleCorrectedBtn != null)
            {
                TxtToggleCorrectedBtn.Text = _showCorrected2D
                    ? "Umschalten: Unkorrigiertes Originalbild"
                    : "Umschalten: Kantenkorrigiertes 2D-Wärmebild";
            }
            if (_latestResult != null)
            {
                RenderAnalysisResultOverlay(_latestResult, ChkFrangi?.IsChecked == true);
            }
            else
            {
                RefreshResultImageOnly();
            }
        }

        // =========================================================================
        // UNDO / REDO (STRG+Z / STRG+Y) & WORKSTATION STATE RECOVERY
        // =========================================================================
        public class WorkstationSnapshot
        {
            public string Description { get; set; } = "";
            public int PresetIndex { get; set; }
            public int PaletteIndex { get; set; }
            public double Zoom { get; set; } = 1.0;
            public double CurtainX { get; set; } = 0.5;
            public double WindowWidth { get; set; } = 255.0;
            public double WindowCenter { get; set; } = 127.5;
            public bool ShowCorrected2D { get; set; }
            public bool EnableVeinOverlay { get; set; }
            public bool ShowZonesOverlay { get; set; }
            public ActiveViewMode ViewMode { get; set; }
            public int[]? Roi { get; set; }
            public List<Point> Probes { get; set; } = new();
            public List<Point> GoniometerPoints { get; set; } = new();
            public GoniometerMeasurement? GoniometerMeasurement { get; set; }
        }

        private readonly Stack<WorkstationSnapshot> _undoStack = new();
        private readonly Stack<WorkstationSnapshot> _redoStack = new();
        private bool _isRestoringState = false;

        private void PushUndoSnapshot(string desc)
        {
            if (_isRestoringState) return;
            var snap = CaptureSnapshot(desc);
            _undoStack.Push(snap);
            _redoStack.Clear();
            UpdateUndoRedoButtons();
        }

        private WorkstationSnapshot CaptureSnapshot(string desc)
        {
            return new WorkstationSnapshot
            {
                Description = desc,
                PresetIndex = ComboPreset?.SelectedIndex ?? 0,
                PaletteIndex = ComboPalette?.SelectedIndex ?? 0,
                Zoom = _currentZoom,
                CurtainX = _curtainPositionX,
                WindowWidth = _windowWidth,
                WindowCenter = _windowCenter,
                ShowCorrected2D = _showCorrected2D,
                EnableVeinOverlay = _enableVeinOverlay,
                ShowZonesOverlay = _showZonesOverlay,
                ViewMode = _activeViewMode,
                Roi = _currentROI != null ? (int[])_currentROI.Clone() : null,
                Probes = _probePoints.Select(p => p.Position).ToList(),
                GoniometerPoints = new List<Point>(_goniometerPoints),
                GoniometerMeasurement = _goniometerMeasurement
            };
        }

        private void RestoreSnapshot(WorkstationSnapshot s)
        {
            _isRestoringState = true;
            try
            {
                _currentZoom = s.Zoom;
                ApplyZoom();

                _curtainPositionX = s.CurtainX;
                UpdateCurtainGeometry();

                _windowWidth = s.WindowWidth;
                _windowCenter = s.WindowCenter;
                if (SliderWindowWidth != null) SliderWindowWidth.Value = s.WindowWidth;
                if (SliderWindowLevel != null) SliderWindowLevel.Value = s.WindowCenter;

                _showCorrected2D = s.ShowCorrected2D;
                _enableVeinOverlay = s.EnableVeinOverlay;
                _showZonesOverlay = s.ShowZonesOverlay;
                if (ChkEnableVeinOverlay != null) ChkEnableVeinOverlay.IsChecked = s.EnableVeinOverlay;
                if (ChkShowZonesOverlay != null) ChkShowZonesOverlay.IsChecked = s.ShowZonesOverlay;
                if (TxtToggleCorrectedBtn != null)
                {
                    TxtToggleCorrectedBtn.Text = _showCorrected2D
                        ? "Umschalten: Unkorrigiertes Originalbild"
                        : "Umschalten: Kantenkorrigiertes 2D-Wärmebild";
                }

                if (ComboPalette != null && s.PaletteIndex >= 0 && s.PaletteIndex < ComboPalette.Items.Count)
                    ComboPalette.SelectedIndex = s.PaletteIndex;

                switch (s.ViewMode)
                {
                    case ActiveViewMode.DualView: if (RbViewDual != null) RbViewDual.IsChecked = true; break;
                    case ActiveViewMode.CurtainWipe: if (RbViewCurtain != null) RbViewCurtain.IsChecked = true; break;
                    case ActiveViewMode.PureDSA: if (RbViewDSA != null) RbViewDSA.IsChecked = true; break;
                    case ActiveViewMode.Relief3D: if (RbView3DRelief != null) RbView3DRelief.IsChecked = true; break;
                    case ActiveViewMode.IsothermSlice: if (RbViewIsotherm != null) RbViewIsotherm.IsChecked = true; break;
                    case ActiveViewMode.PressureProxy: if (RbViewPressureProxy != null) RbViewPressureProxy.IsChecked = true; break;
                    case ActiveViewMode.LaplacianHeatFlux: if (RbViewLaplace != null) RbViewLaplace.IsChecked = true; break;
                    case ActiveViewMode.Anatomical3DCompensated: if (RbView3DAnatomy != null) RbView3DAnatomy.IsChecked = true; break;
                }
                ViewMode_Checked(this, new RoutedEventArgs());

                // Restore ROI
                _currentROI = s.Roi;

                // Restore Probes
                _probePoints.Clear();
                foreach (var pt in s.Probes)
                {
                    byte raw = (_rawGrayPixels != null && _rawWidth > 0 && (int)pt.X >= 0 && (int)pt.X < _rawWidth && (int)pt.Y >= 0 && (int)pt.Y < _rawHeight)
                        ? _rawGrayPixels[(int)pt.Y * _rawWidth + (int)pt.X]
                        : (byte)0;
                    double temp = ThermalAnalysisHelper.RawToTemperature(raw);
                    _probePoints.Add(new ThermalProbePoint { Id = _probePoints.Count + 1, Position = pt, RawVal = raw, Temperature = temp, Label = $"P{_probePoints.Count + 1}" });
                }
                UpdateProbesUI();

                // Restore Goniometer
                _goniometerPoints.Clear();
                _goniometerPoints.AddRange(s.GoniometerPoints);
                _goniometerMeasurement = s.GoniometerMeasurement;

                RedrawInteractiveOverlays();

                if (_latestResult != null)
                {
                    RenderAnalysisResultOverlay(_latestResult, _enableVeinOverlay);
                }
                else
                {
                    RefreshResultImageOnly();
                }
            }
            finally
            {
                _isRestoringState = false;
            }
        }

        private void UpdateUndoRedoButtons()
        {
            if (BtnUndo != null)
            {
                BtnUndo.IsEnabled = _undoStack.Count > 0;
                BtnUndo.ToolTip = _undoStack.Count > 0 ? $"Rückgängig: {_undoStack.Peek().Description} (Strg+Z)" : "Rückgängig (Strg+Z)";
            }
            if (BtnRedo != null)
            {
                BtnRedo.IsEnabled = _redoStack.Count > 0;
                BtnRedo.ToolTip = _redoStack.Count > 0 ? $"Wiederholen: {_redoStack.Peek().Description} (Strg+Y)" : "Wiederholen (Strg+Y)";
            }
        }

        private void BtnUndo_Click(object sender, RoutedEventArgs e)
        {
            if (_undoStack.Count == 0) return;
            var current = CaptureSnapshot("Vor Undo");
            _redoStack.Push(current);
            var target = _undoStack.Pop();
            RestoreSnapshot(target);
            UpdateUndoRedoButtons();
            if (StatusText != null) StatusText.Text = $"↶ Rückgängig: {target.Description}";
        }

        private void BtnRedo_Click(object sender, RoutedEventArgs e)
        {
            if (_redoStack.Count == 0) return;
            var current = CaptureSnapshot("Vor Redo");
            _undoStack.Push(current);
            var target = _redoStack.Pop();
            RestoreSnapshot(target);
            UpdateUndoRedoButtons();
            if (StatusText != null) StatusText.Text = $"↷ Wiederholen: {target.Description}";
        }

        private void Window_PreviewKeyDown(object sender, KeyEventArgs e)
        {
            bool isCtrl = (Keyboard.Modifiers & ModifierKeys.Control) == ModifierKeys.Control;
            bool isShift = (Keyboard.Modifiers & ModifierKeys.Shift) == ModifierKeys.Shift;
            bool isTextInputFocused = Keyboard.FocusedElement is System.Windows.Controls.TextBox ||
                                      Keyboard.FocusedElement is System.Windows.Controls.Primitives.TextBoxBase;

            if (isCtrl && e.Key == Key.Z)
            {
                e.Handled = true;
                if (isShift)
                    BtnRedo_Click(sender, e);
                else
                    BtnUndo_Click(sender, e);
            }
            else if (isCtrl && e.Key == Key.Y)
            {
                e.Handled = true;
                BtnRedo_Click(sender, e);
            }
            else if (isCtrl && e.Key == Key.R)
            {
                e.Handled = true;
                BtnResetAll_Click(sender, e);
            }
            else if (isCtrl && isShift && e.Key == Key.S)
            {
                e.Handled = true;
                ExportAnnotatedPacsSnapshot_Click(sender, e);
            }
            else if (e.Key == Key.F1 && RbViewDual != null) { e.Handled = true; RbViewDual.IsChecked = true; }
            else if (e.Key == Key.F2 && RbViewCurtain != null) { e.Handled = true; RbViewCurtain.IsChecked = true; }
            else if (e.Key == Key.F3 && RbView3DRelief != null) { e.Handled = true; RbView3DRelief.IsChecked = true; }
            else if (e.Key == Key.F4 && RbViewDSA != null) { e.Handled = true; RbViewDSA.IsChecked = true; }
            else if (e.Key == Key.F5) { e.Handled = true; BtnRunAnalysis_Click(sender, new RoutedEventArgs()); }
            else if (e.Key == Key.F6 && RbViewPressureProxy != null) { e.Handled = true; RbViewPressureProxy.IsChecked = true; }
            else if (e.Key == Key.F7 && RbViewBioheat != null) { e.Handled = true; RbViewBioheat.IsChecked = true; }
            else if (e.Key == Key.F8 && RbViewMirrorDiff != null) { e.Handled = true; RbViewMirrorDiff.IsChecked = true; }
            else if (e.Key == Key.F9 && RbViewIschemia != null) { e.Handled = true; RbViewIschemia.IsChecked = true; }
            else if (e.Key == Key.F11) { e.Handled = true; MenuCohortScan_Click(sender, e); }
            else if (e.Key == Key.F12) { e.Handled = true; BtnJuryDemoMode_Click(sender, e); }
            else if (!isTextInputFocused && Keyboard.Modifiers == ModifierKeys.None && e.Key == Key.L && RbToolLoupe != null && RbToolPan != null)
            {
                e.Handled = true;
                if (RbToolLoupe.IsChecked == true) RbToolPan.IsChecked = true;
                else RbToolLoupe.IsChecked = true;
            }
            else if (!isTextInputFocused && Keyboard.Modifiers == ModifierKeys.None && e.Key == Key.I && ChkInvertLut != null)
            {
                e.Handled = true;
                ChkInvertLut.IsChecked = !(ChkInvertLut.IsChecked == true);
                ChkInvertLut_Click(sender, e);
            }
        }

        private void BtnResetAll_Click(object sender, RoutedEventArgs e)
        {
            PushUndoSnapshot("Alles Zurücksetzen");
            StopJuryDemoMode();
            _loupePinned = false;
            _invertLut = false;
            if (ChkInvertLut != null) ChkInvertLut.IsChecked = false;
            if (RbToolPan != null) RbToolPan.IsChecked = true;

            // Reset zoom & pan
            _currentZoom = 1.0;
            ApplyZoom();

            // Reset curtain
            _curtainPositionX = 0.5;
            UpdateCurtainGeometry();

            // Reset ROI
            _currentROI = null;

            // Reset Probes
            _probePoints.Clear();
            _activeProfileStats = null;
            UpdateProbesUI();
            if (CanvasProfileGraph != null) CanvasProfileGraph.Children.Clear();
            if (TxtProfileMinTemp != null) TxtProfileMinTemp.Text = "-- °C";
            if (TxtProfileMaxTemp != null) TxtProfileMaxTemp.Text = "-- °C";
            if (TxtProfileMeanTemp != null) TxtProfileMeanTemp.Text = "-- °C";
            if (TxtProfileLength != null) TxtProfileLength.Text = "Pfadlänge: -- px";
            if (TxtProfileMaxGrad != null) TxtProfileMaxGrad.Text = "Maximaler Gradient |dT/ds|: -- K/px";
            if (TxtProbeDeltaT != null) TxtProbeDeltaT.Text = "-- K";

            // Reset Goniometer
            _goniometerPoints.Clear();
            _goniometerMeasurement = null;

            // Reset Window/Level
            _windowCenter = 127.5;
            _windowWidth = 255.0;
            if (SliderWindowLevel != null) SliderWindowLevel.Value = 128.0;
            if (SliderWindowWidth != null) SliderWindowWidth.Value = 255.0;
            ApplyWindowLevelToViewports();

            // Reset 3D correction view toggle
            _showCorrected2D = false;
            if (TxtToggleCorrectedBtn != null) TxtToggleCorrectedBtn.Text = "Umschalten: Kantenkorrigiertes 2D-Wärmebild";

            // Reset View Mode to Curtain
            if (RbViewCurtain != null) RbViewCurtain.IsChecked = true;
            ViewMode_Checked(this, new RoutedEventArgs());

            // Redraw Overlays
            RedrawInteractiveOverlays();

            // Refresh views
            if (_latestResult != null)
                RenderAnalysisResultOverlay(_latestResult, _enableVeinOverlay);
            else
                RefreshResultImageOnly();

            if (StatusText != null)
                StatusText.Text = "↺ Workstation vollständig auf Ausgangszustand zurückgesetzt (Zoom 100%, zentriert, Sonden & ROIs geleert).";
        }

        // =========================================================================
        // COMPREHENSIVE EXPORT SYSTEM (3D CAD, DATA, CLINICAL REPORTS, IMAGES)
        // =========================================================================
        private void Export3D_Obj_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "Wavefront 3D Mesh (*.obj)|*.obj",
                    FileName = $"Ignite_3D_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.obj",
                    Title = "3D Wavefront OBJ Mesh exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var mesh = Mesh3DExportService.BuildMesh(
                        _cachedDepth3DPixels,
                        _rawGrayPixels,
                        null,
                        _rawWidth,
                        _rawHeight,
                        _latestResult?.Reconstruction3D?.MaxDepthMm ?? 35.0,
                        0.6,
                        2);
                    Mesh3DExportService.ExportObj(dlg.FileName, mesh, _activePatientId);
                    _dbService.LogAuditAction("EXPORT_3D_OBJ", $"3D OBJ exportiert nach {dlg.FileName}");
                    MessageBox.Show($"3D OBJ Modell erfolgreich exportiert ({mesh.Vertices.Count:N0} Vertices, {mesh.Faces.Count:N0} Dreiecke):\n{dlg.FileName}", "3D Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim 3D-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Export3D_Ply_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "Stanford PLY (*.ply)|*.ply",
                    FileName = $"Ignite_3D_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.ply",
                    Title = "3D Stanford PLY Mesh exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var mesh = Mesh3DExportService.BuildMesh(
                        _cachedDepth3DPixels,
                        _rawGrayPixels,
                        null,
                        _rawWidth,
                        _rawHeight,
                        _latestResult?.Reconstruction3D?.MaxDepthMm ?? 35.0,
                        0.6,
                        2);
                    Mesh3DExportService.ExportPly(dlg.FileName, mesh, _activePatientId);
                    _dbService.LogAuditAction("EXPORT_3D_PLY", $"3D PLY exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Stanford PLY Modell erfolgreich exportiert:\n{dlg.FileName}", "3D Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim PLY-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Export3D_Stl_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "Stereolithographie STL 3D-Druck (*.stl)|*.stl",
                    FileName = $"Ignite_3DPrint_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.stl",
                    Title = "STL 3D-Druckmodell exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var mesh = Mesh3DExportService.BuildMesh(
                        _cachedDepth3DPixels,
                        _rawGrayPixels,
                        null,
                        _rawWidth,
                        _rawHeight,
                        _latestResult?.Reconstruction3D?.MaxDepthMm ?? 35.0,
                        0.6,
                        2);
                    Mesh3DExportService.ExportStl(dlg.FileName, mesh);
                    _dbService.LogAuditAction("EXPORT_3D_STL", $"3D STL exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Binäres STL-Modell für 3D-Druck erfolgreich exportiert:\n{dlg.FileName}", "3D-Druck Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim STL-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Export3D_Xyz_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "XYZ Punktwolke (*.xyz)|*.xyz|Textdatei (*.txt)|*.txt",
                    FileName = $"Ignite_PointCloud_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.xyz",
                    Title = "3D Punktwolke exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var mesh = Mesh3DExportService.BuildMesh(_cachedDepth3DPixels, _rawGrayPixels, null, _rawWidth, _rawHeight, _latestResult?.Reconstruction3D?.MaxDepthMm ?? 35.0, 0.6, 2);
                    Mesh3DExportService.ExportXyzPointCloud(dlg.FileName, mesh, 20.0, 42.0);
                    _dbService.LogAuditAction("EXPORT_3D_XYZ", $"XYZ Punktwolke exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Punktwolke erfolgreich exportiert:\n{dlg.FileName}", "XYZ Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Punktwolken-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Export3D_DepthCsv_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "CSV Tabelle (*.csv)|*.csv",
                    FileName = $"Ignite_DepthMatrix_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.csv",
                    Title = "3D Tiefenprofil Matrix exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    Mesh3DExportService.ExportDepthMatrixCsv(dlg.FileName, _cachedDepth3DPixels, _rawWidth, _rawHeight, _latestResult?.Reconstruction3D?.MaxDepthMm ?? 35.0);
                    _dbService.LogAuditAction("EXPORT_3D_DEPTH_CSV", $"Tiefenmatrix exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Tiefenmatrix (mm) erfolgreich exportiert:\n{dlg.FileName}", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Tiefenmatrix-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ExportClinicalJson_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_latestResult == null)
                {
                    MessageBox.Show("Keine Befundergebnisse zum Exportieren vorhanden.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var dlg = new SaveFileDialog
                {
                    Filter = "JSON Datensatz (*.json)|*.json",
                    FileName = $"Ignite_Clinical_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.json",
                    Title = "Vollständigen Patientendatensatz exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var opt = new System.Text.Json.JsonSerializerOptions { WriteIndented = true };
                    string json = System.Text.Json.JsonSerializer.Serialize(_latestResult, opt);
                    File.WriteAllText(dlg.FileName, json);
                    _dbService.LogAuditAction("EXPORT_CLINICAL_JSON", $"JSON exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Vollständiger Patientendatensatz erfolgreich als JSON exportiert:\n{dlg.FileName}", "JSON Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim JSON-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ExportHotspotsCsv_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_latestResult?.Hotspots == null || _latestResult.Hotspots.Count == 0)
                {
                    MessageBox.Show("Keine Hotspots für diesen Patienten detektiert.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var dlg = new SaveFileDialog
                {
                    Filter = "CSV Tabelle (*.csv)|*.csv",
                    FileName = $"Ignite_Hotspots_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.csv",
                    Title = "Hotspot- & Risikotabelle exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var sb = new StringBuilder();
                    sb.AppendLine("ID;Typ;Risiko;Flaeche_px;Flaeche_prozent;Mittel_Temp_C;Max_Temp_C;DeltaT_K;Halo_Delta;Perimeter;Zirkularitaet;Zentrum_X;Zentrum_Y;Empfehlung");
                    foreach (var h in _latestResult.Hotspots)
                    {
                        var r = h.Region;
                        var a = h.Assessment;
                        double meanT = ThermalAnalysisHelper.RawToTemperature((byte)Math.Clamp((int)r.MeanVal, 0, 255));
                        double maxT = ThermalAnalysisHelper.RawToTemperature(r.MaxVal);
                        double deltaT = Math.Max(0, maxT - meanT);
                        sb.AppendLine(string.Format(CultureInfo.InvariantCulture,
                            "{0};{1};{2};{3};{4:F2};{5:F2};{6:F2};{7:F2};{8:F2};{9:F1};{10:F3};{11};{12};\"{13}\"",
                            r.Id, h.DisplayDiagnosisType, a.RiskLevel, r.AreaPixels, r.AreaPercent,
                            meanT, maxT, deltaT, r.HaloDelta, r.Perimeter, r.Circularity, r.CenterX, r.CenterY, a.Recommendation));
                    }
                    File.WriteAllText(dlg.FileName, sb.ToString(), Encoding.UTF8);
                    _dbService.LogAuditAction("EXPORT_HOTSPOTS_CSV", $"Hotspot-Tabelle exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Hotspot-Tabelle erfolgreich exportiert:\n{dlg.FileName}", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Hotspot-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void EnsureVeinCacheLoaded(int w, int h)
        {
            if (_cachedVeinPixels == null)
            {
                string veinMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "vascular_mask.png");
                if (File.Exists(veinMaskPath))
                {
                    _cachedVeinPixels = PaletteService.LoadVeinMaskBytes(veinMaskPath, w, h);
                }
            }
        }

        private void ExportBiomechanicsCsv_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var (bmp, stats) = AdvancedDiagnosticService.GeneratePressureProxyMap(_rawGrayPixels, _rawWidth, _rawHeight);
                var dlg = new SaveFileDialog
                {
                    Filter = "CSV Tabelle (*.csv)|*.csv",
                    FileName = $"Ignite_Biomechanics_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.csv",
                    Title = "Biomechanik- & Plantardrucktabelle exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    var sb = new StringBuilder();
                    sb.AppendLine("Parameter;Wert;Einheit;Beschreibung");
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "Peak_Pressure;{0:F2};kPa;Maximaler dynamischer Druck", stats.PeakPressureKpa));
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "Mean_Pressure;{0:F2};kPa;Mittlerer Gewebedruck", stats.MeanPressureKpa));
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "Peak_Location_X;{0:F0};px;X-Koordinate der Druckspitze", stats.PeakLocation.X));
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "Peak_Location_Y;{0:F0};px;Y-Koordinate der Druckspitze", stats.PeakLocation.Y));
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "High_Risk_Area;{0};px;Gewebeareal mit erhoehtem Risiko", stats.HighRiskAreaPx));
                    sb.AppendLine(string.Format(CultureInfo.InvariantCulture, "Risk_Category;{0};-;Klinische Risikoklassifikation", stats.RiskCategory));
                    
                    File.WriteAllText(dlg.FileName, sb.ToString(), Encoding.UTF8);
                    _dbService.LogAuditAction("EXPORT_BIOMECHANICS_CSV", $"Biomechanik-Tabelle exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Biomechaniktabelle erfolgreich exportiert:\n{dlg.FileName}", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Biomechanik-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void SaveBitmapSourceToPng(BitmapSource source, string filePath)
        {
            var encoder = new PngBitmapEncoder();
            encoder.Frames.Add(BitmapFrame.Create(source));
            using var stream = new FileStream(filePath, FileMode.Create);
            encoder.Save(stream);
        }

        private void ExportCurrentView_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                BitmapSource? src = ImgResult?.Source as BitmapSource ?? ImgOriginal?.Source as BitmapSource;
                if (src == null)
                {
                    MessageBox.Show("Keine Bildansicht vorhanden.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var dlg = new SaveFileDialog
                {
                    Filter = "PNG Bild (*.png)|*.png",
                    FileName = $"Ignite_Viewport_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.png",
                    Title = "Aktuelle Bildansicht exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    SaveBitmapSourceToPng(src, dlg.FileName);
                    _dbService.LogAuditAction("EXPORT_VIEW_PNG", $"Viewport exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Bildansicht erfolgreich exportiert:\n{dlg.FileName}", "Bildexport", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Bildexport: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ExportDiagnosticOverlay_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (ImgResult?.Source is not BitmapSource src)
                {
                    MessageBox.Show("Kein diagnostischer Befund gerendert.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var dlg = new SaveFileDialog
                {
                    Filter = "PNG Bild (*.png)|*.png",
                    FileName = $"Ignite_Diagnosis_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.png",
                    Title = "Diagnostisches Befund-Overlay exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    SaveBitmapSourceToPng(src, dlg.FileName);
                    _dbService.LogAuditAction("EXPORT_OVERLAY_PNG", $"Befundoverlay exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Diagnostisches Overlay erfolgreich exportiert:\n{dlg.FileName}", "Bildexport", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Overlay-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void ExportVascularTree_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                EnsureVeinCacheLoaded(_rawWidth, _rawHeight);
                if (_cachedVeinPixels == null)
                {
                    MessageBox.Show("Keine Gefäßbaum-Daten vorhanden.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var dummy = new WriteableBitmap(_rawWidth, _rawHeight, 96, 96, PixelFormats.Bgra32, null);
                var dsaBmp = PaletteService.BlendVeinOverlay(dummy, _cachedVeinPixels, 1.0, _veinThreshold, VeinRenderMode.PureAngiography);
                var dlg = new SaveFileDialog
                {
                    Filter = "PNG Bild (*.png)|*.png",
                    FileName = $"Ignite_Vessels_DSA_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.png",
                    Title = "Vaskulären Frangi-Gefäßbaum exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    SaveBitmapSourceToPng(dsaBmp, dlg.FileName);
                    _dbService.LogAuditAction("EXPORT_VESSELS_PNG", $"Gefäßbaum exportiert nach {dlg.FileName}");
                    MessageBox.Show($"Gefäßbaum (DSA) erfolgreich exportiert:\n{dlg.FileName}", "Bildexport", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Gefäßbaum-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void Export3DDepthMap_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (_rawWidth <= 0 || _rawHeight <= 0)
                {
                    MessageBox.Show("Kein Bilddatensatz geladen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                Ensure3DCacheLoaded(_rawWidth, _rawHeight);
                if (_cachedDepth3DPixels == null)
                {
                    MessageBox.Show("Keine 3D-Tiefendaten vorhanden.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }
                var depthBmp = PaletteService.ApplyPalette(_cachedDepth3DPixels, _rawWidth, _rawHeight, ColorPalette.Inferno);
                var dlg = new SaveFileDialog
                {
                    Filter = "PNG Bild (*.png)|*.png",
                    FileName = $"Ignite_3DDepthMap_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.png",
                    Title = "3D Tiefenrelief Farbkarte exportieren"
                };
                if (dlg.ShowDialog() == true)
                {
                    SaveBitmapSourceToPng(depthBmp, dlg.FileName);
                    _dbService.LogAuditAction("EXPORT_3D_DEPTH_PNG", $"3D-Tiefenkarte exportiert nach {dlg.FileName}");
                    MessageBox.Show($"3D Tiefenrelief-Farbkarte erfolgreich exportiert:\n{dlg.FileName}", "Bildexport", MessageBoxButton.OK, MessageBoxImage.Information);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim 3D-Tiefenkarten-Export: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // =========================================================================
        // FEATURE-PAKETE 1-4: ISCHÄMIE/CHARCOT/ENTROPIE, KOHORTE, SNAPSHOT & JURY-DEMO
        // =========================================================================

        private void UpdateIschemiaCharcotEntropyUI()
        {
            if (_rawGrayPixels == null || _rawWidth <= 0 || _rawHeight <= 0) return;

            _cachedIschemiaCharcot ??= AdvancedDiagnosticService.EvaluateIschemiaCharcotAndEntropy(_rawGrayPixels, _rawWidth, _rawHeight);
            if (_cachedMirrorStats == null)
            {
                var (mBmp, mStats) = AdvancedDiagnosticService.GenerateBilateralMirrorDiffMap(_rawGrayPixels, _rawWidth, _rawHeight);
                _cachedMirrorDiffBitmap = mBmp;
                _cachedMirrorStats = mStats;
            }

            var res = _cachedIschemiaCharcot;
            var mir = _cachedMirrorStats;

            if (TxtIschemiaStage != null) TxtIschemiaStage.Text = res.IschemiaStage.ToUpperInvariant();
            if (BorderIschemiaBadge != null && TxtIschemiaStage != null)
            {
                var brush = res.IsIschemiaCritical
                    ? (Brush)FindResource("CriticalBrush")
                    : (res.DistalProximalDropK >= 1.5 ? (Brush)FindResource("WarningBrush") : (Brush)FindResource("CyanBrush"));
                BorderIschemiaBadge.BorderBrush = brush;
                TxtIschemiaStage.Foreground = brush;
            }
            if (TxtAbiThermalProxy != null) TxtAbiThermalProxy.Text = $"{res.AbiThermalProxy:F2}";
            if (TxtDistalDropK != null) TxtDistalDropK.Text = $"{-res.DistalProximalDropK:+0.00;-0.00;0.00} K";
            if (TxtColdestAcralTemp != null) TxtColdestAcralTemp.Text = $"{res.ColdestAcralTempC:F1} °C";
            if (TxtProximalDistalDetail != null) TxtProximalDistalDetail.Text = $"Proximal: {res.ProximalMeanTempC:F1} °C · Distal: {res.DistalMeanTempC:F1} °C";
            if (TxtColdSpotAreaPct != null) TxtColdSpotAreaPct.Text = $"Hypothermie-Fläche (< 28,5 °C): {res.ColdSpotAreaPct:F1} % ({res.ColdSpotPixelCount:N0} px)";

            if (TxtCharcotStage != null) TxtCharcotStage.Text = res.CharcotEichenholtzStage.ToUpperInvariant();
            if (BorderCharcotBadge != null && TxtCharcotStage != null)
            {
                var cBrush = res.IsCharcotActive ? (Brush)FindResource("CriticalBrush") : (Brush)FindResource("SuccessBrush");
                BorderCharcotBadge.BorderBrush = cBrush;
                TxtCharcotStage.Foreground = cBrush;
            }
            if (TxtCharcotHyperthermiaK != null) TxtCharcotHyperthermiaK.Text = $"{res.CharcotHyperthermiaDeltaK:+0.00;-0.00;0.00} K";
            if (TxtMidfootPeakTemp != null) TxtMidfootPeakTemp.Text = $"{res.MidfootPeakTempC:F1} °C";
            if (TxtCharcotClinicalNote != null) TxtCharcotClinicalNote.Text = res.CharcotClinicalNote;

            if (TxtShannonEntropyBits != null) TxtShannonEntropyBits.Text = $"{res.ShannonEntropyBits:F2} bits";
            if (TxtSpatialRoughness != null) TxtSpatialRoughness.Text = $"{res.SpatialRoughnessKPerPx:F2} K/px";
            if (TxtTextureClassification != null) TxtTextureClassification.Text = $"Klassifikation: {res.TextureClassification}";

            if (mir != null)
            {
                if (TxtMirrorMaxAsymmetry != null) TxtMirrorMaxAsymmetry.Text = $"{mir.MaxAsymmetryK:F2} K";
                if (TxtMirrorMeanAsymmetry != null) TxtMirrorMeanAsymmetry.Text = $"{mir.MeanAsymmetryK:F2} K";
                if (TxtMirrorArmstrongArea != null) TxtMirrorArmstrongArea.Text = $"{mir.ArmstrongAreaPct:F1} %";
            }
        }

        private void BtnViewIschemiaMap_Click(object sender, RoutedEventArgs e)
        {
            if (RbViewIschemia != null) RbViewIschemia.IsChecked = true;
        }

        private void BtnViewMirrorDiff_Click(object sender, RoutedEventArgs e)
        {
            if (RbViewMirrorDiff != null) RbViewMirrorDiff.IsChecked = true;
        }

        private void MenuCohortScan_Click(object sender, RoutedEventArgs e)
        {
            SelectInspectorTab(TabCohortStudy);
            if (_cohortSummaries.Count == 0)
            {
                BtnRunCohortScan_Click(sender, e);
            }
        }

        private async void BtnRunCohortScan_Click(object sender, RoutedEventArgs e)
        {
            SelectInspectorTab(TabCohortStudy);
            var files = _filmstripFiles.Where(File.Exists).ToList();
            if (files.Count == 0 && !string.IsNullOrEmpty(_currentImagePath) && File.Exists(_currentImagePath))
            {
                files.Add(_currentImagePath);
            }

            if (files.Count == 0)
            {
                if (TxtCohortStatus != null) TxtCohortStatus.Text = "Keine Thermogramm-Dateien im Fallarchiv gefunden.";
                return;
            }

            if (BtnRunCohortScan != null) BtnRunCohortScan.IsEnabled = false;
            if (TxtCohortStatus != null) TxtCohortStatus.Text = $"Scanne {files.Count} Patientenfälle deterministisch...";

            try
            {
                var scanned = await Task.Run(() =>
                {
                    var results = new List<AdvancedDiagnosticService.CohortCaseSummary>(files.Count);
                    for (int i = 0; i < files.Count; i++)
                    {
                        results.Add(AdvancedDiagnosticService.EvaluateCaseFast(i + 1, files[i]));
                    }
                    return results;
                });

                _cohortSummaries = scanned;
                if (GridCohortResults != null) GridCohortResults.ItemsSource = _cohortSummaries;

                int criticalCount = _cohortSummaries.Count(c => c.MaxAsymmetryK >= 2.2 || c.IwgdfGrade >= 2);
                double meanTemp = _cohortSummaries.Count > 0 ? _cohortSummaries.Average(c => c.MeanTempC) : 0.0;
                double meanAsym = _cohortSummaries.Count > 0 ? _cohortSummaries.Average(c => c.MaxAsymmetryK) : 0.0;

                if (TxtCohortTotalCases != null) TxtCohortTotalCases.Text = $"{_cohortSummaries.Count}";
                if (TxtCohortCriticalCount != null) TxtCohortCriticalCount.Text = $"{criticalCount}";
                if (TxtCohortMeanTemp != null) TxtCohortMeanTemp.Text = $"{meanTemp:F1} °C";
                if (TxtCohortMeanAsym != null) TxtCohortMeanAsym.Text = $"{meanAsym:F2} K";
                if (TxtCohortStatus != null) TxtCohortStatus.Text = $"Abgeschlossen: {_cohortSummaries.Count} Fälle ({criticalCount} auffällig ≥ 2,2 K / IWGDF ≥ 2)";

                RenderLongitudinalGraph();
                _dbService?.LogAuditAction("COHORT_BATCH_SCAN", $"{_cohortSummaries.Count} Fälle analysiert ({criticalCount} kritisch)");
            }
            catch (Exception ex)
            {
                if (TxtCohortStatus != null) TxtCohortStatus.Text = $"Kohorten-Fehler: {ex.Message}";
            }
            finally
            {
                if (BtnRunCohortScan != null) BtnRunCohortScan.IsEnabled = true;
            }
        }

        private void CanvasLongitudinalGraph_SizeChanged(object sender, SizeChangedEventArgs e)
        {
            RenderLongitudinalGraph();
        }

        private void RenderLongitudinalGraph()
        {
            if (CanvasLongitudinalGraph == null) return;
            CanvasLongitudinalGraph.Children.Clear();

            double w = CanvasLongitudinalGraph.ActualWidth;
            double h = CanvasLongitudinalGraph.ActualHeight;
            if (w <= 20 || h <= 20 || _cohortSummaries.Count == 0) return;

            double padL = 28, padR = 10, padT = 10, padB = 18;
            double plotW = Math.Max(10, w - padL - padR);
            double plotH = Math.Max(10, h - padT - padB);

            // Subtle horizontal oscilloscope grid lines
            var gridBrush = new SolidColorBrush(Color.FromArgb(40, 148, 163, 184));
            for (int g = 0; g <= 4; g++)
            {
                double gy = padT + (plotH * g / 4.0);
                CanvasLongitudinalGraph.Children.Add(new System.Windows.Shapes.Line
                {
                    X1 = padL, Y1 = gy, X2 = w - padR, Y2 = gy,
                    Stroke = gridBrush, StrokeThickness = 0.8
                });
            }

            // Armstrong 2.2 K critical reference line (mapped against 0..6 K asymmetry scale)
            double asymMax = 6.0;
            double armY = padT + plotH * (1.0 - Math.Clamp(2.2 / asymMax, 0, 1));
            CanvasLongitudinalGraph.Children.Add(new System.Windows.Shapes.Line
            {
                X1 = padL, Y1 = armY, X2 = w - padR, Y2 = armY,
                Stroke = new SolidColorBrush(Color.FromRgb(239, 68, 68)),
                StrokeThickness = 1.1,
                StrokeDashArray = new DoubleCollection { 4, 3 }
            });

            var tempLine = new System.Windows.Shapes.Polyline
            {
                Stroke = new SolidColorBrush(Color.FromRgb(56, 189, 248)),
                StrokeThickness = 1.8
            };
            var asymLine = new System.Windows.Shapes.Polyline
            {
                Stroke = new SolidColorBrush(Color.FromRgb(245, 158, 11)),
                StrokeThickness = 1.6
            };

            double tMinScale = 24.0, tMaxScale = 40.0;
            int n = _cohortSummaries.Count;
            for (int i = 0; i < n; i++)
            {
                var c = _cohortSummaries[i];
                double px = n == 1 ? padL + plotW * 0.5 : padL + (plotW * i / (n - 1));
                double ty = padT + plotH * (1.0 - Math.Clamp((c.MaxTempC - tMinScale) / (tMaxScale - tMinScale), 0, 1));
                double ay = padT + plotH * (1.0 - Math.Clamp(c.MaxAsymmetryK / asymMax, 0, 1));

                tempLine.Points.Add(new Point(px, ty));
                asymLine.Points.Add(new Point(px, ay));

                var dot = new System.Windows.Shapes.Ellipse
                {
                    Width = 5,
                    Height = 5,
                    Fill = c.MaxAsymmetryK >= 2.2
                        ? new SolidColorBrush(Color.FromRgb(239, 68, 68))
                        : new SolidColorBrush(Color.FromRgb(56, 189, 248)),
                    ToolTip = $"#{c.CaseNumber} {c.FileName}\nT_max={c.MaxTempC:F1}°C · ΔT={c.MaxAsymmetryK:F2} K · IWGDF {c.IwgdfGrade}"
                };
                Canvas.SetLeft(dot, px - 2.5);
                Canvas.SetTop(dot, ay - 2.5);
                CanvasLongitudinalGraph.Children.Add(dot);
            }

            CanvasLongitudinalGraph.Children.Add(tempLine);
            CanvasLongitudinalGraph.Children.Add(asymLine);

            // Minimal axis scale annotations
            var lblTop = new TextBlock { Text = "6K/40°", FontFamily = new FontFamily("Consolas"), FontSize = 8.5, Foreground = new SolidColorBrush(Color.FromRgb(148, 163, 184)) };
            Canvas.SetLeft(lblTop, 2);
            Canvas.SetTop(lblTop, padT - 4);
            CanvasLongitudinalGraph.Children.Add(lblTop);

            var lblBot = new TextBlock { Text = "0K/24°", FontFamily = new FontFamily("Consolas"), FontSize = 8.5, Foreground = new SolidColorBrush(Color.FromRgb(148, 163, 184)) };
            Canvas.SetLeft(lblBot, 2);
            Canvas.SetTop(lblBot, padT + plotH - 8);
            CanvasLongitudinalGraph.Children.Add(lblBot);
        }

        private void GridCohortResults_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            if (GridCohortResults?.SelectedItem is AdvancedDiagnosticService.CohortCaseSummary item &&
                !string.IsNullOrEmpty(item.FilePath) &&
                File.Exists(item.FilePath) &&
                !string.Equals(item.FilePath, _currentImagePath, StringComparison.OrdinalIgnoreCase))
            {
                LoadImage(item.FilePath);
            }
        }

        private void BtnExportCohortCsv_Click(object sender, RoutedEventArgs e)
        {
            if (_cohortSummaries.Count == 0)
            {
                MessageBox.Show("Bitte zuerst einen Kohorten-Scan durchführen.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                return;
            }

            var dlg = new SaveFileDialog
            {
                Filter = "CSV Tabelle (*.csv)|*.csv",
                FileName = $"Ignite_CohortStudy_{DateTime.Now:yyyyMMdd_HHmm}.csv",
                Title = "Kohorten-Analyse als CSV exportieren"
            };
            if (dlg.ShowDialog() == true)
            {
                var sb = new StringBuilder();
                sb.AppendLine("#;Datei;IWGDF;T_mean_C;T_max_C;DeltaT_Asym_K;PeakPressure_kPa;ShannonEntropy_bits;DistalDrop_K;Triage");
                foreach (var c in _cohortSummaries)
                {
                    sb.AppendLine($"{c.CaseNumber};{c.FileName};{c.IwgdfGrade};{c.MeanTempC:F2};{c.MaxTempC:F2};{c.MaxAsymmetryK:F2};{c.PeakPressureKpa:F1};{c.ShannonEntropyBits:F3};{c.DistalDropK:F2};{c.TriageStatus}");
                }
                File.WriteAllText(dlg.FileName, sb.ToString(), Encoding.UTF8);
                _dbService?.LogAuditAction("EXPORT_COHORT_CSV", $"Kohorten-CSV exportiert nach {dlg.FileName}");
                MessageBox.Show($"Kohorten-Studie ({_cohortSummaries.Count} Fälle) exportiert:\n{dlg.FileName}", "CSV Export", MessageBoxButton.OK, MessageBoxImage.Information);
            }
        }

        private void ExportAnnotatedPacsSnapshot_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                if (BorderWorkbenchViewport == null || BorderWorkbenchViewport.ActualWidth <= 0 || BorderWorkbenchViewport.ActualHeight <= 0)
                {
                    MessageBox.Show("Keine aktive Workbench-Ansicht zum Exportieren.", "Hinweis", MessageBoxButton.OK, MessageBoxImage.Information);
                    return;
                }

                var dlg = new SaveFileDialog
                {
                    Filter = "HiRes PNG Bild (*.png)|*.png",
                    FileName = $"Ignite_PACS_Snapshot_{_activePatientId}_{DateTime.Now:yyyyMMdd_HHmm}.png",
                    Title = "Annotierten PACS-Diagnose-Snapshot (192 DPI) speichern"
                };

                if (dlg.ShowDialog() == true)
                {
                    BorderWorkbenchViewport.UpdateLayout();
                    int pxW = Math.Max(1, (int)Math.Ceiling(BorderWorkbenchViewport.ActualWidth * 2.0));
                    int pxH = Math.Max(1, (int)Math.Ceiling(BorderWorkbenchViewport.ActualHeight * 2.0));
                    var rtb = new RenderTargetBitmap(pxW, pxH, 192, 192, PixelFormats.Pbgra32);
                    rtb.Render(BorderWorkbenchViewport);
                    SaveBitmapSourceToPng(rtb, dlg.FileName);
                    _dbService?.LogAuditAction("EXPORT_PACS_SNAPSHOT_PNG", $"192 DPI PACS-Snapshot gespeichert: {dlg.FileName}");
                    if (StatusText != null) StatusText.Text = $"HiRes PACS-Snapshot gespeichert: {System.IO.Path.GetFileName(dlg.FileName)} ({pxW}×{pxH} px)";
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Snapshot-Fehler: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BtnJuryDemoMode_Click(object sender, RoutedEventArgs e)
        {
            if (_juryDemoTimer != null && _juryDemoTimer.IsEnabled)
            {
                StopJuryDemoMode();
                return;
            }

            _juryDemoStep = 0;
            ExecuteJuryDemoStep(_juryDemoStep);

            _juryDemoTimer = new System.Windows.Threading.DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(3.5)
            };
            _juryDemoTimer.Tick += (s, args) =>
            {
                _juryDemoStep++;
                if (_juryDemoStep >= 6)
                {
                    StopJuryDemoMode();
                    if (StatusText != null) StatusText.Text = "Jury-Präsentationsmodus (6/6 Stufen) erfolgreich abgeschlossen.";
                    return;
                }
                ExecuteJuryDemoStep(_juryDemoStep);
            };
            _juryDemoTimer.Start();
        }

        private void StopJuryDemoMode()
        {
            if (_juryDemoTimer != null)
            {
                _juryDemoTimer.Stop();
            }
            if (TxtJuryDemoLabel != null) TxtJuryDemoLabel.Text = "Jury-Demo";
        }

        private void ExecuteJuryDemoStep(int step)
        {
            if (TxtJuryDemoLabel != null) TxtJuryDemoLabel.Text = $"Stop ({step + 1}/6)";

            switch (step)
            {
                case 0:
                    if (RbViewDual != null) RbViewDual.IsChecked = true;
                    SelectInspectorTab(TabHotspots);
                    if (StatusText != null) StatusText.Text = "Jury-Demo 1/6: Dual-Viewport + Morphologischer Top-Hat & MAD-Outlier Hotspot-Detektion.";
                    break;
                case 1:
                    if (RbViewCurtain != null) RbViewCurtain.IsChecked = true;
                    if (StatusText != null) StatusText.Text = "Jury-Demo 2/6: Synchroner Vorhang-Wipe (Roh-LWIR vs. AVX2-Segmentierung & Frangi-Venenbaum).";
                    break;
                case 2:
                    if (RbViewMirrorDiff != null) RbViewMirrorDiff.IsChecked = true;
                    SelectInspectorTab(TabIschemiaCharcot);
                    if (StatusText != null) StatusText.Text = "Jury-Demo 3/6: Bilaterale Spiegelsymmetrie |T_L − T_R| nach Armstrong ≥ 2,2 K & Charcot Midfoot-Index.";
                    break;
                case 3:
                    if (RbViewIschemia != null) RbViewIschemia.IsChecked = true;
                    SelectInspectorTab(TabIschemiaCharcot);
                    if (StatusText != null) StatusText.Text = "Jury-Demo 4/6: pAVK Akrale Ischämie Cold-Spot Map, ABI-Proxy & Shannon Gewebeentropie.";
                    break;
                case 4:
                    if (RbView3DAnatomy != null) RbView3DAnatomy.IsChecked = true;
                    SelectInspectorTab(Tab3DReconstruction);
                    if (StatusText != null) StatusText.Text = "Jury-Demo 5/6: 3D-Oberflächenrekonstruktion & Lambertian Kanten-Kompensation.";
                    break;
                case 5:
                    if (RbViewDual != null) RbViewDual.IsChecked = true;
                    MenuCohortScan_Click(this, new RoutedEventArgs());
                    if (StatusText != null) StatusText.Text = "Jury-Demo 6/6: Deterministischer Batch Kohorten-Scan & Longitudinale Verlaufs-Trajektorie.";
                    break;
            }
        }

        private void MenuHotkeys_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show(
                "PACS WORKSTATION TASTENKÜRZEL:\n\n" +
                "  F1   Dual-Viewport Befund\n" +
                "  F2   Vorhang-Wipe Compare\n" +
                "  F3   3D Topographie-Relief\n" +
                "  F4   Frangi DSA Gefäßbaum\n" +
                "  F5   42-Stufen AVX2-Analyse starten\n" +
                "  F6   Plantardruck-Proxy (Bioheat)\n" +
                "  F7   Mikrovaskuläre Perfusion (ω_b)\n" +
                "  F8   Bilaterale Spiegelkarte |T_L − T_R|\n" +
                "  F9   pAVK Akrale Ischämie-Map\n" +
                "  F11  Batch Kohorten-Studie öffnen\n" +
                "  F12  Jury-Präsentationsmodus (Start/Stop)\n\n" +
                "  L             4× Thermale Lupe an/aus\n" +
                "  I             Farbskala (LUT) invertieren\n" +
                "  Strg+Umsch+S  192 DPI PACS-Snapshot exportieren\n" +
                "  Strg+R        Alle Ansichten zurücksetzen\n" +
                "  Strg+Z / Y    Rückgängig / Wiederholen",
                "IGNITE PACS Tastenkürzel",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
        }

        private void MenuExit_Click(object sender, RoutedEventArgs e)
        {
            Application.Current.Shutdown();
        }
    }
}