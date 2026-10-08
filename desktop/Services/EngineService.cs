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

        public async Task<AnalysisResult?> RunAnalysisAsync(
            string imagePath,
            double kFactor,
            double kernelFactor,
            string thresholdMode,
            bool vascular,
            bool perfusion,
            int[]? roi = null,
            string? luaScriptPath = null,
            bool reconstruct3d = true)
        {
            if (!File.Exists(_coreExecutablePath))
            {
                throw new FileNotFoundException($"Die Go-Engine 'ignite-core.exe' wurde nicht gefunden unter: {_coreExecutablePath}. Bitte zuerst 'go build' in core/ ausführen.");
            }

            string outJson = Path.Combine(_cacheDirectory, $"result_{Guid.NewGuid():N}.json");
            var inv = System.Globalization.CultureInfo.InvariantCulture;

            string args = $"-mode=cli -input=\"{Path.GetFullPath(imagePath)}\" -output=\"{outJson}\" -maskdir=\"{_cacheDirectory}\" " +
                          $"-k={kFactor.ToString("F2", inv)} -kernel={kernelFactor.ToString("F3", inv)} -threshmode={thresholdMode} " +
                          $"-vascular={(vascular ? "true" : "false")} -perfusion={(perfusion ? "true" : "false")} " +
                          $"-reconstruct3d={(reconstruct3d ? "true" : "false")}";

            if (roi != null && roi.Length == 4)
            {
                args += $" -roi=\"{roi[0]},{roi[1]},{roi[2]},{roi[3]}\"";
            }

            var psi = new ProcessStartInfo
            {
                FileName = _coreExecutablePath,
                Arguments = args,
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
            if (!File.Exists(_coreExecutablePath))
            {
                throw new FileNotFoundException($"Die Go-Engine 'ignite-core.exe' wurde nicht gefunden.");
            }

            string outJson = Path.Combine(_cacheDirectory, $"sym_{Guid.NewGuid():N}.json");
            var inv = System.Globalization.CultureInfo.InvariantCulture;

            string args;
            if (string.Equals(Path.GetFullPath(leftPath), Path.GetFullPath(rightPath), StringComparison.OrdinalIgnoreCase))
            {
                // Single dual-limb image -> automated limb split
                args = $"-mode=split-symmetry -input=\"{Path.GetFullPath(leftPath)}\" -output=\"{outJson}\" -threshdelta={thresholdDelta.ToString("F1", inv)}";
            }
            else
            {
                // Two separate contralateral images
                args = $"-mode=symmetry -left=\"{Path.GetFullPath(leftPath)}\" -right=\"{Path.GetFullPath(rightPath)}\" -output=\"{outJson}\" -threshdelta={thresholdDelta.ToString("F1", inv)}";
            }

            var psi = new ProcessStartInfo
            {
                FileName = _coreExecutablePath,
                Arguments = args,
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
                throw new InvalidOperationException($"Der bilaterale Vergleich ist fehlgeschlagen: {stderr}");
            }

            string jsonContent = await File.ReadAllTextAsync(outJson);
            File.Delete(outJson);

            return JsonSerializer.Deserialize<BilateralResult>(jsonContent);
        }
    }
}
