using System;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using Ignite.Desktop.Views;

namespace Ignite.Desktop
{
    public partial class App : Application
    {
        protected override async void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                try { File.AppendAllText("crash_log.txt", $"[{DateTime.Now:HH:mm:ss}] [Unhandled] {args.ExceptionObject}\r\n"); } catch { }
                MessageBox.Show($"Unerwarteter Fehler: {args.ExceptionObject}", "IGNITE Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            DispatcherUnhandledException += (s, args) =>
            {
                try
                {
                    string details = $"[{DateTime.Now:HH:mm:ss}] [Dispatcher] {args.Exception.Message}\r\nInner: {args.Exception.InnerException?.Message}\r\n{args.Exception.StackTrace}\r\nInnerStack: {args.Exception.InnerException?.StackTrace}\r\n";
                    File.AppendAllText("crash_log.txt", details);
                }
                catch { }
                MessageBox.Show($"Dispatcher-Fehler: {args.Exception.Message}\n\nInner: {args.Exception.InnerException?.Message}", "IGNITE Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
                args.Handled = true;
            };

            try
            {
                // Prevent application from shutting down when the splash window closes
                ShutdownMode = ShutdownMode.OnExplicitShutdown;

                var splash = new SplashWindow();
                splash.Show();

                // Run animated hardware/clinical startup sequence
                await splash.PerformStartupSequenceAsync();

                // Initialize main workstation
                var mainWindow = new MainWindow();
                MainWindow = mainWindow;
                ShutdownMode = ShutdownMode.OnMainWindowClose;
                mainWindow.Show();

                // Close splash screen
                splash.Close();
            }
            catch (Exception ex)
            {
                string msg = ex.InnerException != null ? $"{ex.Message}\n\nDetail: {ex.InnerException.Message}" : ex.Message;
                MessageBox.Show($"Initialisierungsfehler: {msg}", "IGNITE Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown();
            }
        }
    }
}
