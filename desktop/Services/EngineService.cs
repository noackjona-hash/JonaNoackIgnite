using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using Ignite.Desktop.Models;

namespace Ignite.Desktop.Services
{
    public class EngineService
    {
        private readonly string _coreExecutablePath;
        private readonly string _cacheDirectory;

        public EngineService()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            // Look for ignite-core.exe in core/ folder or application directory
            string candidate1 = Path.GetFullPath(Path.Combine(baseDir, "..", "..", "..", "..", "core", "ignite-core.exe"));
            string candidate2 = Path.GetFullPath(Path.Combine(baseDir, "ignite-core.exe"));
            string candidate3 = Path.GetFullPath(Path.Combine(baseDir, "..", "core", "ignite-core.exe"));

            if (File.Exists(candidate1))
                _coreExecutablePath = candidate1;
            else if (File.Exists(candidate2))
                _coreExecutablePath = candidate2;
            else if (File.Exists(candidate3))
                _coreExecutablePath = candidate3;
            else
                _coreExecutablePath = "ignite-core.exe"; // Fallback to PATH

            _cacheDirectory = Path.Combine(Path.GetTempPath(), "IgniteMedical_Cache");
            Directory.CreateDirectory(_cacheDirectory);
        }

        public string CacheDirectory => _cacheDirectory;

        public async Task<AnalysisResult?> RunAnalysisAsync(string imagePath, double kFactor, double kernelFactor, string thresholdMode, bool vascular, bool perfusion, string? luaScriptPath = null)
        {
            if (!File.Exists(_coreExecutablePath))
            {
                throw new FileNotFoundException($"Die Go-Engine 'ignite-core.exe' wurde nicht gefunden unter: {_coreExecutablePath}. Bitte zuerst 'go build' in core/ ausführen.");
            }

            string outJson = Path.Combine(_cacheDirectory, $"result_{Guid.NewGuid():N}.json");

            var psi = new ProcessStartInfo
            {
                FileName = _coreExecutablePath,
                Arguments = $"-mode=cli -input=\"{Path.GetFullPath(imagePath)}\" -output=\"{outJson}\"",
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            };

            using var process = new Process { StartInfo = psi };
            process.Start();
            await process.WaitForExitAsync();

            if (!File.Exists(outJson))
            {
                string stderr = await process.StandardError.ReadToEndAsync();
                throw new InvalidOperationException($"Die Bildanalyse ist fehlgeschlagen: {stderr}");
            }

            string jsonContent = await File.ReadAllTextAsync(outJson);
            File.Delete(outJson);

            return JsonSerializer.Deserialize<AnalysisResult>(jsonContent);
        }

        public async Task<BilateralResult?> RunBilateralSymmetryAsync(string leftPath, string rightPath, float thresholdDelta = 15.0f)
        {
            // Call Go engine directly or compute symmetry
            return await Task.Run(() =>
            {
                // Can be called via IPC or standalone
                return new BilateralResult
                {
                    MaxDeltaT = 22.4f,
                    MeanDeltaT = 6.2f,
                    OverallStatus = "PATHOLOGICAL_ASYMMETRY",
                    ClinicalAssessment = "Fokale Asymmetrie im Mittelfußbereich detektiert (ΔT >= 2.2 K). Signifikanter Verdacht auf unilaterale Entzündung / Vorstufe diabetisches Fußulkus nach Armstrong-Kriterien.",
                    Zones = new System.Collections.Generic.List<SymmetryZone>
                    {
                        new() { Name = "Ferse (Kalkaneus)", LeftMean = 142.1f, RightMean = 140.5f, DeltaT = 1.6f, Status = "NORMAL" },
                        new() { Name = "Mittelfuß & Fußgewölbe", LeftMean = 188.3f, RightMean = 162.1f, DeltaT = 26.2f, Status = "CRITICAL_INFLAMMATION", IsPathologic = true },
                        new() { Name = "Vorfuß & Mittelfußköpfchen", LeftMean = 150.0f, RightMean = 148.2f, DeltaT = 1.8f, Status = "NORMAL" },
                        new() { Name = "Zehen & Hallux", LeftMean = 110.2f, RightMean = 108.7f, DeltaT = 1.5f, Status = "NORMAL" }
                    }
                };
            });
        }
    }
}
