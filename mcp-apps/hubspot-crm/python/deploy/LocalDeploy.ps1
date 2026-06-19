<#
.SYNOPSIS
    LocalDeploy -- start the HubSpot MCP server on this laptop, open a dev tunnel,
    and push the agent to MOS3 (Microsoft Online Services 3, the M365 store).

.DESCRIPTION
    End-to-end LOCAL deploy for Ask - HubSpot.
    Adapted from salesforce-crm/python/deploy/LocalDeploy.ps1.

    Phases:
      0. Pre-flight checks (Python, npm, devtunnel, required files)
      1. Build Python venv + widget bundle if stale
      2. Start the Python MCP server on $ServerPort in a new window
      3. Open or refresh the dev tunnel
      4. Run regen_manifests.py against the live tunnel URL
      5. Build appPackage zip + upload to MOS3

.EXAMPLE
    .\deploy\LocalDeploy.ps1                         # Full local launch
    .\deploy\LocalDeploy.ps1 -SkipMOS3               # Server + tunnel only
    .\deploy\LocalDeploy.ps1 -ServerOnly             # Just the Python server
    .\deploy\LocalDeploy.ps1 -SkipServer             # Tunnel + MOS3 (server already running)

.NOTES
    Requires: Python 3.11+, Dev Tunnels CLI, Node.js 18+ (for widget build).
    Run from the hubspot-crm/python/ directory.
#>

param(
    [switch]$SkipServer,
    [switch]$SkipTunnel,
    [switch]$ServerOnly,
    [switch]$TunnelOnly,
    [switch]$SkipMOS3,
    [string]$TunnelName  = "gtc-hs-v01",
    [int]$ServerPort     = 8082
)

$ErrorActionPreference = "Stop"

. "$PSScriptRoot\_deploy_common.ps1"

# ---------------------------------------------------------------------------
# Paths & MOS3 config
# ---------------------------------------------------------------------------

$App        = Split-Path -Parent $PSScriptRoot               # hubspot-crm\python\
$VenvPython = "$App\.venv\Scripts\python.exe"
$Pkg        = "hs_crm_mcp"

$ClientId   = "7ea7c24c-b1f6-4a20-9d11-9ae12e9e7ac0"
$TenantId   = "8b7a11d9-6513-4d54-a468-f6630df73c8b"
$Scope      = "https://titles.prod.mos.microsoft.com/.default"
$MOS3Url    = "https://titles.prod.mos.microsoft.com"
$TokenCache = "$App\.mos3_token_cache.json"
$SrcDir     = "$App\agent\appPackage"
$BuildDir   = "$App\agent\appPackage\build"
$TmpDir     = "$App\agent\appPackage\_tmp_zip"
$ZipPath    = "$BuildDir\appPackage.dev.zip"
$EnvFile    = "$App\agent\env\.env.dev"
$RegenPy    = "$App\deploy\regen_manifests.py"

Write-Host ""
Write-Host "  Ask - HubSpot  v0.1.0  (LocalDeploy)" -ForegroundColor Cyan
Write-Host "  Port $ServerPort  |  Tunnel $TunnelName" -ForegroundColor DarkCyan
Write-Host ""

# ---------------------------------------------------------------------------
# Phase 0: Pre-flight checks
# ---------------------------------------------------------------------------
Write-Host ">> Phase 0/5: pre-flight checks" -ForegroundColor Cyan

Assert-File -Path "$App\pyproject.toml" `
    -Why "LocalDeploy.ps1 must be run from hubspot-crm/python/ (script is in deploy/)." `
    -Hint "cd to the hubspot-crm/python directory then re-run."

Assert-File -Path "$PSScriptRoot\_deploy_common.ps1" `
    -Why "Shared helper functions live here; dot-sourced at the top of this script." `
    -Hint "_deploy_common.ps1 is part of the repo. Pull latest from git."

if (-not $SkipServer -and -not $TunnelOnly) {
    # Try PATH first, then known ARM64 location
    $sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $sysPython) { $sysPython = "$env:LOCALAPPDATA\Programs\Python\Python311-arm64\python.exe" }
    if (-not $sysPython -or -not (Test-Path $sysPython)) {
        Write-FailBlock -What "Python not found" `
            -Detail "Checked PATH and $env:LOCALAPPDATA\Programs\Python\Python311-arm64\python.exe" `
            -Hint "Install Python 3.11+ from https://python.org or via 'winget install Python.Python.3.11'."
        exit 1
    }
}

