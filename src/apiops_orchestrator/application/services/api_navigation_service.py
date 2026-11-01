"""Use-cases dos comandos de navegação: `sen get ...` e `sen export api`.

Tudo aqui é leitura. O serviço lê a API inteira uma vez (`GET /apis/{id}`, que
já traz as revisões com recursos e interceptors inline) e delega a leitura ao
domínio (`api_navigation`, `repo_materializer`). Visibilidade segue a regra dos
demais comandos: quem não vê tudo passa pelo catálogo e pela guarda antes de
ler o Manager cru; API invisível e inexistente respondem o mesmo.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from apiops_orchestrator.application.enums.manager_failure_kind_enum import (
    ManagerFailureKind,
)
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationApiNotFound,
    NavigationCustomNotFound,
    NavigationError,
    NavigationInterceptorNotFound,
    NavigationPlatformError,
    NavigationRevisionNotFound,
    NavigationScopeNotFound,
)
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.application.services.governance_precheck_service import (
    GovernancePrecheckService,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.services import governance_check as gov
from apiops_orchestrator.domain.services import tenant_catalog as tenant
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiError,
    ManagerApiPort,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services import api_navigation as nav
from apiops_orchestrator.domain.services.repo_materializer import (
    MaterializationResult,
    materialize,
)

logger = logging.getLogger(__name__)

_PORT_FAILURES = (ManagerApiTransportRejectedError, ManagerApiTransportUnavailableError)


def _revision_label(number: Optional[int], revision_id: Optional[int]) -> str:
    if revision_id is not None:
        return f"de id {revision_id}"
    return f"de número {number}"


class ApiNavigationService:
    def __init__(
        self, manager_api: ManagerApiPort, session: Optional[LoginSession] = None
    ):
        self.manager_api = manager_api
        self.session = session
        self._guard = ApiAccessGuard(session)

    # ------------------------------------------------------------------ leitura

    def load_api(self, api_id: int) -> Dict[str, Any]:
        """A API crua do Manager, já com a visibilidade conferida."""
        try:
            if not self._guard.sees_everything():
                entry = self.manager_api.list_api_detail(api_id)
                if entry is None or not self._guard.can_see(entry.visibility()):
                    raise NavigationApiNotFound(api_id)
            api = self.manager_api.get_api_by_id(api_id)
        except _PORT_FAILURES as exc:
            raise self._translate(exc, api_id=api_id) from exc
        if not isinstance(api, dict) or api.get("id") is None:
            raise NavigationApiNotFound(api_id)
        return api

    def revision(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """`(api, revisão)`: pelo número da UI, pelo id, ou a corrente."""
        api = self.load_api(api_id)
        revision = nav.select_revision(api, number=number, revision_id=revision_id)
        if revision is None:
            raise NavigationRevisionNotFound(
                api_id,
                _revision_label(number, revision_id),
                nav.available_revision_numbers(api),
            )
        return api, revision

    # ------------------------------------------------------------------ catálogos

    def _safe(self, reader, default):
        """Leitura auxiliar que não derruba o comando: falha vira o default."""
        try:
            return reader()
        except Exception as exc:  # noqa: BLE001 - enriquecimento opcional
            logger.info("navigation.catalog.unavailable type=%s", type(exc).__name__)
            return default

    def environments(self) -> list:
        try:
            rows = self.manager_api.list_environments()
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        return [
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "description": e.get("description") or None,
                "inboundUrl": e.get("inboundUrl"),
                "isDeployable": e.get("isDeployable"),
                "tlsType": e.get("tlsType"),
            }
            for e in rows
        ]

    def _environment_names(self) -> Dict[Any, str]:
        return {
            e.get("id"): str(e.get("name"))
            for e in self._safe(self.manager_api.list_environments, [])
            if e.get("id") is not None
        }

    def _attribute_names(self) -> Dict[Any, str]:
        return {
            a.get("id"): str(a.get("name"))
            for a in self._safe(self.manager_api.list_attributes, [])
            if a.get("id") is not None
        }

    @staticmethod
    def _workflow_header(workflow: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": workflow.get("workflowId"),
            "name": workflow.get("workflowName"),
            "description": workflow.get("workflowDescription") or None,
            "category": workflow.get("workflowCategory"),
            "group": workflow.get("groupId"),
        }

    def workflows(self) -> list:
        try:
            rows = self.manager_api.list_workflows()
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        documents = []
        for workflow in rows:
            documents.append(
                {
                    **self._workflow_header(workflow),
                    "stages": [
                        {
                            "id": s.get("workflowStageId"),
                            "name": s.get("workflowStageName"),
                            "position": s.get("position"),
                            "maturityRequired": s.get("completenessRequisite"),
                            "interceptors": len(s.get("interceptorsRequisites") or []),
                            "attributes": len(s.get("attributesRequisites") or []),
                            "deployableEnvironments": list(s.get("deployableEnvironments") or []),
                        }
                        for s in gov.ordered_stages(workflow)
                    ],
                }
            )
        return documents

    def workflow(self, workflow_id: int) -> Dict[str, Any]:
        try:
            workflow = self.manager_api.get_workflow(workflow_id)
        except _PORT_FAILURES as exc:
            kind = classify_manager_failure(exc)
            if kind is ManagerFailureKind.NOT_FOUND:
                raise NavigationError(
                    f"Workflow {workflow_id} não encontrado. Liste os existentes com: sen list workflows"
                ) from exc
            raise self._translate(exc) from exc
        if not isinstance(workflow, dict) or workflow.get("workflowId") is None:
            raise NavigationError(
                f"Workflow {workflow_id} não encontrado. Liste os existentes com: sen list workflows"
            )
        attributes = self._attribute_names()
        environments = self._environment_names()
        return {
            **self._workflow_header(workflow),
            "stages": [
                gov.describe_requisites(s, attributes, environments)
                for s in gov.ordered_stages(workflow)
            ],
        }

    def attributes(self) -> list:
        try:
            rows = self.manager_api.list_attributes()
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        return [
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "tags": [str(t) for t in (a.get("tags") or [])],
                "inUse": a.get("inUse"),
            }
            for a in rows
            if isinstance(a, dict)
        ]

    def interceptor_catalog(
        self, *, custom_only: bool = False, tag: Optional[str] = None
    ) -> list:
        try:
            rows = self.manager_api.list_interceptor_catalog()
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        documents = []
        for item in rows:
            category = str(item.get("category") or "")
            is_custom = category.upper() != "DEFAULT"
            if custom_only and not is_custom:
                continue
            tags = [str(t) for t in (item.get("tags") or [])]
            if tag is not None and tag.lower() not in {t.lower() for t in tags}:
                continue
            points = str(item.get("executionPoint") or "")
            documents.append(
                {
                    "name": item.get("name"),
                    "kind": "custom" if is_custom else "native",
                    "category": category or None,
                    "id": item.get("id"),
                    "executionPoints": [
                        label
                        for code, label in (("1", "request"), ("2", "response"))
                        if code in points.split(";")
                    ],
                    "flowType": item.get("flowType"),
                    "tags": tags,
                }
            )
        documents.sort(key=lambda d: (d["kind"] != "native", str(d["name"]).lower()))
        return documents

    # ------------------------------------------------------------------ níveis

    def api_detail(self, api_id: int) -> Dict[str, Any]:
        document = nav.api_summary(self.load_api(api_id))
        workflows = {
            w.get("workflowId"): w for w in self._safe(self.manager_api.list_workflows, [])
        }
        for revision in document.get("revisions") or []:
            workflow = workflows.get(revision.get("workflowId")) or {}
            stage = gov.find_stage(workflow, revision.get("workflowStageId")) or {}
            revision["workflowName"] = workflow.get("workflowName")
            revision["stageName"] = stage.get("workflowStageName")
        return document

    def governance(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """A revisão contra os requisitos do stage atual e do próximo do workflow."""
        api, revision = self.revision(api_id, number, revision_id)
        header = nav.revision_header(api, revision)
        warnings: list = []
        workflow_id = revision.get("workflowId")
        stage_id = revision.get("workflowStageId")

        document: Dict[str, Any] = {
            "api": nav.api_header(api),
            "revision": header,
            "workflow": None,
            "stage": None,
            "maturity": None,
            "deployedIn": [],
            "current": None,
            "next": None,
            "warnings": warnings,
        }
        if workflow_id is None or stage_id is None:
            warnings.append(
                "a revisão não declara workflowId/workflowStageId: o Adaptive "
                "Governance não se aplica a ela"
            )
            return document

        workflow = self._safe(lambda: self.manager_api.get_workflow(workflow_id), None)
        if not isinstance(workflow, dict) or workflow.get("workflowId") is None:
            warnings.append(f"o workflow {workflow_id} não pôde ser lido no Manager")
            return document
        document["workflow"] = self._workflow_header(workflow)

        stage = gov.find_stage(workflow, stage_id)
        if stage is None:
            warnings.append(
                f"o stage {stage_id} não existe no workflow {workflow_id}; "
                "a revisão aponta para um stage de outro workflow"
            )
            return document
        document["stage"] = {
            "id": stage.get("workflowStageId"),
            "name": stage.get("workflowStageName"),
            "position": stage.get("position"),
        }

        reading = self._safe(
            lambda: self.manager_api.get_revision_completeness(int(revision["id"])), None
        )
        score = reading.score if reading is not None else None
        document["maturity"] = {
            "score": score,
            "suggestions": len(reading.suggestions) if reading is not None else None,
        }
        if reading is None:
            warnings.append("o completeness da revisão não pôde ser lido")

        environments = self._environment_names()
        attributes = self._attribute_names()
        deployed_ids = [
            env.get("id")
            for env in api.get("environments") or []
            if isinstance(env, dict)
            and isinstance(env.get("revisionDeployed"), dict)
            and env["revisionDeployed"].get("revisionId") == revision.get("id")
        ]
        document["deployedIn"] = [
            {"id": env_id, "name": environments.get(env_id)} for env_id in deployed_ids
        ]

        precheck = GovernancePrecheckService(self.manager_api)
        api_tags = api.get("apiTags")
        present = set(self._safe(lambda: precheck.present_attribute_ids(api_tags), set()))
        ids_by_name = {name: attribute_id for attribute_id, name in attributes.items()}
        for invalid in self._safe(lambda: precheck.invalid_tags(api_tags), []):
            warnings.append(
                f"a tag {invalid.tag!r} do atributo {invalid.attribute_name!r} não existe "
                f"no catálogo (válidas: {', '.join(invalid.valid)}); a plataforma apaga "
                "os apiTags nesse caso, então o atributo não conta"
            )
            present.discard(ids_by_name.get(invalid.attribute_name))

        def evaluate(target: Dict[str, Any]) -> Dict[str, Any]:
            verdicts = []
            maturity = gov.evaluate_maturity(target, score)
            if maturity is not None:
                verdicts.append(maturity)
            verdicts += gov.evaluate_interceptors(target, revision)
            verdicts += gov.evaluate_attributes(target, present, attributes)
            verdicts += gov.evaluate_environments(target, deployed_ids, environments)
            return {
                "stage": gov.describe_requisites(target, attributes, environments),
                "verdicts": [v.to_dict() for v in verdicts],
                "summary": gov.summarize(verdicts),
            }

        document["current"] = evaluate(stage)
        following = gov.next_stage(workflow, stage_id)
        document["next"] = evaluate(following) if following is not None else None
        return document

    def impact(self, api_id: int, environment_id: Optional[int] = None) -> Dict[str, Any]:
        """Grafo de impacto: rotas, destinos, planos e apps que consomem a API."""
        api = self.load_api(api_id)
        if environment_id is None:
            environment_id = self._default_environment(api)
        try:
            tree = self.manager_api.get_impact_tree(api_id, environment_id)
        except _PORT_FAILURES as exc:
            raise self._translate(exc, api_id=api_id) from exc
        root = tree.get("rootNode") if isinstance(tree, dict) else None
        if not isinstance(root, dict):
            raise NavigationPlatformError(
                manager_failure_message(ManagerFailureKind.INTERNAL) or "resposta inesperada"
            )
        names = self._environment_names()
        return {
            "api": nav.api_header(api),
            "environment": {"id": environment_id, "name": names.get(environment_id)},
            **_impact_document(root),
        }

    @staticmethod
    def _default_environment(api: Dict[str, Any]) -> int:
        """Primeiro ambiente com revisão no ar; senão o primeiro da API; senão 1."""
        environments = [e for e in api.get("environments") or [] if isinstance(e, dict)]
        for env in environments:
            if isinstance(env.get("revisionDeployed"), dict) and env.get("id") is not None:
                return int(env["id"])
        for env in environments:
            if env.get("id") is not None:
                return int(env["id"])
        return 1

    def structure(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        return nav.structure(api, revision)

    def interceptors(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
        *,
        resource: Optional[str] = None,
        operation: Optional[str] = None,
        effective: bool = False,
        include_content: bool = False,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        document = nav.scope_flows(
            api,
            revision,
            resource=resource,
            operation=operation,
            effective=effective,
            include_content=include_content,
        )
        if document is None:
            selector = " ".join(
                part
                for part in (
                    f"--resource {resource!r}" if resource else "",
                    f"--operation {operation!r}" if operation else "",
                )
                if part
            )
            raise NavigationScopeNotFound(api_id, selector)
        return document

    def interceptor(
        self,
        api_id: int,
        item_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        api, revision = self.revision(api_id, number, revision_id)
        found = nav.find_interceptor(revision, item_id)
        if found is None:
            raise NavigationInterceptorNotFound(api_id, item_id)
        scope, item = found
        return nav.describe_interceptor(api, revision, scope, item)

    def custom_interceptor(self, custom_id: int) -> Dict[str, Any]:
        try:
            custom = self.manager_api.get_custom_interceptor_by_id(custom_id)
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        if not custom:
            raise NavigationCustomNotFound(custom_id)
        return {
            "id": custom.get("id"),
            "name": custom.get("name"),
            "script": custom.get("script"),
        }

    def swagger(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        _, revision = self.revision(api_id, number, revision_id)
        try:
            return self.manager_api.get_revision_swagger(int(revision["id"]))
        except _PORT_FAILURES as exc:
            raise self._translate(exc) from exc
        except ManagerApiError as exc:
            # Resposta fora do contrato (ex.: swagger que não é JSON).
            logger.info("navigation.swagger.unexpected type=%s", type(exc).__name__)
            raise NavigationPlatformError(
                manager_failure_message(ManagerFailureKind.INTERNAL) or str(exc)
            ) from exc

    def export(
        self,
        api_id: int,
        number: Optional[int] = None,
        revision_id: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], MaterializationResult]:
        """Árvore canônica da revisão (o mesmo layout que `sen validate` lê)."""
        api, revision = self.revision(api_id, number, revision_id)
        return api, revision, materialize(api, revision)

    # ------------------------------------------------------------------ consumo e infra

    def _read(self, reader, api_id: Optional[int] = None):
        try:
            return reader()
        except _PORT_FAILURES as exc:
            raise self._translate(exc, api_id=api_id) from exc

    def environment(self, environment_id: int, *, show_values: bool = False) -> Dict[str, Any]:
        """Ambiente com gateway, mapas de variáveis e tudo que está no ar nele."""
        raw = self._read(lambda: self.manager_api.get_environment(environment_id))
        if not isinstance(raw, dict) or raw.get("id") is None:
            raise NavigationError(
                f"Ambiente {environment_id} não encontrado. Liste os existentes com: sen list environments"
            )
        return tenant.describe_environment(raw, show_values=show_values)

    def variables(
        self,
        environment_id: Optional[int] = None,
        *,
        key: Optional[str] = None,
        show_values: bool = False,
    ) -> list:
        """Variáveis de um ambiente, ou de todos; segredos mascarados por padrão."""
        if environment_id is not None:
            raw = self._read(lambda: self.manager_api.get_environment(environment_id))
            if not isinstance(raw, dict) or raw.get("id") is None:
                raise NavigationError(
                    f"Ambiente {environment_id} não encontrado. Liste os existentes com: sen list environments"
                )
            return tenant.environment_variables(raw, show_values=show_values, key=key)
        rows: list = []
        for env in self._read(self.manager_api.list_environments):
            if env.get("id") is None:
                continue
            raw = self._safe(lambda env_id=env["id"]: self.manager_api.get_environment(env_id), None)
            if isinstance(raw, dict):
                rows.extend(tenant.environment_variables(raw, show_values=show_values, key=key))
        return rows

    def apps(self, *, api_id: Optional[int] = None, query: Optional[str] = None) -> list:
        rows = self._read(self.manager_api.list_apps)
        documents = [
            tenant.describe_app(app)
            for app in rows
            if (api_id is None or tenant.app_subscribes(app, api_id))
            and tenant.matches_query((app.get("name"), app.get("developer")), query)
        ]
        documents.sort(key=lambda a: str(a["name"] or "").lower())
        return documents

    def app(self, app_id: int) -> Dict[str, Any]:
        raw = self._read(lambda: self.manager_api.get_app(app_id))
        if not raw:
            raise NavigationError(
                f"App {app_id} não encontrado. Liste os existentes com: sen list apps"
            )
        return tenant.describe_app(raw, detail=True)

    def plans(self, *, api_id: Optional[int] = None, query: Optional[str] = None) -> list:
        rows = self._read(self.manager_api.list_plans)
        documents = [
            tenant.describe_plan(plan)
            for plan in rows
            if (api_id is None or (plan.get("api") or {}).get("id") == api_id)
            and tenant.matches_query((plan.get("name"), (plan.get("api") or {}).get("name")), query)
        ]
        documents.sort(key=lambda p: (str((p["api"] or {}).get("name") or "").lower(), str(p["name"] or "").lower()))
        return documents

    def plan(self, plan_id: int) -> Dict[str, Any]:
        raw = self._read(lambda: self.manager_api.get_plan(plan_id))
        if not raw:
            raise NavigationError(
                f"Plano {plan_id} não encontrado. Liste os existentes com: sen list plans"
            )
        return tenant.describe_plan(raw, detail=True)

    def tokens(self, *, app_id: Optional[int] = None, api_id: Optional[int] = None) -> list:
        rows = self._read(self.manager_api.list_access_tokens)
        documents = [
            tenant.describe_token(t)
            for t in rows
            if tenant.token_touches(t, app_id=app_id, api_id=api_id)
        ]
        documents.sort(key=lambda t: str(t.get("creationDate") or ""), reverse=True)
        return documents

    def users(self, query: Optional[str] = None) -> list:
        rows = self._read(lambda: self.manager_api.list_users(query))
        documents = [tenant.describe_user(u) for u in rows]
        documents.sort(key=lambda u: str(u["username"] or "").lower())
        return documents

    def teams(self, query: Optional[str] = None) -> list:
        rows = self._read(lambda: self.manager_api.list_groups(query))
        documents = [tenant.describe_group(g) for g in rows]
        documents.sort(key=lambda g: str(g["name"] or "").lower())
        return documents

    def inbounds(self) -> list:
        return [tenant.describe_inbound(i) for i in self._read(self.manager_api.list_inbounds)]

    def gateway_pools(self) -> list:
        return [tenant.describe_gateway_pool(p) for p in self._read(self.manager_api.list_gateway_pools)]

    # ------------------------------------------------------------------ falhas

    @staticmethod
    def _translate(
        exc: ManagerApiTransportRejectedError | ManagerApiTransportUnavailableError,
        api_id: Optional[int] = None,
    ) -> NavigationError:
        kind = classify_manager_failure(exc)
        if kind is ManagerFailureKind.NOT_FOUND and api_id is not None:
            return NavigationApiNotFound(api_id)
        if kind is ManagerFailureKind.NOT_FOUND:
            kind = ManagerFailureKind.INTERNAL
        return NavigationPlatformError(manager_failure_message(kind) or str(exc))


# --------------------------------------------------------------------------- impacto


def _props(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        str(p.get("key")): p.get("value")
        for p in node.get("properties") or []
        if isinstance(p, dict) and p.get("key") is not None
    }


def _impact_document(root: Dict[str, Any]) -> Dict[str, Any]:
    """`rootNode` do tree-analysis → rotas (com destino) e planos → apps."""
    properties = _props(root)
    routes = []
    plans = []
    for child in root.get("children") or []:
        if not isinstance(child, dict):
            continue
        kind = str(child.get("type") or "").upper()
        if kind == "RESOURCE":
            methods = []
            for method in child.get("children") or []:
                if not isinstance(method, dict):
                    continue
                destination = next(
                    (
                        _props(d).get("Endpoint")
                        for d in method.get("children") or []
                        if isinstance(d, dict)
                        and str(d.get("type") or "").upper() == "DESTINATION"
                    ),
                    None,
                )
                methods.append(
                    {
                        "method": method.get("name"),
                        "operationId": method.get("operationId"),
                        "destination": destination,
                    }
                )
            routes.append({"path": child.get("name"), "methods": methods})
        elif kind == "PLAN":
            apps = []
            for app in child.get("children") or []:
                if not isinstance(app, dict):
                    continue
                app_props = _props(app)
                apps.append(
                    {
                        "name": app.get("name"),
                        "status": app_props.get("Status"),
                        "appId": app_props.get("appId"),
                    }
                )
            plans.append({"name": child.get("name"), "apps": apps})
    routes.sort(key=lambda r: str(r["path"]))
    return {
        "revisionNumber": properties.get("Revision"),
        "basePath": properties.get("Base Path"),
        "routes": routes,
        "plans": plans,
        "totals": {
            "routes": len(routes),
            "operations": sum(len(r["methods"]) for r in routes),
            "plans": len(plans),
            "apps": sum(len(p["apps"]) for p in plans),
        },
    }
