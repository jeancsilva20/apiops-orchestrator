# Bootstrap do apiops-orchestrator SEM Poetry.
#
# Uso (a partir da raiz do repositorio):
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -Dev   # inclui pytest/linters
#
# Equivalencia com o fluxo Poetry:
#   setup.ps1                ~ poetry install --without dev
#   setup.ps1 -Dev           ~ poetry install
# O poetamento (pyproject.toml/poetry.lock) NAO e tocado por este script.

param(
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

function Resolve-Python {
    $candidates = @(
        @{ Exe = "py"; Args = @("-3.12") },
        @{ Exe = "py"; Args = @("-3.13") },
        @{ Exe = "python"; Args = @() }
    )
    foreach ($c in $candidates) {
        $raw = $null
        try { $raw = (& $c.Exe @($c.Args + @("--version")) 2>&1) -join " " } catch { continue }
        if ($LASTEXITCODE -ne 0 -or -not $raw) { continue }
        $ver = ([string]$raw) -replace ".* (\d+\.\d+).*", '$1'
        if ($ver -match '^\d+\.\d+$' -and ([version]$ver -ge [version]"3.12")) {
            return $c
        }
    }
    throw "Python >= 3.12 nao encontrado no PATH. Instale em https://www.python.org/downloads/"
}

function Invoke-Step {
    param([string]$Message, [scriptblock]$Block)
    Write-Host "==> $Message" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "Falhou: $Message" }
}

$py = Resolve-Python
$pyLabel = ((& $py.Exe @($py.Args + @("--version")) 2>&1) -join " ")
Write-Host "Interpretador detectado: $pyLabel" -ForegroundColor DarkGray

$VenvExists = Test-Path -LiteralPath (Join-Path $RepoRoot ".venv\Scripts\python.exe")
if (-not $VenvExists) {
    Invoke-Step "Criando ambiente virtual (.venv)" -Block {
        & $py.Exe @($py.Args + @("-m", "venv", ".venv"))
    }
} else {
    Write-Host "==> Ambiente virtual ja existe - reutilizando" -ForegroundColor Cyan
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$ReqFile = if ($Dev) { "requirements-dev.txt" } else { "requirements.txt" }

Invoke-Step "Instalando dependencias ($ReqFile)" -Block {
    & $VenvPython -m pip install -r $ReqFile
}

Invoke-Step "Instalando o pacote (editable) - habilita src-layout, sen e versao" -Block {
    & $VenvPython -m pip install -e .
}

Write-Host ""
Write-Host "Setup concluido." -ForegroundColor Green
Write-Host "Para usar:"
Write-Host "  .\.venv\Scripts\python.exe src\apiops_orchestrator\main.py"
Write-Host "  .\.venv\Scripts\sen login            (binario gerado pelo pip install -e .)"
Write-Host "  .\.venv\Scripts\python.exe -m pytest          (requer -Dev)"
Write-Host "Opcional: .\.venv\Scripts\Activate.ps1 para ativar o ambiente neste shell."
