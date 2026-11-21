@echo off
set "ATLAS_PROJECT_ROOT=%~dp0."
start "Atlas Chat" "%~dp0atlas-rust-desktop\src-tauri\target\release\atlas-desktop.exe"
