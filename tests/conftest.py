"""Fixtures de toda a suite.

`ambiente_limpo` e autouse: nenhum teste depende do ambiente da maquina de quem
o roda. A ordem aqui foi medir antes de ligar — existe um `.env` na raiz do
repositorio e o `pydantic-settings` o le por fora de `os.environ`, entao o efeito
da limpeza nao era presumivel. Ligada, a suite inteira segue verde (2053
testes), e e isso que autoriza o autouse.

Nao substitui o `_clean_env()` de `test_main_gate.py`: aquele monta o ambiente de
um SUBPROCESSO, que nao herda monkeypatch nenhum.
"""

from __future__ import annotations

import pytest

# Espelha `tests/unit/test_main_gate.py:_clean_env`.
VARIAVEIS_DO_AMBIENTE = (
    "EXECUTION_MODE",
    "TEMPLATE_API_ID",
    "TARGET_REVISION_NUMBER",
    "TARGET_ENVIRONMENT_ID",
    "AUTH_HOST",
    "AUTH_LOGIN_PATH",
    "SEN_CREDENTIALS",
    "HOST",
)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tira do processo as variaveis que mudariam o comportamento do comando."""
    for nome in VARIAVEIS_DO_AMBIENTE:
        monkeypatch.delenv(nome, raising=False)
