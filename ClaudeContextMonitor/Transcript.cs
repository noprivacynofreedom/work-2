using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace ClaudeContextMonitor
{
    /// <summary>What the monitor knows about one Claude Code session transcript.</summary>
    public sealed class SessionState
    {
        public string Path = "";
        public string SessionId = "";
        public string Cwd = "";
        public string Title = "";
        /// <summary>Context size of the last main-chain assistant line. 0 = not known.</summary>
        public long Tokens;
        /// <summary>True when the last line is an assistant answer with no tool call pending.</summary>
        public bool TurnDone;
        public DateTime LastWriteUtc;
        public List<string> UserGoals = new List<string>();
        public List<string> Findings = new List<string>();
        public List<string> Files = new List<string>();
    }

    /// <summary>
    /// Reads Claude Code JSONL transcripts. Pure file reading, no UI and no Windows calls.
    /// The file is opened read-only and shared, so Claude can keep writing to it.
    /// </summary>
    public static class Transcript
    {
        /// <summary>Only the tail is read. 4 MB holds many turns and keeps each poll fast.</summary>
        private const int TailBytes = 4 * 1024 * 1024;

        /// <summary>Returns the transcript that changed last, or null. Sub-agent files are skipped.</summary>
        public static string? FindNewest(IEnumerable<string> roots)
        {
            string? best = null;
            DateTime bestTime = DateTime.MinValue;
            foreach (string root in roots)
            {
                try
                {
                    if (!Directory.Exists(root)) continue;
                    foreach (string file in Directory.EnumerateFiles(root, "*.jsonl", SearchOption.AllDirectories))
                    {
                        if (file.IndexOf("subagents", StringComparison.OrdinalIgnoreCase) >= 0) continue;
                        DateTime t = File.GetLastWriteTimeUtc(file);
                        if (t > bestTime) { bestTime = t; best = file; }
                    }
                }
                catch { /* A folder we cannot read is not an error. Try the next root. */ }
            }
            return best;
        }

        /// <summary>Reads one transcript. Bad lines are skipped, so a half-written last line does no harm.</summary>
        public static SessionState Read(string path)
        {
            var s = new SessionState { Path = path, LastWriteUtc = File.GetLastWriteTimeUtc(path) };
            s.SessionId = System.IO.Path.GetFileNameWithoutExtension(path);
            string text;
            bool cut;
            using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
            {
                cut = fs.Length > TailBytes;
                if (cut) fs.Seek(-TailBytes, SeekOrigin.End);
                using (var sr = new StreamReader(fs, Encoding.UTF8)) text = sr.ReadToEnd();
            }
            string[] lines = text.Split('\n');
            for (int i = cut ? 1 : 0; i < lines.Length; i++)   // after a seek the first line is partial
            {
                string line = lines[i].Trim();
                if (line.Length == 0) continue;
                try { using (JsonDocument doc = JsonDocument.Parse(line)) ReadLine(doc.RootElement, s); }
                catch { /* not JSON, or a shape we do not know */ }
            }
            if (s.Title.Length == 0 && s.UserGoals.Count > 0) s.Title = Clip(s.UserGoals[0], 80);
            return s;
        }

        private static void ReadLine(JsonElement e, SessionState s)
        {
            if (e.ValueKind != JsonValueKind.Object) return;
            if (e.TryGetProperty("isSidechain", out JsonElement side) && side.ValueKind == JsonValueKind.True) return;
            string cwd = Str(e, "cwd"); if (cwd.Length > 0) s.Cwd = cwd;
            string type = Str(e, "type");

            if (type == "summary") { string t = Str(e, "summary"); if (t.Length > 0) s.Title = t; return; }
            if (type == "ai-title") { string t = Str(e, "aiTitle"); if (t.Length > 0) s.Title = t; return; }
            if (type == "custom-title") { string t = Str(e, "customTitle"); if (t.Length > 0) s.Title = t; return; }
            if (!e.TryGetProperty("message", out JsonElement msg) || msg.ValueKind != JsonValueKind.Object) return;
            if (!msg.TryGetProperty("content", out JsonElement content)) return;

            if (type == "user")
            {
                if (e.TryGetProperty("isMeta", out JsonElement meta) && meta.ValueKind == JsonValueKind.True) return;
                s.TurnDone = false;   // a prompt or a tool result: Claude still has to answer
                string t = content.ValueKind == JsonValueKind.String ? (content.GetString() ?? "") : TextBlocks(content);
                t = t.Trim();
                // Lines that start with "<" are slash commands and system notes, not goals.
                if (t.Length > 0 && !t.StartsWith("<") && !t.StartsWith("Caveat:")) s.UserGoals.Add(t);
            }
            else if (type == "assistant")
            {
                if (msg.TryGetProperty("usage", out JsonElement u) && u.ValueKind == JsonValueKind.Object)
                {
                    long sum = Num(u, "input_tokens") + Num(u, "cache_read_input_tokens")
                             + Num(u, "cache_creation_input_tokens") + Num(u, "output_tokens");
                    if (sum > 0) s.Tokens = sum;   // last line wins, so /compact shows the smaller number
                }
                bool tool = Str(msg, "stop_reason") == "tool_use";
                if (content.ValueKind == JsonValueKind.Array)
                {
                    foreach (JsonElement b in content.EnumerateArray())
                    {
                        if (b.ValueKind != JsonValueKind.Object) continue;
                        string bt = Str(b, "type");
                        if (bt == "text") { string t = Str(b, "text").Trim(); if (t.Length > 0) s.Findings.Add(t); }
                        else if (bt == "tool_use")
                        {
                            tool = true;
                            if (b.TryGetProperty("input", out JsonElement inp) && inp.ValueKind == JsonValueKind.Object)
                                foreach (string key in new[] { "file_path", "path", "notebook_path" })
                                {
                                    string f = Str(inp, key);
                                    if (f.Length > 0) { s.Files.Remove(f); s.Files.Add(f); }
                                }
                        }
                    }
                }
                s.TurnDone = !tool;
            }
        }

        /// <summary>
        /// Builds the handoff prompt for the new chat: where the work is, the last goals,
        /// the last answers, the files touched, and where the full transcript is.
        /// </summary>
        public static string BuildPrompt(SessionState s)
        {
            var sb = new StringBuilder();
            sb.AppendLine("This chat continues an earlier session that reached its context limit. Use the handoff below.");
            sb.AppendLine();
            sb.AppendLine("## Handoff");
            sb.AppendLine("- Previous session: " + (s.Title.Length > 0 ? s.Title : "(no title)") + " (" + s.SessionId + ")");
            if (s.Cwd.Length > 0) sb.AppendLine("- Working folder: " + s.Cwd);
            sb.AppendLine("- Context at handoff: " + s.Tokens + " tokens");
            sb.AppendLine("- Full transcript (read only the parts you need): " + s.Path);
            sb.AppendLine();
            sb.AppendLine("### Last user goals (oldest first)");
            foreach (string g in s.UserGoals.Skip(Math.Max(0, s.UserGoals.Count - 4))) sb.AppendLine("- " + Clip(g, 360));
            sb.AppendLine();
            sb.AppendLine("### Last assistant findings (oldest first)");
            foreach (string f in s.Findings.Skip(Math.Max(0, s.Findings.Count - 3))) sb.AppendLine("- " + Clip(f, 420));
            if (s.Files.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("### Files touched last");
                foreach (string f in s.Files.Skip(Math.Max(0, s.Files.Count - 12))) sb.AppendLine("- " + f);
            }
            sb.AppendLine();
            sb.AppendLine("### What to do now");
            sb.AppendLine("Continue the work from the last goal. First state in 3 lines what is done and what is next. Then do the next step.");
            return sb.ToString();
        }

        private static string TextBlocks(JsonElement content)
        {
            if (content.ValueKind != JsonValueKind.Array) return "";
            var sb = new StringBuilder();
            foreach (JsonElement b in content.EnumerateArray())
                if (b.ValueKind == JsonValueKind.Object && Str(b, "type") == "text") sb.Append(Str(b, "text")).Append(' ');
            return sb.ToString();
        }

        private static string Str(JsonElement e, string name) =>
            e.TryGetProperty(name, out JsonElement v) && v.ValueKind == JsonValueKind.String ? (v.GetString() ?? "") : "";

        private static long Num(JsonElement e, string name) =>
            e.TryGetProperty(name, out JsonElement v) && v.ValueKind == JsonValueKind.Number && v.TryGetInt64(out long n) ? n : 0;

        /// <summary>One line, at most max characters.</summary>
        private static string Clip(string t, int max)
        {
            t = string.Join(" ", t.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
            return t.Length <= max ? t : t.Substring(0, max) + "...";
        }
    }
}
