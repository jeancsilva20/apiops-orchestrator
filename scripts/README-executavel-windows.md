# sen — Sensedia API Orchestrator CLI

CLI do APIOps Orchestrator. Requer Windows 10 ou 11, 64 bits; nada mais precisa estar instalado.

## Instalar

Extraia o zip e, no PowerShell, dentro da pasta extraída:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

O instalador pede a credencial: `client_id` e `client_secret`, ou o Basic já pronto. Depois, abra um terminal novo.

## Usar

```powershell
sen login
sen --help
```

## Atualizar ou trocar a credencial

- **Nova versão:** rode o `install.ps1` do pacote novo. A credencial e a sessão são mantidas.
- **Trocar a credencial:** rode `powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\sen\install.ps1"` e responda `n` em "Manter a credencial atual?".
