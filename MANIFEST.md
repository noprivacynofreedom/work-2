# Atlas response selection and copy patch

## Modified
- `index.html` — forces selectable text in the chat log for Chromium/Tauri WebView, adds a per-assistant-message `COPY RESPONSE` control, and makes code-block copy use a clipboard API plus `execCommand` fallback.

## Added
- `INSTALL-ATLAS-SELECTION-FIX.ps1` — backs up the existing root `index.html` and installs this replacement.
- `ROLLBACK.txt` — restoration instructions.
- `TEST-RESULTS.md` — validation performed in the patch build environment.

## Not changed
No Rust, React shell, Python, MCP, bot data, chat history, settings, or knowledge-library data files are modified by this focused patch.
