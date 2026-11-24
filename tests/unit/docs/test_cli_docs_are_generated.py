"""A documentacao de comandos nao pode divergir da CLI.

Era o buraco central: os 44 comandos estavam nos dois arquivos, mas 11 deles com
flag errada ou ausente, e nada acusava. `sen get environment` chegou a mandar o
leitor usar `--env`, opcao que nao existe no comando.

Dois mecanismos, e os dois sao necessarios:

1. **O bloco gerado** (entre marcadores) e conferido contra `render()`. Isto pega
   por construcao tudo o que a geracao enxerga: omissao, atribuicao errada,
   default, obrigatoriedade, remocao, reordenacao, anomalia do `-o`.
2. **A prosa escrita a mao** (fora dos marcadores) e varrida atras de flag que
   nao existe mais. E a unica direcao que a geracao nao enxerga, porque ela nao
   toca nesse texto.
"""

from __future__ import annotations

import importlib.util
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = RAIZ / "scripts" / "gen_cli_docs.py"

# O numero esta escrito a mao de proposito: comando novo quebra aqui e obriga a
# rodar `--write`, em vez de entrar na CLI sem documentacao.
TOTAL_DE_COMANDOS = 44


def _carregar_gerador():
    """Carrega o script por caminho: ele vive em `scripts/`, fora do pacote."""
    spec = importlib.util.spec_from_file_location("gen_cli_docs", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("gen_cli_docs", modulo)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def gerador():
    return _carregar_gerador()


def _bloco(gerador, arquivo: str) -> str:
    texto = (RAIZ / arquivo).read_text(encoding="utf-8")
    _, meio, _ = gerador._fatiar(texto, arquivo)
    return meio


@pytest.mark.parametrize(
    "arquivo, idioma", [("README.md", "en"), ("COMMANDS.md", "pt")]
)
def test_o_bloco_commitado_e_o_bloco_gerado(gerador, arquivo, idioma):
    commitado = _bloco(gerador, arquivo)
    esperado = "\n" + gerador.render(idioma)

    assert commitado == esperado, (
        f"{arquivo} esta fora de sincronia com a CLI. "
        "Rode: python scripts/gen_cli_docs.py --write"
    )


@pytest.mark.parametrize("arquivo", ["README.md", "COMMANDS.md"])
def test_todo_comando_da_arvore_esta_no_bloco(gerador, arquivo):
    bloco = _bloco(gerador, arquivo)
    folhas = gerador.folhas()

    assert len(folhas) == TOTAL_DE_COMANDOS
    ausentes = [no.rotulo for no in folhas if f"#### `{no.rotulo}`" not in bloco]
    assert not ausentes, ausentes


@pytest.mark.parametrize("arquivo", ["README.md", "COMMANDS.md"])
def test_os_comandos_ocultos_sao_documentados_e_marcados(gerador, arquivo):
    """Oculto no `--help`, presente no repositorio — e dito que e oculto.

    Documentar sem marcar seria pior que nao documentar: alguem o usaria achando
    que faz parte da superficie suportada.
    """
    bloco = _bloco(gerador, arquivo)
    ocultos = [no for no in gerador.folhas() if no.oculto]

    assert {no.rotulo for no in ocultos} == {
        "sen diag structure",
        "sen diag template",
        "sen diag draft",
    }
    for no in ocultos:
        trecho = bloco.split(f"#### `{no.rotulo}`", 1)[1].split("#### ")[0]
        assert "oculto" in trecho or "hidden" in trecho, no.rotulo


def test_so_get_swagger_tem_default_de_output_diferente_de_text(gerador):
    """Trava a ressalva que o README afirmava errado.

    O README dizia que todo comando usa `text` como padrao de `-o`; `sen get
    swagger` usa YAML. Agora a excecao e emitida pelo gerador, e uma SEGUNDA
    excecao aparece sozinha no diff em vez de virar a proxima frase falsa.
    """
    from enum import Enum

    excecoes = []
    for no in gerador.folhas():
        saida = next(
            (o for o in gerador.opcoes(no.comando) if "--output" in o.opts), None
        )
        if saida is None:
            continue
        padrao = saida.default.value if isinstance(saida.default, Enum) else saida.default
        if padrao != "text":
            excecoes.append((no.rotulo, padrao))

    assert excecoes == [("sen get swagger", "yaml")], excecoes


@pytest.mark.parametrize("arquivo", ["README.md", "COMMANDS.md"])
def test_a_prosa_nao_cita_flag_inexistente(gerador, arquivo):
    """Varre so o texto a mao: o gerado nao pode errar, o escrito pode.

    Pega renomeacao e remocao de flag citada num exemplo ou numa nota — a
    divergencia que sobreviveria a qualquer geracao.
    """
    texto = (RAIZ / arquivo).read_text(encoding="utf-8")
    antes, _, depois = gerador._fatiar(texto, arquivo)
    prosa = antes + depois

    reais = {
        alias
        for no in gerador.folhas()
        for opcao in gerador.opcoes(no.comando)
        for alias in opcao.opts
    }
    reais |= {
        alias for opcao in gerador.opcoes(gerador._grupo_sen()) for alias in opcao.opts
    }
    reais |= {"--help", "--version"}
    # Flags de outras ferramentas citadas na prosa (pip, poetry, o proprio script).
    de_terceiros = {"--write", "--check", "--cov", "--cov-fail-under", "-Dev", "-e"}

    citadas = set(re.findall(r"`(--[a-z0-9][a-z0-9-]*)`", prosa))
    inexistentes = sorted(citadas - reais - de_terceiros)

    assert not inexistentes, (
        f"{arquivo}: a prosa cita flag que a CLI nao tem: {inexistentes}"
    )
