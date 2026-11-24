"""A matriz completa de opcoes, derivada de `sen_support.cli_matrix`.

Oito funcoes, ~370 casos. O ganho nao e o numero: e que a cobertura passa a ser
uma propriedade da tabela, e a tabela e conferida contra a arvore Typer. Antes,
20 dos 44 comandos tinham so um happy-path de texto e um (`sen diag template`)
nao tinha nada — porque cobertura dependia de alguem lembrar de escrever o teste.

Tres mitigacoes tornam a tabela confiavel, e sem as tres isto seria teatro:
`create_autospec` derruba a chamada se o nome do parametro nao existir no
servico; `apply_defaults()` compara o bind inteiro, nao uma chave solta; e
`test_toda_folha_esta_na_matriz` impede tabela incompleta.
"""

from __future__ import annotations

import json

import pytest
import yaml

from sen_support import cli_matrix, cli_tree
from sen_support.cli_fakes import argumentos_da_chamada, servico
from sen_support.cli_matrix import NAO_INFORMADO

COMANDOS = list(cli_matrix.COMANDOS.values())
CONFERIVEIS = cli_matrix.comandos_conferiveis()


def _id_comando(comando) -> str:
    return comando.ident


def _fake(comando):
    return servico(comando.fabrica, **{comando.metodo: comando.retorno})


def _metodo(fake, comando):
    return getattr(fake, comando.metodo)


# --- a tabela cobre a arvore inteira -----------------------------------------


def test_toda_folha_esta_na_matriz():
    """O fecho do contrato: comando novo sem linha na tabela falha aqui.

    E o unico ponto do projeto que torna "comando novo vem sem teste" um erro
    visivel em vez de uma omissao silenciosa.
    """
    na_arvore = {no.ident for no in cli_tree.folhas()}
    na_matriz = set(cli_matrix.COMANDOS)

    assert na_matriz == na_arvore, (
        f"fora da matriz: {sorted(na_arvore - na_matriz)}; "
        f"na matriz mas nao na CLI: {sorted(na_matriz - na_arvore)}"
    )


def test_toda_flag_da_matriz_existe_na_cli():
    """A tabela nao pode afirmar sobre flag que nao existe mais."""
    por_ident = cli_tree.por_ident()
    inexistentes = []
    for comando in COMANDOS:
        reais = {
            alias
            for opcao in cli_tree.opcoes(por_ident[comando.ident])
            for alias in opcao.opts
        }
        inexistentes += [
            f"{comando.ident} {o.flag}" for o in comando.opcoes if o.flag not in reais
        ]

    assert not inexistentes, inexistentes


# --- a opcao chega ao servico com o nome do contrato -------------------------

_COM_KWARG = [
    (c, o) for c in CONFERIVEIS for o in c.opcoes if o.kwarg and o.esperado is not NAO_INFORMADO
]


@pytest.mark.parametrize(
    "comando, opcao", _COM_KWARG, ids=[f"{c.ident}{o.flag}" for c, o in _COM_KWARG]
)
def test_opcao_chega_ao_servico_com_o_nome_do_contrato(comando, opcao, invoke_sen):
    """Pega renomeacao e inversao silenciosas na travessia borda -> servico.

    Dois casos reais que so este teste cobre: `--content` chega como
    `include_content=` (navigation_cli.py:527) e `--no-headers` chega **negado**,
    como `include_headers=not no_headers` (:1741).
    """
    fake = _fake(comando)
    argumentos = [*comando.args_minimos]
    if opcao.flag not in argumentos:
        argumentos += [opcao.flag] + ([opcao.valor] if opcao.valor is not None else [])

    resultado = invoke_sen(
        [*comando.caminho, *argumentos, "-o", "json"], **{comando.fabrica: fake}
    )

    assert resultado.exit_code == 0, resultado.output
    metodo = _metodo(fake, comando)
    assert metodo.called, f"{comando.ident} nao chamou {comando.metodo}"
    recebido = argumentos_da_chamada(comando.classe, comando.metodo, metodo.call_args)
    assert opcao.kwarg in recebido, (
        f"{comando.metodo} nao recebeu `{opcao.kwarg}`; recebeu {sorted(recebido)}"
    )
    assert recebido[opcao.kwarg] == opcao.esperado


# --- obrigatoria ausente e recusada, nomeando a flag -------------------------

_OBRIGATORIAS = [(c, f) for c in COMANDOS for f in c.obrigatorias]


@pytest.mark.parametrize(
    "comando, flag", _OBRIGATORIAS, ids=[f"{c.ident}{f}" for c, f in _OBRIGATORIAS]
)
def test_opcao_obrigatoria_ausente_recusa_nomeando_a_flag(comando, flag, invoke_sen):
    """Recusar nao basta: a saida tem de dizer QUAL flag falta."""
    restantes = []
    argumentos = list(comando.args_minimos)
    pular = False
    for item in argumentos:
        if pular:
            pular = False
            continue
        if item == flag:
            pular = True  # descarta tambem o valor da flag removida
            continue
        restantes.append(item)

    fake = _fake(comando) if comando.servico_conferivel else None
    fabricas = {comando.fabrica: fake} if fake is not None else {comando.fabrica: object()}
    resultado = invoke_sen([*comando.caminho, *restantes], **fabricas)

    assert resultado.exit_code != 0
    assert flag in " ".join(resultado.output.split())


# --- exclusividade mutua, recusada ANTES da rede -----------------------------

_CONFLITOS = [
    (c, o, outro) for c in COMANDOS for o in c.opcoes for outro in o.conflita_com
]


