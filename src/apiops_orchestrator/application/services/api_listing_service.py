from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.api_collection_model import (
    ApiCollection,
    ApiCollectionError,
    InsufficientSessionError,
    finder_rows_visible_to,
    finder_stage_by_revision,
    normalize_finder_rows,
)
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort

_INSUFFICIENT_GROUPS_MESSAGE = (
    "Sua sessão não possui grupos de acesso, refaça `sen login` ou "
    "acione o time de acesso."
)

_NOT_FOUND_MESSAGE = "API não encontrada ou sem permissão de acesso."

_FETCH_GROW_CAP = 2000  # teto de segurança contra universos gigantes


class ApiListingService:
    def __init__(
        self,
        manager_api: ManagerApiPort,
        session: Optional[LoginSession] = None,
    ):
        self.manager_api = manager_api
        self.session = session

    def list_apis(
        self,
        api_id: Optional[int] = None,
        query: Optional[str] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves APIs. With api_id, returns the single API detail (manager).

        Listing source (sondas r5, selado): API-FINDER catalog com
        onlyMyContextApi=false — paginacao server-side real não existe
        (skip/offset/page inertes; `_limit` apenas trunca), então a fatia
        buscada é `_limit = offset+limit` e o window client-side observa as
        regras A3 (janela APÓS filtro/visibilidade). Se o universo (header
        `count`) exceder o que veio, refetch única com o total inteiro —
        A3-1c (offset além do total → vazio/exit 0) depende de universo
        completo pois o filtro de visibilidade e `--query` rodam no cliente.
        """
        if api_id is not None:
            frame = self.manager_api.list_api_detail(api_id)
            if not frame:
                raise ApiCollectionError(_NOT_FOUND_MESSAGE)
            return normalize_finder_rows([frame])

        if self.session is not None:
            super_admin = self.session.is_super_admin
            groups = list(self.session.userGroups or [])
            if not super_admin and not groups:
                # Fail-fast: bloqueio antes de qualquer requisicao.
                raise InsufficientSessionError(_INSUFFICIENT_GROUPS_MESSAGE)

        page_needed = int(offset or 0) + int(limit or 0)
        rows, total = self._fetch_catalog(page_needed)

        rows = self._filter_visibility(rows)

        collection = ApiCollection.from_raw(normalize_finder_rows(rows))
        return (
            collection.filtered_by(query)
            .sorted_by_id()
            .window(offset, limit)
            .rows()
        )

    def api_revisions(self, api_id: int) -> List[Dict[str, Any]]:
        """Grade de revisões da API, fonte única = frame do catálogo.

        1 chamada (`list_api_detail`): REV ID · REV # · ENVS · COMPLETE nascem
        inline no frame; STAGE resolve nome via catálogo da port (cache no
        adapter, 1 chamada por workflow distinto, miss → id do workflow).
        CREATED/LAST DEPLOY não existem no frame (opção A) → colunas nem exibidas.
        """
        frame = self.manager_api.list_api_detail(api_id)
        if not frame:
            raise ApiCollectionError(_NOT_FOUND_MESSAGE)

        stage_refs = finder_stage_by_revision(frame)
        stage_names = self._resolve_stage_names(stage_refs)

        rows: List[Dict[str, Any]] = []
        for revision in frame.get("revisions") or []:
            if not isinstance(revision, dict):
                continue
            revision_id = revision.get("id")
            if revision_id is None or not revision.get("revisionNumber"):
                continue
            reference = stage_refs.get(revision_id, {})
            stage_name = stage_names.get(reference.get("workflow_stage_id"))
            rows.append(
                {
                    "revision_id": revision_id,
                    "revision_number": revision.get("revisionNumber"),
                    "stage_name": stage_name if stage_name else reference.get("workflow_id"),
                    "environments": self._env_names(frame, revision_id),
                    "complete": self._complete_cell(frame, revision_id),
                }
            )
        rows.sort(key=lambda row: (0, int(row["revision_number"])))
        return rows

    @staticmethod
    def _complete_cell(frame: Dict[str, Any], revision_id: Any) -> str:
        """Score inline do frame (`completeness[]`); absent/não-numérico → '-'."""
        for scored in frame.get("completeness") or []:
            if not isinstance(scored, dict):
                continue
            if scored.get("apiRevision") != revision_id:
                continue
            score = scored.get("score")
            try:
                return f"{float(score):.0f}%"
            except (TypeError, ValueError):
                return "-"
        return "-"

    def _resolve_stage_names(self, stage_refs: Dict[Any, Dict[str, Any]]) -> Dict[Any, str]:
        """1 busca por workflow distinto (cache no adapter); catálogo mudo → degrada."""
        workflow_ids = {
            reference["workflow_id"]
            for reference in stage_refs.values()
            if reference.get("workflow_id") is not None
        }
        resolved: Dict[Any, str] = {}
        for workflow_id in sorted(workflow_ids):
            try:
                for stage in self.manager_api.get_workflow_stages(workflow_id):
                    if isinstance(stage, dict) and stage.get("workflowStageId") is not None:
                        resolved[stage["workflowStageId"]] = stage.get("workflowStageName")
            except Exception:
                continue
        return resolved

    @staticmethod
    def _env_names(frame: Dict[str, Any], revision_id: Any) -> str:
        names = [
            str(env.get("name"))
            for env in frame.get("environments") or []
            if isinstance(env, dict)
            and env.get("apiRevision") == revision_id
            and env.get("name")
        ]
        return ", ".join(names)

    def _fetch_catalog(self, needed: int) -> tuple[List[Dict[str, Any]], int]:
        """Universo visível-bruto em até 2 consultas (`_limit` truncante).

        1ª chamada: `_limit = needed` (clamp >= 1). Header `count` informa o
        total do universo — se exceder o que veio (e fizer sentido crescer),
        reconsulta UMA vez com o total, cap `_FETCH_GROW_CAP` (proteção contra
        universos absurdos; estouro → segunda chamada truncada mesmo assim e
        nota em backlog).
        """
        first = max(needed, 1)
        page = self.manager_api.list_catalog_apis(limit=first)
        rows, total = list(page.rows), page.total

        if total > len(rows) and total <= _FETCH_GROW_CAP and needed < total:
            page = self.manager_api.list_catalog_apis(limit=total)
            rows, total = list(page.rows), page.total
        return rows, total

    def _filter_visibility(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sem sessão injetada: passthrough legado (enrich/bare preservados).

        Com sessão: matriz de contexto (r5) — ORGANIZATION todos · ME owner
        · GROUP exclusivamente por grupo da sessão · desconhecido nega.
        """
        if self.session is None:
            return rows
        return finder_rows_visible_to(
            rows,
            self.session.userName,
            list(self.session.userGroups or []),
            self.session.is_super_admin,
        )
