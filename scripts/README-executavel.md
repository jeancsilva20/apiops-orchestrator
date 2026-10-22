# sen — Sensedia API Orchestrator CLI

CLI do APIOps Orchestrator. Nada mais precisa estar instalado: baixe o pacote do seu sistema.

| Sistema | Pacote | Requisitos |
|---|---|---|
| Windows | `sen-<versão>-windows-x64.zip` | Windows 10 ou 11, 64 bits |
| Linux | `sen-<versão>-linux-x64.tar.gz` | 64 bits, glibc 2.35 ou mais nova (Ubuntu 22.04+, Debian 12+, Fedora 36+) |

O instalador coloca o `sen` na sua pasta de usuário, põe no PATH e pede a credencial: `client_id` e `client_secret`, ou o Basic já pronto.

## Windows

Extraia o zip e, no PowerShell, dentro da pasta extraída:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

Depois, abra um terminal novo. O `sen` fica em `%LOCALAPPDATA%\sen`.

## Linux

```bash
tar -xzf sen-<versão>-linux-x64.tar.gz
cd sen-<versão>-linux-x64
./install.sh
```

Depois, abra um terminal novo. O `sen` fica em `~/.local/share/sen`, com um atalho em `~/.local/bin`.

## Usar

```bash
sen login
sen --help
```

## Atualizar ou trocar a credencial

- **Nova versão:** instale o pacote novo do mesmo jeito. A credencial e a sessão são mantidas.
- **Trocar a credencial:** rode o instalador da pasta onde o `sen` está e responda `n` em "Manter a credencial atual?".
  - Windows: `powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\sen\install.ps1"`.
  - Linux: `~/.local/share/sen/install.sh`.
