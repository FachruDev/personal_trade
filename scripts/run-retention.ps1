param(
    [switch]$Preview
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$previousPreview = $env:RETENTION_PREVIEW
$env:RETENTION_PREVIEW = if ($Preview) { "1" } else { "0" }
Push-Location $projectRoot
try {
    & docker compose --env-file .env.example exec -T -e "RETENTION_PREVIEW=$env:RETENTION_PREVIEW" api python -c @'
import json
import os
import urllib.request

preview = os.environ.get("RETENTION_PREVIEW") == "1"
request = urllib.request.Request(
    "http://localhost:8000/v1/maintenance/retention/preview" if preview else "http://localhost:8000/v1/maintenance/retention",
    method="GET" if preview else "POST",
    headers={"X-Bot-Control-Token": os.environ["BOT_CONTROL_TOKEN"]},
)
response = urllib.request.urlopen(request)
print(json.dumps(json.loads(response.read()), indent=2))
'@
    exit $LASTEXITCODE
}
finally {
    Pop-Location
    if ($null -eq $previousPreview) {
        Remove-Item Env:RETENTION_PREVIEW -ErrorAction SilentlyContinue
    }
    else {
        $env:RETENTION_PREVIEW = $previousPreview
    }
}
