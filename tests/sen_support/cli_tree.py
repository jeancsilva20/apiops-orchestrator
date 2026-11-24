"""Enumeracao da arvore de comandos, a fonte unica dos testes de contrato.

Por que pela arvore e nunca por grep: 16 dos 17 subcomandos de `sen list` NAO
tem decorador — sao funcoes de `navigation_cli.py` registradas imperativamente
em `cli_adapter.py:2048-2063`. E as opcoes vem em parte de fabricas
compartilhadas (`_output_option()`, `_revision_option()`, `_api_option()`…), de
modo que contar `typer.Option(` no fonte da 101 call sites para 148 pares
(comando, opcao) reais. Qualquer numero tirado do texto do fonte esta errado.

Tres detalhes de Typer 0.19 / Click 8.3 que este modulo encapsula:

1. `typer.main.get_command(app)` devolve o grupo RAIZ, cujo filho unico e `sen`.
   O caminho exposto aqui ja exclui esse `sen`; quem invoca usa `["sen", *caminho]`.
2. `--help` nao esta em `cmd.params` (o Click o injeta por `get_help_option`),
   entao a guarda "toda opcao declara help" nao precisa de excecao.
3. `cmd.hidden` das folhas de `diag` e `False` — oculto e so o GRUPO
   (`cli_adapter.py:1757`). Por isso `oculto` aqui e herdado dos ancestrais.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List, Tuple

import click
import typer.main

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app

# Contagens travadas: comando novo quebra a guarda que as afirma, que e o ponto.
TOTAL_DE_FOLHAS = 44
TOTAL_DE_GRUPOS = 6
TOTAL_DE_OPCOES = 148


@dataclass(frozen=True)
class NoDaArvore:
    caminho: Tuple[str, ...]  # ("get", "interceptors") — sem o "sen" da frente
    comando: click.Command
    grupo: bool
    oculto: bool  # herdado: True se QUALQUER ancestral for hidden

    @property
    def ident(self) -> str:
        """Identificador legivel, usado como id de parametrizacao do pytest."""
        return " ".join(self.caminho) or "sen"

    @property
    def argv(self) -> List[str]:
        """O argv que o CliRunner espera, com o token `sen` obrigatorio."""
        return ["sen", *self.caminho]


def _caminhar(
    comando: click.Command, caminho: Tuple[str, ...], oculto: bool
) -> Iterator[NoDaArvore]:
    oculto = oculto or bool(getattr(comando, "hidden", False))
    grupo = isinstance(comando, click.Group)
    yield NoDaArvore(caminho=caminho, comando=comando, grupo=grupo, oculto=oculto)
    if grupo:
        for nome, sub in comando.commands.items():
            yield from _caminhar(sub, caminho + (nome,), oculto)


def arvore() -> List[NoDaArvore]:
    """Todos os nos endereçaveis, a partir do grupo `sen` (a raiz fica de fora)."""
    raiz = typer.main.get_command(app)
    sen = raiz.commands["sen"] if isinstance(raiz, click.Group) else raiz
    return list(_caminhar(sen, (), bool(getattr(sen, "hidden", False))))


def folhas() -> List[NoDaArvore]:
    return [no for no in arvore() if not no.grupo]


def grupos() -> List[NoDaArvore]:
    return [no for no in arvore() if no.grupo]


def superficies_de_help() -> List[NoDaArvore]:
    """Tudo que responde a `--help`: as folhas mais os grupos."""
    return arvore()


def opcoes(no: NoDaArvore) -> List[click.Option]:
    """As opcoes declaradas, sem o `--help` que o Click injeta."""
    return [
        p
        for p in no.comando.params
        if isinstance(p, click.Option) and p.name != "help"
    ]


def argumentos(no: NoDaArvore) -> List[click.Argument]:
    return [p for p in no.comando.params if isinstance(p, click.Argument)]


def pares_de_opcao() -> List[Tuple[NoDaArvore, click.Option]]:
    return [(no, opcao) for no in arvore() for opcao in opcoes(no)]


def por_ident() -> dict:
    return {no.ident: no for no in arvore()}


def ident(no: NoDaArvore) -> str:
    return no.ident
