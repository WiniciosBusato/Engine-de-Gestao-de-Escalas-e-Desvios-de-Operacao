param(
    [ValidateSet("server", "test", "docs")]
    [string]$Action = "server"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$venvActivate = Join-Path $root "venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
} else {
    Write-Error "Ambiente virtual 'venv' nao localizado."
    exit 1
}

switch ($Action) {
    "server" {
        Write-Host "Iniciando servidor Uvicorn..." -ForegroundColor Cyan
        uvicorn app.main:app --reload
    }
    "test" {
        Write-Host "Executando testes automatizados..." -ForegroundColor Green
        pytest -v tests/test_adherence.py
    }
    "docs" {
        Write-Host "Abrindo documentacao Swagger e subindo servidor..." -ForegroundColor Yellow
        Start-Process "http://127.0.0.1:8000/docs"
        uvicorn app.main:app --reload
    }
}
