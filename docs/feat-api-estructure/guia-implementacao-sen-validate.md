# Guia de implementação — `sen validate` no orquestrador

| Meta | Valor |
|---|---|
| Data | 2026-10-15 |
| Para quem | quem for escrever o código de produção do `sen validate` |
| Base empírica | [Caderno de testes](prova-fluxo-validate/CADERNO-DE-TESTES.md) — 10 cenários validados contra a API 417 |
| Base de contrato | [plano §8.4](plano-comandos-sen.md) — W-1 a W-9, regras do wire provadas por escrita |
| Protótipo de referência | `prova-fluxo-validate/provar_sen_validate.py` — **não é código de produção**, é a prova de que o fluxo funciona |
| Gate | este guia alimenta a change proposal OpenSpec; nada aqui autoriza código |

> Este documento é **prescritivo**: diz onde cada peça entra na arquitetura
> existente, qual padrão seguir e quais armadilhas já custaram caro. O protótipo
> provou *o que* funciona; aqui está *como* escrever direito.

---

## 1. As nove regras que o código precisa respeitar

Tudo abaixo foi observado na plataforma, não inferido. Violar qualquer uma gera
falha **silenciosa** — HTTP 200 com perda — ou 500 sem mensagem.

| # | Regra | Consequência de violar |
|---|---|---|
| **W-1** | `idTemp` é **obrigatório** em interceptor novo | HTTP **500** com `errors: []` |
| **W-9** | `idTemp` é único no **payload inteiro**, não no escopo | o Manager deduplica e **descarta** um item, com 200 |
| **W-3** | `position` é contínua **entre escopos** (resource 2..8, operation 9..15) | ordem de execução corrompida |
| **W-5** | Lista vazia de interceptors significa **herdar** | não existe "rota sem fluxo"; quebrar herança exige **reproduzir a lista** |
| **W-4** | O Manager guarda o fluxo **resolvido**; o repositório guarda o **delta** | publicar o delta cru **apaga** o herdado |
| **W-6** | A operação **pertence ao recurso**; `id` de operação não é global | operação que muda de recurso é **descartada**, com 200 |
| **W-7** | O gate do AG está no `PUT /revisions`, **não** no `PUT /apis` | escrever nos dois deixa estado meio-aplicado |
| **W-2** | O repositório pode referenciar um `Custom` que não existe mais | falha só na publicação — **decidido em 2026-10-15:** passa a abortar na validação, nomeando o id |
| **W-8** | **HTTP 200 não é prova de sucesso** | três perdas silenciosas distintas nesta investigação |

### A regra de identidade, condensada

```
position  →  do ESCOPO    (por escopo e execution point; contínua entre escopos)
idTemp    →  do PAYLOAD   (único em toda a chamada)
id        →  null em item novo; preservado em item existente
```

> ⚠️ **Correção (2026-10-15).** Uma versão anterior deste guia afirmava que
> `domain/models/interceptors_model.py` já implementava essa convenção. **Não
> implementa.** O `set_ids_from_position` deriva `idTemp` de `position` — que é
> do **escopo** — e com isso fabrica exatamente a colisão da armadilha #2 do §8.
> Além disso, `id` e `idTemp` são `int` obrigatórios, então "`id` nulo em item
> novo" não é sequer representável. O modelo precisa ser **separado** em
> declarativo (o que o YAML expressa) e wire (o que o payload exige), como o §2
> já indica.

---

## 2. Onde cada peça entra

```
adapters/inbound/cli/
   cli_adapter.py ........................ comando `sen validate` (+ subcomandos ocultos)

application/services/
   validate_service.py ................... NOVO  — orquestra E1→E4
   governance_precheck_service.py ........ NOVO  — calcula faltantes ANTES de escrever
   repo_importer_service.py .............. REESCREVER — descoberta do layout D-005

application/exceptions/
   validate_exceptions.py ................ NOVO  — erros de negócio + exit codes

domain/services/              (lógica pura, sem rede, 100% testável)
   repo_layout.py ........................ NOVO  — slug, nome de pasta/arquivo, método
   interceptor_flow.py ................... NOVO  — partição, casamento, construção, idTemp
   template_conformance.py ............... NOVO  — comparação com a régua

domain/models/
   api_operations_model.py ............... AJUSTAR — destination objeto, inherit
   resources_model.py .................... AJUSTAR — destination, inherit, interceptors
   interceptors_model.py ................. SEPARAR — declarativo (YAML) × wire
   validate_view.py ...................... NOVO  — resposta do use-case → CLI

domain/ports/
   manager_api_port.py ................... ESTENDER — PUT de revision, governança

adapters/outbound/http/manager_api/
   manager_api_adapter.py ................ ESTENDER — implementar os métodos novos
```

