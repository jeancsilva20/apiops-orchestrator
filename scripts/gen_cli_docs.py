#!/usr/bin/env python
"""Gera a referencia de comandos do README.md e do COMMANDS.md a partir da CLI.

Por que gerar em vez de manter a mao. Os 44 comandos estavam nos dois arquivos,
mas 11 deles com flag errada ou ausente: `--repo` de `publish`/`deploy` nao
aparecia em doc nenhum, `sen get environment` mandava usar `--env` quando o
codigo exige `--id`, `sen list calls` escondia 7 das 12 flags. E o COMMANDS.md,
mantido fiel a mao por quem escreveu os comandos, ainda assim perdeu o `--repo`.
Checklist humano ja foi tentado aqui e o resultado esta medido.

A divisao que isto estabelece:

  o codigo e a unica fonte da verdade;
  `sen --help` e a projecao direta dele;
  README.md e COMMANDS.md sao projecoes GERADAS, nunca autoridades.

O texto de cada opcao e escrito uma vez, no `help=` do codigo, e os dois
arquivos recebem o mesmo dado com cabecalho no idioma de cada um. Custo marginal
de manutencao: zero. "README diverge do --help" deixa de ser possivel.

    python scripts/gen_cli_docs.py            # confere (exit 1 e diff se divergir)
    python scripts/gen_cli_docs.py --write    # reescreve os blocos marcados

O bloco gerado vive entre marcadores, um par por arquivo; tudo fora deles e
prosa escrita a mao e nunca e tocado.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import click  # noqa: E402
import typer.main  # noqa: E402

# So o `app`: importar o resto do pacote arriscaria tocar `Settings`, que o
# ADR 0006 mantem preguicosa para `--help`/`--version` responderem sem `.env`.
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app  # noqa: E402
from apiops_orchestrator.infrastructure.utils.stdio import harden_stdio  # noqa: E402

INICIO = "<!-- BEGIN GENERATED: sen cli reference -->"
FIM = "<!-- END GENERATED -->"
AVISO = (
    "<!-- Nao edite este bloco a mao: ele e gerado de `sen --help`. "
    "Rode `python scripts/gen_cli_docs.py --write`. -->"
)

# Ordem determinista. Sem ela o diff-check oscila: a ordem de registro de
# `list_app` e a de insercao em cli_adapter.py:2048-2063, entao quem acrescenta
# um comando o joga no fim.
ORDEM_DOS_GRUPOS: Tuple[str, ...] = ("", "list", "get", "export", "reveal", "diag")
# Dentro de `sen`, ciclo de vida em vez de alfabetica: alfabetica poria `deploy`
# antes de `login`, invertendo a ordem em que os comandos sao usados.
ORDEM_EM_SEN: Tuple[str, ...] = (
    "login",
    "completeness",
    "validate",
    "publish",
    "deploy",
)

TITULO_DOS_GRUPOS: Dict[str, Tuple[str, str]] = {
    "": ("Session and pipeline", "Sessao e esteira"),
    "list": ("`sen list` — catalogs", "`sen list` — catalogos"),
    "get": ("`sen get` — detail levels", "`sen get` — niveis de detalhe"),
    "export": ("`sen export`", "`sen export`"),
    "reveal": ("`sen reveal`", "`sen reveal`"),
    "diag": (
        "Internal diagnostics (hidden from `--help`)",
        "Diagnostico interno (oculto no `--help`)",
    ),
}

# Vocabulario proprio: um upgrade de Click que renomeie um tipo nao pode
# reescrever as 44 tabelas.
TIPOS: Dict[str, str] = {
    "integer": "int",
    "text": "text",
    "boolean": "flag",
    "path": "path",
    "choice": "choice",
}

CABECALHOS = {
    "en": ("Option", "Type", "Default", "Effect"),
    "pt": ("Opcao", "Tipo", "Padrao", "Efeito"),
}

ROTULOS = {
    "en": {
        "required": "**required**",
        "off": "off",
        "vazio": "—",
        "oculto": "_hidden: internal use, absent from `sen --help`._",
        "indice": "Jump to",
        "sem_opcoes": "_No options beyond `--output/-o`._",
        "default_o": "Default for `-o` is `{valor}`, not `text`.",
    },
    "pt": {
        "required": "**obrigatorio**",
        "off": "off",
        "vazio": "—",
        "oculto": "_oculto: uso interno, ausente do `sen --help`._",
        "indice": "Ir para",
        "sem_opcoes": "_Sem opcoes alem de `--output/-o`._",
        "default_o": "O padrao de `-o` aqui e `{valor}`, nao `text`.",
    },
}


# --------------------------------------------------------------- leitura da arvore


class No:
    def __init__(self, caminho: Tuple[str, ...], comando: click.Command, oculto: bool):
        self.caminho = caminho
        self.comando = comando
        self.oculto = oculto

    @property
    def grupo(self) -> str:
        """O grupo a que a folha pertence: '' para os comandos diretos de `sen`."""
        return self.caminho[0] if len(self.caminho) > 1 else ""

    @property
    def nome(self) -> str:
        return self.caminho[-1]

    @property
    def rotulo(self) -> str:
        return "sen " + " ".join(self.caminho)


def _caminhar(comando: click.Command, caminho: Tuple[str, ...], oculto: bool):
    oculto = oculto or bool(getattr(comando, "hidden", False))
    if isinstance(comando, click.Group):
        for nome, sub in comando.commands.items():
            yield from _caminhar(sub, caminho + (nome,), oculto)
    else:
        yield No(caminho, comando, oculto)


def folhas() -> List[No]:
    raiz = typer.main.get_command(app)
    sen = raiz.commands["sen"]
    todas = list(_caminhar(sen, (), bool(getattr(sen, "hidden", False))))

    def chave(no: No) -> Tuple[int, int, str]:
        grupo = ORDEM_DOS_GRUPOS.index(no.grupo)
        if no.grupo == "":
            return (grupo, ORDEM_EM_SEN.index(no.nome), "")
        return (grupo, 0, no.nome)

    return sorted(todas, key=chave)


def opcoes(comando: click.Command) -> List[click.Option]:
    """Inclui as ocultas de proposito.

    Opcao oculta continua sendo aceita na linha de comando; some do `--help`
    (para nao poluir o uso diario) mas nao pode sumir da documentacao, ou o
    repositorio deixaria de ser onde mantenedor e agente descobrem o que existe.
    E o caso de `--verbose`, aceito em 4 comandos e sem efeito nenhum.
    """
    return [
        p for p in comando.params if isinstance(p, click.Option) and p.name != "help"
    ]


def _grupo_sen() -> click.Group:
    return typer.main.get_command(app).commands["sen"]


# ------------------------------------------------------------------- formatacao


def _tipo(opcao: click.Option) -> str:
    if opcao.is_flag:
        return TIPOS["boolean"]
    return TIPOS.get(opcao.type.name, opcao.type.name)


def _default(opcao: click.Option, idioma: str) -> str:
    rotulos = ROTULOS[idioma]
    if opcao.required:
        return rotulos["required"]
    valor = opcao.default
    if isinstance(valor, Enum):  # sem isto sai `<OutputFormat.TEXT: 'text'>`
        valor = valor.value
    if opcao.is_flag:
        return rotulos["off"] if not valor else "on"
    if valor is None:
        # Nunca inventar o default efetivo. `--since` e o caso exemplar: o Click
        # diz None, e o proprio `help=` ja diz "Padrao: 24h" — a coluna Efeito
        # carrega essa verdade, porque e o texto que a pessoa le no terminal.
        return rotulos["vazio"]
    return f"`{valor}`"


def _placeholder(opcao: click.Option) -> str:
    if opcao.is_flag:
        return ""
    return {"integer": " N", "path": " PATH", "text": " TEXT"}.get(
        opcao.type.name, " VALUE"
    )


def _sinopse(no: No, lista: Sequence[click.Option]) -> List[str]:
    """Uma linha de uso, quebrada em 88 colunas, com obrigatoria sem colchetes."""
    partes = []
    for opcao in lista:
        if "--output" in opcao.opts:
            continue
        flag = opcao.opts[0] + _placeholder(opcao)
        partes.append(flag if opcao.required else f"[{flag}]")

    linhas: List[str] = []
    atual = no.rotulo
    recuo = " " * (len(no.rotulo) + 1)
    for parte in partes:
        if len(atual) + 1 + len(parte) > 88:
            linhas.append(atual)
            atual = recuo + parte
        else:
            atual = f"{atual} {parte}"
    linhas.append(atual)
    return linhas


def _ancora(titulo: str) -> str:
    """Ancora no formato do GitHub: minuscula, pontuacao fora, espaco vira hifen."""
    limpo = "".join(
        ch for ch in titulo.lower() if ch.isalnum() or ch in " -_"
    )
    return "-".join(limpo.split())


def _bloco_do_comando(no: No, idioma: str) -> List[str]:
    rotulos = ROTULOS[idioma]
    lista = opcoes(no.comando)
    linhas = [f"#### `{no.rotulo}`", ""]
    if no.oculto:
        linhas += [rotulos["oculto"], ""]
    ajuda = " ".join((no.comando.help or "").split())
    if ajuda:
        linhas += [ajuda, ""]

    linhas += ["```", *_sinopse(no, lista), "```", ""]

    visiveis = [o for o in lista if "--output" not in o.opts]
    saida = next((o for o in lista if "--output" in o.opts), None)
    if saida is not None:
        padrao = saida.default.value if isinstance(saida.default, Enum) else saida.default
        if padrao != "text":
            linhas += [rotulos["default_o"].format(valor=padrao), ""]

    if not visiveis:
        linhas += [rotulos["sem_opcoes"], ""]
        return linhas

    cabecalho = CABECALHOS[idioma]
    linhas += [
        "| " + " | ".join(cabecalho) + " |",
        "|---|---|---|---|",
    ]
    for opcao in visiveis:
        flags = "/".join(f"`{alias}`" for alias in opcao.opts)
        if opcao.hidden:
            # Aceita, mas fora do `--help`. Marcada para a pessoa saber que nao
            # a vera no terminal — e nao concluir que a doc esta errada.
            flags += " (hidden)" if idioma == "en" else " (oculta)"
        efeito = " ".join((opcao.help or "").split()).replace("|", "\\|")
        linhas.append(
            f"| {flags} | {_tipo(opcao)} | {_default(opcao, idioma)} | {efeito} |"
        )
    linhas.append("")
    return linhas


def render(idioma: str) -> str:
    """O bloco inteiro: indice por grupo + uma secao por comando."""
    todas = folhas()
    rotulos = ROTULOS[idioma]
    linhas: List[str] = [AVISO, ""]

    # Indice: o bloco passa de 500 linhas e sem ele ninguem acha o comando.
    grupos_presentes = [g for g in ORDEM_DOS_GRUPOS if any(n.grupo == g for n in todas)]
    def _entrada(g: str) -> str:
        titulo = TITULO_DOS_GRUPOS[g][0 if idioma == "en" else 1]
        return f"[{titulo}](#{_ancora(titulo)})"

    indice = " · ".join(_entrada(g) for g in grupos_presentes)
    linhas += [f"{rotulos['indice']}: {indice}", ""]

    atual: Optional[str] = None
    for no in todas:
        if no.grupo != atual:
            atual = no.grupo
            titulo = TITULO_DOS_GRUPOS[atual][0 if idioma == "en" else 1]
            linhas += [f"### {titulo}", ""]
            if atual == "":
                # `--verbose`/`--version` vivem no callback do grupo `sen`
                # (cli_adapter.py:887): nao pertencem a comando nenhum, e esta e
                # a unica forma de documenta-los.
                linhas += _bloco_das_globais(idioma)
        linhas += _bloco_do_comando(no, idioma)

    return "\n".join(linhas).rstrip() + "\n"


def _bloco_das_globais(idioma: str) -> List[str]:
    rotulos = ROTULOS[idioma]
    cabecalho = CABECALHOS[idioma]
    titulo = "#### `sen` (global options)" if idioma == "en" else "#### `sen` (opcoes globais)"
    linhas = [titulo, "", "```", "sen [--verbose] [--version] <command>", "```", ""]
    linhas += ["| " + " | ".join(cabecalho) + " |", "|---|---|---|---|"]
    for opcao in opcoes(_grupo_sen()):
        flags = "/".join(f"`{alias}`" for alias in opcao.opts)
        efeito = " ".join((opcao.help or "").split())
        linhas.append(
            f"| {flags} | {_tipo(opcao)} | {_default(opcao, idioma)} | {efeito} |"
        )
    linhas.append("")
    return linhas


# ------------------------------------------------------------------ arquivos

DESTINOS: Tuple[Tuple[str, str], ...] = (("README.md", "en"), ("COMMANDS.md", "pt"))


def _ler(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _fatiar(texto: str, arquivo: str) -> Tuple[str, str, str]:
    if INICIO not in texto or FIM not in texto:
        raise SystemExit(
            f"{arquivo}: marcadores ausentes. Acrescente, na posicao desejada:\n"
            f"  {INICIO}\n  {FIM}"
        )
    antes, resto = texto.split(INICIO, 1)
    meio, depois = resto.split(FIM, 1)
    return antes, meio, depois


def _montar(antes: str, bloco: str, depois: str) -> str:
    return f"{antes}{INICIO}\n{bloco}{FIM}{depois}"


def _escrever(caminho: pathlib.Path, conteudo: str) -> None:
    # newline="" + \n explicito: nao ha regra para *.md no .gitattributes e o
    # checkout e Windows; sem isto o diff-check oscilaria entre CRLF e LF.
    with caminho.open("w", encoding="utf-8", newline="") as fh:
        fh.write(conteudo)


def main() -> int:
    harden_stdio()  # o proprio diff imprime acento, e no CI stdout e um pipe
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="reescreve os blocos em vez de conferir"
    )
    args = parser.parse_args()

    divergiu = False
    for arquivo, idioma in DESTINOS:
        caminho = RAIZ / arquivo
        antes, atual, depois = _fatiar(_ler(caminho), arquivo)
        novo = "\n" + render(idioma)
        if atual == novo:
            print(f"{arquivo}: em dia ({len(folhas())} comandos)")
            continue
        divergiu = True
        if args.write:
            _escrever(caminho, _montar(antes, novo.lstrip("\n"), depois))
            print(f"{arquivo}: reescrito")
            continue
        print(f"{arquivo}: DIVERGENTE")
        diff = difflib.unified_diff(
            atual.splitlines(), novo.splitlines(), "commitado", "gerado", lineterm=""
        )
        for linha in diff:
            print("  " + linha)

    if divergiu and not args.write:
        print(
            "\nA documentacao nao bate com a CLI. "
            "Rode: python scripts/gen_cli_docs.py --write"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
