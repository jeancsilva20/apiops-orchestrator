import unicodedata
from typing import Any


def accent_fold(value: Any) -> str:
    """Normaliza texto para comparacao: minusculo e sem diacriticos.

    'Autenticação' -> 'autenticacao'. Aceita None/vazio devolvendo string
    vazia, para uso direto em comparacoes de campos opcionais.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFD", str(value))
    without_marks = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return without_marks.casefold()
