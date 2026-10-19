"""Regras de serialização de escalares para o YAML do repositório.

Lógica pura. Transplantada de `extrair_estrutura.py` com os **dois reparos**
registrados na fila de templates/schemas (itens 23 e 24), ambos com caso real
observado:

1. **Indicador YAML no início do escalar.** O protótipo citava em `:`, `#`,
   quebra de linha e espaço nas bordas, mas não nos indicadores. O resultado é
   que `replaceChar: *****` sai sem aspas e o arquivo **deixa de ser parseável**
   — `yaml.safe_load` tenta ler um alias. Dois arquivos de `api-400-rev4` estão
   nesse estado hoje.

2. **String numérica.** O wire devolve `"quota": "1000"` e `timeout: '30'` como
   STRING. Emitidos sem aspas, voltam da releitura como inteiro: o round-trip
   quebra, e a comparação com a régua acusa achado falso num campo idêntico.
"""

import json
import re
from typing import Any

# Caracteres que, no início de um escalar, mudam o significado para o parser:
# âncora, alias, tag, blocos, diretiva, coleções em fluxo, comentário, aspas.
INDICADORES_YAML = frozenset("-?:,[]{}#&*!|>'\"%@`")

# Palavras que o YAML interpreta como booleano ou nulo se não forem citadas.
PALAVRAS_RESERVADAS = frozenset(
    {"true", "false", "null", "yes", "no", "on", "off", "y", "n", "~"}
)

_NUMERICO = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
_EXIGE_ASPAS = re.compile(r"[:#\n]|^\s|\s$")


def parece_numero(texto: str) -> bool:
    """A string seria relida como número se fosse emitida sem aspas."""
    return bool(_NUMERICO.match(texto))


def precisa_aspas(texto: str) -> bool:
    """Decide se o escalar precisa ser citado para sobreviver ao round-trip."""
    if texto == "":
        return True
    if texto[0] in INDICADORES_YAML:
        return True
    if texto.lower() in PALAVRAS_RESERVADAS:
        return True
    if parece_numero(texto):
        return True
    return bool(_EXIGE_ASPAS.search(texto))


def escalar(valor: Any) -> str:
    """Renderiza um escalar preservando o tipo na releitura.

    `None` vira `null` e os booleanos viram `true`/`false` sem aspas, porque
    nesses casos o tipo YAML É o tipo pretendido. Números nativos saem crus. Só
    strings passam pela decisão de citação.
    """
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    texto = str(valor)
    if precisa_aspas(texto):
        return json.dumps(texto, ensure_ascii=False)
    return texto
