"""Contract step of `validate` and `publish`: validates, reads, writes and verifies the revision swagger.

Receives **ports**, never concrete adapters. An error in the declared contract
aborts; a platform problem becomes the reason the documentation was not updated,
and the written flow stays.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    InvalidContractError,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    LoadedRepository,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.domain.services import (
    openapi_contract,
    openapi_contract_validator,
    revision_payload,
)
from apiops_orchestrator.domain.models.validate_view import (
    DOCUMENTATION_NOT_UPDATED,
    DOCUMENTATION_UNCHANGED,
    DOCUMENTATION_UPDATED,
    DocumentationResult,
)
from apiops_orchestrator.domain.services.openapi_contract import RepositoryContract

logger = logging.getLogger(__name__)

_STATUS_WITH_REASON = frozenset({400, 409, 412, 422})

SWAGGER_2_WARNING = (
    "O swagger desta revisão está em Swagger 2.0, e o contrato só é gravado em "
    "OpenAPI 3. O fluxo é gravado normalmente; a documentação, não.\n"
    "Migre o swagger da API para OpenAPI 3 no Manager."
)


@dataclass(frozen=True)
class PreparedContract:
    """Contract ready to be written and what to warn before the write."""

    contract: RepositoryContract
    write: bool
    warnings: List[str] = field(default_factory=list)
    # Swagger read before any write of the run.
    before: Optional[Dict[str, Any]] = None


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"  - {item}" for item in items)


def _updated(reason: Optional[str]) -> DocumentationResult:
    return DocumentationResult(status=DOCUMENTATION_UPDATED, reason=reason)


def _not_updated(reason: Optional[str]) -> DocumentationResult:
    return DocumentationResult(status=DOCUMENTATION_NOT_UPDATED, reason=reason)


class ContractWriter:
    def __init__(self, manager_api: ManagerApiPort, command: str):
        self._manager_api = manager_api
        # Log event prefix: `validate.contract.*`, `publish.contract.*`.
        self._command = command

    def validate(self, loaded: LoadedRepository) -> Tuple[RepositoryContract, List[str]]:
        """Validates and extracts the repository contract; an error aborts before any write."""
        result = openapi_contract_validator.validate(
            basic_info=loaded.basic_info,
            components=loaded.components,
            resources=loaded.resources,
            ignored=loaded.ignored,
        )
        if result.errors:
            logger.info("%s.contract.invalid errors=%d", self._command, len(result.errors))
            raise InvalidContractError(result.errors)
        contract = openapi_contract.extract_contract(
            basic_info=loaded.basic_info,
            components=loaded.components,
            resources=loaded.resources,
        )
        return contract, list(result.warnings)

    def prepare(
        self,
        revision_id: int,
        contract: RepositoryContract,
        step: Callable[[str], None] = lambda _: None,
    ) -> PreparedContract:
        """Reads the current swagger and says what leaves the documentation on write."""
        step("Lendo o swagger da revisão")
        try:
            current = self._manager_api.get_revision_swagger(revision_id)
        except ManagerApiError as exc:
            warning = self._failure_warning(
                "Não consegui ler o swagger da revisão no Manager, então o contrato não "
                "será gravado. O fluxo é gravado normalmente.",
                exc,
            )
            return PreparedContract(contract, write=False, warnings=[warning])
        if openapi_contract.is_swagger_2(current):
            logger.info("%s.contract.swagger_2", self._command)
            return PreparedContract(contract, write=False, warnings=[SWAGGER_2_WARNING])

        removed = openapi_contract.removed_items(current, contract)
        warnings = []
        if removed:
            warnings.append(
                "Ao gravar o contrato, estes itens saem da documentação da API no "
                "Manager, porque não estão no repositório:\n"
                + _bullets(removed)
                + "\n\nSe não era essa a intenção, declare-os no repositório."
            )
        return PreparedContract(contract, write=True, warnings=warnings, before=current)

    def write(
        self,
        revision_id: int,
        prepared: PreparedContract,
        approved: Dict[str, Any],
        step: Callable[[str], None] = lambda _: None,
    ) -> DocumentationResult:
        """Writes the contract over the current swagger and verifies it; says whether it was updated."""
        if not prepared.write:
            return _not_updated(prepared.warnings[0] if prepared.warnings else None)

        step("Montando o contrato")
        try:
            current = self._manager_api.get_revision_swagger(revision_id)
        except ManagerApiError as exc:
            return _not_updated(
                self._failure_warning(
                    "Não consegui ler o swagger da revisão no Manager, então o contrato "
                    "não foi gravado. O fluxo foi gravado normalmente.",
                    exc,
                )
            )
        if openapi_contract.is_swagger_2(current):
            return _not_updated(SWAGGER_2_WARNING)
        missing = openapi_contract.missing_routes(current, prepared.contract)
        if missing:
            logger.info("%s.contract.missing_routes total=%d", self._command, len(missing))
            return _not_updated(
                "O contrato não foi gravado: estas rotas do repositório não aparecem no "
                "swagger da revisão:\n"
                + _bullets(missing)
                + "\n\nO fluxo foi gravado. Rode o comando de novo; se continuar, confira "
                "a revisão no Manager."
            )

        document = openapi_contract.apply_contract(current, prepared.contract)
        if openapi_contract.same_document(document, current):
            # The revision write may have changed the documentation already
            # (route description, new route): that run still updated it.
            if prepared.before is not None and not openapi_contract.same_documentation(
                prepared.before, current
            ):
                logger.info("%s.contract.updated_by_revision", self._command)
                return _updated(None)
            logger.info("%s.contract.unchanged", self._command)
            return DocumentationResult(status=DOCUMENTATION_UNCHANGED)

        step("Gravando o contrato no Manager")
        try:
            self._manager_api.update_revision_swagger(revision_id, document)
        except ManagerApiTransportRejectedError as exc:
            return _not_updated(self._rejection_warning(exc))
        except ManagerApiError as exc:
            return _not_updated(
                self._failure_warning(
                    "O Manager não respondeu à gravação do contrato. O fluxo foi gravado "
                    "normalmente; a documentação, não.",
                    exc,
                )
            )

        step("Conferindo o contrato gravado")
        try:
            written = self._manager_api.get_revision_swagger(revision_id)
            revision = self._manager_api.get_revision(revision_id) or {}
        except ManagerApiError as exc:
            return _updated(
                self._failure_warning(
                    "O contrato foi enviado, mas não consegui relê-lo para conferir.", exc
                )
            )

        differences = openapi_contract.verify_contract(document, written)
        differences += [f"fluxo: {d}" for d in revision_payload.verify(approved, revision)]
        for key in ("workflowId", "workflowStageId"):
            if approved.get(key) != revision.get(key):
                differences.append(
                    f"`{key}` era {approved.get(key)!r} e ficou {revision.get(key)!r}"
                )
        if differences:
            logger.info("%s.contract.diverged total=%d", self._command, len(differences))
            return _updated(
                "O Manager aceitou o contrato, mas o que ficou gravado não é o que foi "
                "enviado:\n"
                + _bullets(differences)
                + "\n\nO fluxo continua gravado. Confira a revisão no Manager."
            )
        logger.info("%s.contract.written", self._command)
        return _updated(None)

    def _failure_warning(self, text: str, exc: ManagerApiError) -> str:
        logger.info("%s.contract.failure type=%s", self._command, type(exc).__name__)
        family = manager_failure_message(classify_manager_failure(exc))
        return f"{text}\n{family}" if family else text

    def _rejection_warning(self, exc: ManagerApiTransportRejectedError) -> str:
        reasons = [m for m in exc.messages if m] if exc.status_code in _STATUS_WITH_REASON else []
        logger.info(
            "%s.contract.rejected status_code=%s reasons=%d",
            self._command,
            exc.status_code,
            len(reasons),
        )
        if not reasons:
            return self._failure_warning(
                "O Manager recusou a gravação do contrato. O fluxo foi gravado "
                "normalmente; a documentação, não.",
                exc,
            )
        return (
            "O Manager recusou a gravação do contrato:\n"
            + _bullets(reasons)
            + "\n\nO fluxo foi gravado normalmente; a documentação, não. Corrija o "
            "contrato conforme o motivo acima."
        )
