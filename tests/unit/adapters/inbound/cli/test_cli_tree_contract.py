"""Contrato que todo comando da CLI cumpre, conferido pela arvore Typer.

Estas guardas existem para que um comando novo **falhe sozinho** quando vier sem
contrato. Era o que faltava: a CLI chegou a 44 comandos por branch tematica, e
nada reclamava de comando sem ajuda, sem opcao documentada ou fora da matriz de
teste. O smoke de `--help` que existia cobria 8 superficies de 50, por lista
digitada a mao — e comando novo nao entrava nela sozinho.

Cada guarda esta escrita para MORDER: se alguem desfizer o que ela protege, ela
fica vermelha. As contagens travadas (`cli_tree.TOTAL_DE_*`) sao de proposito o
ponto de atrito — comando novo obriga a encarar esta lista.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import list_app
from sen_support import cli_tree
from sen_support.cli_fabricas import FABRICAS

FOLHAS = cli_tree.folhas()
GRUPOS = cli_tree.grupos()
SUPERFICIES = cli_tree.superficies_de_help()
PARES = cli_tree.pares_de_opcao()


def _id(no: cli_tree.NoDaArvore) -> str:
    return no.ident


# --- a arvore e do tamanho que os testes afirmam -----------------------------


def test_a_arvore_tem_o_tamanho_declarado():
    """Comando novo passa por aqui, e e intencional.

    Sem este atrito, um comando entra na CLI sem visitar nenhuma das guardas
    abaixo — exatamente como `sen diag template` entrou e ficou sem teste.
    """
    assert len(FOLHAS) == cli_tree.TOTAL_DE_FOLHAS
    assert len(GRUPOS) == cli_tree.TOTAL_DE_GRUPOS
    assert len(PARES) == cli_tree.TOTAL_DE_OPCOES


# --- ajuda declarada ---------------------------------------------------------


@pytest.mark.parametrize("no", FOLHAS, ids=_id)
def test_toda_folha_declara_ajuda(no):
    assert (no.comando.help or "").strip(), f"{no.ident} nao tem docstring/help"


@pytest.mark.parametrize("no", GRUPOS, ids=_id)
def test_todo_grupo_declara_ajuda(no):
    assert (no.comando.help or "").strip(), f"grupo {no.ident} nao tem help"


@pytest.mark.parametrize(
    "no, opcao", PARES, ids=[f"{n.ident}{o.opts[0]}" for n, o in PARES]
)
def test_toda_opcao_declara_help(no, opcao):
    assert (opcao.help or "").strip(), f"{no.ident} {opcao.opts} sem help"


# --- saida de maquina em toda folha ------------------------------------------


@pytest.mark.parametrize("no", FOLHAS, ids=_id)
def test_toda_folha_oferece_output(no):
    """`-o json|yaml` e o contrato com agente e com a esteira: vale para as 44."""
    nomes = {alias for opcao in cli_tree.opcoes(no) for alias in opcao.opts}
    assert {"--output", "-o"} <= nomes, f"{no.ident} nao aceita -o"


# --- o help de toda superficie responde --------------------------------------


@pytest.mark.parametrize("no", SUPERFICIES, ids=_id)
def test_help_de_toda_superficie_responde_zero(no, invoke_sen):
    resultado = invoke_sen([*no.caminho, "--help"], obj={})

    assert resultado.exit_code == 0, resultado.output
    assert "Usage" in resultado.output


# --- a ajuda declarada sobrevive a um console legado --------------------------

# Caracteres que o Rich ja troca por ASCII sozinho no caminho legacy: nao sao o
# problema e nao devem ser confundidos com ele.
_TROCADOS_PELO_RICH = set("─│┌┐└┘├┤┬┴┼")


def _fora_do_cp1252(texto):
    ruins = []
    for ch in texto or "":
        if ch in _TROCADOS_PELO_RICH:
            continue
        try:
            ch.encode("cp1252")
        except UnicodeEncodeError:
            ruins.append(f"U+{ord(ch):04X}")
    return ruins


@pytest.mark.parametrize("no", SUPERFICIES, ids=_id)
def test_ajuda_declarada_e_renderizavel_em_console_legado(no):
    """A guarda que de fato pega o defeito, e a unica aqui que nao e obvia.

    `test_help_de_toda_superficie_responde_zero` roda sob `CliRunner`, cujo
    buffer e utf-8: as 50 superficies davam exit 0 **mesmo com o bug presente**.
    O `sen --help` de verdade saia com codigo 1 num stdout cp1252 porque a ajuda
    do grupo `get` trazia U+2192 e a de `--effective` trazia U+2212.

    `harden_stdio()` impede a queda; esta guarda impede o reaparecimento do
    caractere, para que num console cp1252 legitimo o texto continue legivel em
    vez de virar `?`.
    """
    textos = [("help", no.comando.help)]
    textos += [(opcao.opts[0], opcao.help) for opcao in cli_tree.opcoes(no)]

    problemas = {
        rotulo: ruins
        for rotulo, ruins in ((r, _fora_do_cp1252(t)) for r, t in textos)
        if ruins
    }

    assert not problemas, (
        f"{no.ident}: ajuda com caractere fora do cp1252 {problemas}. "
        "Use ASCII no texto de ajuda."
    )


# --- a orientacao de `sen list` nao vira segunda fonte da verdade -------------


def test_orientacao_do_list_nomeia_exatamente_os_subcomandos(invoke_sen):
    """`sen list` sem subcomando imprime uma lista escrita a mao.

    Essa lista (cli_adapter.py:96-103) e uma segunda fonte da verdade frente ao
    registro de cli_adapter.py:2048-2063: subcomando novo entra no registro e
    some da orientacao sem ninguem notar. A ordem difere nos dois e nao importa;
    o conjunto importa.
    """
    resultado = invoke_sen(["list"], obj={})
    assert resultado.exit_code == 2

    texto = " ".join(resultado.output.split())
    registrados = {c.name for c in list_app.registered_commands}
    nomeados = {
        nome for nome in registrados if re.search(rf"(?<![\w-]){re.escape(nome)}(?![\w-])", texto)
    }

    assert nomeados == registrados, (
        f"a orientacao de `sen list` nao nomeia {sorted(registrados - nomeados)}"
    )


# --- os apelidos de fabrica batem com o composition root ----------------------


def test_toda_fabrica_do_contexto_tem_apelido_na_suite():
    """Fabrica nova no `ctx.obj` sem apelido aqui = comando novo sem como testar."""
    from apiops_orchestrator.main import build_context

    assert set(build_context()) == set(FABRICAS.values())


# --- nenhum arquivo de teste fica fora da coleta -----------------------------


def test_todo_arquivo_de_teste_comeca_com_test():
    """`tests/unit/infrastructure/utils/http_client.py` tinha 4 testes que o
    pytest nunca coletou, porque o nome nao casa com `python_files`. Um deles
    afirmava o oposto do contrato da funcao, e ninguem viu."""
    raiz = pathlib.Path(__file__).resolve().parents[4] / "tests"
    permitidos = {"conftest.py"}
    foras = [
        str(p.relative_to(raiz)).replace("\\", "/")
        for p in raiz.rglob("*.py")
        if not p.name.startswith("test_")
        and p.name not in permitidos
        and "sen_support" not in p.parts
        and "__pycache__" not in p.parts
    ]

    assert not foras, f"arquivos sob tests/ que o pytest nao coleta: {foras}"


# --- a convencao de so-opcoes -------------------------------------------------


@pytest.mark.parametrize("no", FOLHAS, ids=_id)
def test_nenhum_comando_usa_typer_argument(no):
    """A CLI inteira e de opcoes nomeadas. Um posicional mudaria o contrato de
    quem automatiza (`sen get api 400` x `sen get api --id 400`) sem aviso."""
    posicionais = [p.name for p in cli_tree.argumentos(no)]
    assert not posicionais, f"{no.ident} declara argumento posicional {posicionais}"
