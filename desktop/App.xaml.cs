using System;
using System.IO;
using System.Windows;

namespace Ignite.Desktop
{
    public partial class App : Application
    {
        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            AppDomain.CurrentDomain.UnhandledException += (s, args) =>
            {
                try { File.AppendAllText("crash_log.txt", $"[{DateTime.Now:HH:mm:ss}] [Unhandled] {args.ExceptionObject}\r\n"); } catch { }
                MessageBox.Show($"Unerwarteter Fehler: {args.ExceptionObject}", "IGNITE Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
            };

            DispatcherUnhandledException += (s, args) =>
            {
                try { File.AppendAllText("crash_log.txt", $"[{DateTime.Now:HH:mm:ss}] [Dispatcher] {args.Exception.Message}\r\n{args.Exception.StackTrace}\r\n"); } catch { }
                MessageBox.Show($"Dispatcher-Fehler: {args.Exception.Message}\n\n{args.Exception.StackTrace}", "IGNITE Fehler", MessageBoxButton.OK, MessageBoxImage.Error);
                args.Handled = true;
            };
        }
    }
}
