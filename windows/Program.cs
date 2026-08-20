using System.Diagnostics;
using System.Drawing.Imaging;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using Microsoft.Win32;

internal static class Program
{
    private const int WmHotkey = 0x0312;
    private const uint ModNoRepeat = 0x4000;
    private const uint InvalidScreenshot = 0xFFFFFFFF;

    private static readonly string DataDir = Path.Combine(AppContext.BaseDirectory, "data");
    private static readonly string LogPath = Path.Combine(DataDir, "steam-screenshot-bridge.log");
    private static readonly string ConfigPath = Path.Combine(AppContext.BaseDirectory, "config.ini");
    private static readonly List<SteamGame> Games = LoadSteamGames();
    private static int _capturing;
    private static string? _steamApi;

    [STAThread]
    private static void Main()
    {
        // The game is on a high-DPI display. Without per-monitor awareness,
        // Win32 window coordinates and CopyFromScreen pixels use different scales.
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Directory.CreateDirectory(DataDir);
        using var single = new Mutex(true, @"Local\SteamScreenshotBridge", out bool first);
        if (!first) return;

        var hotkeyConfig = LoadHotkey();

        using var hotkey = new HotkeyWindow();
        if (!RegisterHotKey(hotkey.Handle, 1, hotkeyConfig.Modifiers | ModNoRepeat, hotkeyConfig.VirtualKey))
        {
            Log($"FAIL RegisterHotKey {hotkeyConfig.Display}: " + Marshal.GetLastWin32Error());
            return;
        }
        using var trayIcon = CreateTrayIconImage();
        using var tray = CreateTrayIcon(trayIcon, hotkeyConfig.Display);
        Log($"READY global {hotkeyConfig.Display} registered");
        try { Application.Run(); }
        finally { UnregisterHotKey(hotkey.Handle, 1); }
    }

    private static NotifyIcon CreateTrayIcon(Icon icon, string hotkey)
    {
        var menu = new ContextMenuStrip();
        menu.Items.Add(new ToolStripMenuItem($"Steam Screenshot Bridge — Running ({hotkey})")
        {
            Enabled = false
        });
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add(new ToolStripMenuItem("Open configuration", null, (_, _) =>
            Process.Start(new ProcessStartInfo("notepad.exe", ConfigPath) { UseShellExecute = true })));
        menu.Items.Add(new ToolStripMenuItem("Exit", null, (_, _) =>
        {
            Log("EXIT requested from tray");
            Application.Exit();
        }));

        return new NotifyIcon
        {
            Icon = icon,
            Text = $"Steam Screenshot Bridge — Running ({hotkey})",
            ContextMenuStrip = menu,
            Visible = true
        };
    }

    private sealed record HotkeyConfig(int VirtualKey, uint Modifiers, string Display);

    private static HotkeyConfig LoadHotkey()
    {
        const string fallback = "F10";
        try
        {
            if (!File.Exists(ConfigPath)) File.WriteAllText(ConfigPath, "hotkey=F10\n");
            var setting = File.ReadLines(ConfigPath)
                .Select(line => line.Trim())
                .FirstOrDefault(line => !line.StartsWith(';') && !line.StartsWith('#') &&
                    line.StartsWith("hotkey=", StringComparison.OrdinalIgnoreCase));
            var value = setting == null ? fallback : setting[(setting.IndexOf('=') + 1)..].Trim();
            return ParseHotkey(string.IsNullOrWhiteSpace(value) ? fallback : value);
        }
        catch (Exception ex)
        {
            Log("WARN invalid config, using F10: " + ex.Message);
            return ParseHotkey(fallback);
        }
    }

