$ErrorActionPreference = "Stop"
$baseUrl = if ($env:RUNBOOKIQ_URL) { $env:RUNBOOKIQ_URL } else { "http://localhost:8080" }

Get-ChildItem -Path "$PSScriptRoot\..\examples\runbooks" -Filter *.md | ForEach-Object {
    Write-Host "Ingesting $($_.Name)"
    curl.exe --fail --silent --show-error `
        -F "knowledge_base_id=platform" `
        -F "file=@$($_.FullName);type=text/markdown" `
        "$baseUrl/api/documents"
    Write-Host ""
}

Write-Host "RunbookIQ sample knowledge is ready."

