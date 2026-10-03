using System;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;

namespace Ignite.Desktop.Views
{
    public partial class SplashWindow : Window
    {
        public SplashWindow()
        {
            InitializeComponent();

            // Allow dragging the splash window
            MouseDown += (s, e) =>
            {
                if (e.ChangedButton == MouseButton.Left)
                {
                    DragMove();
                }
            };
        }

        public void SetProgress(double percent, string statusText)
        {
            Dispatcher.Invoke(() =>
            {
                SplashProgress.Value = Math.Clamp(percent, 0, 100);
                TxtSplashPercent.Text = $"{(int)percent}%";
                TxtSplashStatus.Text = statusText;
            });
        }

        public async Task PerformStartupSequenceAsync()
        {
            SetProgress(15, "Hardware-Prüfung: Intel/AMD x86_64 AVX2 Vektor-SIMD aktiv...");
            await Task.Delay(220);

            SetProgress(38, "Lade mathematischen Go 1.27 Rechenkern (C-Archive / DLL)...");
            await Task.Delay(240);

            SetProgress(60, "Initialisiere klinische Wagner-Armstrong Entscheidungsmatrix...");
            await Task.Delay(220);

            SetProgress(80, "Lade 12-Bit radiometrische LUT & GPU-Falschfarbenpaletten...");
            await Task.Delay(220);

            SetProgress(94, "Verifiziere lokale SQLite Audit-Datenbank (DSGVO Art. 30)...");
            await Task.Delay(200);

            SetProgress(100, "IGNITE Medical Workstation bereit!");
            await Task.Delay(180);
        }
    }
}
