# Bootstrap gold reference documents for lab_ec_sw validation
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\demo\bootstrap_lab_gold.ps1

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$LabDir = Join-Path $Root 'data\cases\lab_ec_sw'
$RefDir = Join-Path $Root 'data\cases\jm_collection'

New-Item -ItemType Directory -Path $LabDir -Force | Out-Null

Copy-Item (Join-Path $RefDir 'output_mdsr.docx') (Join-Path $LabDir 'gold_mdsr.docx') -Force
Copy-Item (Join-Path $RefDir 'output_mddr.docx') (Join-Path $LabDir 'gold_mddr.docx') -Force

Write-Host "Gold documents copied to $LabDir"
Write-Host "  gold_mdsr.docx"
Write-Host "  gold_mddr.docx"
