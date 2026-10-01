using System;
using System.IO;
using System.Linq;
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
    public partial class MainWindow : Window
    {
        private readonly EngineService _engineService;
        private readonly DatabaseService _dbService;

        private string? _currentImagePath;
        private string? _contralateralImagePath;
        private BitmapSource? _originalBitmap;
        private AnalysisResult? _latestResult;
        private ColorPalette _activePalette = ColorPalette.Ironbow;
        private double _currentZoom = 1.0;
        private string _activePatientId = "ANON-DEMO";

        // Interactive ROI Rubberband Selection
        private bool _isSelectingROI = false;
        private Point _roiStartPoint;
        private System.Windows.Shapes.Rectangle? _roiSelectionRect;
        private int[]? _currentROI = null; // [minX, minY, maxX, maxY]

        public MainWindow()
        {
            InitializeComponent();
            _engineService = new EngineService();
            _dbService = new DatabaseService();

            _activePatientId = _dbService.EnsurePatient("Patient_001_Demo");
            PatientIdText.Text = $"DSGVO: {_activePatientId}";

            LoadDefaultLuaRule();
            RefreshAuditGrid();

            // Load demo image from test-data if available
            TryLoadInitialDemoImage();
        }

        private void TryLoadInitialDemoImage()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string testDir = System.IO.Path.GetFullPath(System.IO.Path.Combine(baseDir, "..", "..", "..", "..", "test-data"));
            if (Directory.Exists(testDir))
            {
                var files = Directory.GetFiles(testDir, "*.jpeg");
                if (files.Length > 0)
                {
                    LoadImage(files[0]);
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

        private void LoadImage(string path)
        {
            try
            {
                _currentImagePath = path;
                _currentROI = null;
                OverlayOriginalCanvas.Children.Clear();

                _originalBitmap = PaletteService.LoadAndColorize(path, _activePalette);
                ImgOriginal.Source = _originalBitmap;
                StatusText.Text = $"Bild geladen: {System.IO.Path.GetFileName(path)} ({_originalBitmap.PixelWidth}x{_originalBitmap.PixelHeight}). Ziehen Sie mit der Maus ein Rechteck, um einen Fuß/Bereich auszuwählen.";

                _ = RunPipelineAsync();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Fehler beim Laden des Bildes: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private async Task RunPipelineAsync()
        {
            if (string.IsNullOrEmpty(_currentImagePath) || !File.Exists(_currentImagePath))
                return;

            AnalysisProgressBar.Visibility = Visibility.Visible;
            StatusText.Text = "Berechne Bildverarbeitungspipeline in Go (AVX2-beschleunigt)...";

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

            int w = _originalBitmap.PixelWidth;
            int h = _originalBitmap.PixelHeight;

            // Base result image: Colorized original
            BitmapSource baseBmp = PaletteService.ApplyPalette(_originalBitmap, _activePalette);

            // If vein overlay is requested and mask exists, blend veins in cyan!
            if (showVeins)
            {
                try
                {
                    string veinMaskPath = System.IO.Path.Combine(_engineService.CacheDirectory, "vascular_mask.png");
                    if (File.Exists(veinMaskPath))
                    {
                        baseBmp = PaletteService.BlendVeinOverlay(baseBmp, veinMaskPath);
                    }
                }
                catch { }
            }

            ImgResult.Source = baseBmp;

            // Clear previous vector annotations
            OverlayResultCanvas.Children.Clear();
            OverlayResultCanvas.Width = w;
            OverlayResultCanvas.Height = h;

            if (result.Hotspots == null)
                return;

            double origMed = result.Stats?.OrigMedian ?? 0;

            // Draw professional medical highlight boxes and tags for each confirmed hotspot
            foreach (var hspot in result.Hotspots)
            {
                if (hspot == null || hspot.Region == null)
                    continue;

                var box = hspot.Region.BoundingBox;
                if (box == null || box.Length < 4)
                    continue;

                int minX = box[0], minY = box[1], maxX = box[2], maxY = box[3];
                int bw = maxX - minX;
                int bh = maxY - minY;
                var risk = hspot.Assessment?.RiskLevel ?? "NORMAL";

                // Pulsing highlight glow
                var rect = new System.Windows.Shapes.Rectangle
                {
                    Width = Math.Max(bw, 12),
                    Height = Math.Max(bh, 12),
                    Stroke = risk == "CRITICAL" ? new SolidColorBrush(Color.FromRgb(255, 45, 85)) : Brushes.Yellow,
                    StrokeThickness = 2.5,
                    RadiusX = 4,
                    RadiusY = 4,
                    Fill = new SolidColorBrush(Color.FromArgb(40, 255, 45, 85))
                };
                Canvas.SetLeft(rect, minX);
                Canvas.SetTop(rect, minY);
                OverlayResultCanvas.Children.Add(rect);

                // Crosshair at center
                var crosshairH = new Line
                {
                    X1 = hspot.Region.CenterX - 8,
                    Y1 = hspot.Region.CenterY,
                    X2 = hspot.Region.CenterX + 8,
                    Y2 = hspot.Region.CenterY,
                    Stroke = Brushes.White,
                    StrokeThickness = 1.5
                };
                var crosshairV = new Line
                {
                    X1 = hspot.Region.CenterX,
                    Y1 = hspot.Region.CenterY - 8,
                    X2 = hspot.Region.CenterX,
                    Y2 = hspot.Region.CenterY + 8,
                    Stroke = Brushes.White,
                    StrokeThickness = 1.5
                };
                OverlayResultCanvas.Children.Add(crosshairH);
                OverlayResultCanvas.Children.Add(crosshairV);

                // Floating clinical badge with delta T
                double deltaT = Math.Round((hspot.Region.MaxVal - origMed) * 0.1, 1);
                var labelBorder = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(230, 20, 20, 24)),
                    BorderBrush = rect.Stroke,
                    BorderThickness = new Thickness(1.5),
                    CornerRadius = new CornerRadius(4),
                    Padding = new Thickness(6, 2, 6, 2)
                };
                var tb = new TextBlock
                {
                    Text = $"🔥 HERD #{hspot.Region.Id} (ΔT = +{deltaT:F1} K) [{risk}]",
                    FontSize = 11,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                labelBorder.Child = tb;
                Canvas.SetLeft(labelBorder, minX);
                Canvas.SetTop(labelBorder, Math.Max(0, minY - 24));
                OverlayResultCanvas.Children.Add(labelBorder);
            }
        }

        // --- Interactive ROI Rubberband Selection ---
        private void ViewportOriginal_MouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.LeftButton == MouseButtonState.Pressed && _originalBitmap != null)
            {
                _isSelectingROI = true;
                _roiStartPoint = e.GetPosition(CanvasOriginal);

                if (_roiSelectionRect == null)
                {
                    _roiSelectionRect = new System.Windows.Shapes.Rectangle
                    {
                        Stroke = Brushes.Cyan,
                        StrokeThickness = 2,
                        StrokeDashArray = new DoubleCollection { 4, 2 },
                        Fill = new SolidColorBrush(Color.FromArgb(40, 0, 229, 255))
                    };
                    OverlayOriginalCanvas.Children.Add(_roiSelectionRect);
                }
                _roiSelectionRect.Visibility = Visibility.Visible;
                Canvas.SetLeft(_roiSelectionRect, _roiStartPoint.X);
                Canvas.SetTop(_roiSelectionRect, _roiStartPoint.Y);
                _roiSelectionRect.Width = 0;
                _roiSelectionRect.Height = 0;
            }
        }

        private void ViewportOriginal_MouseMove(object sender, MouseEventArgs e)
        {
            var pos = e.GetPosition(CanvasOriginal);
            int x = (int)pos.X;
            int y = (int)pos.Y;

            if (_originalBitmap != null && x >= 0 && x < _originalBitmap.PixelWidth && y >= 0 && y < _originalBitmap.PixelHeight)
            {
                CursorCoordsText.Text = $"X: {x}, Y: {y}";
            }

            if (_isSelectingROI && _roiSelectionRect != null)
            {
                double curX = Math.Max(0, Math.Min(_originalBitmap?.PixelWidth ?? 0, pos.X));
                double curY = Math.Max(0, Math.Min(_originalBitmap?.PixelHeight ?? 0, pos.Y));

                double minX = Math.Min(_roiStartPoint.X, curX);
                double minY = Math.Min(_roiStartPoint.Y, curY);
                double w = Math.Abs(curX - _roiStartPoint.X);
                double h = Math.Abs(curY - _roiStartPoint.Y);

                Canvas.SetLeft(_roiSelectionRect, minX);
                Canvas.SetTop(_roiSelectionRect, minY);
                _roiSelectionRect.Width = w;
                _roiSelectionRect.Height = h;
            }
        }

        private void ViewportOriginal_MouseUp(object sender, MouseButtonEventArgs e)
        {
            if (_isSelectingROI && _roiSelectionRect != null)
            {
                _isSelectingROI = false;
                double w = _roiSelectionRect.Width;
                double h = _roiSelectionRect.Height;

                if (w > 30 && h > 30)
                {
                    double minX = Canvas.GetLeft(_roiSelectionRect);
                    double minY = Canvas.GetTop(_roiSelectionRect);
                    _currentROI = new int[] { (int)minX, (int)minY, (int)(minX + w), (int)(minY + h) };
                    StatusText.Text = $"ROI gewählt: [{_currentROI[0]}, {_currentROI[1]} bis {_currentROI[2]}, {_currentROI[3]}]. Berechne...";
                    _ = RunPipelineAsync();
                }
            }
        }

        private void ViewportResult_MouseMove(object sender, MouseEventArgs e)
        {
            var pos = e.GetPosition(CanvasResult);
            int x = (int)pos.X;
            int y = (int)pos.Y;
            if (_originalBitmap != null && x >= 0 && x < _originalBitmap.PixelWidth && y >= 0 && y < _originalBitmap.PixelHeight)
            {
                CursorCoordsText.Text = $"X: {x}, Y: {y} [Ergebnis-Viewport]";
            }
        }

        private void ViewportOriginal_MouseLeave(object sender, MouseEventArgs e)
        {
            CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
        }

        private void Viewport_MouseLeave(object sender, MouseEventArgs e)
        {
            CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
        }

        private void BtnResetROI_Click(object sender, RoutedEventArgs e)
        {
            _currentROI = null;
            if (_roiSelectionRect != null)
            {
                _roiSelectionRect.Visibility = Visibility.Collapsed;
            }
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

            // Automated bilateral analysis for a single image with two feet:
            AnalysisProgressBar.Visibility = Visibility.Visible;
            StatusText.Text = "Trennt linke und rechte Extremität automatisch und berechnet bilateralen Armstrong-Vergleich...";

            try
            {
                // Run bilateral comparison of left half vs right half
                var symRes = await _engineService.RunBilateralSymmetryAsync(_currentImagePath, _currentImagePath);
                if (symRes != null)
                {
                    symRes.Zones ??= new();
                    GridSymmetry.ItemsSource = symRes.Zones;
                    TxtSymmetryAssessment.Text = $"{symRes.OverallStatus ?? "NORMAL"}: {symRes.ClinicalAssessment ?? string.Empty} (Max ΔT = {symRes.MaxDeltaT:F1} K)";
                    InspectorTabs.SelectedIndex = 3; // Switch to bilateral tab
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

        private void RefreshAuditGrid()
        {
            try
            {
                var list = _dbService?.GetRecentEvaluations() ?? new();
                GridAudit.ItemsSource = list;
            }
            catch { }
        }

        // --- Menu and Toolbar Event Handlers ---
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
                    InspectorTabs.SelectedIndex = 3;
                    StatusText.Text = $"Seitenvergleich abgeschlossen: Max ΔT = {symRes.MaxDeltaT:F1} K";
                }
            }
            finally
            {
                AnalysisProgressBar.Visibility = Visibility.Collapsed;
            }
        }

        private void BtnRunAnalysis_Click(object sender, RoutedEventArgs e)
        {
            _ = RunPipelineAsync();
        }

        private void BtnToggleVascular_Click(object sender, RoutedEventArgs e)
        {
            bool isVascular = ChkFrangi.IsChecked != true;
            ChkFrangi.IsChecked = isVascular;
            BtnVascularToggle.Background = isVascular ? new SolidColorBrush(Color.FromRgb(0, 122, 204)) : new SolidColorBrush(Color.FromRgb(37, 37, 41));
            BtnVascularToggle.Foreground = isVascular ? Brushes.Cyan : Brushes.White;
            _ = RunPipelineAsync();
        }

        private void ComboPalette_SelectionChanged(object sender, SelectionChangedEventArgs e)
        {
            _activePalette = ComboPalette.SelectedIndex switch
            {
                1 => ColorPalette.Rainbow,
                2 => ColorPalette.Inferno,
                3 => ColorPalette.Grayscale,
                _ => ColorPalette.Ironbow
            };

            if (_currentImagePath != null && File.Exists(_currentImagePath))
            {
                _originalBitmap = PaletteService.LoadAndColorize(_currentImagePath, _activePalette);
                ImgOriginal.Source = _originalBitmap;
                if (_latestResult != null)
                {
                    RenderAnalysisResultOverlay(_latestResult, ChkFrangi.IsChecked == true);
                }
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

        private void BtnResetLua_Click(object sender, RoutedEventArgs e)
        {
            LoadDefaultLuaRule();
        }

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

        private void BtnZoomIn_Click(object sender, RoutedEventArgs e)
        {
            _currentZoom = Math.Min(4.0, _currentZoom + 0.25);
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
            _currentZoom = 0.5;
            ApplyZoom();
        }

        private void ApplyZoom()
        {
            var st = new ScaleTransform(_currentZoom, _currentZoom);
            CanvasOriginal.LayoutTransform = st;
            CanvasResult.LayoutTransform = st;
        }

        private void ModeInflammation_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedIndex = 0;
            _ = RunPipelineAsync();
        }

        private void ModeVascular_Click(object sender, RoutedEventArgs e)
        {
            BtnToggleVascular_Click(sender, e);
        }

        private void ModePerfusion_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedIndex = 2;
            _ = RunPipelineAsync();
        }

        private void ModeBilateral_Click(object sender, RoutedEventArgs e)
        {
            BtnAutoSplitFeet_Click(sender, e);
        }

        private void PaletteIronbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 0;
        private void PaletteRainbow_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 1;
        private void PaletteInferno_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 2;
        private void PaletteGray_Click(object sender, RoutedEventArgs e) => ComboPalette.SelectedIndex = 3;

        private void MenuAuditLog_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 5;
        private void MenuLuaEditor_Click(object sender, RoutedEventArgs e) => InspectorTabs.SelectedIndex = 4;

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