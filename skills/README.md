# Skills de agente para o `sen`

Roteiros para um agente de IA (Claude Code) usar a CLI `sen` em nome de quem desenvolve a API.

| Skill | Para quê | Altera algo? |
|---|---|---|
| [`sen-explore`](sen-explore/SKILL.md) | Responder perguntas sobre o que está no Manager: APIs, revisões, ambientes, régua e Draft. Completude e governança ficam de fora, porque dependem do Adaptive Governance | Não |
| [`sen-api-developer`](sen-api-developer/SKILL.md) | Responder perguntas sobre os arquivos do repositório da API e alterá-los (rotas, responses, timeout, backend, interceptors, apiTags, componentes) | Sim. Mudança sem risco é aplicada direto; com risco, só depois do seu ok |

As skills não entram no build do `sen`. Elas ficam neste repositório e são instaladas por cópia.

## Requisito

Um `sen` que tenha o comando `sen schema`. Para conferir:

```bash
sen schema --help
```

Se aparecer `No such command 'schema'`, atualize o `sen`.

## Instalar

Copie a pasta de cada skill para a pasta de skills do agente:

- `.claude/skills/` dentro do repositório da API, para valer só nele. Commitada, vale para o time.
- `~/.claude/skills/`, para valer em todos os seus projetos.

Linux ou macOS, a partir da raiz deste repositório:

```bash
mkdir -p ~/.claude/skills
cp -r skills/sen-explore skills/sen-api-developer ~/.claude/skills/
```

Windows (PowerShell), a partir da raiz deste repositório:

```powershell
New-Item -ItemType Directory -Force "$HOME\.claude\skills" | Out-Null
Copy-Item -Recurse skills\sen-explore, skills\sen-api-developer "$HOME\.claude\skills\"
```

## Proteger a credencial

As skills orientam o agente a nunca ler o `.sen` (credencial) nem o `.sen_session` (sessão). A proteção de verdade, porém, é uma regra de permissão do Claude Code. Acrescente esta regra ao `~/.claude/settings.json`. Se o arquivo já tiver `permissions.deny`, junte as duas linhas às que já existem:

```json
{
  "permissions": {
    "deny": [
      "Read(//**/.sen)",
      "Read(//**/.sen_session*)"
    ]
  }
}
```

- O `//**` vale para qualquer pasta, inclusive a de instalação do `sen`, fora do projeto. No Windows, vale para todos os drives.
- A regra barra as ferramentas de leitura do agente e os comandos de arquivo que ele roda no terminal, como `cat`, `head` e `tail`. Ela não barra um script que abra o arquivo por conta própria. Para esse caso, use o sandbox do Claude Code.
- O próprio `sen` continua lendo esses arquivos normalmente, porque é ele que usa a sessão.

## Menos pedidos de permissão (opcional)

Por padrão, o Claude Code pede permissão a cada comando do `sen`. Os comandos abaixo só leem, e podem ser liberados em `permissions.allow` no mesmo `settings.json`:

```json
"allow": [
  "Bash(sen list *)",
  "Bash(sen schema *)",
  "Bash(sen diag *)"
]
```

Não libere o `sen validate`. Ele pode gravar na Draft do Manager, e a skill só faz isso quando você pede. Deixe o pedido de permissão como uma segunda conferência.
