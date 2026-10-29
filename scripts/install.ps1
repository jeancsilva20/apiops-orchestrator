<#
.SYNOPSIS
    Instala (ou atualiza) o `sen` em %LOCALAPPDATA%\sen, coloca no PATH do usuário e configura a credencial.

.DESCRIPTION
    No fim, apaga da pasta extraída os arquivos do pacote, para o único sen.exe ser o instalado.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install.ps1
#>
param(
    [string]$Destino = (Join-Path $env:LOCALAPPDATA "sen")
)

$ErrorActionPreference = "Stop"

$origem = $PSScriptRoot
$senFile = Join-Path $Destino ".sen"
$utf8SemBom = New-Object Text.UTF8Encoding $false
$arquivosDoPacote = "sen.exe", "install.ps1", "install.cmd", ".sen.example"

function Get-CredencialAtual {
    if (-not (Test-Path $senFile)) { return "" }
    $linha = Get-Content -Encoding UTF8 $senFile | Where-Object { $_ -match '^\s*SEN_CREDENTIALS=' } | Select-Object -Last 1
    if (-not $linha) { return "" }
    return ($linha -replace '^\s*SEN_CREDENTIALS=', '').Trim().Trim('"', "'")
}

# Base64 de `client_id:client_secret`, sem prefixo `Basic`.
function Test-Credencial([string]$Valor) {
    if (-not $Valor) { return $false }
    try {
        $decodificado = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Valor))
    }
    catch {
        return $false
    }
    return $decodificado -match '^[^:]+:.+$'
}

function Read-Segredo([string]$Rotulo) {
    $seguro = Read-Host -AsSecureString $Rotulo
    $ponteiro = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ponteiro)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ponteiro)
    }
}

function Read-Credencial {
    :pergunta while ($true) {
        Write-Host ""
        Write-Host "Como você quer informar a credencial?"
        Write-Host "  1) client_id e client_secret"
        Write-Host "  2) Basic (Base64 já pronto)"
        $opcao = Read-Host "Opção [1]"
        if (-not $opcao) { $opcao = "1" }

        switch ($opcao) {
            "1" {
                $id = Read-Host "client_id"
                $secret = Read-Segredo "client_secret"
                if (-not $id -or -not $secret) {
                    Write-Host "client_id e client_secret são obrigatórios." -ForegroundColor Red
                    continue pergunta
                }
                $credencial = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${id}:${secret}"))
            }
            "2" {
                $credencial = ((Read-Segredo "Basic") -replace '^\s*basic\s+', '').Trim()
            }
            default {
                Write-Host "Opção inválida." -ForegroundColor Red
                continue pergunta
            }
        }
        if (Test-Credencial $credencial) { return $credencial }
        Write-Host "Credencial inválida: o Basic deve ser o Base64 de client_id:client_secret." -ForegroundColor Red
    }
}

function Add-PathUsuario([string]$Pasta) {
    $chave = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Environment", $true)
    try {
        $atual = $chave.GetValue("Path", "", [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $entradas = @($atual -split ';' | Where-Object { $_ })
        if ($entradas -contains $Pasta) { return $false }
        $chave.SetValue("Path", (($entradas + $Pasta) -join ';'), [Microsoft.Win32.RegistryValueKind]::ExpandString)
    }
    finally {
        $chave.Close()
    }
    # Avisa o Windows da mudança, para os terminais novos já enxergarem o PATH.
    [Environment]::SetEnvironmentVariable("SEN_INSTALL_REFRESH", $null, "User")
    return $true
}

# Apaga da pasta extraída os arquivos do pacote e a pasta, se ficar vazia. Nunca
# derruba a instalação: o que estiver em uso fica. Devolve se a pasta saiu.
function Remove-PastaExtraida {
    foreach ($arquivo in $arquivosDoPacote) {
        try { Remove-Item -Force -ErrorAction Stop (Join-Path $origem $arquivo) } catch { }
    }
    try { Remove-Item -Force -ErrorAction Stop (Join-Path $origem "README.md") } catch { }
    try {
        if (-not (Get-ChildItem -Force $origem)) { Remove-Item -Force -ErrorAction Stop $origem }
    }
    catch { }
    return -not (Test-Path $origem)
}

if (-not (Test-Path (Join-Path $origem "sen.exe")) -or -not (Test-Path (Join-Path $origem ".sen.example"))) {
    throw "Rode o install.ps1 de dentro da pasta extraída do pacote do sen."
}

$credencial = Get-CredencialAtual
if (Test-Credencial $credencial) {
    $manter = Read-Host "Manter a credencial atual? [S/n]"
    if ($manter -match '^[nN]') { $credencial = Read-Credencial }
}
else {
    $credencial = Read-Credencial
}

New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$daPastaExtraida = (Resolve-Path $origem).Path -ne (Resolve-Path $Destino).Path
if ($daPastaExtraida) {
    foreach ($arquivo in $arquivosDoPacote) {
        Copy-Item -Force (Join-Path $origem $arquivo) $Destino
    }
}
# O README vai dentro do pacote baixado e não é instalado: o de versões antigas sai.
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $Destino "README.md")
Get-ChildItem -Force $Destino | Unblock-File

# O .sen nasce sempre do gabarito da versão instalada, levando só a credencial.
$linhas = Get-Content -Encoding UTF8 (Join-Path $Destino ".sen.example") | ForEach-Object {
    if ($_ -match '^SEN_CREDENTIALS=') { "SEN_CREDENTIALS=`"$credencial`"" } else { $_ }
}
[IO.File]::WriteAllLines($senFile, [string[]]$linhas, $utf8SemBom)

$pathNovo = Add-PathUsuario $Destino

$versao = (& (Join-Path $Destino "sen.exe") --version | Select-Object -First 1)
Write-Host ""
Write-Host "Instalado: $versao em $Destino" -ForegroundColor Green
if ($daPastaExtraida) {
    if (Remove-PastaExtraida) {
        Write-Host "A pasta extraída foi apagada: o sen agora roda de $Destino."
    }
    else {
        Write-Host "A pasta extraída ($origem) não foi apagada (está em uso ou tem outros arquivos); pode apagá-la." -ForegroundColor Yellow
    }
}
if ($pathNovo) {
    Write-Host "Abra um terminal novo e rode: sen login"
}
else {
    Write-Host "Rode: sen login"
}
