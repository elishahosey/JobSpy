param(
    [string]$Source = 'C:\Users\ehose\Development\Jobspy',
    [string]$Destination = '"C:\Users\ehose\Development\JobSpy\import',
    [switch]$Execute
)

New-Item -ItemType Directory -Path $Destination -Force | Out-Null

$files = Get-ChildItem -LiteralPath $Source -File |
    Where-Object Name -Match '^jobs-\d{1,2}-\d{1,2}-\d{2,4}\.csv$'

if (-not $files) {
    Write-Host 'No matching job CSV files found.'
    exit
}

foreach ($file in $files) {
    $target = Join-Path $Destination $file.Name

    if (Test-Path -LiteralPath $target) {
        Write-Warning "Skipped because destination already exists: $target"
        continue
    }

    if ($Execute) {
        Move-Item -LiteralPath $file.FullName -Destination $target
        Write-Host "Moved: $($file.Name)"
    }
    else {
        Write-Host "Would move: $($file.FullName) -> $target"
    }
}

if (-not $Execute) {
    Write-Host
    Write-Host 'Preview only. Add -Execute to perform these moves.'
}