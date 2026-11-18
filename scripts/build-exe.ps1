<#
.SYNOPSIS
    Gera o executável `sen` para Windows e o pacote de entrega em dist/.

.DESCRIPTION
    Monta um venv limpo em build/exe (só dependências de runtime do
    requirements.txt + o pacote), empacota com PyInstaller em arquivo único,
    confere que nenhum .sen/.sen_session/.env entrou no binário e gera, em
    dist/sen-<versão>/<cliente>/, o sen-<versão>-<cliente>-windows-x64.zip
    (o `sen.exe`, o instalador, o `install.cmd`, o `.sen.example` com os
    endereços do cliente e o README do dev, scripts/README-executavel.md,
    com a versão e o cliente preenchidos). O README vai dentro do zip, o
    mesmo do pacote Linux.

.PARAMETER Client
    Cliente do pacote: nome de um arquivo de scripts/clients, sem o `.sen`.

.EXAMPLE
    .\scripts\build-exe.ps1 -Client ecad
#>
param(
    [string]$Client,
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

# Devolve as linhas de scripts/clients/<cliente>.sen, depois de conferir o nome e as chaves.
function Get-ClientBlock {
    param([string]$Name)
    $folder = Join-Path $PSScriptRoot "clients"
    $available = (Get-ChildItem -Path $folder -Filter "*.sen" | ForEach-Object { $_.BaseName }) -join ", "
    if (-not $Name) {
        throw "Informe o cliente com -Client. Disponíveis: $available"
    }
    $file = Join-Path $folder "$Name.sen"
    if ($Name -cnotmatch '^[a-z0-9-]+$' -or -not (Test-Path $file)) {
        throw "Cliente '$Name' não existe em scripts\clients. Disponíveis: $available"
    }
    $lines = @(Get-Content -Encoding UTF8 $file)
    foreach ($key in "AUTH_HOST", "AUTH_LOGIN_PATH") {
        if (-not ($lines -match ('^' + $key + '=["'']?[^"''\s]'))) {
            throw "scripts\clients\$Name.sen não define $key."
        }
    }
    if ($lines -match '^\s*SEN_CREDENTIALS=') {
        throw "scripts\clients\$Name.sen não pode definir SEN_CREDENTIALS."
    }
    return $lines
}

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
    $clientBlock = @(Get-ClientBlock $Client)
    $nome = "sen-$versao-$Client-windows-x64"
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
    # O .sen.example do pacote é o gabarito até a credencial, seguido dos endereços do cliente.
    $template = @(Get-Content -Encoding UTF8 "src\apiops_orchestrator\.sen.example")
    $credentialLine = -1
    for ($i = 0; $i -lt $template.Count; $i++) {
        if ($template[$i] -match '^SEN_CREDENTIALS=') { $credentialLine = $i; break }
    }
    if ($credentialLine -lt 0) { throw "O .sen.example não tem a linha SEN_CREDENTIALS=." }
    $senExample = @($template[0..$credentialLine]) + "" + $clientBlock
    [IO.File]::WriteAllLines((Join-Path $pacote ".sen.example"), [string[]]$senExample, (New-Object Text.UTF8Encoding $false))
    Copy-Item "scripts\install.ps1" $pacote
    Copy-Item "scripts\install.cmd" $pacote
    # O README entra no zip, com a versão e o cliente preenchidos, para os comandos funcionarem colados.
    $readme = (Get-Content -Raw -Encoding UTF8 "scripts\README-executavel.md").Replace("<versão>", $versao).Replace("<cliente>", $Client)
    [IO.File]::WriteAllText((Join-Path $pacote "README.md"), $readme)
    $entrega = Join-Path $dist "sen-$versao\$Client"
    New-Item -ItemType Directory -Force -Path $entrega | Out-Null
    $readmeSolto = Join-Path $entrega "README.md"
    if (Test-Path $readmeSolto) { Remove-Item -Force $readmeSolto }
    $zip = Join-Path $entrega "$nome.zip"
    if (Test-Path $zip) { Remove-Item -Force $zip }
    Compress-Archive -Path $pacote -DestinationPath $zip

    Write-Host "Pronto: $zip" -ForegroundColor Green
}
finally {
    Pop-Location
}
