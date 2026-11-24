"""Fakes de servico para os testes de borda da CLI.

Duas escolhas que pagam o proprio custo:

**`create_autospec(Classe, instance=True)` no lugar de `MagicMock()`.** O mock
nu aceita qualquer chamada: o dia em que a CLI passar um parametro que o service
nao tem, o teste continua verde e o erro so aparece em producao. Com autospec a
assinatura e conferida na chamada, de graca.

**`argumentos_da_chamada`.** A CLI chama metade dos servicos por posicao
(`_service(ctx).structure(api_id, revision, revision_id)`, navigation_cli.py:301)
e metade por nome (`.interceptors(api_id, ..., resource=..., include_content=...)`,
:521-529). Comparar `call.args`/`call.kwargs` cru obrigaria cada linha da matriz
de opcoes a saber qual estilo o comando usa. O bind normaliza os dois no mesmo
dicionario, entao a matriz afirma so o que importa: o valor chegou com o nome do
contrato.
"""

from __future__ import annotations

import inspect
from typing import Any, Dict
from unittest.mock import create_autospec

from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.api_navigation_service import (
    ApiNavigationService,
)
from apiops_orchestrator.application.services.completeness_service import (
    CompletenessService,
)
from apiops_orchestrator.application.services.deploy_service import DeployService
from apiops_orchestrator.application.services.publish_service import PublishService
from apiops_orchestrator.application.services.ruler_service import RulerService
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

CLASSES = {
    "navegacao": ApiNavigationService,
    "listagem": ApiListingService,
    "completude": CompletenessService,
    "validate": ValidateService,
    "publish": PublishService,
    "deploy": DeployService,
    "regua": RulerService,
    "manager": ManagerApiPort,
}


def servico(apelido: str, **retornos: Any) -> Any:
    """Fake com assinatura conferida: `servico("navegacao", api_detail={...})`."""
    fake = create_autospec(CLASSES[apelido], instance=True)
    for metodo, valor in retornos.items():
        getattr(fake, metodo).return_value = valor
    return fake


def servico_de_navegacao(**retornos: Any) -> Any:
    return servico("navegacao", **retornos)


def servico_de_listagem(**retornos: Any) -> Any:
    return servico("listagem", **retornos)


def argumentos_da_chamada(classe: type, metodo: str, call: Any) -> Dict[str, Any]:
    """Normaliza posicional x nomeado num dicionario comparavel.

    `self` sai do resultado; os defaults da assinatura entram, para que a
    ausencia de uma flag seja afirmavel do mesmo jeito que a presenca.
    """
    assinatura = inspect.signature(getattr(classe, metodo))
    ligado = assinatura.bind(None, *call.args, **call.kwargs)
    ligado.apply_defaults()
    argumentos = dict(ligado.arguments)
    argumentos.pop("self", None)
    return argumentos
