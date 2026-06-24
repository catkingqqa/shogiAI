param(
  [string]$SshUser = "s11211213",
  [string]$SshHost = "140.135.65.59",
  [int]$SshPort = 12122,
  [string]$DbHost = "140.135.65.53",
  [int]$DbPort = 3306,
  [string]$DbUser = "11211213",
  [string]$DbName = "DB11211213",
  [string]$OutputDir = "outputs\db_schema"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$outputPath = Join-Path $repoRoot $OutputDir
New-Item -ItemType Directory -Path $outputPath -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$fileName = "${DbName}_schema_${timestamp}.sql"
$remoteDir = "~/shogiAI/out/db_schema"
$remotePath = "$remoteDir/$fileName"
$localPath = Join-Path $outputPath $fileName

$remoteCommand = @"
set -e
mkdir -p $remoteDir
mysqldump \
  --host=$DbHost \
  --port=$DbPort \
  --user=$DbUser \
  --password \
  --no-data \
  --routines \
  --triggers \
  --events \
  --no-tablespaces \
  --single-transaction \
  --skip-lock-tables \
  --databases $DbName \
  > $remotePath
ls -lh $remotePath
"@

Write-Host "Exporting database schema on remote host..."
Write-Host "Remote output: $remotePath"
ssh -t -p $SshPort "$SshUser@$SshHost" $remoteCommand

Write-Host "Downloading schema to local workspace..."
scp -P $SshPort "${SshUser}@${SshHost}:$remotePath" $localPath

Write-Host "Schema exported:"
Write-Host $localPath
