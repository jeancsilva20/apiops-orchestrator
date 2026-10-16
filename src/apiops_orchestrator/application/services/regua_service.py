"""Resolução e leitura da régua — a E2 do `sen validate`.

A régua é uma **API template** no Manager, lida por GET. Este serviço resolve de
onde vem o id, lê o fluxo, computa o snapshot que torna um achado reproduzível e
verifica que os `Custom` referenciados pelo repositório existem no tenant.

Decisões que o código implementa:

* **V-11 binding** — em `local` o id vem de `spec.template`; em `pipeline` vem de
  variável de ambiente alimentada pelo cofre, fora do alcance de um commit. Na
  esteira, divergência entre os dois faz a **variável vencer**, com `WARNING`;
* **D-12** — `spec.template` vazio é **erro**: sem régua não há validação;
* **P-2** — régua inalcançável **aborta**, nos dois modos;
* **D-4/P-3** — o snapshot (`id`, `revisionNumber`, hash) viaja no relatório;
* **W-2** — `Custom` inexistente aborta, nomeando o id.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    CustomInexistenteError,
    ReguaInalcancavelError,
    TemplateAusenteError,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services.repo_layout import eh_governado

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReguaCarregada:
    """A régua e o seu snapshot."""

    template_id: int
    revision_number: Optional[int]
    interceptors: List[Dict[str, Any]]
    flow_hash: str
    avisos: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.interceptors)


def calcular_flow_hash(interceptors: Sequence[Dict[str, Any]]) -> str:
    """Hash determinístico do fluxo comparado (D-4/P-3).

    Cobre o que a conformidade de fato compara — tipo, `customInterceptorId`,
    ponto de execução e `content` —, na ordem. Deixa de fora `id`, `idTemp` e
    `position`, que mudam entre revisões sem mudar o que a régua exige: incluí-los
    faria o hash variar sem que a régua tivesse mudado.
    """
    semente = []
    for item in interceptors:
        content = item.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError):
                pass
        semente.append(
            {
                "type": item.get("type"),
                "customInterceptorId": item.get("customInterceptorId"),
                "executionPoint": (item.get("executionPoint") or "").upper(),
                "content": content,
            }
        )
    bruto = json.dumps(semente, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:12]


class ReguaService:
    def __init__(self, manager_api: ManagerApiPort, settings: Settings):
        self._manager_api = manager_api
        self._settings = settings

    # --- resolução do id ----------------------------------------------------

    def resolver_id(self, basic_info: Dict[str, Any]) -> int:
        """De onde vem o id da régua, conforme o modo de execução (V-11)."""
        do_manifesto = (basic_info.get("spec") or {}).get("template")
        if self._settings.modo_pipeline:
            return self._resolver_em_pipeline(do_manifesto)
        return self._resolver_em_local(do_manifesto)

    def _resolver_em_pipeline(self, do_manifesto: Any) -> int:
        do_cofre = self._settings.TEMPLATE_API_ID
        if do_cofre is None:
            # Validar contra nada numa esteira é pior do que parar (V-11 §4).
            raise ReguaInalcancavelError(
                template_id="(não configurado)", status_code=None
            )
        if do_manifesto not in (None, "") and str(do_manifesto) != str(do_cofre):
            logger.info(
                "regua.divergencia manifesto=%s cofre=%s", do_manifesto, do_cofre
            )
        return int(do_cofre)

    def _resolver_em_local(self, do_manifesto: Any) -> int:
        if do_manifesto in (None, ""):
            # D-12 revogou o "vazio permitido" da V-11 §1.
            raise TemplateAusenteError()
        try:
            return int(do_manifesto)
        except (TypeError, ValueError):
            raise TemplateAusenteError()

    def divergencia_de_binding(self, basic_info: Dict[str, Any]) -> Optional[str]:
        """Aviso quando a esteira ignora o `spec.template` do manifesto."""
        if not self._settings.modo_pipeline:
            return None
        do_manifesto = (basic_info.get("spec") or {}).get("template")
        do_cofre = self._settings.TEMPLATE_API_ID
        if do_manifesto in (None, "") or do_cofre is None:
            return None
        if str(do_manifesto) == str(do_cofre):
            return None
        return (
            f"O `api-basic-info.yaml` aponta a API-template {do_manifesto}, mas a "
            f"esteira está usando a {do_cofre}, definida em variável de ambiente. "
            "A variável tem prioridade de propósito: assim a template não pode ser "
            f"trocada por um commit. Seguindo com a {do_cofre}."
        )

    # --- leitura -------------------------------------------------------------

    def carregar(self, basic_info: Dict[str, Any]) -> ReguaCarregada:
        """Resolve o id, lê a régua em UM GET e devolve o fluxo com o snapshot."""
        avisos = []
        divergencia = self.divergencia_de_binding(basic_info)
        if divergencia:
            avisos.append(divergencia)

        template_id = self.resolver_id(basic_info)
        payload = self._ler(template_id)

        ultima = payload.get("lastRevision") or {}
        # Um GET basta: `lastRevision` já traz o fluxo completo com `content`
        # (V-11 §6). "A implantada" não serviria — a 414 tem `deployments: []`.
        governados = [
            i
            for i in (ultima.get("interceptors") or [])
            if eh_governado(i.get("executionPoint")) and i.get("status") != "REMOVED"
        ]
        if not governados:
            avisos.append(
                f"A API-template {template_id} não tem nenhum interceptor configurado, "
                "então não há padrão para comparar. A validação segue, mas sem "
                "verificar conformidade."
            )

        return ReguaCarregada(
            template_id=template_id,
            revision_number=ultima.get("revisionNumber"),
            interceptors=governados,
            flow_hash=calcular_flow_hash(governados),
            avisos=avisos,
        )

    def _ler(self, template_id: int) -> Dict[str, Any]:
        try:
            return self._manager_api.get_api_by_id(template_id) or {}
        except ManagerApiTransportRejectedError as exc:
            raise ReguaInalcancavelError(template_id, exc.status_code) from exc
        except ManagerApiTransportUnavailableError as exc:
            raise ReguaInalcancavelError(template_id, None) from exc

    # --- existência dos Custom referenciados (W-2) --------------------------

    def verificar_customs(self, referencias: Sequence[tuple]) -> None:
        """Aborta no primeiro `Custom` que não existe, nomeando id e escopo.

        `referencias` são pares `(custom_id, escopo)`. O catálogo é autoridade:
        `404` significa ausente. O conteúdo **não** é reposto de revisão antiga —
        isso ressuscitaria uma referência que um administrador apagou de propósito.
        """
        vistos: Dict[int, bool] = {}
        for custom_id, escopo in referencias:
            if custom_id is None:
                continue
            if custom_id not in vistos:
                vistos[custom_id] = self._existe(custom_id)
            if not vistos[custom_id]:
                raise CustomInexistenteError(custom_id, escopo)

    def _existe(self, custom_id: int) -> bool:
        try:
            return self._manager_api.get_custom_interceptor_by_id(custom_id) is not None
        except ManagerApiTransportRejectedError as exc:
            if exc.status_code == 404:
                return False
            raise
