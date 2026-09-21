# Document Harness E2E demo — case-intake → harness-generate → document-quality
# Usage: .\scripts\demo\run_document_harness_demo.ps1

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$CaseDir = Join-Path $Root 'data\cases\demo_hospital'
$TextFile = Join-Path $PSScriptRoot 'demo_hospital_intake.txt'
$AuthorOrg = 'Sample Medical IT Co., Ltd.'

function Write-Step([string]$Message) {
    Write-Host ''
    Write-Host ('=' * 72) -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host ('=' * 72) -ForegroundColor Cyan
}

function Invoke-DemoCommand([string]$Label, [string[]]$Arguments, [switch]$AllowNonZero) {
    Write-Host ">> $Label" -ForegroundColor Yellow
    Push-Location $Root
    try {
        & python @Arguments
        if (-not $AllowNonZero -and $LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 2) {
            throw "Command failed (exit $LASTEXITCODE): python $($Arguments -join ' ')"
        }
    } finally {
        Pop-Location
    }
}

Write-Step 'Document Harness Demo — Initialize case directory'
if (Test-Path $CaseDir) {
    Write-Host "Resetting $CaseDir"
    Remove-Item $CaseDir -Recurse -Force
}
New-Item -ItemType Directory -Path $CaseDir -Force | Out-Null
Write-Host "Case directory: $CaseDir"

Write-Step 'Step 1/3 — case-intake (natural language → input.json)'
if (-not (Test-Path $TextFile)) {
    throw "Missing demo text file: $TextFile"
}
Invoke-DemoCommand 'case-intake' @(
    '-m', 'document_ai.cli', 'case-intake',
    '--case', $CaseDir,
    '--text-file', $TextFile,
    '--domain', 'hospital_reservation',
    '--product-name', 'Hospital Reservation System',
    '--product-code', 'HRS',
    '--author-org', $AuthorOrg,
    '--confirm'
)

Write-Step 'Step 2/3 — harness-generate (MDSR / MDDR)'
Invoke-DemoCommand 'harness-generate' @(
    '-m', 'document_ai.cli', 'harness-generate',
    '--case', $CaseDir,
    '--force-form-fill'
) -AllowNonZero

Write-Step 'Step 3/3 — document-quality'
$qualityRaw = ''
Push-Location $Root
try {
    $qualityRaw = & python -m document_ai.cli document-quality --case $CaseDir 2>&1 | Out-String
    Write-Host $qualityRaw
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "document-quality returned exit code $LASTEXITCODE (review quality_report.md)"
    }
} finally {
    Pop-Location
}

Write-Step 'Generated artifacts'
$expected = @(
    'input.json',
    'intake_log.json',
    'requirements.json',
    'mdsr_content.json',
    'design_items.json',
    'output_mdsr.docx',
    'output_mddr.docx',
    'quality_report.md'
)
foreach ($name in $expected) {
    $path = Join-Path $CaseDir $name
    if (Test-Path $path) {
        $size = (Get-Item $path).Length
        Write-Host ("  [OK] {0,-22} {1,10:N0} bytes" -f $name, $size) -ForegroundColor Green
    } else {
        Write-Host ("  [MISSING] {0}" -f $name) -ForegroundColor Red
    }
}

Write-Step 'Quality summary'
$qualityPath = Join-Path $CaseDir 'quality_report.md'
if (Test-Path $qualityPath) {
    Get-Content $qualityPath -Encoding UTF8 | Select-Object -First 20 | ForEach-Object { Write-Host $_ }
} else {
    Write-Warning 'quality_report.md not found'
}

if ($qualityRaw.Trim()) {
    try {
        $quality = $qualityRaw.Trim() | ConvertFrom-Json
        Write-Host ''
        Write-Host 'Key scores:' -ForegroundColor Green
        Write-Host ("  Status:      {0}" -f $quality.status)
        Write-Host ("  Overall:     {0}" -f $quality.scores.overall)
        Write-Host ("  Terminology: {0}" -f $quality.scores.terminology)
        Write-Host ("  Traceability:{0}" -f $quality.scores.traceability)
        Write-Host ("  Structure:   {0}" -f $quality.scores.structure)
    } catch {
        Write-Warning 'Could not parse document-quality JSON output'
    }
}

Write-Step 'Demo complete'
Write-Host "Open documents:"
Write-Host "  MDSR: $(Join-Path $CaseDir 'output_mdsr.docx')"
Write-Host "  MDDR: $(Join-Path $CaseDir 'output_mddr.docx')"
Write-Host "  Report: $(Join-Path $CaseDir 'quality_report.md')"
