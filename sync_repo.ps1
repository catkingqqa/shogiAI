param(
    [string]$Message = "Sync repository $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

git add -A
git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    git commit -m $Message
} elseif ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect staged changes."
}

git pull --rebase origin main
if ($LASTEXITCODE -ne 0) {
    throw "git pull --rebase failed. Resolve the conflict, then run this script again."
}

git push origin main
if ($LASTEXITCODE -ne 0) {
    throw "git push failed."
}
