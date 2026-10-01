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
    local delta_t = hotspot.max_val - stats.median
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
                _originalBitmap = PaletteService.LoadAndColorize(path, _activePalette);
                ImgOriginal.Source = _originalBitmap;
                StatusText.Text = $"Bild geladen: {System.IO.Path.GetFileName(path)} ({_originalBitmap.PixelWidth}x{_originalBitmap.PixelHeight})";

                // Trigger automatic initial analysis
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

            StatusText.Text = "Berechne Bildverarbeitungspipeline in Go (AVX2-beschleunigt)...";
            double kFactor = SliderK.Value;
            double kernelFactor = SliderKernel.Value;
            string mode = ComboThresholdMode.SelectedIndex == 1 ? "GAUSSIAN" : "MAD";
            bool vascular = ChkFrangi.IsChecked == true;
            bool perfusion = ChkPerfusion.IsChecked == true;

            try
            {
                var result = await _engineService.RunAnalysisAsync(_currentImagePath, kFactor, kernelFactor, mode, vascular, perfusion);
                if (result == null)
                    return;

                _latestResult = result;

                // Update UI metrics
                TxtTissuePixels.Text = $"Gewebe-Pixel: {result.TissuePixelCount:N0}";
                TxtHotspotCount.Text = $"Gefundene Herde: {result.TotalHotspots}";
                TxtLatency.Text = $"Rechenzeit: {result.Timing.TotalMs:F1} ms (Top-Hat: {result.Timing.TopHatMs:F1} ms)";
                EngineTimingText.Text = $"Go Core: {result.Timing.TotalMs:F1} ms (AVX2)";

                // Update Hotspot Table
                GridHotspots.ItemsSource = result.Hotspots;

                // Update Perfusion Tab
                if (result.Perfusion != null)
                {
                    TxtPerfusionStatus.Text = $"STATUS: {result.Perfusion.Status}";
                    TxtPerfusionStatus.Foreground = result.Perfusion.Status.Contains("CRITICAL") ? Brushes.Red : Brushes.LightGreen;
                    TxtPerfusionDrop.Text = $"Maximaler Gradientenabfall: {result.Perfusion.MaxGradientDrop:F2} K/Zeile";
                    TxtPerfusionDesc.Text = result.Perfusion.Description;
                }

                // Render Overlays in Viewport 2
                RenderAnalysisResultOverlay(result);

                // Log into SQLite database
                double maxVal = result.Hotspots.Count > 0 ? result.Hotspots.Max(h => h.Region.MaxVal) - result.Stats.Median : 0;
                _dbService.LogEvaluation(_activePatientId, _currentImagePath, "INFLAMMATION_HOTSPOTS", result.TotalHotspots, maxVal, result.HighestRisk, result.Timing.TotalMs);
                RefreshAuditGrid();

                StatusText.Text = $"Analyse erfolgreich abgeschlossen ({result.TotalHotspots} Herde gefunden, Status: {result.HighestRisk}).";
            }
            catch (Exception ex)
            {
                StatusText.Text = $"Fehler bei der Analyse: {ex.Message}";
                MessageBox.Show($"Pipeline-Fehler: {ex.Message}", "Fehler", MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private void RenderAnalysisResultOverlay(AnalysisResult result)
        {
            if (_originalBitmap == null)
                return;

            int w = _originalBitmap.PixelWidth;
            int h = _originalBitmap.PixelHeight;

            // Base result image: Colorized original
            var overlayBmp = new WriteableBitmap(PaletteService.ApplyPalette(_originalBitmap, _activePalette));
            ImgResult.Source = overlayBmp;

            // Clear previous vector annotations
            OverlayResultCanvas.Children.Clear();
            OverlayResultCanvas.Width = w;
            OverlayResultCanvas.Height = h;

            // Draw bounding boxes and indicators for each confirmed hotspot
            foreach (var hspot in result.Hotspots)
            {
                var box = hspot.Region.BoundingBox;
                int minX = box[0], minY = box[1], maxX = box[2], maxY = box[3];
                int bw = maxX - minX;
                int bh = maxY - minY;

                var rect = new System.Windows.Shapes.Rectangle
                {
                    Width = Math.Max(bw, 10),
                    Height = Math.Max(bh, 10),
                    Stroke = hspot.Assessment.RiskLevel == "CRITICAL" ? Brushes.Red : Brushes.Yellow,
                    StrokeThickness = 2,
                    Fill = new SolidColorBrush(Color.FromArgb(50, 255, 0, 0))
                };
                Canvas.SetLeft(rect, minX);
                Canvas.SetTop(rect, minY);
                OverlayResultCanvas.Children.Add(rect);

                // Add label with ID and Max T
                var labelBorder = new Border
                {
                    Background = new SolidColorBrush(Color.FromArgb(200, 20, 20, 20)),
                    BorderBrush = rect.Stroke,
                    BorderThickness = new Thickness(1),
                    Padding = new Thickness(3, 1, 3, 1)
                };
                var tb = new TextBlock
                {
                    Text = $"#{hspot.Region.Id} (ΔT={hspot.Region.MaxVal - result.Stats.Median})",
                    FontSize = 10,
                    FontWeight = FontWeights.Bold,
                    Foreground = Brushes.White
                };
                labelBorder.Child = tb;
                Canvas.SetLeft(labelBorder, minX);
                Canvas.SetTop(labelBorder, Math.Max(0, minY - 18));
                OverlayResultCanvas.Children.Add(labelBorder);
            }
        }

        private void RefreshAuditGrid()
        {
            try
            {
                var list = _dbService.GetRecentEvaluations();
                GridAudit.ItemsSource = list;
            }
            catch { }
        }

        // --- Viewport & Mouse Tracking ---
        private void Viewport_MouseMove(object sender, MouseEventArgs e)
        {
            var pos = e.GetPosition((IInputElement)sender);
            int x = (int)pos.X;
            int y = (int)pos.Y;

            if (_originalBitmap != null && x >= 0 && x < _originalBitmap.PixelWidth && y >= 0 && y < _originalBitmap.PixelHeight)
            {
                CursorCoordsText.Text = $"X: {x}, Y: {y} | Pos";
            }
        }

        private void Viewport_MouseLeave(object sender, MouseEventArgs e)
        {
            CursorCoordsText.Text = "X: --, Y: -- | Temp: --";
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

            StatusText.Text = "Berechne bilateralen Seitenvergleich (Armstrong-Kriterien)...";
            var symRes = await _engineService.RunBilateralSymmetryAsync(_currentImagePath, _contralateralImagePath);
            if (symRes != null)
            {
                GridSymmetry.ItemsSource = symRes.Zones;
                TxtSymmetryAssessment.Text = $"{symRes.OverallStatus}: {symRes.ClinicalAssessment} (Max ΔT = {symRes.MaxDeltaT:F1} K)";
                InspectorTabs.SelectedIndex = 3; // Switch to symmetry tab
                StatusText.Text = $"Seitenvergleich abgeschlossen: Max ΔT = {symRes.MaxDeltaT:F1} K";
            }
        }

        private void BtnRunAnalysis_Click(object sender, RoutedEventArgs e)
        {
            _ = RunPipelineAsync();
        }

        private void BtnToggleVascular_Click(object sender, RoutedEventArgs e)
        {
            ChkFrangi.IsChecked = !(ChkFrangi.IsChecked == true);
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
                    RenderAnalysisResultOverlay(_latestResult);
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
            ChkFrangi.IsChecked = true;
            _ = RunPipelineAsync();
        }

        private void ModePerfusion_Click(object sender, RoutedEventArgs e)
        {
            InspectorTabs.SelectedIndex = 2;
            _ = RunPipelineAsync();
        }

        private void ModeBilateral_Click(object sender, RoutedEventArgs e)
        {
            MenuOpenContralateral_Click(sender, e);
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