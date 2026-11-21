# Claude Context Monitor

A small Windows tray program for Claude Desktop. It is a separate program. It shares no code with Atlas Chat.

It reads the token count of the active Code-tab session. At 150k tokens it opens a new chat,
pastes a handoff prompt (the gist of the last chat) and presses Enter.

## Build and run (PowerShell)
```powershell
dotnet build -c Release
.\bin\Release\net8.0-windows\ClaudeContextMonitor.exe
.\bin\Release\net8.0-windows\ClaudeContextMonitor.exe --uia-dump
```
Needs the .NET 8 SDK. No NuGet packages.

## How it works
1. Every 2 seconds it finds the newest `.jsonl` under `%UserProfile%\.claude\projects`.
2. Context = input + cache read + cache creation + output tokens of the last assistant line.
3. It fires when: tokens >= limit, Claude finished its answer, and the file is idle 8 s. It brings Claude Desktop to the front itself.
4. Auto mode shows a 5 s countdown. CANCEL / SKIP stops it for that session.
5. Keys go out only while Claude Desktop is the foreground window.

Settings: `%AppData%\ClaudeContextMonitor\settings.json`. Log: `log.txt` in the same folder (no prompt text).

## Not verified. This code was not compiled or run before delivery.
- The "new chat" control name. Run `--uia-dump`, read `uia-dump.txt`, put the real name first in `NewChatNames`.
- The fallback shortcut `Ctrl+Shift+O`. Change `NewChatShortcut` if it is wrong.
- The transcript folder for the Code tab. Add other folders to `ExtraRoots`.
- The chat tab keeps no token counts on disk. Only Code-tab sessions are covered.
- "Newest transcript" is taken as the session on screen. A Claude Code terminal session can be picked by mistake.
