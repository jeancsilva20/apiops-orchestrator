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
    CustomNotFoundError,
    RulerUnreachableError,
    MissingTemplateError,
    TemplateNotConfiguredError,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services.repo_layout import is_governed

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoadedRuler:
    """A régua e o seu snapshot."""

    template_id: int
    revision_number: Optional[int]
    interceptors: List[Dict[str, Any]]
    flow_hash: str
    warnings: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.interceptors)


def compute_flow_hash(interceptors: Sequence[Dict[str, Any]]) -> str:
    """Hash determinístico do fluxo comparado (D-4/P-3).

    Cobre o que a conformidade de fato compara — tipo, `customInterceptorId`,
    ponto de execução e `content` —, na ordem. Deixa de fora `id`, `idTemp` e
    `position`, que mudam entre revisões sem mudar o que a régua exige: incluí-los
    faria o hash variar sem que a régua tivesse mudado.
    """
    seed = []
    for item in interceptors:
        content = item.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (TypeError, ValueError):
                pass
        seed.append(
            {
                "type": item.get("type"),
                "customInterceptorId": item.get("customInterceptorId"),
                "executionPoint": (item.get("executionPoint") or "").upper(),
                "content": content,
            }
        )
    raw = json.dumps(seed, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


class RulerService:
    def __init__(self, manager_api: ManagerApiPort, settings: Settings):
        self._manager_api = manager_api
        self._settings = settings

    # --- resolução do id ----------------------------------------------------

    def resolver_id(self, basic_info: Dict[str, Any]) -> int:
        """De onde vem o id da régua, conforme o modo de execução (V-11)."""
        from_manifest = (basic_info.get("spec") or {}).get("template")
        if self._settings.pipeline_mode:
            return self._resolve_in_pipeline(from_manifest)
        return self._resolve_locally(from_manifest)

    def _resolve_in_pipeline(self, from_manifest: Any) -> int:
        from_vault = self._settings.TEMPLATE_API_ID
        if from_vault is None:
            # Validar contra nada numa esteira é pior do que parar.
            raise TemplateNotConfiguredError()
        if from_manifest not in (None, "") and str(from_manifest) != str(from_vault):
            logger.info(
                "regua.divergencia manifesto=%s cofre=%s", from_manifest, from_vault
            )
        return int(from_vault)

    def _resolve_locally(self, from_manifest: Any) -> int:
        if from_manifest in (None, ""):
            # D-12 revogou o "vazio permitido" da V-11 §1.
            raise MissingTemplateError()
        try:
            return int(from_manifest)
        except (TypeError, ValueError):
            raise MissingTemplateError()

    def binding_divergence(self, basic_info: Dict[str, Any]) -> Optional[str]:
        """Aviso quando a esteira ignora o `spec.template` do manifesto."""
        if not self._settings.pipeline_mode:
            return None
        from_manifest = (basic_info.get("spec") or {}).get("template")
        from_vault = self._settings.TEMPLATE_API_ID
        if from_manifest in (None, "") or from_vault is None:
            return None
        if str(from_manifest) == str(from_vault):
            return None
        return (
            f"O `api-basic-info.yaml` aponta a API-template {from_manifest}, mas a "
            f"esteira está usando a {from_vault}, definida pela plataforma. "
            "A da esteira tem prioridade, para que a template não possa ser "
            f"trocada por um commit. Seguindo com a {from_vault}."
        )

    # --- leitura -------------------------------------------------------------

    def load(self, basic_info: Dict[str, Any]) -> LoadedRuler:
        """Resolve o id, lê a régua em UM GET e devolve o fluxo com o snapshot."""
        warnings = []
        divergence = self.binding_divergence(basic_info)
        if divergence:
            warnings.append(divergence)

        template_id = self.resolver_id(basic_info)
        payload = self._read(template_id)

        last = payload.get("lastRevision") or {}
        # Um GET basta: `lastRevision` já traz o fluxo completo com `content`
        # (V-11 §6). "A implantada" não serviria — a 414 tem `deployments: []`.
        governed = [
            i
            for i in (last.get("interceptors") or [])
            if is_governed(i.get("executionPoint")) and i.get("status") != "REMOVED"
        ]
        if not governed:
            warnings.append(
                f"A API-template {template_id} não tem nenhum interceptor configurado, "
                "então não há padrão para comparar. A validação segue, mas sem "
                "verificar conformidade."
            )

        return LoadedRuler(
            template_id=template_id,
            revision_number=last.get("revisionNumber"),
            interceptors=governed,
            flow_hash=compute_flow_hash(governed),
            warnings=warnings,
        )

    def _read(self, template_id: int) -> Dict[str, Any]:
        try:
            return self._manager_api.get_api_by_id(template_id) or {}
        except (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError) as exc:
            raise RulerUnreachableError(
                template_id,
                getattr(exc, "status_code", None),
                manager_failure_message(classify_manager_failure(exc)),
            ) from exc

    # --- existência dos Custom referenciados (W-2) --------------------------

    def check_customs(self, references: Sequence[tuple]) -> None:
        """Aborta no primeiro `Custom` que não existe, nomeando id e escopo.

        `references` são pares `(custom_id, scope)`. O catálogo é autoridade:
        `404` significa ausente. O conteúdo **não** é reposto de revisão antiga —
        isso ressuscitaria uma referência que um administrador apagou de propósito.
        """
        seen: Dict[int, bool] = {}
        for custom_id, scope in references:
            if custom_id is None:
                continue
            if custom_id not in seen:
                seen[custom_id] = self._exists(custom_id)
            if not seen[custom_id]:
                raise CustomNotFoundError(custom_id, scope)

    def _exists(self, custom_id: int) -> bool:
        try:
            return self._manager_api.get_custom_interceptor_by_id(custom_id) is not None
        except ManagerApiTransportRejectedError as exc:
            if exc.status_code == 404:
                return False
            raise
