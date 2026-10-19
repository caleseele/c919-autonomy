$ErrorActionPreference = "Stop"
$proj = "C:\Users\希儿\Projects\c919-autonomy"
Set-Location $proj
$BLENDER = "C:\Blender\blender-5.2.2-windows-x64\blender.exe"
Write-Host "PROJ=$proj"
$txt = Get-Content scripts\build_c919.py -Raw -Encoding UTF8
if ($txt -match 'mask_obj = link\("CockpitMask"') { throw "CockpitMask link still present" }
if ($txt -notmatch 'punch_windshield_openings\(bpy\.data\.objects\.get\("Nose"\)\)') { throw "punch not enabled" }
if ($txt -notmatch 'Transmission Weight", 1\.0\)') { throw "glass transmission not 1.0" }
if ($txt -notmatch 'cockpit_pane_mesh') { throw "pane mesh missing" }
$i0 = $txt.IndexOf("def cabin_door_frames"); $i1 = $txt.IndexOf("def cabin_door_windows")
$blk = $txt.Substring($i0, $i1 - $i0)
if ($blk -match '(?m)^\s*add_rounded_frame\(') { throw "door2 broken" }
Write-Host "GUARDS_OK"
if (Test-Path public\models\c919.glb) {
  Copy-Item public\models\c919.glb public\models\c919.glb.bak-ws3 -Force
}
& $BLENDER --factory-startup -b -P scripts\build_c919.py
if ($LASTEXITCODE -ne 0) { throw "build failed" }
Get-Item public\models\c919.glb | Format-Table Name, Length
& $BLENDER --factory-startup -b -P scripts\render_ws3.py
if ($LASTEXITCODE -ne 0) { throw "render failed" }
Write-Host "WS3_ALL_DONE"
