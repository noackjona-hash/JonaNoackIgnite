using System.Windows;
using Ignite.Desktop.Views;

namespace Ignite.Desktop
{
    public partial class App : Application
    {
        protected override async void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);

            var splash = new SplashWindow();
            splash.Show();

            await splash.AnimateAndCloseAsync();

            var mainWin = new MainWindow();
            mainWin.Show();
        }
    }
}