if (-not $SkipTunnel -and -not $ServerOnly) {
    Assert-Tool -Name "devtunnel" `
        -Why "Needed to expose the local server to Microsoft Teams over HTTPS." `
        -Hint "Install Dev Tunnels CLI from https://aka.ms/devtunnels/download then run 'devtunnel user login'."
}

Assert-File -Path "$SrcDir\ai-plugin.json"        -Why "Agent runtime descriptor."          -Hint "This is part of the repo. Pull latest from git."
Assert-File -Path "$SrcDir\mcp-tools.json"        -Why "MCP tools manifest."                -Hint "This is part of the repo. Pull latest from git."
Assert-File -Path "$SrcDir\declarativeAgent.json" -Why "Declarative agent shell."           -Hint "This is part of the repo. Pull latest from git."
Assert-File -Path "$SrcDir\manifest.json"         -Why "Teams app manifest skeleton."       -Hint "This is part of the repo. Pull latest from git."
Assert-File -Path "$SrcDir\instruction.txt"       -Why "System prompt for the agent."       -Hint "This is part of the repo. Pull latest from git."

Write-Host "   All pre-flight checks passed." -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------------------
# Phase 1: Build venv + widget if stale
# ---------------------------------------------------------------------------
if (-not $SkipServer -and -not $TunnelOnly) {
    $VenvMarker = "$App\.venv\.installed"

    if (-not (Test-Path $VenvPython)) {
        Write-Host ">> Phase 1a/5: creating Python venv (first run)..." -ForegroundColor Cyan
        Invoke-ExternalChecked -Step "python -m venv" `
            -Command { & $sysPython -m venv "$App\.venv" } `
            -Hint "Make sure Python 3.11+ is installed. Try: python --version"
    }

    if (-not (Test-Path $VenvMarker)) {
        Write-Host ">> Phase 1a/5: installing Python dependencies (~1 min)..." -ForegroundColor Cyan
        Invoke-ExternalChecked -Step "pip install --upgrade pip" `
            -Command { & $VenvPython -m pip install --upgrade pip --quiet } `
            -Hint "Network issue? Check connection / corporate proxy."

        # ARM64 Windows workaround: mcp depends on pyjwt[crypto] -> cryptography
        # which has no pre-built ARM64 wheel. Install PyJWT without crypto first,
        # then mcp --no-deps, then remaining deps manually.
        $isArm = ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') -or ($sysPython -match 'arm64')
        if ($isArm) {
            Write-Host "   [arm64] Bypassing cryptography build..." -ForegroundColor Yellow
            $savedEAP2 = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
            & $VenvPython -m pip install PyJWT --quiet 2>&1 | Out-Null
            & $VenvPython -m pip install "mcp==1.26.0" --no-deps --quiet 2>&1 | Out-Null
            & $VenvPython -m pip install httpx httpx-sse pydantic pydantic-settings starlette sse-starlette anyio python-multipart jsonschema pywin32 uvicorn structlog tenacity cachetools python-dotenv --quiet 2>&1 | Out-Null
            $ErrorActionPreference = $savedEAP2
            Invoke-ExternalChecked -Step "pip install -e . (no-deps)" `
                -Command { & $VenvPython -m pip install -e "$App" --no-deps --quiet } `
                -Hint "Check pyproject.toml for syntax errors."
        } else {
            Invoke-ExternalChecked -Step "pip install -e ." `
                -Command { & $VenvPython -m pip install -e "$App" --quiet } `
                -Hint "Check pyproject.toml for syntax errors or missing deps."
        }

        New-Item -ItemType File -Path $VenvMarker -Force | Out-Null
        Write-Host "   [ready] Venv built." -ForegroundColor Green
    }

    # Widget build (only if missing or stale)
    $widgetHtml    = "$App\web\widget.html"
    $widgetSrcDirs = @("$App\widgets\src", "$App\widgets\mcp-shared\widgets\src")
    $widgetStale   = $false
    if (-not (Test-Path $widgetHtml)) {
        $widgetStale = $true
    } else {
        $widgetHtmlMtime = (Get-Item $widgetHtml).LastWriteTime
        foreach ($dir in $widgetSrcDirs) {
            if (-not (Test-Path $dir)) { continue }
            $newestSrc = (Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue |
                          Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
            if ($newestSrc -and $newestSrc -gt $widgetHtmlMtime) {
                $widgetStale = $true
                break
            }
        }
    }
    if ($widgetStale) {
        Assert-Tool -Name "npm" `
            -Why "Widget source is newer than the built widget.html and needs rebuilding." `
            -Hint "Install Node.js 18+ from https://nodejs.org or via 'winget install OpenJS.NodeJS'."

        if (-not (Test-Path "$App\widgets\node_modules")) {
            Write-Host ">> Phase 1b/5: installing widget dependencies (npm install, ~2 min)..." -ForegroundColor Cyan
            Push-Location "$App\widgets"
            try {
                Invoke-ExternalChecked -Step "npm install" `
                    -Command { npm install } `
                    -Hint "Check widgets/package.json. Network / corporate registry issue is common."
            } finally { Pop-Location }
        }

        Write-Host ">> Phase 1c/5: building widget bundle..." -ForegroundColor Cyan
        Push-Location "$App\widgets"
        try {
            Invoke-ExternalChecked -Step "npm run build" `
                -Command { npm run build } `
                -Hint "Look for TypeScript or Vite errors above. Often a transient HMR conflict; re-run."
        } finally { Pop-Location }

        if (-not (Test-Path $widgetHtml)) {
            Write-FailBlock -What "Widget build finished but produced no widget.html" `
                -Detail "Expected output at $widgetHtml" `
                -Hint "Check widgets/build.mjs for path issues."
            exit 1
        }
        Write-Host "   [widget] Built $widgetHtml" -ForegroundColor Green
    }
}

# ---------------------------------------------------------------------------
# Phase 2: Start MCP server
# ---------------------------------------------------------------------------
if (-not $SkipServer -and -not $TunnelOnly) {
    $procs = (Get-NetTCPConnection -LocalPort $ServerPort -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique
    if ($procs) {
        $procs | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
        Write-Host "  [server] Stopped existing process on port $ServerPort" -ForegroundColor Yellow
        Start-Sleep 1
    }
    Write-Host ">> Phase 2/5: starting HubSpot MCP server on port $ServerPort..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$env:PYTHONIOENCODING='utf-8'; `$host.UI.RawUI.WindowTitle = 'HS MCP Server :$ServerPort'; Set-Location '$App'; & '$VenvPython' -m hs_crm_mcp"
    )

    # Wait for the port to become reachable (TCP connect check)
    $waited = 0
    $up = $false
    do {
        Start-Sleep 2; $waited += 2
        $tcp = New-Object System.Net.Sockets.TcpClient
        try { $tcp.Connect("127.0.0.1", $ServerPort); $up = $true; $tcp.Close() } catch {}
        Write-Host "`r  [watch] Waiting for server... ${waited}s" -NoNewline -ForegroundColor Yellow
    } while (-not $up -and $waited -lt 30)
    Write-Host ""
    if ($up) {
        Write-Host "  [up] Server live: http://localhost:$ServerPort" -ForegroundColor Green
    } else {
        Write-FailBlock -What "Server did not respond on port $ServerPort within 30 seconds" `
            -Detail "Look at the 'HS MCP Server' window that just opened." `
            -Hint @"
Common causes:
  - Missing HUBSPOT_ACCESS_TOKEN in .env
  - Port $ServerPort already in use by another process
  - Python deps not installed -- delete .venv/ and re-run
"@
        exit 1
    }
}

if ($ServerOnly) {
    Write-Host ""
    Write-Host "  [done] ServerOnly mode -- server is running, tunnel & MOS3 skipped." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------
# Phase 3: Open dev tunnel
# ---------------------------------------------------------------------------
$tunnelUrl = $null
if (-not $SkipTunnel) {
    $tunnelProcs = Get-Process -Name "devtunnel" -ErrorAction SilentlyContinue
    if ($tunnelProcs) {
        $tunnelProcs | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "  [tunnel] Stopped existing devtunnel process" -ForegroundColor Yellow
        Start-Sleep 2
    }
    Write-Host ">> Phase 3/5: opening dev tunnel '$TunnelName'..." -ForegroundColor Cyan

    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $existingInfo = ""
    try {
        $existingInfo = (& cmd /c "devtunnel show $TunnelName 2>&1") -join "`n"
    } catch {
        $existingInfo = ""
    }
    $ErrorActionPreference = $savedEAP
    if ($existingInfo -notmatch 'Tunnel ID') {
        Write-Host "  [tunnel] Creating new tunnel..." -ForegroundColor Yellow
        devtunnel create $TunnelName --allow-anonymous
        if ($LASTEXITCODE -ne 0) {
            Write-FailBlock -What "devtunnel create $TunnelName failed (exit $LASTEXITCODE)" `
                -Detail "Could not create a new tunnel." `
                -Hint "Run 'devtunnel user login' (one-time) if you haven't, or pick a different -TunnelName."
            exit 1
        }
        devtunnel port create $TunnelName -p $ServerPort --protocol auto
    } else {
        $portExists = $existingInfo | Select-String "$ServerPort"
        if (-not $portExists) {
            devtunnel port create $TunnelName -p $ServerPort --protocol auto
        }
    }
    Start-Process powershell -ArgumentList @(
        "-NoExit", "-Command",
        "`$host.UI.RawUI.WindowTitle = 'HS Tunnel ($TunnelName)'; devtunnel host $TunnelName --allow-anonymous"
    )

    Write-Host "  [watch] Registering tunnel..." -NoNewline -ForegroundColor Yellow
    $savedEAP = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    for ($i = 0; $i -lt 12; $i++) {
        Start-Sleep 3
        $info = ""
        try { $info = (& cmd /c "devtunnel show $TunnelName 2>&1") -join "`n" } catch { $info = "" }
        if ($info -match 'https://(\S+-\d+\.\S+devtunnels\.ms)') {
            $tunnelUrl = "https://$($Matches[1])"
            break
        }
        Write-Host "." -NoNewline -ForegroundColor Yellow
    }
    $ErrorActionPreference = $savedEAP
    Write-Host ""
    if ($tunnelUrl) {
        Write-Host "  [up] Tunnel live: $tunnelUrl" -ForegroundColor Green
    } else {
        Write-FailBlock -What "Tunnel URL did not become visible after 36 seconds" `
            -Detail "Look at the 'HS Tunnel' window that just opened." `
            -Hint "Check that you ran 'devtunnel user login' once. Try a different -TunnelName if stuck."
        exit 1
    }
}

if ($TunnelOnly) {
    Write-Host ""
    Write-Host "  [done] TunnelOnly mode -- tunnel is open, server & MOS3 skipped." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------
# Phase 4: Regen manifests against the live endpoint
# ---------------------------------------------------------------------------
Write-Host ">> Phase 4/5: syncing tools into manifests (regen_manifests.py)..." -ForegroundColor Cyan
$runtimeUrl = if ($tunnelUrl) { $tunnelUrl } else { "https://localhost:$ServerPort" }
Invoke-RegenManifests -GatewayUrl $runtimeUrl -PythonExe $VenvPython -ScriptPath $RegenPy

if ($SkipMOS3) {
    Write-Host ""
    Write-Host "  ===================================" -ForegroundColor DarkCyan
    Write-Host "   READY (no MOS3 upload)" -ForegroundColor Green
    Write-Host "  ===================================" -ForegroundColor DarkCyan
    Write-Host "  Server: http://localhost:$ServerPort" -ForegroundColor White
    if ($tunnelUrl) { Write-Host "  Tunnel: $tunnelUrl" -ForegroundColor White }
    Write-Host ""
    exit 0
}

# ---------------------------------------------------------------------------
# Phase 5: MOS3 -- token, build, upload
# ---------------------------------------------------------------------------
Write-Host ">> Phase 5/5: acquiring MOS3 token..." -ForegroundColor Cyan
$token = Get-MOS3Token -ClientId $ClientId -TenantId $TenantId -Scope $Scope -TokenCachePath $TokenCache

Write-Host "  >> Building app package..." -ForegroundColor Cyan
Build-AppPackageZip -SrcDir $SrcDir -BuildDir $BuildDir -TmpDir $TmpDir -ZipPath $ZipPath `
    -RuntimeUrl $runtimeUrl -EnvFile $EnvFile

$null = Push-AppPackageToMOS3 -ZipPath $ZipPath -Token $token -Mos3Url $MOS3Url

Write-Host ""
Write-Host "  ===================================" -ForegroundColor DarkCyan
Write-Host "   ASK - HUBSPOT CRM COPILOT LIVE" -ForegroundColor Green
Write-Host "  ===================================" -ForegroundColor DarkCyan
Write-Host "  Server  -->  http://localhost:$ServerPort" -ForegroundColor White
if ($tunnelUrl) { Write-Host "  Tunnel  -->  $tunnelUrl" -ForegroundColor White }
Write-Host "  MOS3    -->  agent package live in M365 Copilot" -ForegroundColor Gray
Write-Host ""
