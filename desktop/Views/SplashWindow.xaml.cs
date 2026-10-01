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

        public async Task AnimateAndCloseAsync()
        {
            TxtSplashStatus.Text = "Lade Go AVX2 Bildverarbeitungspipeline...";
            await Task.Delay(300);
            TxtSplashStatus.Text = "Prüfe klinische Lua-Regeln (Armstrong 2007)...";
            await Task.Delay(300);
            TxtSplashStatus.Text = "Initialisiere GPU-Falschfarben-Shader & SQLite...";
            await Task.Delay(300);
            TxtSplashStatus.Text = "Bereit!";
            await Task.Delay(200);
            Close();
        }
    }
}
