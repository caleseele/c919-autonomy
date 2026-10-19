$ErrorActionPreference = "Stop"
$proj = (Get-ChildItem "C:\Users" -Directory | ForEach-Object {
  $p = Join-Path $_.FullName "Projects\c919-autonomy"
  if (Test-Path (Join-Path $p "scripts\build_c919.py")) { $p }
} | Select-Object -First 1)
if (-not $proj) { throw "project not found" }
Set-Location $proj
$BLENDER = "C:\Blender\blender-5.2.2-windows-x64\blender.exe"
Write-Host "PROJ=$proj"

$txt = Get-Content scripts\build_c919.py -Raw -Encoding UTF8
if ($txt -match '(?m)^\s*punch_windshield_openings\(') { throw "punch still enabled" }
if ($txt -notmatch 'DISABLED ws4|ws4: NO face-delete') { throw "ws4 punch disable marker missing" }
Write-Host "GUARDS_OK continuous skin build"

& $BLENDER --factory-startup -b -P scripts\build_c919.py
if ($LASTEXITCODE -ne 0) { throw "build failed" }
Get-Item public\models\c919.glb | Format-Table Name, Length

Write-Host "Starting GUI knife_project pass..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $BLENDER
$psi.Arguments = "--factory-startup --python `"$proj\scripts\ws4_knife_project_windshield.py`""
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$proc = [System.Diagnostics.Process]::Start($psi)
$out = $proc.StandardOutput.ReadToEnd()
$err = $proc.StandardError.ReadToEnd()
if (-not $proc.WaitForExit(600000)) { $proc.Kill(); throw "knife pass timeout" }
Write-Host $out
if ($err) { Write-Host "STDERR_TAIL:"; Write-Host ($err.Substring([Math]::Max(0, $err.Length - 2500))) }
if ($proc.ExitCode -ne 0) { throw "knife pass exit $($proc.ExitCode)" }
Get-Item public\models\c919.glb | Format-Table Name, Length
Write-Host "WS4_ALL_DONE"
