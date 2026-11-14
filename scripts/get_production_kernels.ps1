<#
LUNA-OPS: download the pinned production NAIF kernels with PowerShell, check them against the
values NAIF publishes, and install them through the project's own verified pipeline.

Use this only if `python -m lunaops.acquire kernels` cannot reach naif.jpl.nasa.gov (for example
behind a proxy that only Windows networking handles). It downloads nothing but the kernels named in
backend/lunaops/manifests/kernels.production.json (no terrain).

Usage, from the luna-ops folder (Windows PowerShell 5.1 or PowerShell 7):
    powershell -ExecutionPolicy Bypass -File scripts\get_production_kernels.ps1
    powershell -ExecutionPolicy Bypass -File scripts\get_production_kernels.ps1 -Python .venv\Scripts\python.exe
#>
param(
    [string]$Python = "python",
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is very slow with the progress bar in PS 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

$Backend = Join-Path $Root "backend"
$Download = Join-Path $Root "data\kernels_download"
New-Item -ItemType Directory -Force -Path $Download | Out-Null
$Naif = "https://naif.jpl.nasa.gov/pub/naif"

# Name, candidate URLs (in order), NAIF-published size and MD5 where NAIF publishes them, required?
$Kernels = @(
    @{ Name = "naif0012.tls"; Urls = @("$Naif/generic_kernels/lsk/naif0012.tls"); Bytes = 5257; Md5 = "25a2fff30b0dedb4d76c06727b1895b1"; Required = $true },
    @{ Name = "pck00011.tpc"; Urls = @("$Naif/generic_kernels/pck/pck00011.tpc"); Required = $true },
    @{ Name = "de440s.bsp"; Urls = @("$Naif/generic_kernels/spk/planets/de440s.bsp"); ChecksumList = "$Naif/generic_kernels/spk/planets/aa_checksums.txt"; Required = $true },
    @{ Name = "moon_pa_de440_200625.bpc"; Urls = @("$Naif/generic_kernels/pck/moon_pa_de440_200625.bpc"); Required = $true },
    @{ Name = "moon_de440_250416.tf"; Urls = @("$Naif/generic_kernels/fk/satellites/moon_de440_250416.tf",
                                              "$Naif/pds/pds4/clps/clps_spice/spice_kernels/fk/moon_de440_250416.tf");
       Bytes = 19478; Md5 = "3556dde4bb7ca54a89917c301e650bbf"; Required = $false; FallbackFor = "lunar_fk" },
    # superseded by 250416 (IB-2, resolved 2026-11-09); NAIF keeps it only in a_old_versions
    @{ Name = "moon_de440_220930.tf"; Urls = @("$Naif/generic_kernels/fk/satellites/a_old_versions/moon_de440_220930.tf");
       Required = $false; FallbackFor = "lunar_fk" },
    @{ Name = "moon_pa_de421_1900-2050.bpc"; Urls = @("$Naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc"); Required = $false },
    @{ Name = "moon_080317.tf"; Urls = @("$Naif/generic_kernels/fk/satellites/moon_080317.tf"); Required = $false }
)

function Get-Kernel($k) {
    $dest = Join-Path $Download $k.Name
    foreach ($u in $k.Urls) {
        try {
            Write-Host "  downloading $($k.Name) from $u"
            Invoke-WebRequest -Uri $u -OutFile $dest -UseBasicParsing -UserAgent "LUNA-OPS/0.1 (data acquisition)"
        } catch {
            Write-Host "    failed: $($_.Exception.Message)"
            if (Test-Path $dest) { Remove-Item $dest -Force }
            continue
        }
        $size = (Get-Item $dest).Length
        if ($k.Bytes -and $size -ne $k.Bytes) {
            Write-Host "    REJECTED: $size bytes, NAIF publishes $($k.Bytes)"; Remove-Item $dest -Force; continue
        }
        if ($k.Md5) {
            $md5 = (Get-FileHash -Algorithm MD5 -Path $dest).Hash.ToLower()
            if ($md5 -ne $k.Md5) { Write-Host "    REJECTED: MD5 $md5, NAIF publishes $($k.Md5)"; Remove-Item $dest -Force; continue }
            Write-Host "    MD5 matches the NAIF-published value"
        }
        if ($k.ChecksumList) {
            try {
                $list = (Invoke-WebRequest -Uri $k.ChecksumList -UseBasicParsing).Content -split "`n"
                # any layout: "<hash> <name>", "<name> <hash>" or "MD5 (<name>) = <hash>"; exact file name only
                $namePat = "(?<![\w.+\-])" + [regex]::Escape($k.Name) + "(?![\w.+\-])"
                $hexPat = "(?<![0-9A-Fa-f])([0-9A-Fa-f]{64}|[0-9A-Fa-f]{40}|[0-9A-Fa-f]{32})(?![0-9A-Fa-f])"
                $line = $list | Where-Object { $_ -match $namePat -and $_ -match $hexPat } | Select-Object -First 1
                if ($line) {
                    $want = ([regex]::Match($line, $hexPat)).Groups[1].Value.ToLower()
                    $algo = @{ 32 = "MD5"; 40 = "SHA1"; 64 = "SHA256" }[$want.Length]
                    $got = (Get-FileHash -Algorithm $algo -Path $dest).Hash.ToLower()
                    if ($got -ne $want) { Write-Host "    REJECTED: $algo differs from aa_checksums.txt"; Remove-Item $dest -Force; continue }
                    Write-Host "    $algo matches NAIF aa_checksums.txt"
                } else { Write-Host "    note: $($k.Name) not listed in aa_checksums.txt" }
            } catch { Write-Host "    note: could not read aa_checksums.txt; the Python install step checks it again" }
        }
        return $true
    }
    return $false
}

$missing = @()
$haveFk = $false
foreach ($k in $Kernels) {
    if ($k.FallbackFor -and $haveFk) { continue }        # the newer FK was obtained; skip the fallback
    $ok = Get-Kernel $k
    if ($k.FallbackFor -and $ok) { $haveFk = $true }
    if (-not $ok -and $k.Required) { $missing += $k.Name }
    if (-not $ok -and -not $k.Required -and -not $k.FallbackFor) { Write-Host "  optional $($k.Name) unavailable; V-02e will be skipped" }
}
if (-not $haveFk) { $missing += "moon_de440_250416.tf (or fallback moon_de440_220930.tf)" }
if ($missing.Count -gt 0) {
    Write-Host "`nNot obtained: $($missing -join ', '). Nothing was installed." -ForegroundColor Red
    exit 1
}

Write-Host "`nSHA-256 of the downloaded files:"
Get-ChildItem $Download -File | ForEach-Object { "{0,-30} {1,10} B  {2}" -f $_.Name, $_.Length, (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash.ToLower() }

Write-Host "`nInstalling through the LUNA-OPS pipeline (re-checks, test-loads with SPICE, writes data\kernels\lock.json) ..."
Push-Location $Backend
try {
    & $Python -m lunaops.acquire kernels --from-dir $Download
    if ($LASTEXITCODE -ne 0) { throw "kernel install failed (exit $LASTEXITCODE)" }
    & $Python -m lunaops.acquire verify-kernels
    if ($LASTEXITCODE -ne 0) { throw "verify-kernels reported problems (exit $LASTEXITCODE)" }
} finally { Pop-Location }
Write-Host "`nDone. Next: cd backend; $Python -m pytest -s -k V02e tests/test_engine.py; $Python -m validation.run_validation"
