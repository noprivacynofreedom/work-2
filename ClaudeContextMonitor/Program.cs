using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace ClaudeContextMonitor
{
    /// <summary>User settings. Stored in %AppData%\ClaudeContextMonitor\settings.json. Edit the file, then restart.</summary>
    public sealed class Settings
    {
        /// <summary>Hand off when the session reaches this many tokens.</summary>
        public long ThresholdTokens { get; set; } = 150000;
        /// <summary>Auto = hand off after a countdown. Ask = wait for the button. Off = only show the number.</summary>
        public string Mode { get; set; } = "Auto";
        /// <summary>The transcript must be unchanged this long, so Claude is not cut off in the middle of an answer.</summary>
        public int IdleSeconds { get; set; } = 8;
        public int CountdownSeconds { get; set; } = 5;
        /// <summary>Ignore sessions that did not change in this many minutes.</summary>
        public int MaxAgeMinutes { get; set; } = 30;
        /// <summary>Extra transcript folders. The default folders are always searched.</summary>
        public List<string> ExtraRoots { get; set; } = new List<string>();
        /// <summary>Names of the "new chat" control. NOT verified. Run --uia-dump and put the real name first.</summary>
        public List<string> NewChatNames { get; set; } = new List<string> { "New session", "New chat", "New conversation", "New task" };
        /// <summary>Used when no control name matches.</summary>
        public string NewChatShortcut { get; set; } = "Ctrl+Shift+O";
    }

    public sealed class MainForm : Form
    {
        private static readonly string DataDir =
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "ClaudeContextMonitor");

        private readonly Settings _settings;
        private readonly List<string> _roots = new List<string>();
        private readonly HashSet<string> _handled = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private readonly Label _session = new Label();
        private readonly Label _tokens = new Label();
        private readonly Label _status = new Label();
        private readonly ProgressBar _bar = new ProgressBar();
        private readonly ComboBox _mode = new ComboBox();
        private readonly NumericUpDown _limit = new NumericUpDown();
        private readonly Button _now = new Button();
        private readonly Button _cancel = new Button();
        private readonly NotifyIcon _tray = new NotifyIcon();
        private readonly Timer _timer = new Timer();
        private SessionState? _state;
        private DateTime? _fireAt;        // end of the countdown, when one runs
        private bool _running;

        [STAThread]
        public static void Main(string[] args)
        {
            Directory.CreateDirectory(DataDir);
            if (args.Length > 0 && args[0] == "--uia-dump") { UiaDump(); return; }
            Application.EnableVisualStyles();
            Application.Run(new MainForm());
        }

        /// <summary>Writes the names of all controls in Claude Desktop to a file. Use it to find the real "new chat" name.</summary>
        private static void UiaDump()
        {
            string file = Path.Combine(DataDir, "uia-dump.txt");
            IntPtr h = Native.ClaudeWindow();
            string text = h == IntPtr.Zero ? "Claude Desktop window not found. Start Claude Desktop first." : Native.Dump(h);
            File.WriteAllText(file, text);
            MessageBox.Show("Written to " + file, "Claude Context Monitor");
        }

        public MainForm()
        {
            _settings = LoadSettings();
            string home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            _roots.Add(Path.Combine(home, ".claude", "projects"));
            _roots.Add(Path.Combine(appData, "Claude", "local-agent-mode-sessions"));
            _roots.AddRange(_settings.ExtraRoots);

            Text = "Claude Context Monitor";
            Font = new Font("Consolas", 10f);
            BackColor = Color.FromArgb(18, 18, 24);
            ForeColor = Color.Gainsboro;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            ClientSize = new Size(460, 215);

            Place(_session, 12, 12, 436, 22);
            Place(_tokens, 12, 40, 436, 22);
            Place(_bar, 12, 68, 436, 18);
            Place(_mode, 12, 100, 80, 26);
            Place(_limit, 100, 100, 80, 26);
            Place(_now, 190, 99, 125, 28);
            Place(_cancel, 323, 99, 125, 28);
            // The limit in thousands of tokens. A change is saved at once, no restart needed.
            _limit.Minimum = 1; _limit.Maximum = 2000; _limit.Increment = 10;
            _limit.Value = Math.Min(2000, Math.Max(1, _settings.ThresholdTokens / 1000));
            _limit.ValueChanged += (s, e) => { _settings.ThresholdTokens = (long)_limit.Value * 1000; SaveSettings(); };
            Place(_status, 12, 140, 436, 66);
            _mode.DropDownStyle = ComboBoxStyle.DropDownList;
            _mode.Items.AddRange(new object[] { "Auto", "Ask", "Off" });
            _mode.SelectedItem = _mode.Items.Contains(_settings.Mode) ? _settings.Mode : "Auto";
            _mode.SelectedIndexChanged += (s, e) => { _settings.Mode = (string)_mode.SelectedItem!; SaveSettings(); };
            _now.Text = "HANDOFF NOW"; _now.ForeColor = Color.Black; _now.BackColor = Color.Gainsboro;
            _cancel.Text = "CANCEL / SKIP"; _cancel.ForeColor = Color.Black; _cancel.BackColor = Color.Gainsboro;
            _now.Click += (s, e) => { if (_state != null) { _fireAt = null; _ = RunHandoff(_state); } };
            _cancel.Click += (s, e) =>
            {
                _fireAt = null;
                if (_state != null) _handled.Add(_state.Path);   // no automatic handoff for this session again
                Say("Skipped for this session.");
            };

            _tray.Icon = SystemIcons.Application;
            _tray.Text = "Claude Context Monitor";
            _tray.Visible = true;
            _tray.DoubleClick += (s, e) => { Show(); WindowState = FormWindowState.Normal; Activate(); };
            var menu = new ContextMenuStrip();
            menu.Items.Add("Exit", null, (s, e) => Close());
            _tray.ContextMenuStrip = menu;
            Resize += (s, e) => { if (WindowState == FormWindowState.Minimized) Hide(); };   // minimise = go to the tray
            FormClosed += (s, e) => _tray.Dispose();

            _timer.Interval = 2000;
            _timer.Tick += (s, e) => Tick();
            _timer.Start();
            Tick();
        }

        private void Place(Control c, int x, int y, int w, int h) { c.SetBounds(x, y, w, h); Controls.Add(c); }

        /// <summary>Runs every 2 seconds: read the newest transcript, show it, and decide about the handoff.</summary>
        private void Tick()
        {
            if (_running) return;
            try
            {
                string? path = Transcript.FindNewest(_roots);
                if (path == null) { _session.Text = "No session transcript found."; _tokens.Text = ""; return; }
                SessionState s = Transcript.Read(path);
                _state = s;
                long limit = Math.Max(1, _settings.ThresholdTokens);
                _session.Text = s.Title.Length > 0 ? s.Title : s.SessionId;
                _tokens.Text = "CTX " + (s.Tokens / 1000) + "k / " + (limit / 1000) + "k  (" + (s.Tokens * 100 / limit) + "%)";
                _bar.Value = (int)Math.Min(100, s.Tokens * 100 / limit);
                _tray.Text = "Claude context " + (s.Tokens / 1000) + "k / " + (limit / 1000) + "k";


                double idle = (DateTime.UtcNow - s.LastWriteUtc).TotalSeconds;
                bool due = _settings.Mode != "Off" && !_handled.Contains(s.Path) && s.Tokens >= limit
                        && s.TurnDone && idle >= _settings.IdleSeconds && idle <= _settings.MaxAgeMinutes * 60;
                if (!due) { _fireAt = null; return; }

                if (_settings.Mode == "Ask") { Say("Over the limit. Press HANDOFF NOW, or CANCEL / SKIP."); return; }
                if (_fireAt == null)
                {
                    _fireAt = DateTime.UtcNow.AddSeconds(_settings.CountdownSeconds);
                    _tray.ShowBalloonTip(3000, "Claude Context Monitor",
                        "Context is at " + (s.Tokens / 1000) + "k. New chat in " + _settings.CountdownSeconds + " s. Open the monitor to cancel.", ToolTipIcon.Info);
                    Say("Handoff in " + _settings.CountdownSeconds + " s. Press CANCEL / SKIP to stop it.");
                }
                else if (DateTime.UtcNow >= _fireAt) _ = RunHandoff(s);
            }
            catch (Exception ex) { Say("Read error: " + ex.Message); }
        }

        /// <summary>
        /// The handoff: open a new chat, paste the handoff prompt, press Enter.
        /// It stops at once when Claude Desktop is not the foreground window.
        /// </summary>
        private async Task RunHandoff(SessionState s)
        {
            _running = true; _fireAt = null;
            _handled.Add(s.Path);   // one handoff for each session, also when a step fails. This prevents a loop.
            try
            {
                IntPtr hwnd = Native.ClaudeForeground();
                if (hwnd == IntPtr.Zero)
                {
                    Native.ActivateClaude();   // bring Claude to the front, so no click is needed
                    await Task.Delay(600);
                    hwnd = Native.ClaudeForeground();
                }
                if (hwnd == IntPtr.Zero) { Say("Stopped: Claude Desktop did not come to the front."); return; }
                string prompt = Transcript.BuildPrompt(s);

                List<string> names = _settings.NewChatNames;
                bool pressed = await Task.Run(() => Native.InvokeByNames(hwnd, names));
                if (!pressed) Native.Chord(_settings.NewChatShortcut);
                await Task.Delay(1500);   // let the new chat open and focus its input box
                if (Native.ClaudeForeground() == IntPtr.Zero) { Say("Stopped: Claude lost the focus."); return; }

                string? saved = null;
                try { if (Clipboard.ContainsText()) saved = Clipboard.GetText(); } catch { /* clipboard busy */ }
                Clipboard.SetText(prompt);
                Native.Chord("Ctrl+V");
                await Task.Delay(700);
                if (Native.ClaudeForeground() == IntPtr.Zero) { Say("Stopped before Enter: Claude lost the focus."); return; }
                Native.Chord("Enter");
                await Task.Delay(500);
                try { if (saved != null) Clipboard.SetText(saved); } catch { /* the old clipboard text is lost, not fatal */ }

                Log("handoff session=" + s.SessionId + " tokens=" + s.Tokens + " newChat=" + (pressed ? "button" : "shortcut"));
                Say("Handoff sent at " + DateTime.Now.ToString("HH:mm:ss") + " (" + (pressed ? "button" : "shortcut " + _settings.NewChatShortcut) + ").");
            }
            catch (Exception ex) { Say("Handoff failed: " + ex.Message); Log("handoff failed: " + ex.Message); }
            finally { _running = false; }
        }

        private void Say(string text) { _status.Text = text; }

        /// <summary>The log holds numbers and ids only. No prompt text is written.</summary>
        private static void Log(string line)
        {
            try { File.AppendAllText(Path.Combine(DataDir, "log.txt"), DateTime.Now.ToString("s") + " " + line + Environment.NewLine); }
            catch { /* a log must never stop the program */ }
        }

        private static Settings LoadSettings()
        {
            string file = Path.Combine(DataDir, "settings.json");
            try { if (File.Exists(file)) return JsonSerializer.Deserialize<Settings>(File.ReadAllText(file)) ?? new Settings(); }
            catch { /* a broken file gives the defaults */ }
            var fresh = new Settings();
            try { File.WriteAllText(file, JsonSerializer.Serialize(fresh, new JsonSerializerOptions { WriteIndented = true })); } catch { }
            return fresh;
        }

        private void SaveSettings()
        {
            try { File.WriteAllText(Path.Combine(DataDir, "settings.json"), JsonSerializer.Serialize(_settings, new JsonSerializerOptions { WriteIndented = true })); }
            catch { /* settings are a convenience */ }
        }
    }
}