A regra da hexagonal que importa aqui: **`domain/services/` não conhece rede**.
Toda a lógica das nove regras acima é determinística e deve morar lá, recebendo
dados já lidos. Só o `application/` conversa com ports.

---

## 3. Port — o que falta no contrato

`domain/ports/manager_api_port.py` hoje tem `publish_api_changes`, que faz
**`POST /revisions`** — isso **cria** uma revision. O `sen validate` precisa
**atualizar** a Draft existente.

```python
class ManagerApiPort(ABC):
    # ... métodos existentes ...

    @abstractmethod
    def get_revision(self, revision_id: int) -> Dict[str, Any]:
        """Estado completo de uma revision (interceptors, resources, api aninhado)."""

    @abstractmethod
    def update_revision(self, revision_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        """PUT denso na revision. NÃO cria revision — atualiza a existente.

        Criar revision é ato humano (D-005 §9): o orquestrador nunca usa POST.
        """

    @abstractmethod
    def get_workflow(self, workflow_id: int) -> Dict[str, Any]:
        """Workflow com seus stages e `attributesRequisites` (Adaptive Governance)."""

    @abstractmethod
    def list_attributes(self) -> List[Dict[str, Any]]:
        """Catálogo `id ↔ name` dos atributos do AG."""
```

E os erros do port seguem o padrão já estabelecido: `ManagerApiTransportRejectedError`
(4xx, com `status_code`) e `ManagerApiTransportUnavailableError` (5xx/rede). Para o
bloqueio de governança, **um sinal de domínio próprio** (§7).

### Uma correção necessária no adapter

`get_custom_interceptor_by_id` chama `GET /custom-interceptors/{id}` e **assume
que existe**. Comprovado: o endpoint devolve **404** para ids apagados.

> ⚠️ **Correção (2026-10-15).** O mecanismo não é `KeyError`. O `_request` traduz
> 4xx em `ManagerApiTransportRejectedError` **antes** de o corpo ser lido, então
> `json_response["id"]` nunca chega a executar. Trocar o acesso por `.get()` não
> corrigiria nada: o que falta é **capturar o 404** e devolver `None`.

E o destino desse `None` está decidido: **aborta**. O repositório que referencia um
`Custom` inexistente falha na validação, nomeando o id. O protótipo faz diferente —
repõe o `content` varrendo revisions antigas da própria API (`indexar_customs_da_api`) —
e isso **não deve ser transplantado**: ressuscita uma referência que um administrador
apagou de propósito e, quando não acha, descarta o item em silêncio.

---

## 4. Domain services — a lógica pura

### 4.1 `repo_layout.py`

Descoberta e nomenclatura do layout D-005 §4. Sem rede, sem IO — recebe caminhos
e devolve estrutura.

```python
GOVERNED_EXECUTION_POINTS = frozenset({"FIRST", "SECOND"})
MAX_SLUG, MAX_ARQUIVO = 60, 90
METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")


def metodo_do_arquivo(nome: str) -> str | None:
    """`<método>_<path>.yaml` → método. O YAML da operação NÃO carrega `method`."""
```

Fonte: `exemplos-gerados/extrair_estrutura.py` já implementa slug, desambiguação
legível, marca `sha1(operações)[:6]` e orçamento de caminho — validados contra 6
APIs reais. **Transplantar, não reescrever**, com dois reparos conhecidos:

