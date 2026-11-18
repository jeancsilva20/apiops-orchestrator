# Clientes do pacote do `sen`

Cada arquivo `<cliente>.sen` desta pasta guarda os endereços de um cliente. O build recebe o nome do cliente e grava esse bloco no `.sen.example` do pacote, de onde o instalador cria o `.sen`.

```powershell
.\scripts\build-exe.ps1 -Client ecad
wsl bash scripts/build-linux.sh ecad
```

## Novo cliente

Crie `<cliente>.sen` (nome em minúsculas, com letras, números e hífen) no formato do `.sen`:

| Chave | Obrigatória | O que é |
|---|---|---|
| `AUTH_HOST` | Sim | Endereço do gateway que expõe a Orchestrator Auth API |
| `AUTH_LOGIN_PATH` | Sim | Caminho da rota de login nessa API |
| `AUTH_VALIDATE_PATH` | Não | Caminho da rota de validação, quando não for o do login seguido de `/validation` |
| `HOST` | Não | Endereço do Manager, quando não for `https://platform-production.sensedia.com` |

O arquivo não leva segredo: o build recusa um que defina `SEN_CREDENTIALS`. A credencial é pedida pelo instalador, na máquina de quem usa.
