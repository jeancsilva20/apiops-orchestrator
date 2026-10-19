"""Erros de negócio do `sen deploy`: `message` em PT-BR e `exit_code` (1 falha, 3 governança)."""

from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from apiops_orchestrator.domain.models.deploy_model import DeployView

NENHUM_DEPLOY = "Nenhum deploy foi feito."


class DeployError(Exception):
    """Base dos erros do `sen deploy`."""

    exit_code = 1

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class DeployGovernanceBlockedError(DeployError):
    """O stage da revisão não libera o deploy no ambiente alvo."""

    exit_code = 3

    def __init__(
        self,
        workflow_id: Optional[int],
        stage_id: Optional[int],
        violacoes: List[str],
    ):
        listadas = "\n".join(f"  - {v}" for v in violacoes) or "  - motivo não informado"
        onde = f"workflow {workflow_id}" + (
            f", stage {stage_id}" if stage_id is not None else ""
        )
        super().__init__(
            "A governança do Manager não libera este deploy:\n\n"
            f"{listadas}\n\n{NENHUM_DEPLOY} ({onde})"
        )
        self.workflow_id = workflow_id
        self.stage_id = stage_id
        self.violacoes = list(violacoes)


class DeployFalhouError(DeployError):
    """O deploy foi tentado e não terminou conferido; carrega o resultado com `FAILED`."""

    def __init__(self, message: str, view: "DeployView"):
        super().__init__(message)
        self.view = view
