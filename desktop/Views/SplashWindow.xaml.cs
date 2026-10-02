using System.Threading.Tasks;
using System.Windows;

namespace Ignite.Desktop.Views
{
    public partial class SplashWindow : Window
    {
        public SplashWindow()
        {
            InitializeComponent();
        }

        public async Task AnimateStatusAsync()
        {
            TxtSplashStatus.Text = "Lade Go AVX2 Bildverarbeitungspipeline...";
            await Task.Delay(250);
            TxtSplashStatus.Text = "Prüfe klinische Lua-Regeln (Armstrong 2007)...";
            await Task.Delay(250);
            TxtSplashStatus.Text = "Initialisiere GPU-Falschfarben-Shader & SQLite...";
            await Task.Delay(250);
            TxtSplashStatus.Text = "Bereit!";
            await Task.Delay(150);
        }
    }
}
