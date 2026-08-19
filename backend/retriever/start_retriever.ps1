# Start ReTour Retriever without touching the retrieval pipeline.
# Uses a short-path venv (C:\rt-venv) to avoid Windows MAX_PATH / OneDrive install failures.
# From Command Prompt use start_retriever.bat — CMD cannot run .ps1 files.
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$VenvPython = "C:\rt-venv\Scripts\python.exe"

function Test-RetrieverReady {
    if (-not (Test-Path $VenvPython)) { return $false }
    & $VenvPython -c "import uvicorn, fastapi, chromadb, sentence_transformers" 2>$null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating short-path venv at C:\rt-venv ..."
    py -3.11 -m venv C:\rt-venv
    if ($LASTEXITCODE -ne 0) { throw "Failed to create C:\rt-venv. Is Python 3.11 installed?" }
}

if (-not (Test-RetrieverReady)) {
    Write-Host "Installing retriever packages into C:\rt-venv (first time can take several minutes) ..."
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
    if (-not (Test-RetrieverReady)) {
        throw "Packages installed but uvicorn still missing. Close other retriever windows and run start_retriever.bat again."
    }
}

Set-Location $Root
Write-Host "Starting retriever on http://127.0.0.1:8001 ..."
& $VenvPython -m uvicorn api.main:app --host 127.0.0.1 --port 8001
if ($LASTEXITCODE -ne 0) {
    Write-Host "Retriever exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}
