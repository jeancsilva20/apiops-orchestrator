<#
.SYNOPSIS
    Gera o executável `sen` para Windows e o pacote de entrega em dist/.

.DESCRIPTION
    Monta um venv limpo em build/exe (só dependências de runtime do
    requirements.txt + o pacote), empacota com PyInstaller em arquivo único,
    confere que nenhum .sen/.sen_session/.env entrou no binário e gera, em
    dist/sen-<versão>/, o sen-<versão>-windows-x64.zip (o `sen.exe`, o
    instalador, o `install.cmd` e o `.sen.example`) e, ao lado dele, o README
    do dev (scripts/README-executavel.md), o mesmo do pacote Linux.

.EXAMPLE
    .\scripts\build-exe.ps1
#>
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$PyInstallerVersao = "6.22.3"

# Nome de arquivo sensível numa linha do pyi-archive_viewer (nomes vêm entre aspas).
$padraoSensivel = "[\\/']\.(sen|sen_session[^']*|env)'"

$raiz = Split-Path -Parent $PSScriptRoot
$build = Join-Path $raiz "build\exe"
$venv = Join-Path $build "venv"
$dist = Join-Path $raiz "dist"

function Invoke-Nativo {
    param([string]$Exe, [string[]]$Argumentos)
    & $Exe @Argumentos
    if ($LASTEXITCODE -ne 0) {
        throw "Falhou (exit $LASTEXITCODE): $Exe $($Argumentos -join ' ')"
    }
}

Push-Location $raiz
try {
    $versao = (Select-String -Path "pyproject.toml" -Pattern '^version = "(.+)"').Matches[0].Groups[1].Value
    $nome = "sen-$versao-windows-x64"
    Write-Host "Gerando $nome" -ForegroundColor Cyan

    if (Test-Path $build) { Remove-Item -Recurse -Force $build }

    Write-Host "[1/5] Ambiente limpo"
    Invoke-Nativo $Python @("-m", "venv", $venv)
    $py = Join-Path $venv "Scripts\python.exe"
    Invoke-Nativo $py @("-m", "pip", "install", "--quiet", "--upgrade", "pip")
    Invoke-Nativo $py @("-m", "pip", "install", "--quiet", "-r", "requirements.txt")
    Invoke-Nativo $py @("-m", "pip", "install", "--quiet", "--no-deps", ".")
    Invoke-Nativo $py @("-m", "pip", "install", "--quiet", "pyinstaller==$PyInstallerVersao")

    # Nunca coletar dados do pacote apiops_orchestrator (--collect-*/--add-data):
    # na máquina de quem gera, o .sen e a .sen_session moram dentro dele.
    Write-Host "[2/5] PyInstaller"
    Invoke-Nativo $py @(
        "-m", "PyInstaller", "--onefile", "--clean", "--noconfirm", "--log-level", "WARN",
        "--name", "sen",
        "--copy-metadata", "apiops-orchestrator",
        "--collect-data", "jsonschema_specifications",
        "--specpath", $build,
        "--workpath", (Join-Path $build "work"),
        "--distpath", (Join-Path $build "out"),
        "src\apiops_orchestrator\main.py"
    )
    $exe = Join-Path $build "out\sen.exe"

    Write-Host "[3/5] Conferindo que nenhum segredo entrou no binário"
    $viewer = Join-Path $venv "Scripts\pyi-archive_viewer.exe"
    $conteudo = & $viewer --list --recursive $exe
    if ($LASTEXITCODE -ne 0) { throw "Não foi possível listar o conteúdo de $exe" }
    $vazados = $conteudo | Where-Object { $_ -match $padraoSensivel }
    if ($vazados) {
        throw "Arquivo sensível dentro do binário:`n$($vazados -join "`n")"
    }

    Write-Host "[4/5] Smoke test"
    $saida = & $exe --version
    if ($LASTEXITCODE -ne 0 -or ($saida -join "") -notmatch [regex]::Escape($versao)) {
        throw "sen --version não respondeu $versao (saída: $saida)"
    }

    Write-Host "[5/5] Pacote"
    $pacote = Join-Path $build $nome
    New-Item -ItemType Directory -Path $pacote | Out-Null
    Copy-Item $exe $pacote
    Copy-Item "src\apiops_orchestrator\.sen.example" $pacote
    Copy-Item "scripts\install.ps1" $pacote
    Copy-Item "scripts\install.cmd" $pacote
    # O README fica fora do zip: quem baixa precisa lê-lo antes de extrair.
    $entrega = Join-Path $dist "sen-$versao"
    New-Item -ItemType Directory -Force -Path $entrega | Out-Null
    Copy-Item -Force "scripts\README-executavel.md" (Join-Path $entrega "README.md")
    $zip = Join-Path $entrega "$nome.zip"
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Compress-Archive -Path $pacote -DestinationPath $zip

    Write-Host "Pronto: $zip" -ForegroundColor Green
}
finally {
    Pop-Location
}
