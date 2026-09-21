$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Out = Join-Path $Root 'data\cases\jm_collection\gap_analysis.txt'
$docs = @(
    @{ n='template'; f='data\templates\ec_sw\template_mdsr.docx' },
    @{ n='filled';  f='data\examples\ec_sw\spec_mdsr_EC-SW-MDSR(XA)_소프트웨어_요구사항명세서.docx' },
    @{ n='output';  f='data\cases\jm_collection\output_mdsr.docx' }
)
$lines = @('MDSR GAP ANALYSIS (PowerShell)', '')

function Get-DocxTables($path) {
    $tmp = Join-Path $env:TEMP ("mdsr_" + [guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        Copy-Item $path (Join-Path $tmp 'd.zip')
        Expand-Archive -Path (Join-Path $tmp 'd.zip') -DestinationPath (Join-Path $tmp 'x') -Force
        [xml]$xml = Get-Content (Join-Path $tmp 'x\word\document.xml') -Encoding UTF8
        $paras = @()
        $mgr = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
        $mgr.AddNamespace('w', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
        foreach ($p in $xml.SelectNodes('//w:body/w:p', $mgr)) {
            $txt = ($p.SelectNodes('.//w:t', $mgr) | ForEach-Object { $_.InnerText }) -join ''
            if ($txt.Trim()) { $paras += $txt.Trim() }
        }
        $tables = @()
        foreach ($tbl in $xml.SelectNodes('//w:body/w:tbl', $mgr)) {
            $matrix = @()
            foreach ($tr in $tbl.SelectNodes('./w:tr', $mgr)) {
                $row = @()
                foreach ($tc in $tr.SelectNodes('./w:tc', $mgr)) {
                    $cell = ($tc.SelectNodes('.//w:t', $mgr) | ForEach-Object { $_.InnerText }) -join ''
                    $row += $cell.Trim()
                }
                $matrix += ,@($row)
            }
            $tables += ,@($matrix)
        }
        return @{ paras = $paras; tables = $tables }
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Req-Num($matrix) {
    foreach ($row in $matrix) {
        if ($row.Count -gt 0 -and $row[0] -match 'Req\.\s*(\d+)') { return [int]$Matches[1] }
    }
    return $null
}

$results = @{}
foreach ($d in $docs) {
    $p = Join-Path $Root $d.f
    $lines += ('=' * 80)
    $lines += "DOCUMENT: $($d.n)"
    $lines += "PATH: $p"
    if (-not (Test-Path $p)) { $lines += 'ERROR: not found'; continue }
    $parsed = Get-DocxTables $p
    $results[$d.n] = $parsed
    $lines += "Non-empty paragraphs: $($parsed.paras.Count)"
    for ($i=0; $i -lt $parsed.paras.Count; $i++) {
        $t = $parsed.paras[$i]
        if ($t.Length -gt 200) { $t = $t.Substring(0,200) }
        $lines += "  P[$i]: $t"
    }
    $trace = $null
    for ($ti=0; $ti -lt $parsed.tables.Count; $ti++) {
        foreach ($row in $parsed.tables[$ti]) {
            if ($row.Count -gt 0 -and $row[0].StartsWith('IA-01')) { $trace = $ti; break }
        }
    }
    $lines += "Total tables: $($parsed.tables.Count)"
    $lines += "Traceability index: $trace"
    $show = 0..([Math]::Min(7, $parsed.tables.Count-1))
    if ($null -ne $trace) { $show = @($show + $trace) | Select-Object -Unique }
    foreach ($ti in ($show | Sort-Object)) {
        $m = $parsed.tables[$ti]
        $cols = if ($m.Count -gt 0) { $m[0].Count } else { 0 }
        $lines += "--- Table ${ti}: $($m.Count) rows x $cols cols ---"
        for ($ri=0; $ri -lt $m.Count; $ri++) {
            $cells = ($m[$ri] | ForEach-Object { if ($_.Length -gt 120) { $_.Substring(0,120) } else { $_ } }) -join ' | '
            $lines += "  | $cells"
        }
    }
    $reqCount = 0; $rf=0; $re=0
    foreach ($ti in 0..($parsed.tables.Count-1)) {
        $rn = Req-Num $parsed.tables[$ti]
        if ($null -eq $rn) { continue }
        $reqCount++
        foreach ($row in $parsed.tables[$ti]) {
            foreach ($c in $row) {
                if ([string]::IsNullOrWhiteSpace($c)) { $re++ } else { $rf++ }
            }
        }
        if (@(1,2,10,101,105) -contains $rn) {
            $lines += "Req.$rn @ table $ti :"
            for ($ri=0; $ri -lt [Math]::Min(4, $parsed.tables[$ti].Count); $ri++) {
                $row = $parsed.tables[$ti][$ri]
                $c0 = if ($row.Count -gt 0) { $row[0] } else { '' }
                $lines += "    row${ri} col0=$c0"
                for ($ci=0; $ci -lt $row.Count; $ci++) {
                    $v = $row[$ci]; if ($v.Length -gt 80) { $v = $v.Substring(0,80) }
                    $lines += "      [$ri,$ci]=$v"
                }
            }
        }
    }
    $lines += "Req tables=$reqCount filled_cells=$rf empty_cells=$re"
}

$lines += ('=' * 80)
$lines += 'GAP ANALYSIS'
if ($results.ContainsKey('output') -and $results.ContainsKey('filled')) {
    $out = $results['output']; $fill = $results['filled']
    $lines += '--- Output EMPTY but filled has content ---'
    $maxT = [Math]::Min($out.tables.Count, $fill.tables.Count)
    for ($ti=0; $ti -lt $maxT; $ti++) {
        $om = $out.tables[$ti]; $fm = $fill.tables[$ti]
        $maxR = [Math]::Max($om.Count, $fm.Count)
        for ($ri=0; $ri -lt $maxR; $ri++) {
            $orow = if ($ri -lt $om.Count) { $om[$ri] } else { @() }
            $frow = if ($ri -lt $fm.Count) { $fm[$ri] } else { @() }
            $maxC = [Math]::Max($orow.Count, $frow.Count)
            for ($ci=0; $ci -lt $maxC; $ci++) {
                $oc = if ($ci -lt $orow.Count) { $orow[$ci] } else { '' }
                $fc = if ($ci -lt $frow.Count) { $frow[$ci] } else { '' }
                if ([string]::IsNullOrWhiteSpace($oc) -and -not [string]::IsNullOrWhiteSpace($fc)) {
                    $ex = $fc; if ($ex.Length -gt 80) { $ex = $ex.Substring(0,80) }
                    $lines += "  table=$ti row=$ri col=$ci example=$ex"
                }
            }
        }
    }
}
$pat = '(?i)mindrium|Mindrium|범불안|의료기기|환자|IEC\s*62304|ISO\s*14971|EC-SW-MDSR\(XA\)|식약처'
if ($results.ContainsKey('output')) {
    $lines += '--- Residual Mindrium/medical in OUTPUT ---'
    $hits = 0
    $out = $results['output']
    for ($ti=0; $ti -lt $out.tables.Count; $ti++) {
        for ($ri=0; $ri -lt $out.tables[$ti].Count; $ri++) {
            for ($ci=0; $ci -lt $out.tables[$ti][$ri].Count; $ci++) {
                $c = $out.tables[$ti][$ri][$ci]
                if ($c -match $pat) {
                    $hits++
                    $v = $c; if ($v.Length -gt 140) { $v = $v.Substring(0,140) }
                    $lines += "  table=$ti row=$ri col=$ci : $v"
                }
            }
        }
    }
    for ($i=0; $i -lt $out.paras.Count; $i++) {
        if ($out.paras[$i] -match $pat) {
            $hits++
            $v = $out.paras[$i]; if ($v.Length -gt 140) { $v = $v.Substring(0,140) }
            $lines += "  para P[$i]: $v"
        }
    }
    if ($hits -eq 0) { $lines += '  (none matched)' }
}

Set-Content -Path $Out -Value $lines -Encoding UTF8
Write-Output "Wrote $Out ($($lines.Count) lines)"
