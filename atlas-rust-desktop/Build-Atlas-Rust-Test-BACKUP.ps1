



param([switch]$Dev)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Project = Split-Path -Parent $Root
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) { throw 'Rust/Cargo is missing. Install Rust using https://rustup.rs, reopen PowerShell, then rerun this script.' }
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) { throw 'rustc is missing. Install the stable Rust toolchain with rustup.' }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw 'Node.js/npm is missing. Install the current Node.js LTS release.' }
$Linker = Get-Command link.exe -ErrorAction SilentlyContinue
if (-not $Linker) {
  $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
  if (Test-Path $vswhere) {
    $vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if ($vs) {
      $vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
      if (Test-Path $vcvars) {
        Write-Host 'MSVC linker is installed but not loaded in this shell. Open "x64 Native Tools PowerShell for VS 2022" or run this build from a Developer PowerShell.' -ForegroundColor Yellow
      }
    }
  }
  throw 'MSVC linker link.exe was not found. Install Visual Studio 2022 Build Tools with Desktop development with C++ (MSVC v143, Windows 10/11 SDK), then reopen an x64 Native Tools PowerShell and rerun this build. VS Code alone is not enough.'
}
$env:ATLAS_PROJECT_ROOT = $Project
Push-Location $Root
try {
  if (-not (Test-Path 'node_modules\@tauri-apps\cli')) {
    Write-Host 'Installing desktop frontend/build dependencies...' -ForegroundColor Cyan
    npm install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed. See the npm output above.' }
  }
  if ($Dev) {
    npm run tauri dev
    if ($LASTEXITCODE -ne 0) { throw 'Tauri development run failed. See the Vite/Cargo output above.' }
  } else {
    npm run tauri build
    if ($LASTEXITCODE -ne 0) { throw 'Tauri release build failed. See the Vite/Cargo output above.' }
    $exe = Join-Path $Root 'src-tauri\target\release\atlas-desktop.exe'
    if (-not (Test-Path $exe)) { throw "Build returned but executable not found: $exe" }
    $bat = Join-Path $Project 'Start Atlas Chat (Rust).bat'
    @('@echo off', ('set "ATLAS_PROJECT_ROOT={0}"' -f $Project), ('start "Atlas Chat" "{0}"' -f $exe)) | Set-Content -LiteralPath $bat -Encoding ASCII
    Write-Host "Build succeeded: $exe" -ForegroundColor Green
    Write-Host "Created launcher: $bat" -ForegroundColor Cyan
  }
} finally { Pop-Location }
