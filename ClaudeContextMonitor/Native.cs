using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Automation;

namespace ClaudeContextMonitor
{
    /// <summary>Windows calls: find the Claude Desktop window, press its buttons, send keys.</summary>
    public static class Native
    {
        [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassName(IntPtr hWnd, StringBuilder text, int max);
        [DllImport("user32.dll", SetLastError = true)] private static extern uint SendInput(uint count, INPUT[] inputs, int size);

        [StructLayout(LayoutKind.Sequential)] private struct INPUT { public uint type; public InputUnion U; }
        [StructLayout(LayoutKind.Explicit)] private struct InputUnion
        {
            [FieldOffset(0)] public MOUSEINPUT mi;
            [FieldOffset(0)] public KEYBDINPUT ki;
        }
        [StructLayout(LayoutKind.Sequential)] private struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr dwExtraInfo; }
        [StructLayout(LayoutKind.Sequential)] private struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public IntPtr dwExtraInfo; }

        /// <summary>
        /// Returns the Claude Desktop window when it is the foreground window, else zero.
        /// Every keystroke goes through this check first, so keys never reach another program.
        /// </summary>
        public static IntPtr ClaudeForeground()
        {
            try
            {
                IntPtr h = GetForegroundWindow();
                if (h == IntPtr.Zero) return IntPtr.Zero;
                var cls = new StringBuilder(64);
                GetClassName(h, cls, cls.Capacity);
                if (cls.ToString() != "Chrome_WidgetWin_1") return IntPtr.Zero;
                GetWindowThreadProcessId(h, out uint pid);
                using (Process p = Process.GetProcessById((int)pid))
                    return string.Equals(p.ProcessName, "claude", StringComparison.OrdinalIgnoreCase) ? h : IntPtr.Zero;
            }
            catch { return IntPtr.Zero; }
        }

        /// <summary>Returns the main Claude Desktop window, in front or not. Used by --uia-dump.</summary>
        public static IntPtr ClaudeWindow()
        {
            foreach (Process p in Process.GetProcessesByName("claude"))
                if (p.MainWindowHandle != IntPtr.Zero) return p.MainWindowHandle;
            return IntPtr.Zero;
        }

        [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] private static extern bool IsIconic(IntPtr hWnd);
        [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr hWnd, int cmd);

        /// <summary>
        /// Brings Claude Desktop to the front, so the user does not have to click it.
        /// Windows blocks focus changes from background programs. A tap on Alt lifts that block.
        /// </summary>
        public static void ActivateClaude()
        {
            IntPtr h = ClaudeWindow();
            if (h == IntPtr.Zero) return;
            if (IsIconic(h)) ShowWindow(h, 9);   // 9 = restore a minimised window
            Chord("Alt");
            SetForegroundWindow(h);
        }

        /// <summary>Presses the first control whose name is in the list. Returns false when none is found.</summary>
        public static bool InvokeByNames(IntPtr hwnd, IEnumerable<string> names)
        {
            try
            {
                AutomationElement root = AutomationElement.FromHandle(hwnd);
                foreach (string name in names)
                {
                    AutomationElement? el = root.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.NameProperty, name, PropertyConditionFlags.IgnoreCase));
                    if (el != null && el.TryGetCurrentPattern(InvokePattern.Pattern, out object pattern))
                    {
                        ((InvokePattern)pattern).Invoke();
                        return true;
                    }
                }
            }
            catch { /* UI Automation fails often on Electron. The caller uses the shortcut then. */ }
            return false;
        }

        /// <summary>Lists the type and name of every named control in the Claude window.</summary>
        public static string Dump(IntPtr hwnd)
        {
            var sb = new StringBuilder();
            AutomationElement root = AutomationElement.FromHandle(hwnd);
            foreach (AutomationElement el in root.FindAll(TreeScope.Descendants, Condition.TrueCondition))
            {
                try
                {
                    string name = el.Current.Name;
                    if (!string.IsNullOrWhiteSpace(name) && name.Length <= 80)
                        sb.AppendLine(el.Current.ControlType.ProgrammaticName + "\t" + name);
                }
                catch { /* the control went away while we read it */ }
            }
            return sb.ToString();
        }

        /// <summary>Sends a shortcut written as text, for example "Ctrl+Shift+O" or "Enter".</summary>
        public static void Chord(string shortcut)
        {
            var keys = new List<ushort>();
            foreach (string raw in shortcut.Split('+'))
            {
                string k = raw.Trim().ToUpperInvariant();
                if (k == "CTRL") keys.Add(0x11);
                else if (k == "SHIFT") keys.Add(0x10);
                else if (k == "ALT") keys.Add(0x12);
                else if (k == "ENTER") keys.Add(0x0D);
                else if (k.Length == 1) keys.Add(k[0]);   // letters and digits: the key code equals the character
            }
            var inputs = new INPUT[keys.Count * 2];
            for (int i = 0; i < keys.Count; i++)
            {
                inputs[i] = Key(keys[i], false);                               // down, in order
                inputs[keys.Count * 2 - 1 - i] = Key(keys[i], true);           // up, in reverse order
            }
            if (inputs.Length > 0) SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT)));
        }

        private static INPUT Key(ushort vk, bool up)
        {
            var input = new INPUT { type = 1 };   // 1 = keyboard
            input.U.ki = new KEYBDINPUT { wVk = vk, dwFlags = up ? 2u : 0u };   // 2 = key up
            return input;
        }
    }
}
