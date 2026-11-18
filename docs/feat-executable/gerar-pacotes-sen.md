# Gerar os pacotes do `sen`

Como gerar, a partir do repositório `apiops-orchestrator`, o executável do `sen` e os pacotes de entrega para Windows e Linux. Última atualização: **2026-11-18** (branch `feat/executable`).

Cada sistema tem um script na pasta `scripts/` do repositório. Nenhum deles usa o Poetry: cada um monta um ambiente Python próprio, só com as dependências de runtime do `requirements.txt`.

| Sistema | Script | Onde roda |
|---|---|---|
| Windows | `scripts/build-exe.ps1` | PowerShell no Windows |
| Linux | `scripts/build-linux.sh` | WSL com Ubuntu 22.04, ou uma máquina Ubuntu 22.04 |

## Cliente

Todo pacote é gerado para um cliente, e o cliente é obrigatório nos dois scripts. O executável é o mesmo para todos: o que muda é o `.sen.example` do pacote, que leva os endereços do cliente, e o nome do pacote.

Os endereços ficam em `scripts/clients/<cliente>.sen`:

| Chave | Obrigatória | O que é |
|---|---|---|
| `AUTH_HOST` | Sim | Endereço do gateway que expõe a Orchestrator Auth API |
| `AUTH_LOGIN_PATH` | Sim | Caminho da rota de login nessa API |
| `AUTH_VALIDATE_PATH` | Não | Caminho da rota de validação, quando não for o do login seguido de `/validation` |
| `HOST` | Não | Endereço do Manager, quando não for `https://platform-production.sensedia.com` |

Para um cliente novo, crie o arquivo dele nessa pasta (nome em minúsculas, com letras, números e hífen) e gere os pacotes com esse nome. O arquivo não leva segredo: o build recusa um que defina `SEN_CREDENTIALS`.

## Windows

### Pré-requisitos

- Python 3.12 ou mais novo, acessível como `python` no PATH.
- Acesso à internet: o script instala as dependências e o PyInstaller com o pip.

### Gerar

Na raiz do repositório, no PowerShell:

```powershell
.\scripts\build-exe.ps1 -Client ecad
```

Se o PowerShell bloquear a execução de scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1 -Client ecad
```

Se o Python não estiver no PATH como `python`, passe o caminho dele:

```powershell
.\scripts\build-exe.ps1 -Client ecad -Python "C:\caminho\para\python.exe"
```

O executável sozinho fica em `build\exe\out\sen.exe`. O pacote de entrega vai para `dist\` (ver [O que sai](#o-que-sai)).

## Linux

O binário do Linux só roda em distros com glibc igual ou mais nova que a da máquina onde foi gerado. Por isso o build é feito no Ubuntu 22.04 (glibc 2.35): o pacote vale para Ubuntu 22.04+, Debian 12+ e Fedora 36+.

### Preparar uma vez

No Windows, instale o WSL com o Ubuntu 22.04, se ainda não tiver. Pode pedir reinício e a criação de um usuário do Linux.

```powershell
wsl --install -d Ubuntu-22.04
```

Dentro do Ubuntu, instale o Python 3.12 e o `binutils` (pede a senha do sudo):

```bash
sudo apt-get update
sudo apt-get install -y software-properties-common binutils
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
```

Se faltar o Python 3.12 ou o `binutils`, o script para e mostra esses mesmos comandos.

### Gerar

Do PowerShell, na raiz do repositório:

```powershell
wsl bash scripts/build-linux.sh ecad
```

Se o Ubuntu 22.04 não for a distro padrão do WSL (`wsl -l -v` marca a padrão com `*`):

```powershell
wsl -d Ubuntu-22.04 bash scripts/build-linux.sh ecad
```

Numa máquina Ubuntu 22.04, sem WSL, na raiz do repositório:

```bash
bash scripts/build-linux.sh ecad
```

Para usar outro Python 3.12, defina `PYTHON`:

```bash
PYTHON=/caminho/para/python3.12 bash scripts/build-linux.sh ecad
```

O build acontece em `~/.cache/sen-build`, dentro do Linux. O pacote de entrega vai para a pasta `dist/` do repositório, a mesma do Windows.

## O que sai

Os dois scripts gravam na mesma pasta, `dist/sen-<versão>/<cliente>/`. A versão vem do campo `version` do `pyproject.toml` e é a mesma para todos os clientes.

```
dist/sen-0.1.1/
└── ecad/
    ├── sen-0.1.1-ecad-windows-x64.zip    # sen.exe, install.cmd, install.ps1, .sen.example, README.md
    └── sen-0.1.1-ecad-linux-x64.tar.gz   # sen, install.sh, .sen.example, README.md
```

A pasta do cliente é o que se entrega. O `.sen.example` de cada pacote é o gabarito de `src/apiops_orchestrator/.sen.example` até a linha da credencial, seguido do arquivo do cliente. O `README.md` vai dentro dos pacotes e é gerado a partir de `scripts/README-executavel.md`, com `<versão>` e `<cliente>` preenchidos.

Para gerar uma versão nova, altere o `version` do `pyproject.toml` antes de rodar os scripts.

## O que os scripts fazem

Os dois seguem as mesmas cinco etapas, com os nomes que aparecem na saída:

1. **Ambiente limpo.** Apaga o build anterior e cria um venv só com o `requirements.txt`, o pacote e o PyInstaller 6.22.3.
2. **PyInstaller.** Gera um executável de arquivo único.
3. **Conferindo que nenhum segredo entrou no binário.** Lista o conteúdo do executável e falha se encontrar `.sen`, `.sen_session` ou `.env`. Na máquina de quem gera, esses arquivos ficam dentro do pacote `apiops_orchestrator`. Por isso os scripts nunca coletam dados desse pacote, e o script Linux copia o código para o build já sem eles.
4. **Smoke test.** Roda `sen --version` e confere a versão.
5. **Pacote.** Monta o `.sen.example` do cliente e o README, e gera o zip ou o tar.gz.

## Erros comuns

| Erro | Causa | O que fazer |
|---|---|---|
| `Informe o cliente` ou `Cliente '...' não existe` | O cliente não foi passado, ou não há `scripts/clients/<cliente>.sen` | Passe um dos clientes listados na mensagem, ou crie o arquivo do cliente novo |
| `... não define AUTH_HOST` (ou `AUTH_LOGIN_PATH`) | O arquivo do cliente está sem uma chave obrigatória | Preencha a chave no arquivo do cliente |
| O PowerShell diz que a execução de scripts foi desabilitada | Política de execução do PowerShell | Rode com `powershell -ExecutionPolicy Bypass -File .\scripts\build-exe.ps1 -Client <cliente>` |
| Falha na etapa 1 do Windows, ao criar o venv | `python` não está no PATH ou é anterior ao 3.12 | Passe `-Python` com o caminho do Python 3.12 |
| `Faltam dependências no Linux` | Falta o Python 3.12 ou o `binutils` no Linux | Rode os comandos de [Preparar uma vez](#preparar-uma-vez) |
| `Arquivo sensível dentro do binário` | Algum segredo entrou no executável | Não distribua o pacote. Confira se alguém adicionou `--collect-data` ou `--add-data` do `apiops_orchestrator` ao script |
| `sen --version não respondeu ...` | O executável não abre ou a versão não bate | Rode o executável gerado à mão para ver o erro |