| Reparo | Motivo |
|---|---|
| citar escalar iniciado por indicador YAML (`*`, `&`, `!`, `\|`, `>`, `%`, `@`, `` ` ``, `[`, `{`, `,`, `?`) | `replaceChar: *****` quebra o parse |
| preservar string numérica (`"1000"`) como string citada | o wire traz `"quota": "1000"`; virar inteiro quebra o round-trip |

### 4.2 `interceptor_flow.py`

O coração das regras W-1 a W-6. Toda a aritmética de identidade mora aqui.

```python
def particionar(remotos: list[dict]) -> tuple[list[dict], list[dict]]:
    """governados (FIRST/SECOND) × preservados (V-22). O preservado volta intacto."""


def montar_fluxo(
    bloco_repo: dict,          # o YAML do escopo
    remotos: list[dict],       # o que a plataforma tem HOJE nesse escopo
    e_raiz: bool,
    gerar_idtemp: Callable[[], int],   # contador GLOBAL do payload (W-9)
    resolver_custom: Callable[[int], str | None],
) -> list[dict]:
    """Fluxo a publicar para UM escopo.

    raiz          → publica exatamente o que o repositório declara
    inherit:true  → PRESERVA a lista remota (herança materializada, W-4) + append
    inherit:false → publica SOMENTE os itens declarados
                    ATENÇÃO: lista VAZIA não zera o fluxo — ela HERDA (W-5, T06).
                    "Rota que não executa nada" não existe na plataforma.

    `position` NÃO é renumerada nos itens reusados (W-3).
    """
```

**Por que `inherit: true` preserva em vez de reconstruir:** o Manager guarda o
fluxo já resolvido (W-4). O recurso `Atribuicao Responsavel` tem 9 itens no wire
e 1 no YAML. Publicar o delta apaga 8.

O contador de `idTemp` começa **acima do maior id/idTemp/position do payload
inteiro** e é compartilhado por todos os escopos:

```python
def preparar_contador_idtemp(draft: dict) -> Iterator[int]:
    """W-9: idTemp é do payload, não do escopo. Colisão = item descartado com 200."""
```

### 4.3 `template_conformance.py`

A camada de **política** (§6). Compara o fluxo efetivo com a régua, percorrendo
todos os caminhos de execução (D-013), por **sequência e `content`** (V-11 §4).

```python
def comparar(fluxo_efetivo: list[dict], regua: list[dict]) -> list[Achado]:
    """append → INFO · override/remoção/alteração → WARNING · nunca bloqueia."""
```

Duas armadilhas que o protótipo cometeu e o código não deve repetir:

- a **raiz da revision não herda de ninguém** — comparar item a item com a régua,
  nunca tratar como append;
- `inherit: false` **sem lista** é ambíguo (V-25 em aberto) — reportar como
  "remoção não representável", não como "não executa nada".

---

## 5. Application — o use-case

### 5.1 `ValidateService`

Recebe **ports**, nunca adapters concretos. Espelha `CompletenessService`.

```python
class ValidateService:
    def __init__(self, manager_api: ManagerApiPort, importer: LocalFileImporterPort,
                 settings: Settings, session: Optional[LoginSession] = None):
        ...

    def validate(self, repo_path: Path, *, confirmar: Callable[[str], bool]) -> ValidateView:
        """E1→E4. `confirmar` é injetado pela CLI (guarda 2) — o service não lê stdin."""
```

A ordem, com as guardas no lugar certo:

```
E1  carregar o repositório                        sem rede
    ── guarda 1: version e basePath (D-11) ──     aborta antes de tudo
E2  régua: GET /apis/{template} + conformidade    GET
    ── pré-check de governança (§7) ──            aborta ANTES de escrever
    ── guarda 2: confirmação (D-17) ──            só em EXECUTION_MODE=local
E3  PUT ÚNICO na revisão 1                        ESCRITA
E3.1 conferência pós-publicação (W-8)             GET
E4  completeness                                   GET — reusa o serviço existente
```

**Um único PUT** (W-7): o payload da revision carrega `api` aninhado com
`apiTags`, `name` e `description`. Escrever também em `PUT /apis` fura o gate do
AG e cria estado meio-aplicado.

### 5.2 `GovernancePrecheckService`

O que evita o estado inconsistente que o teste manual expôs. A V-23 §4 já definiu
a mecânica; falta implementá-la **antes** da escrita:

```
1. GET /apis/{id}                     → visibility.groupVisibility.name
2. GET workflows                      → workflow do GRUPO (não o da revision, V-23 §3)
3. GET workflows/{id}                 → attributesRequisites do stage alvo
4. GET attributes                     → catálogo id ↔ name
5. exigidos(mustHave) − presentes(apiTags do repo) = faltantes
6. faltantes? → GovernanceBlockedError, exit 3, SEM escrever
```

**Nunca parsear `messages[]`** (V-23 §4): o faltante é sempre **calculado**.

### 5.3 Conferência pós-publicação

Obrigatória, não opcional (W-8):

```python
def conferir(enviado: dict, publicado: dict) -> list[Divergencia]:
    """Compara operações (método, path), interceptors por escopo e recursos vazios."""
```

Divergência é **falha**: o estado não corresponde ao enviado, mesmo com 200.

---

## 6. CLI — seguindo o padrão do `sen completeness`

O comando `completeness` é o modelo mais recente e deve ser copiado na forma.

```python
@sen_app.command("validate")
def validate(
    ctx: typer.Context,
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repositório da API."),
    output: OutputFormat = typer.Option(OutputFormat.TEXT, "--output", "-o",
                                        help="Output format (text, json, yaml)."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbosity only."),
):
    """Valida o repositório e publica na Draft para obter o veredito do AG."""
    try:
        service_factory = (ctx.obj or {}).get("validate_service_factory")
        if not callable(service_factory):
            rprint("[bold red]Erro:[/bold red] Serviço de validação indisponível no contexto.")
            raise typer.Exit(code=1)

        service = cast(Callable[[], ValidateService], service_factory)()
        view = service.validate(repo_path=repo or Path.cwd(), confirmar=_confirmar_publicacao)

        display_output(
            view.to_document(),
            output_format=output,
            text_callback=lambda: _render_validate_text(view),
        )
    except typer.Exit:
        raise
    except ValidateError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        rprint(f"[bold red]Erro ao validar:[/bold red] {e}")
        raise typer.Exit(code=1)
```

O que o padrão exige, ponto a ponto:

| Elemento | Regra |
|---|---|
| **factory no contexto** | montada no composition root (`main.py`), lazy — `Settings` só é lida quando o comando roda |
| **`--output text\|json\|yaml`** | sempre, via `display_output` + `text_callback` |
| **`--verbose`** | só verbosidade de log, nunca formato |
| **view com `to_document()`** | dataclass `frozen=True` em `domain/models/`, com schema versionado (`apiops.sen-validate/v1`) |
| **exceções tipadas** | herdam de `ValidateError`, carregam `message` e `exit_code`; a CLI só traduz |
| **`typer.Exit` repassado** | o `except typer.Exit: raise` vem antes do catch genérico |
| **subcomandos ocultos** | `hidden=True` (D-19) — `structure`, `template`, `draft` servem a teste, não ao uso diário |

A guarda 2 (confirmação `s/n`) é da **CLI**, não do service: o service recebe um
callable `confirmar`. Em `EXECUTION_MODE=pipeline` a CLI injeta `lambda _: True`.

---

## 7. Erros e exit codes

Seguindo o padrão de `CompletenessError`:

```python
class ValidateError(Exception):
    exit_code = 1
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class IdentidadeDivergenteError(ValidateError):
    """version/basePath diferem do Manager (D-11). Oriente procurar o administrador."""


class TemplateAusenteError(ValidateError):
    """spec.template vazio (D-12)."""


class GovernanceBlockedError(ValidateError):
    """Bloqueio do Adaptive Governance. Canal e exit code próprios (V-23)."""
    exit_code = 3
    def __init__(self, workflow_id: int, stage_id: int, missing: list[dict], raw: dict):
        ...


class PublicacaoDivergenteError(ValidateError):
    """A plataforma aceitou (200) mas o estado não corresponde ao enviado (W-8)."""
```

| Código | Significado |
|---|---|
| `0` | sucesso — inclui WARNING de régua e completeness abaixo do gate |
| `1` | falha técnica ou de gramática |
| `3` | **bloqueio de governança** — canal distinto, a esteira ramifica sem ler texto |

---

## 8. Armadilhas provadas — não repetir

| # | Armadilha | Como se manifesta |
|---|---|---|
| 1 | montar interceptor novo sem `idTemp` | **500** sem mensagem |
| 2 | calcular `idTemp` por escopo | item descartado, **200** |
| 3 | renumerar `position` 1..N por escopo | ordem corrompida (W-3) |
| 4 | publicar o delta de `inherit: true` | apaga o fluxo herdado (W-4) |
| 5 | reaproveitar `id` de operação em outro recurso | operação descartada, **200** |
| 6 | escrever em `PUT /apis` e `PUT /revisions` | estado meio-aplicado quando o AG barra |
| 7 | tratar **200** como sucesso | três perdas silenciosas comprovadas |
| 8 | esperar que lista vazia "zere" o fluxo | ela **herda** (W-5) |
| 9 | parsear `messages[]` do erro do AG | o faltante é **calculado** (V-23 §4) |
| 10 | assumir que `GET /custom-interceptors/{id}` sempre responde | **404** para id apagado |

---

## 9. Testes a escrever

| Camada | O que testar | Rede |
|---|---|---|
| `domain/services/repo_layout` | slug, colisão, truncamento, marca, método do nome do arquivo | não |
| `domain/services/interceptor_flow` | partição, casamento, construção, **unicidade de `idTemp`**, preservação de `position` | não |
| `domain/services/template_conformance` | append/override/tombstone; **oracle real**: os 4 achados previstos nas APIs 409/417 | não |
| `application/ValidateService` | cascata E1→E4 com port fake; guardas; tudo-ou-nada (D-18) | não |
| `application/GovernancePrecheck` | cálculo do faltante com catálogo fake | não |
| CLI | `--output json` bate com o schema; exit codes 0/1/3 | não |
| integração | os 10 cenários do caderno, com backup e restore | **GET + PUT** |

Fixtures: `exemplos-gerados/saida/` — **regerar antes**, com os dois reparos de
serialização do §4.1.

---

## 10. O que ainda falta decidir

**Fila fechada em 2026-10-15.** Os seis itens foram decididos no refino do
`sen validate` e alimentaram a change OpenSpec `add-sen-validate`.

| # | Pendência | Desfecho |
|---|---|---|
| **V-25** | gramática do tombstone | **lista completa explícita** — única forma expressável; o T06 provou que lista vazia herda. [V-25](decisoes-refino-409/V-25-tombstone.md) |
| **D-20** | stage do AG no payload | **lido em runtime** da revisão alvo e reenviado intacto. A pergunta estava mal formulada: o stage 1401 nunca esteve na Draft, e reenviar o atual **dispara** o AG. [D-020](d020-stage-do-adaptive-governance.md) |
| **W-2** | `Custom` referenciado que não existe | **aborta**, nomeando o id. Sem reposição por revisão antiga, sem descarte silencioso. O catálogo é autoridade: `404` significa ausente |
| **D-5** | shape por tipo de interceptor | **dissolvido na API template**, que valida tipo e preenchimento no regime `INFO`/`WARNING`. Os 7 `*-default-interceptors` saem |
| **D-6 / V-18** | arquivo do escopo `all` | **`all.yaml`**, obrigatório pelo nome exato; ausência aborta na E1. [V-18](decisoes-refino-409/V-18-arquivo-do-escopo-raiz.md) |
| **P-2** | régua inalcançável | **aborta nos dois modos**, e também com `spec.template` vazio |

> ⚠️ **Correção (2026-10-15).** A linha da D-5 dizia que o shape fora *"perdido ao
> remover os `*-default-interceptors`"*. Eles **não foram removidos** — estão em
> `domain/schemas/`, sete arquivos, ~128 KB. Não é perda: é aposentadoria
> planejada, e a substituição é a API template.

---

## 11. Referências

- [Caderno de testes](prova-fluxo-validate/CADERNO-DE-TESTES.md) — os 10 cenários
- [Plano dos comandos](plano-comandos-sen.md) — §6 o fluxo, §8.4 o contrato do wire
- [D-005](d005-layout-revisado.md) · [V-11](decisoes-refino-409/V-11-conformidade-com-a-regua.md) · [V-22](decisoes-refino-409/V-22-estado-nao-governado.md) · [V-23](decisoes-refino-409/V-23-bloqueio-do-adaptive-governance.md)
- [Análise de complexidade](analise-complexidade-orquestrador.md) — estado do código atual