    private static HotkeyConfig ParseHotkey(string value)
    {
        uint modifiers = 0;
        string? keyName = null;
        foreach (var raw in value.Split('+', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            switch (raw.ToUpperInvariant())
            {
                case "ALT": modifiers |= 0x0001; break;
                case "CTRL": case "CONTROL": modifiers |= 0x0002; break;
                case "SHIFT": modifiers |= 0x0004; break;
                case "WIN": case "WINDOWS": modifiers |= 0x0008; break;
                default:
                    if (keyName != null) throw new FormatException("hotkey must contain exactly one key");
                    keyName = raw;
                    break;
            }
        }
        if (keyName == null || !Enum.TryParse<Keys>(keyName, true, out var key) || key == Keys.None)
            throw new FormatException($"unknown hotkey: {value}");
        return new HotkeyConfig((int)key, modifiers, value.ToUpperInvariant());
    }

    private static Icon CreateTrayIconImage()
    {
        using var bitmap = new Bitmap(32, 32, PixelFormat.Format32bppArgb);
        using (var graphics = Graphics.FromImage(bitmap))
        {
            graphics.SmoothingMode = SmoothingMode.AntiAlias;
            graphics.Clear(Color.Transparent);
            using var blue = new SolidBrush(Color.FromArgb(35, 105, 185));
            using var white = new SolidBrush(Color.White);
            using var cyan = new SolidBrush(Color.FromArgb(67, 210, 225));
            graphics.FillEllipse(blue, 1, 1, 30, 30);
            graphics.FillRectangle(white, 7, 11, 18, 13);
            graphics.FillRectangle(white, 11, 8, 8, 4);
            graphics.FillEllipse(cyan, 11, 13, 10, 10);
            graphics.FillEllipse(blue, 14, 16, 4, 4);
        }

        var handle = bitmap.GetHicon();
        try { return (Icon)Icon.FromHandle(handle).Clone(); }
        finally { DestroyIcon(handle); }
    }

    private sealed class HotkeyWindow : NativeWindow, IDisposable
    {
        public HotkeyWindow() => CreateHandle(new CreateParams());
        protected override void WndProc(ref Message message)
        {
            if (message.Msg == WmHotkey && message.WParam == 1 &&
                Interlocked.CompareExchange(ref _capturing, 1, 0) == 0)
            {
                var foreground = GetForegroundWindow();
                bool target = TryGetSteamGame(foreground, out var game, out var detail);
                Log($"HOTKEY foreground=0x{foreground:X} target={target} {detail}");
                if (target)
                {
                    try
                    {
                        // Capture at the keypress before the visual novel advances frames.
                        var shot = CaptureNow(foreground, game!);
                        _ = Task.Run(() => RegisterCaptured(shot));
                    }
                    catch (Exception ex)
                    {
                        Log("FAIL capture " + ex.Message);
                        Interlocked.Exchange(ref _capturing, 0);
                    }
                }
                else Interlocked.Exchange(ref _capturing, 0);
            }
            base.WndProc(ref message);
        }
        public void Dispose() => DestroyHandle();
    }

    private sealed record SteamGame(int AppId, string Name, string Root);

    private static bool TryGetSteamGame(IntPtr window, out SteamGame? game, out string detail)
    {
        game = null;
        detail = "";
        if (window == IntPtr.Zero) { detail = "no foreground window"; return false; }
        GetWindowThreadProcessId(window, out uint pid);
        if (pid == 0) { detail = "no foreground pid"; return false; }
        try
        {
            using var process = Process.GetProcessById((int)pid);
            var path = process.MainModule?.FileName;
            if (path != null)
            {
                var full = Path.GetFullPath(path);
                game = Games.FirstOrDefault(candidate => full.StartsWith(
                    candidate.Root + Path.DirectorySeparatorChar,
                    StringComparison.OrdinalIgnoreCase));
            }
            detail = $"pid={pid} process={process.ProcessName} path={path}" +
                (game == null ? " appid=none" : $" appid={game.AppId} game={game.Name}");
            return game != null;
        }
        catch (Exception ex) { detail = $"pid={pid} lookup={ex.Message}"; return false; }
    }

    private static HashSet<string> SteamLibraries()
    {
        var libraries = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var steam = Registry.CurrentUser.OpenSubKey(@"Software\Valve\Steam")?.GetValue("SteamPath") as string;
        if (string.IsNullOrWhiteSpace(steam)) return libraries;
        libraries.Add(steam.Replace('/', '\\'));
        var folders = Path.Combine(steam, "steamapps", "libraryfolders.vdf");
        if (File.Exists(folders))
        {
            var text = File.ReadAllText(folders);
            foreach (Match match in Regex.Matches(text, "\\\"path\\\"\\s+\\\"([^\\\"]+)\\\""))
                libraries.Add(match.Groups[1].Value.Replace("\\\\", "\\"));
        }
        return libraries;
    }

    /// <summary>
    /// Steam for Windows does not ship steam_api64.dll itself -- it is the
    /// Steamworks redistributable that games bundle. Any installed game's copy
    /// works, so find one instead of hard-coding a path. Drop your own copy next
    /// to the executable to skip the search.
    /// </summary>
    private static string SteamApiPath()
    {
        if (_steamApi != null) return _steamApi;

        var local = Path.Combine(AppContext.BaseDirectory, "steam_api64.dll");
        if (File.Exists(local)) return _steamApi = local;

        foreach (var library in SteamLibraries())
        {
            var common = Path.Combine(library, "steamapps", "common");
            if (!Directory.Exists(common)) continue;
            try
            {
                foreach (var dll in Directory.EnumerateFiles(common, "steam_api64.dll", SearchOption.AllDirectories))
                {
                    Log("using Steam API from an installed game: " + dll);
                    return _steamApi = dll;
                }
            }
            catch { }
        }

        throw new FileNotFoundException(
            "steam_api64.dll not found. Copy one from any installed Steam game " +
            "into this program's folder.");
    }

    private static List<SteamGame> LoadSteamGames()
    {
        var result = new List<SteamGame>();
        try
        {
            foreach (var library in SteamLibraries())
            {
                var steamapps = Path.Combine(library, "steamapps");
                if (!Directory.Exists(steamapps)) continue;
                foreach (var manifest in Directory.EnumerateFiles(steamapps, "appmanifest_*.acf"))
                {
                    try
                    {
                        var text = File.ReadAllText(manifest);
                        var app = Regex.Match(text, "\\\"appid\\\"\\s+\\\"(\\d+)\\\"");
                        var dir = Regex.Match(text, "\\\"installdir\\\"\\s+\\\"([^\\\"]+)\\\"");
                        var name = Regex.Match(text, "\\\"name\\\"\\s+\\\"([^\\\"]+)\\\"");
                        if (app.Success && dir.Success)
                            result.Add(new SteamGame(int.Parse(app.Groups[1].Value),
                                name.Success ? name.Groups[1].Value : app.Groups[1].Value,
                                Path.GetFullPath(Path.Combine(steamapps, "common", dir.Groups[1].Value)).TrimEnd('\\')));
                    }
                    catch { }
                }
            }
        }
        catch { }
        return result.OrderByDescending(game => game.Root.Length).ToList();
    }

    private sealed record CapturedShot(int AppId, string Path, int Width, int Height);

    private static CapturedShot CaptureNow(IntPtr window, SteamGame game)
    {
            if (window != GetForegroundWindow() ||
                !TryGetSteamGame(window, out var current, out _) || current?.AppId != game.AppId)
                throw new InvalidOperationException("game is no longer foreground");
            if (!GetClientRect(window, out var client))
                throw new InvalidOperationException("cannot read the game client area");
            var topLeft = client.TopLeft;
            var bottomRight = client.BottomRight;
            if (!ClientToScreen(window, ref topLeft) || !ClientToScreen(window, ref bottomRight))
                throw new InvalidOperationException("cannot read the game client area");
            client.TopLeft = topLeft;
            client.BottomRight = bottomRight;

            int width = client.Right - client.Left;
            int height = client.Bottom - client.Top;
            if (width < 2 || height < 2) throw new InvalidOperationException("invalid game window size");

            var shots = Path.Combine(DataDir, "pending");
            Directory.CreateDirectory(shots);
            var imagePath = Path.Combine(shots, $"{game.AppId}_{DateTime.Now:yyyyMMddHHmmssfff}.jpg");
            using (var bitmap = new Bitmap(width, height, PixelFormat.Format24bppRgb))
            using (var graphics = Graphics.FromImage(bitmap))
            {
                graphics.CopyFromScreen(client.Left, client.Top, 0, 0, new Size(width, height), CopyPixelOperation.SourceCopy);
                bitmap.Save(imagePath, ImageFormat.Jpeg);
            }

            Log($"CAPTURE x={client.Left} y={client.Top} {width}x{height}");
            return new CapturedShot(game.AppId, imagePath, width, height);
    }

    private static void RegisterCaptured(CapturedShot shot)
    {
        try
        {
            RegisterWithSteam(shot.AppId, shot.Path, shot.Width, shot.Height);
            Log($"OK appid={shot.AppId} {shot.Width}x{shot.Height}");
            TryDelete(shot.Path);
        }
        catch (Exception ex) { Log("FAIL " + ex.Message); }
        finally { Interlocked.Exchange(ref _capturing, 0); }
    }

    private static void RegisterWithSteam(int appId, string imagePath, int width, int height)
    {
        var apiPath = SteamApiPath();
        Environment.SetEnvironmentVariable("SteamAppId", appId.ToString());
        Environment.SetEnvironmentVariable("SteamGameId", appId.ToString());

        var lib = NativeLibrary.Load(apiPath);
        try
        {
            var init = Marshal.GetDelegateForFunctionPointer<SteamApiInit>(NativeLibrary.GetExport(lib, "SteamAPI_Init"));
            var shutdown = Marshal.GetDelegateForFunctionPointer<SteamApiShutdown>(NativeLibrary.GetExport(lib, "SteamAPI_Shutdown"));
            var callbacks = Marshal.GetDelegateForFunctionPointer<SteamApiRunCallbacks>(NativeLibrary.GetExport(lib, "SteamAPI_RunCallbacks"));
            if (!init()) throw new InvalidOperationException("SteamAPI_Init failed");
            try
            {
                var steamClient = Marshal.GetDelegateForFunctionPointer<GetSteamClient>(NativeLibrary.GetExport(lib, "SteamClient"));
                var getUser = Marshal.GetDelegateForFunctionPointer<GetSteamHandle>(NativeLibrary.GetExport(lib, "SteamAPI_GetHSteamUser"));
                var getPipe = Marshal.GetDelegateForFunctionPointer<GetSteamHandle>(NativeLibrary.GetExport(lib, "SteamAPI_GetHSteamPipe"));
                var getScreenshots = Marshal.GetDelegateForFunctionPointer<GetScreenshots>(NativeLibrary.GetExport(lib, "SteamAPI_ISteamClient_GetISteamScreenshots"));
                var add = Marshal.GetDelegateForFunctionPointer<AddScreenshot>(NativeLibrary.GetExport(lib, "SteamAPI_ISteamScreenshots_AddScreenshotToLibrary"));
                var client = steamClient();
                var user = getUser();
                var pipe = getPipe();
                IntPtr screenshots = IntPtr.Zero;
                string selected = "";
                foreach (var version in new[] { "STEAMSCREENSHOTS_INTERFACE_VERSION003", "STEAMSCREENSHOTS_INTERFACE_VERSION002", "STEAMSCREENSHOTS_INTERFACE_VERSION001" })
                {
                    screenshots = getScreenshots(client, user, pipe, version);
                    if (screenshots != IntPtr.Zero) { selected = version; break; }
                }
                if (screenshots == IntPtr.Zero) throw new InvalidOperationException("ISteamScreenshots unavailable (v003-v001)");
                uint handle = add(screenshots, imagePath, null, width, height);
                if (handle == InvalidScreenshot) throw new InvalidOperationException("Steam rejected screenshot");
                callbacks();
                Thread.Sleep(20);
                Log($"Steam interface={selected} handle={handle}");
            }
            finally { shutdown(); }
        }
        finally { NativeLibrary.Free(lib); }
    }

    private static void Log(string message)
    {
        try { File.AppendAllText(LogPath, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} {message}{Environment.NewLine}"); }
        catch { }
    }

    private static void TryDelete(string path) { try { File.Delete(path); } catch { } }

    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate bool SteamApiInit();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate void SteamApiShutdown();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate void SteamApiRunCallbacks();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate IntPtr GetSteamClient();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] private delegate int GetSteamHandle();
    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    private delegate IntPtr GetScreenshots(IntPtr client, int user, int pipe, string version);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    private delegate uint AddScreenshot(IntPtr self, string file, string? thumbnail, int width, int height);

    [StructLayout(LayoutKind.Sequential)] private struct Point { public int X; public int Y; }
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect
    {
        public int Left, Top, Right, Bottom;
        public Point TopLeft { get => new() { X = Left, Y = Top }; set { Left = value.X; Top = value.Y; } }
        public Point BottomRight { get => new() { X = Right, Y = Bottom }; set { Right = value.X; Bottom = value.Y; } }
    }

    [DllImport("user32.dll", SetLastError = true)] private static extern bool RegisterHotKey(IntPtr window, int id, uint modifiers, int virtualKey);
    [DllImport("user32.dll")] private static extern bool UnregisterHotKey(IntPtr window, int id);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out uint pid);
    [DllImport("user32.dll")] private static extern bool GetClientRect(IntPtr window, out Rect rect);
    [DllImport("user32.dll")] private static extern bool ClientToScreen(IntPtr window, ref Point point);
    [DllImport("user32.dll")] private static extern bool DestroyIcon(IntPtr icon);
}
