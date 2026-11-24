"""Tabela declarativa dos 44 comandos: a matriz completa de opcoes em dados.

Escrever 148 testes a mao seria insustentavel e, pior, incompleto por omissao —
comando novo simplesmente nao ganharia testes. Aqui cada comando e uma linha, e
`test_option_matrix.py` deriva ~370 casos de 8 funcoes. A guarda
`test_toda_folha_esta_na_matriz` fecha o circuito: folha sem linha = vermelho.

O que a tabela consegue afirmar: a opcao e aceita, o valor chega ao servico com
o nome do contrato, exclusividade e limite sao recusados ANTES da rede, o
obrigatorio ausente e nomeado, a saida de maquina e parseavel, a fabrica ausente
encerra com 1 e excecao inesperada nao vaza texto cru.

O que ela NAO consegue, e nenhum ajuste de tabela faria: em que coluna o valor
cai, o texto de rotulo e rodape, mascaramento de valor sensivel, escape de `[`
em dado externo, escrita crua de `--raw`/`--script-only`, gravacao de
`--dir`/`--force`, prompt e exit 130. Essas continuam em testes escritos a mao,
e a maioria ja existe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.api_navigation_service import (
    ApiNavigationService,
)

NAO_INFORMADO = object()

NAV = ApiNavigationService
LIST = ApiListingService


@dataclass(frozen=True)
class Opcao:
    """Uma opcao de um comando, e o que se pode afirmar sobre ela."""

    flag: str
    valor: Optional[str] = None  # None => flag booleana
    kwarg: Optional[str] = None  # nome do parametro NO SERVICO
    esperado: Any = NAO_INFORMADO  # valor esperado apos o bind
    # Cada tupla e um conjunto de argumentos que nao pode conviver com esta flag.
    conflita_com: Tuple[Tuple[str, ...], ...] = ()
    # (valor fora da faixa, motivo) — recusa esperada antes de tocar o servico.
    limites: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Comando:
    caminho: Tuple[str, ...]
    fabrica: str
    retorno: Any
    classe: Optional[type] = None
    metodo: Optional[str] = None
    args_minimos: Tuple[str, ...] = ()
    opcoes: Tuple[Opcao, ...] = ()
    obrigatorias: Tuple[str, ...] = ()
    formatos: Tuple[str, ...] = ("json", "yaml")
    # False para os comandos cujo servico nao e um `_service(ctx).metodo(...)`
    # simples (escrita, prompt, repositorio local): esses tem teste dedicado.
    servico_conferivel: bool = True
    # `diag structure` nao recebe `ctx`: le o repositorio local sem fabrica.
    usa_fabrica: bool = True

    @property
    def ident(self) -> str:
        return " ".join(self.caminho)

    @property
    def argv(self) -> Tuple[str, ...]:
        return ("sen", *self.caminho)


def _linhas(*itens: Dict[str, Any]) -> list:
    return list(itens)


# Documentos minimos: com `-o json` o comando serializa o documento cru
# (`output_display.display_output`), entao basta ser serializavel e ter as
# chaves que o proprio comando le antes de imprimir.
_API = {"id": 400, "name": "API", "version": "1", "basePath": "/x"}
_REV = {"id": 8948, "number": 4, "lifeCycle": "DRAFT", "deployedIn": []}
_ENVELOPE = {"api": _API, "revision": _REV}


COMANDOS: Dict[str, Comando] = {}


def _registrar(comando: Comando) -> None:
    COMANDOS[comando.ident] = comando


# --------------------------------------------------------------------- sen get

_registrar(
    Comando(
        caminho=("get", "api"),
        fabrica="navegacao",
        classe=NAV,
        metodo="api_detail",
        retorno={**_API, "environments": [], "revisions": []},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "400", kwarg="api_id", esperado=400),),
    )
)

_REVISAO = (
    Opcao("--revision", "4", kwarg="number", esperado=4, conflita_com=(("--revision-id", "8948"),)),
    Opcao("--revision-id", "8948", kwarg="revision_id", esperado=8948),
)

_registrar(
    Comando(
        caminho=("get", "resources"),
        fabrica="navegacao",
        classe=NAV,
        metodo="structure",
        retorno={**_ENVELOPE, "root": {}, "resources": []},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "400", kwarg="api_id", esperado=400), *_REVISAO),
    )
)

_registrar(
    Comando(
        caminho=("get", "interceptors"),
        fabrica="navegacao",
        classe=NAV,
        metodo="interceptors",
        retorno={**_ENVELOPE, "mode": "own", "scopes": []},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(
            Opcao("--id", "400", kwarg="api_id", esperado=400),
            Opcao(
                "--revision",
                "4",
                kwarg="number",
                esperado=4,
                conflita_com=(("--revision-id", "8948"),),
            ),
            Opcao("--revision-id", "8948", kwarg="revision_id", esperado=8948),
            Opcao("--resource", "Token", kwarg="resource", esperado="Token"),
            Opcao("--operation", "POST /x", kwarg="operation", esperado="POST /x"),
            Opcao("--effective", kwarg="effective", esperado=True),
            # O nome muda na travessia: `--content` vira `include_content=`.
            Opcao("--content", kwarg="include_content", esperado=True),
            Opcao("--point", "FIRST", kwarg="point", esperado="FIRST"),
            # `--item` e nivel 4: nao convive com nenhum recorte de escopo.
            Opcao(
                "--item",
                "19220",
                conflita_com=(
                    ("--resource", "Token"),
                    ("--operation", "POST /x"),
                    ("--effective",),
                    ("--content",),
                    ("--point", "FIRST"),
                ),
            ),
        ),
    )
)

_registrar(
    Comando(
        caminho=("get", "custom"),
        fabrica="navegacao",
        classe=NAV,
        metodo="custom_interceptor",
        retorno={"id": 31, "name": "custom", "script": "console.log(1)"},
        args_minimos=("--custom-id", "31"),
        obrigatorias=("--custom-id",),
        opcoes=(
            Opcao("--custom-id", "31", kwarg="custom_id", esperado=31),
            Opcao("--script-only"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("get", "swagger"),
        fabrica="navegacao",
        classe=NAV,
        metodo="swagger",
        retorno={"openapi": "3.0.0", "paths": {}},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "400", kwarg="api_id", esperado=400), *_REVISAO),
    )
)

_registrar(
    Comando(
        caminho=("get", "workflow"),
        fabrica="navegacao",
        classe=NAV,
        metodo="workflow",
        retorno={"id": 327, "name": "w", "stages": []},
        args_minimos=("--id", "327"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "327", kwarg="workflow_id", esperado=327),),
    )
)

_registrar(
    Comando(
        caminho=("get", "governance"),
        fabrica="navegacao",
        classe=NAV,
        metodo="governance",
        retorno={**_ENVELOPE, "current": None, "next": None},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "400", kwarg="api_id", esperado=400), *_REVISAO),
    )
)

_registrar(
    Comando(
        caminho=("get", "impact"),
        fabrica="navegacao",
        classe=NAV,
        metodo="impact",
        retorno={"api": _API, "routes": [], "plans": [], "apps": []},
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        opcoes=(
            Opcao("--id", "400", kwarg="api_id", esperado=400),
            Opcao("--env", "1", kwarg="environment_id", esperado=1),
        ),
    )
)

_registrar(
    Comando(
        caminho=("get", "app"),
        fabrica="navegacao",
        classe=NAV,
        metodo="app",
        retorno={"id": 42, "name": "app", "subscriptions": []},
        args_minimos=("--id", "42"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "42", kwarg="app_id", esperado=42),),
    )
)

_registrar(
    Comando(
        caminho=("get", "plan"),
        fabrica="navegacao",
        classe=NAV,
        metodo="plan",
        retorno={"id": 66, "name": "plano", "interceptors": []},
        args_minimos=("--id", "66"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "66", kwarg="plan_id", esperado=66),),
    )
)

_registrar(
    Comando(
        caminho=("get", "environment"),
        fabrica="navegacao",
        classe=NAV,
        metodo="environment",
        retorno={"id": 1, "name": "Default", "maps": [], "apis": []},
        args_minimos=("--id", "1"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "1", kwarg="environment_id", esperado=1),),
    )
)

_registrar(
    Comando(
        caminho=("get", "role"),
        fabrica="navegacao",
        classe=NAV,
        metodo="role",
        retorno={"id": "uuid", "name": "role", "permissions": [], "members": []},
        args_minimos=("--id", "uuid"),
        obrigatorias=("--id",),
        opcoes=(Opcao("--id", "uuid", kwarg="role_id", esperado="uuid"),),
    )
)

_registrar(
    Comando(
        caminho=("get", "user"),
        fabrica="navegacao",
        classe=NAV,
        metodo="user",
        retorno={"username": "paulo", "teams": [], "roles": []},
        args_minimos=("--username", "paulo"),
        obrigatorias=("--username",),
        opcoes=(Opcao("--username", "paulo", kwarg="username", esperado="paulo"),),
    )
)

_registrar(
    Comando(
        caminho=("get", "team"),
        fabrica="navegacao",
        classe=NAV,
        metodo="team",
        retorno={"name": "APIOps", "members": []},
        args_minimos=("--name", "APIOps"),
        obrigatorias=("--name",),
        opcoes=(Opcao("--name", "APIOps", kwarg="name", esperado="APIOps"),),
    )
)

_registrar(
    Comando(
        caminho=("get", "interceptor-type"),
        fabrica="navegacao",
        classe=NAV,
        # Sem `--type` chama `interceptor_types()`; com a flag, `interceptor_type(nome)`
        # (navigation_cli.py:1617). A matriz afirma sobre o caminho sem flag.
        metodo="interceptor_types",
        retorno=[{"type": "Log", "fields": []}],
        opcoes=(Opcao("--type", "Rate limit"),),
    )
)

_registrar(
    Comando(
        caminho=("get", "trace"),
        fabrica="navegacao",
        classe=NAV,
        metodo="trace",
        retorno={"id": "abc", "steps": [], "request": {}, "response": {}},
        args_minimos=("--id", "abc"),
        obrigatorias=("--id",),
        opcoes=(
            Opcao("--id", "abc", kwarg="trace_id", esperado="abc"),
            # Inversao na travessia: a flag nega o parametro do servico.
            Opcao("--no-headers", kwarg="include_headers", esperado=False),
        ),
    )
)

_registrar(
    Comando(
        caminho=("get", "analytics"),
        fabrica="navegacao",
        classe=NAV,
        metodo="analytics",
        retorno={"total": 0, "window": {}, "sample": 0, "rankings": {}},
        opcoes=(
            Opcao("--api", "400", kwarg="api_id", esperado=400),
            Opcao("--env", "1", kwarg="environment_id", esperado=1),
            Opcao("--since", "24h", kwarg="since", esperado="24h"),
            Opcao("--until", "agora", kwarg="until", esperado="agora"),
            Opcao("--errors", kwarg="errors", esperado=True),
            Opcao("--uri", "/x", kwarg="uri", esperado="/x"),
            Opcao("--sample", "100", kwarg="sample", esperado=100),
            Opcao("--top", "3", kwarg="top", esperado=3),
        ),
    )
)

# -------------------------------------------------------------------- sen list

_registrar(
    Comando(
        caminho=("list", "api"),
        fabrica="listagem",
        classe=LIST,
        metodo="list_apis",
        retorno=[],
        servico_conferivel=False,  # passa por um pipeline de filtros, nao por bind direto
        formatos=(),
        opcoes=(
            Opcao("--id", "400", conflita_com=(("--query", "x"), ("--owner", "u"), ("--all",))),
            Opcao("--query", "x"),
            Opcao("--limit", "5", limites=(("0", "limite minimo"),)),
            Opcao("--offset", "0", limites=(("-1", "offset negativo"),)),
            Opcao("--all", conflita_com=(("--limit", "5"), ("--offset", "1"), ("--id", "400"))),
            Opcao("--revisions"),
            Opcao("--owner", "paulo"),
            Opcao("--team", "APIOps"),
            Opcao("--context", "me", limites=(("xyz", "contexto fora do catalogo"),)),
            Opcao("--workflow", "139"),
            Opcao("--stage", "420"),
            Opcao("--attribute", "CLI", limites=(("   ", "atributo em branco"),)),
            Opcao("--wide"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "environments"),
        fabrica="navegacao",
        classe=NAV,
        metodo="environments",
        retorno=_linhas({"id": 1, "name": "Default"}),
    )
)

_registrar(
    Comando(
        caminho=("list", "workflows"),
        fabrica="navegacao",
        classe=NAV,
        metodo="workflows",
        retorno=_linhas({"id": 139, "name": "w", "stages": []}),
    )
)

_registrar(
    Comando(
        caminho=("list", "attributes"),
        fabrica="navegacao",
        classe=NAV,
        metodo="attributes",
        retorno=_linhas({"name": "team", "tags": ["apiops"]}),
    )
)

_registrar(
    Comando(
        caminho=("list", "interceptors"),
        fabrica="navegacao",
        classe=NAV,
        metodo="interceptor_catalog",
        retorno=_linhas({"type": "Log", "custom": False}),
        opcoes=(
            Opcao("--custom", kwarg="custom_only", esperado=True),
            Opcao("--tag", "Oauth", kwarg="tag", esperado="Oauth"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "apps"),
        fabrica="navegacao",
        classe=NAV,
        metodo="apps",
        retorno=_linhas({"id": 42, "name": "app"}),
        opcoes=(
            Opcao("--api", "400", kwarg="api_id", esperado=400),
            Opcao("--query", "x", kwarg="query", esperado="x"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "plans"),
        fabrica="navegacao",
        classe=NAV,
        metodo="plans",
        retorno=_linhas({"id": 66, "name": "plano"}),
        opcoes=(
            Opcao("--api", "400", kwarg="api_id", esperado=400),
            Opcao("--query", "x", kwarg="query", esperado="x"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "tokens"),
        fabrica="navegacao",
        classe=NAV,
        metodo="tokens",
        retorno=_linhas({"id": 7, "app": "app", "status": "ACTIVE"}),
        opcoes=(
            Opcao("--app", "45", kwarg="app_id", esperado=45),
            Opcao("--api", "400", kwarg="api_id", esperado=400),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "variables"),
        fabrica="navegacao",
        classe=NAV,
        metodo="variables",
        retorno=_linhas({"map": "m", "key": "k", "value": "•••"}),
        opcoes=(
            Opcao("--env", "1", kwarg="environment_id", esperado=1),
            Opcao("--key", "k", kwarg="key", esperado="k"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "users"),
        fabrica="navegacao",
        classe=NAV,
        metodo="users",
        retorno=_linhas({"username": "paulo", "status": "ACTIVE"}),
        opcoes=(Opcao("--query", "pa", kwarg="query", esperado="pa"),),
    )
)

_registrar(
    Comando(
        caminho=("list", "teams"),
        fabrica="navegacao",
        classe=NAV,
        metodo="teams",
        retorno=_linhas({"name": "APIOps"}),
        opcoes=(Opcao("--query", "api", kwarg="query", esperado="api"),),
    )
)

_registrar(
    Comando(
        caminho=("list", "inbounds"),
        fabrica="navegacao",
        classe=NAV,
        metodo="inbounds",
        retorno=_linhas({"host": "gw", "protocol": "https"}),
    )
)

_registrar(
    Comando(
        caminho=("list", "gateway-pools"),
        fabrica="navegacao",
        classe=NAV,
        metodo="gateway_pools",
        retorno=_linhas({"name": "pool", "routes": 3}),
    )
)

_registrar(
    Comando(
        caminho=("list", "owners"),
        fabrica="listagem",
        classe=LIST,
        metodo="list_apis",
        retorno=[],
        servico_conferivel=False,  # o comando resume o catalogo por `owners_summary`
        formatos=(),
    )
)

_registrar(
    Comando(
        caminho=("list", "roles"),
        fabrica="navegacao",
        classe=NAV,
        metodo="roles",
        retorno=_linhas({"id": "uuid", "name": "role"}),
        opcoes=(Opcao("--query", "ro", kwarg="query", esperado="ro"),),
    )
)

_registrar(
    Comando(
        caminho=("list", "permissions"),
        fabrica="navegacao",
        classe=NAV,
        metodo="permissions",
        retorno={"product": "API Platform", "domains": {}},
        opcoes=(
            Opcao("--product", "API Platform", kwarg="product", esperado="API Platform"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("list", "calls"),
        fabrica="navegacao",
        classe=NAV,
        metodo="calls",
        retorno={"total": 0, "page": 1, "pageSize": 20, "window": {}, "calls": []},
        opcoes=(
            Opcao("--api", "400", kwarg="api_id", esperado=400),
            Opcao("--env", "1", kwarg="environment_id", esperado=1),
            Opcao("--since", "24h", kwarg="since", esperado="24h"),
            Opcao("--until", "agora", kwarg="until", esperado="agora"),
            Opcao("--errors", kwarg="errors", esperado=True),
            Opcao("--status-from", "400", kwarg="status_from", esperado=400),
            Opcao("--status-to", "599", kwarg="status_to", esperado=599),
            Opcao("--uri", "/x", kwarg="uri", esperado="/x"),
            Opcao("--operation-id", "9", kwarg="operation_id", esperado=9),
            Opcao("--revision-id", "8948", kwarg="revision_id", esperado=8948),
            Opcao(
                "--limit",
                "50",
                kwarg="limit",
                esperado=50,
                limites=(("0", "abaixo do minimo"), ("501", "acima do maximo")),
            ),
            Opcao("--page", "2", kwarg="page", esperado=2, limites=(("0", "pagina zero"),)),
        ),
    )
)

# ------------------------------------------------------- sen export / reveal

_registrar(
    Comando(
        caminho=("export", "api"),
        fabrica="navegacao",
        classe=NAV,
        metodo="export",
        retorno=NAO_INFORMADO,  # tupla (api, revision, MaterializationResult)
        args_minimos=("--id", "400"),
        obrigatorias=("--id",),
        servico_conferivel=False,  # devolve tupla e o comando remonta o envelope
        formatos=(),
        opcoes=(
            Opcao("--id", "400"),
            Opcao("--revision", "4", conflita_com=(("--revision-id", "8948"),)),
            Opcao("--revision-id", "8948"),
            # `--dir`/`--force` escrevem em disco: ficam com o teste dedicado
            # `test_export_api_command.py`, que usa tmp_path.
            Opcao("--force"),
        ),
    )
)

_registrar(
    Comando(
        caminho=("reveal", "variable"),
        fabrica="navegacao",
        classe=NAV,
        metodo="reveal_variable",
        retorno={"env": 1, "key": "k", "value": "segredo", "map": None},
        args_minimos=("--env", "1", "--key", "k"),
        obrigatorias=("--env", "--key"),
        opcoes=(
            Opcao("--env", "1", kwarg="environment_id", esperado=1),
            Opcao("--key", "k", kwarg="key", esperado="k"),
            Opcao("--map", "m", kwarg="map_name", esperado="m"),
            Opcao("--raw"),
        ),
    )
)

# ----------------------------------------------- sen (diretos) e sen diag
# Estes nao seguem o formato `_service(ctx).metodo(...)`: escrevem na plataforma,
# leem repositorio local, perguntam ao usuario. A matriz cobre o que e generico
# (ajuda, fabrica ausente, nao-vazamento); o resto esta nos testes dedicados
# `test_login_command.py`, `test_validate_command.py`, `test_publish_command.py`,
# `test_deploy_command.py` e `test_diag_commands.py`.

for _caminho, _fabrica, _minimos in (
    (("login",), "login", ()),
    # `completeness` valida --id/--revision ANTES de resolver a fabrica
    # (cli_adapter.py:1052): sem eles a saida e a mensagem de alvo ausente.
    (("completeness",), "completude", ("--id", "400", "--revision", "8948")),
    (("validate",), "validate", ()),
    (("publish",), "publish", ()),
    (("deploy",), "deploy", ()),
    (("diag", "structure"), "validate", ()),  # sem ctx: le o repositorio local
    (("diag", "template"), "regua", ()),
    (("diag", "draft"), "validate", ()),
):
    _registrar(
        Comando(
            caminho=_caminho,
            fabrica=_fabrica,
            retorno=NAO_INFORMADO,
            args_minimos=_minimos,
            servico_conferivel=False,
            formatos=(),
            usa_fabrica=_caminho != ("diag", "structure"),
        )
    )


def comandos_conferiveis() -> list:
    """Os que a matriz consegue afirmar ponta a ponta contra o servico."""
    return [c for c in COMANDOS.values() if c.servico_conferivel]


def pares_de_opcao() -> list:
    return [(c, o) for c in COMANDOS.values() for o in c.opcoes]
