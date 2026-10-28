# sen — Sensedia API Orchestrator CLI

CLI do APIOps Orchestrator. Nada mais precisa estar instalado: baixe o pacote do seu sistema.

| Sistema | Pacote | Requisitos |
|---|---|---|
| Windows | `sen-<versão>-windows-x64.zip` | Windows 10 ou 11, 64 bits |
| Linux | `sen-<versão>-linux-x64.tar.gz` | 64 bits, glibc 2.35 ou mais nova (Ubuntu 22.04+, Debian 12+, Fedora 36+) |

O instalador coloca o `sen` na sua pasta de usuário, põe no PATH e pede a credencial: `client_id` e `client_secret`, ou o Basic já pronto. No fim, ele apaga a pasta extraída, que não é mais necessária.

## Windows

1. Extraia o zip.
2. Na pasta extraída, dê dois cliques em `install.cmd`. Se o Windows pedir confirmação para executar, confirme.

   Ou, no PowerShell:

   ```powershell
   powershell -ExecutionPolicy Bypass -File "<pasta extraída>\install.ps1"
   ```

3. Abra um terminal novo.

O `sen` fica em `%LOCALAPPDATA%\sen`.

## Linux

No terminal, na pasta onde o arquivo foi baixado:

```bash
tar -xzf sen-<versão>-linux-x64.tar.gz
./sen-<versão>-linux-x64/install.sh
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
  - Windows: dois cliques em `install.cmd` em `%LOCALAPPDATA%\sen` (cole esse caminho na barra do Explorador de Arquivos), ou `powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\sen\install.ps1"`.
  - Linux: `~/.local/share/sen/install.sh`.
