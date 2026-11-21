# Test results

- Extracted both inline application scripts and ran `node --check`: **PASS**.
- Static regression check for forced `user-select` and `-webkit-user-select` across the chat log: **PASS**.
- Static regression check for a per-assistant-message `COPY RESPONSE` control: **PASS**.
- Static regression check for Clipboard API plus `document.execCommand('copy')` fallback: **PASS**.
- Static regression check that the complete raw assistant response is copied (not rendered HTML): **PASS**.
- Static regression check that the earlier Development Cycle `COPY OUTPUT` control remains present: **PASS**.
- ZIP integrity: to be checked after packaging.

Not run: Windows PowerShell installer execution, interactive text selection in the user's Tauri WebView, and actual Windows clipboard round-trip. Those require the user's Windows desktop runtime.
