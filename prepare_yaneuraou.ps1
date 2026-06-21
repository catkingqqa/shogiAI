$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Download YaneuraOu and a compatible free HalfKP evaluation file.
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ToolRoot = Join-Path $ProjectRoot "tools\yaneuraou"
$DownloadRoot = Join-Path $ToolRoot "downloads"
$ExtractRoot = Join-Path $ToolRoot "extracted"
$RuntimeRoot = Join-Path $ToolRoot "runtime"
$EvalRoot = Join-Path $RuntimeRoot "eval"

New-Item -ItemType Directory -Force -Path $DownloadRoot | Out-Null
New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $EvalRoot | Out-Null

function Get-ReleaseAsset {
    param(
        [string]$Repository,
        [string]$Tag,
        [string]$Kind
    )

    $headers = @{ "User-Agent" = "shogiAI-setup" }
    $releaseUrl = "https://api.github.com/repos/$Repository/releases/tags/$Tag"
    Write-Host "Reading release: $Repository / $Tag"
    $release = Invoke-RestMethod -Uri $releaseUrl -Headers $headers

    if ($Kind -eq "engine") {
        $asset = @($release.assets) | Where-Object {
            ($_.name -like "*win-all.7z" -or $_.name -like "*win64-all.7z") -and
            $_.name -notlike "*learn*"
        } | Select-Object -First 1
    } else {
        $asset = @($release.assets) | Where-Object {
            $_.name -eq "nn.bin" -or $_.name -like "*.7z" -or $_.name -like "*.zip"
        } | Select-Object -First 1
    }

    if ($null -eq $asset) {
        $available = (@($release.assets) | ForEach-Object { $_.name }) -join ", "
        throw "No matching asset. Available assets: $available"
    }
    return $asset
}

function Download-Asset {
    param(
        $Asset,
        [string]$DestinationDirectory
    )

    $destination = Join-Path $DestinationDirectory $Asset.name
    if ((Test-Path $destination) -and ((Get-Item $destination).Length -gt 0)) {
        Write-Host "Using existing download: $destination"
        return $destination
    }
    Write-Host "Downloading: $($Asset.name)"
    $headers = @{ "User-Agent" = "shogiAI-setup" }
    Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $destination -Headers $headers
    return $destination
}

function Find-SevenZip {
    $command = Get-Command 7z.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles "7-Zip\7z.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "7-Zip\7z.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Expand-Package {
    param(
        [string]$Archive,
        [string]$Destination
    )

    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    $extension = [IO.Path]::GetExtension($Archive).ToLowerInvariant()
    if ($extension -eq ".zip") {
        Expand-Archive -Path $Archive -DestinationPath $Destination -Force
        return
    }
    if ($extension -ne ".7z") {
        throw "Unsupported archive format: $Archive"
    }

    $sevenZip = Find-SevenZip
    if ($null -ne $sevenZip) {
        & $sevenZip x $Archive "-o$Destination" -y | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip extraction failed: $Archive"
        }
        return
    }

    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($null -ne $tar) {
        & $tar.Source -xf $Archive -C $Destination
        if ($LASTEXITCODE -eq 0) {
            return
        }
    }
    throw "Cannot extract .7z. Install 7-Zip and run this script again."
}

$engineAsset = Get-ReleaseAsset -Repository "yaneurao/YaneuraOu" -Tag "v8.30git" -Kind "engine"
$engineArchive = Download-Asset -Asset $engineAsset -DestinationDirectory $DownloadRoot
$engineExtract = Join-Path $ExtractRoot "engine"
Expand-Package -Archive $engineArchive -Destination $engineExtract

$evalAsset = Get-ReleaseAsset -Repository "nodchip/tanuki-" -Tag "tanuki-.halfkp_256x2-32-32.2023-05-08" -Kind "eval"
$evalDownload = Download-Asset -Asset $evalAsset -DestinationDirectory $DownloadRoot
$evalExtension = [IO.Path]::GetExtension($evalDownload).ToLowerInvariant()

if ($evalExtension -eq ".bin") {
    $downloadedNn = Get-Item $evalDownload
} else {
    $evalExtract = Join-Path $ExtractRoot "eval"
    Expand-Package -Archive $evalDownload -Destination $evalExtract
    $downloadedNn = Get-ChildItem -Path $evalExtract -Recurse -File -Filter "nn.bin" | Select-Object -First 1
}
if ($null -eq $downloadedNn) {
    throw "nn.bin was not found in the evaluation package."
}

$selectedEngine = Get-ChildItem -Path $engineExtract -Recurse -File -Filter "*.exe" |
    Where-Object { $_.Name -like "*NNUE*halfKP256*AVX2*.exe" } |
    Select-Object -First 1
if ($null -eq $selectedEngine) {
    throw "HalfKP256 AVX2 executable was not found."
}

$EnginePath = Join-Path $RuntimeRoot "YaneuraOu.exe"
$EvalPath = Join-Path $EvalRoot "nn.bin"
Copy-Item -Force $selectedEngine.FullName $EnginePath
Copy-Item -Force $downloadedNn.FullName $EvalPath

Write-Host "Testing USI engine..."
$usiInput = "usi`nsetoption name EvalDir value eval`nsetoption name FV_SCALE value 20`nisready`nquit`n"
Push-Location $RuntimeRoot
try {
    $usiOutput = $usiInput | & $EnginePath 2>&1 | Out-String
} finally {
    Pop-Location
}
if ($usiOutput -notmatch "usiok" -or $usiOutput -notmatch "readyok") {
    Write-Host $usiOutput
    throw "YaneuraOu test failed: usiok or readyok was not received."
}

$RunnerPath = Join-Path $ProjectRoot "run_label_nnue.bat"
$runner = @"
@echo off
cd /d "%~dp0"
python src\label_nnue_positions.py ^
  --input out\samples.npz ^
  --output out\samples_teacher.npz ^
  --engine "%~dp0tools\yaneuraou\runtime\YaneuraOu.exe" ^
  --nodes 20000 ^
  --threads 1 ^
  --hash-mb 256 ^
  --min-ply 30 ^
  --setoption "EvalDir value eval" ^
  --setoption "FV_SCALE value 20"
pause
"@
Set-Content -Path $RunnerPath -Value $runner -Encoding ASCII

Write-Host ""
Write-Host "Setup completed."
Write-Host "Engine: $EnginePath"
Write-Host "Evaluation file: $EvalPath"
Write-Host "Next command: run_label_nnue.bat"
