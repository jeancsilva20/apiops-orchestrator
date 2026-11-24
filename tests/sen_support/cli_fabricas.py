"""Montagem do `ctx.obj` que os comandos da CLI consomem.

A CLI nao recebe o service: recebe uma FABRICA em
`ctx.obj["<nome>_service_factory"]` e a chama. Os testes injetam um fake por ai
— sem patch de modulo e sem mock de HTTP na borda.

Armadilha que o tipo `Fabrica` existe para fechar: `MagicMock` e callable. Um
helper ingenuo que fizesse `valor if callable(valor) else lambda: valor`
trataria o mock como *fabrica* e o comando receberia `mock()` — um mock-filho,
nao o servico. Toda assercao passaria, vazia. Por isso aqui se embrulha SEMPRE,
e `fabrica()` e o unico jeito de passar uma fabrica crua.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

# Apelido curto -> chave real do ctx.obj. As chaves sao conferidas contra
# `main.build_context()` pela guarda G9, entao esta tabela nao pode derivar.
FABRICAS: Dict[str, str] = {
    "login": "login_service_factory",
    "listagem": "api_listing_service_factory",
    "navegacao": "api_navigation_service_factory",
    "completude": "completeness_service_factory",
    "validate": "validate_service_factory",
    "publish": "publish_service_factory",
    "deploy": "deploy_service_factory",
    "regua": "regua_service_factory",
    "manager": "manager_api_factory",
}


class Fabrica:
    """Marca um callable que JA e a fabrica, nao o servico."""

    __slots__ = ("fn",)

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.fn = fn


def fabrica(fn: Callable[[], Any]) -> Fabrica:
    """Passa uma fabrica crua (ex.: uma classe que o comando deve instanciar)."""
    return Fabrica(fn)


def fabrica_que_falha(erro: BaseException) -> Fabrica:
    """Fabrica que explode ao ser chamada: simula falha na montagem do servico."""

    def _explode() -> Any:
        raise erro

    return Fabrica(_explode)


def contexto(**fabricas: Any) -> Dict[str, Any]:
    """Monta o ctx.obj a partir dos apelidos: `contexto(navegacao=servico)`."""
    obj: Dict[str, Any] = {}
    for apelido, valor in fabricas.items():
        if apelido not in FABRICAS:
            raise KeyError(
                f"apelido desconhecido: {apelido!r}. Conhecidos: {sorted(FABRICAS)}"
            )
        chave = FABRICAS[apelido]
        obj[chave] = valor.fn if isinstance(valor, Fabrica) else (lambda v=valor: v)
    return obj


def chaves(*apelidos: str) -> Mapping[str, str]:
    return {apelido: FABRICAS[apelido] for apelido in apelidos}