@pytest.mark.parametrize(
    "comando, opcao, outro",
    _CONFLITOS,
    ids=[f"{c.ident}{o.flag}x{outro[0]}" for c, o, outro in _CONFLITOS],
)
def test_exclusividade_mutua_recusa_antes_da_rede(comando, opcao, outro, invoke_sen):
    """Nao basta sair com erro: o servico nao pode ter sido tocado.

    Uma recusa depois da chamada ja teria gasto uma ida ao Manager — e, nos
    comandos de escrita, ja teria mudado estado.
    """
    fake = _fake(comando) if comando.servico_conferivel else servico(comando.fabrica)
    argumentos = [*comando.args_minimos]
    if opcao.flag not in argumentos:
        argumentos += [opcao.flag] + ([opcao.valor] if opcao.valor is not None else [])
    argumentos += list(outro)

    resultado = invoke_sen([*comando.caminho, *argumentos], **{comando.fabrica: fake})

    assert resultado.exit_code != 0, resultado.output
    if comando.metodo:
        _metodo(fake, comando).assert_not_called()


# --- limite fora da faixa, recusado ANTES da rede ----------------------------

_LIMITES = [
    (c, o, valor, motivo)
    for c in COMANDOS
    for o in c.opcoes
    for valor, motivo in o.limites
]


@pytest.mark.parametrize(
    "comando, opcao, valor, motivo",
    _LIMITES,
    ids=[f"{c.ident}{o.flag}={v}" for c, o, v, _ in _LIMITES],
)
def test_limite_fora_da_faixa_recusa_antes_da_rede(
    comando, opcao, valor, motivo, invoke_sen
):
    fake = _fake(comando) if comando.servico_conferivel else servico(comando.fabrica)

    resultado = invoke_sen(
        [*comando.caminho, *comando.args_minimos, opcao.flag, valor],
        **{comando.fabrica: fake},
    )

    assert resultado.exit_code != 0, f"{motivo}: {resultado.output}"
    if comando.metodo:
        _metodo(fake, comando).assert_not_called()


# --- a saida de maquina e parseavel e e o documento --------------------------

_FORMATOS = [(c, f) for c in CONFERIVEIS for f in c.formatos]


@pytest.mark.parametrize(
    "comando, formato", _FORMATOS, ids=[f"{c.ident}-{f}" for c, f in _FORMATOS]
)
def test_formato_de_maquina_e_parseavel_e_e_o_documento(comando, formato, invoke_sen):
    """O contrato com a esteira e com um agente: `-o json` sai parseavel e inteiro.

    Nao basta "parseia": tem de ser o MESMO documento que o servico devolveu, ou
    a borda estaria filtrando dado sem ninguem notar.
    """
    fake = _fake(comando)

    resultado = invoke_sen(
        [*comando.caminho, *comando.args_minimos, "-o", formato],
        **{comando.fabrica: fake},
    )

    assert resultado.exit_code == 0, resultado.output
    carregar = json.loads if formato == "json" else yaml.safe_load
    assert carregar(resultado.output) == comando.retorno


# --- fabrica ausente encerra com 1 -------------------------------------------

_COM_FABRICA = [c for c in COMANDOS if c.usa_fabrica]


@pytest.mark.parametrize("comando", _COM_FABRICA, ids=_id_comando)
def test_fabrica_ausente_encerra_com_1(comando, invoke_sen):
    """Contexto vazio e falha de montagem, nao stack trace.

    Sozinho, este caso fecha os ~24 pares `if not callable(factory)` de
    `navigation_cli.py`, que nenhum teste tocava.
    """
    resultado = invoke_sen([*comando.caminho, *comando.args_minimos], obj={})

    assert resultado.exit_code == 1, resultado.output
    assert "indispon" in resultado.output.lower()


# --- excecao inesperada nao vaza texto cru -----------------------------------


@pytest.mark.parametrize("comando", CONFERIVEIS, ids=_id_comando)
def test_erro_inesperado_nao_vaza_texto_cru(comando, invoke_sen):
    """Mensagem de excecao pode carregar host, token ou payload: nunca sai na tela."""
    fake = servico(comando.fabrica)
    _metodo(fake, comando).side_effect = RuntimeError("segredo interno")

    resultado = invoke_sen(
        [*comando.caminho, *comando.args_minimos], **{comando.fabrica: fake}
    )

    assert resultado.exit_code == 1
    assert "segredo interno" not in resultado.output
    assert "erro interno" in resultado.output.lower()


# --- resultado vazio e dito, nao e tela em branco ----------------------------

# So os `sen list *`: `get interceptor-type` tambem devolve lista, mas e
# referencia de documentacao, nao catalogo do tenant — vazio ali significa "o
# tipo nao tem campos conhecidos", e o comando fecha com o rodape de navegacao.
_LISTAGENS = [
    c
    for c in CONFERIVEIS
    if isinstance(c.retorno, list) and c.caminho[0] == "list"
]


@pytest.mark.parametrize("comando", _LISTAGENS, ids=_id_comando)
def test_listagem_vazia_avisa_em_vez_de_imprimir_nada(comando, invoke_sen, uma_linha):
    """Catalogo vazio ou filtro sem resultado responde com frase, nao com silencio.

    E o ramo que a matriz nao alcancava, porque ela consulta em `-o json` e com
    documento cheio. Tela em branco deixa quem usa sem saber se o filtro nao
    casou ou se o comando falhou.
    """
    fake = servico(comando.fabrica, **{comando.metodo: []})

    resultado = invoke_sen(
        [*comando.caminho, *comando.args_minimos], **{comando.fabrica: fake}
    )

    assert resultado.exit_code == 0, resultado.output
    assert "nenhum" in uma_linha(resultado).lower()
