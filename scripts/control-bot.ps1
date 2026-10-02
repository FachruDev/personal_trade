param(
    [Parameter(Mandatory)]
    [ValidateSet("Stop", "Resume")]
    [string]$Action,
    [switch]$WhatIf
)

$projectRoot = Split-Path -Parent $PSScriptRoot
if ($WhatIf) {
    Write-Output "Would call the local $Action control endpoint through the API container."
    exit 0
}

Push-Location $projectRoot
try {
    & docker compose --env-file .env.example exec -T -e "BOT_ACTION=$Action" api python -c @'
import json
import os
import urllib.request

action = os.environ["BOT_ACTION"].lower()
request = urllib.request.Request(
    f"http://localhost:8000/v1/bot/{action}",
    method="POST",
    headers={"X-Bot-Control-Token": os.environ["BOT_CONTROL_TOKEN"]},
)
response = urllib.request.urlopen(request)
print(json.dumps(json.loads(response.read()), indent=2))
'@
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
