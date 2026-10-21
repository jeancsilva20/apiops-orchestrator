"""Testes da BORDA do `sen validate` (fase 0 da change `add-sen-validate`).

A cascata E1→E4 não existe ainda; o que se testa aqui é o contrato da borda:
gramática do comando, contrato JSON, exit codes e ausência de credencial na
saída. O serviço é injetado por `ctx.obj` — é a fronteira hexagonal que permite
testar a CLI sem rede.
"""

import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.services.api_access_guard import ApiAccessGuard
from apiops_orchestrator.domain.models.login_session_model import LoginSession
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    IdentidadeDivergenteError,
    ReguaInalcancavelError,
    ValidateError,
)
from apiops_orchestrator.domain.models.validate_view import (
    SCHEMA_SEN_VALIDATE_V1,
    SEVERIDADE_INFO,
    SEVERIDADE_WARNING,
    Achado,
    AtributoExigido,
    CompletenessResumo,
    GovernancaResultado,
    PublicacaoResultado,
    ReguaSnapshot,
    ValidateApi,
    ValidateRevision,
    ValidateView,
)

runner = CliRunner()


def _view(**overrides) -> ValidateView:
    base = dict(
        schema=SCHEMA_SEN_VALIDATE_V1,
        generated_at="2026-10-15T14:00:00Z",
        execution_mode="local",
        api=ValidateApi(
            manager_id=417,
            name="Servico de Letras 2.0.0",
            version="1.0.0",
            base_path="/letras/v2",
        ),
        revision=ValidateRevision(manager_id=9161, revision_number=1),
        regua=ReguaSnapshot(
            template_id=414,
            revision_number=3,
            flow_hash="a1b2c3d4",
            interceptors_count=8,
        ),
        achados=[
            Achado(SEVERIDADE_WARNING, "GET /health-check", "sobrescreve a regua"),
            Achado(SEVERIDADE_INFO, "resource Tarefas", "1 item alem da regua"),
        ],
        governanca=GovernancaResultado(
            workflow_id=500,
            stage_id=1402,
            required=[AtributoExigido(149, "My new"), AtributoExigido(231, "teste giroto")],
            missing=[],
            blocked=False,
        ),
        publicacao=PublicacaoResultado(attempted=True, accepted=True, verified=True),
        completeness=CompletenessResumo(
            score=42.0, gate_percent=70.0, suggestions=["Adicione exemplos"]
        ),
    )
    base.update(overrides)
    return ValidateView(**base)


class _ServicoFake:
    """Service fake: registra o que recebeu e devolve o que foi mandado devolver."""

    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro
        self.chamado_com = None

    def validate(self, repo_path, *, confirmar, progresso=None):
        self.chamado_com = {
            "repo_path": repo_path,
            "confirmar": confirmar,
            "progresso": progresso,
        }
        if self._erro is not None:
            raise self._erro
        # A borda narra as etapas por este callable; exercitá-lo aqui garante
        # que a barra de progresso não quebre a saída legível por máquina.
        if progresso is not None:
            progresso("Lendo o repositório")
        return self._resultado


def _ctx(servico):
    return {"validate_service_factory": lambda: servico}


# --- gramática do comando --------------------------------------------------


def test_comando_registrado_com_as_flags_do_contrato():
    resultado = runner.invoke(app, ["sen", "validate", "--help"])
    assert resultado.exit_code == 0
    for flag in ("--repo", "--output", "--verbose"):
        assert flag in resultado.output


def test_servico_ausente_no_contexto_encerra_com_1_sem_rede():
    resultado = runner.invoke(app, ["sen", "validate"], obj={})
    assert resultado.exit_code == 1
    assert "indisponível" in resultado.output


def test_confirmacao_e_injetada_pela_cli_e_nao_lida_pelo_service():
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert callable(servico.chamado_com["confirmar"])


def test_repo_default_e_o_diretorio_atual():
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert servico.chamado_com["repo_path"] is not None


# --- contrato JSON ---------------------------------------------------------


def test_json_conforme_ao_contrato_v1():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert resultado.exit_code == 0

    doc = json.loads(resultado.output)
    assert doc["schema"] == "apiops.sen-validate/v1"
    assert list(doc) == [
        "schema",
        "generatedAt",
        "api",
        "revision",
        "ruler",
        "findings",
        "governance",
        "publication",
        "completeness",
    ]


def test_json_da_esteira_traz_o_modo():
    servico = _ServicoFake(resultado=_view(execution_mode="pipeline"))
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))

    doc = json.loads(resultado.output)
    assert list(doc)[:3] == ["schema", "generatedAt", "executionMode"]
    assert doc["executionMode"] == "pipeline"


def test_json_carrega_o_snapshot_da_regua_para_a_esteira():
    """D-4/P-3: sem o snapshot, um achado deixa de ser reproduzível."""
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))

    ruler = json.loads(resultado.output)["ruler"]
    assert ruler["templateId"] == 414
    assert ruler["revisionNumber"] == 3
    assert ruler["flowHash"] == "a1b2c3d4"


def test_json_expoe_governanca_calculada_e_nao_texto_do_erro():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))

    gov = json.loads(resultado.output)["governance"]
    assert gov["workflowId"] == 500 and gov["stageId"] == 1402
    assert [r["attributeId"] for r in gov["required"]] == [149, 231]
    assert gov["missing"] == []


def test_publicacao_distingue_aceita_de_conferida():
    """W-8: HTTP 200 não é prova — `accepted` e `verified` são campos distintos."""
    servico = _ServicoFake(
        resultado=_view(
            publicacao=PublicacaoResultado(
                attempted=True,
                accepted=True,
                verified=False,
                divergences=["raiz: 8 enviados, 7 presentes"],
            )
        )
    )
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))

    pub = json.loads(resultado.output)["publication"]
    assert pub["accepted"] is True
    assert pub["verified"] is False
    assert pub["divergences"] == ["raiz: 8 enviados, 7 presentes"]


def test_yaml_serializa_a_mesma_arvore():
    servico = _ServicoFake(resultado=_view())
    r_json = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    r_yaml = runner.invoke(app, ["sen", "validate", "-o", "yaml"], obj=_ctx(servico))

    import yaml

    assert yaml.safe_load(r_yaml.output) == json.loads(r_json.output)


def test_nenhuma_saida_carrega_credencial():
    servico = _ServicoFake(resultado=_view())
    for formato in ("text", "json", "yaml"):
        resultado = runner.invoke(
            app, ["sen", "validate", "-o", formato], obj=_ctx(servico)
        )
        saida = resultado.output.lower()
        for proibido in ("authorization", "bearer", "client_secret", "token", "cookie"):
            assert proibido not in saida, f"{proibido!r} vazou no formato {formato}"


# --- exit codes ------------------------------------------------------------


def test_exit_0_com_achados_warning():
    """V-11 §3: divergência de régua informa, não bloqueia."""
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert resultado.exit_code == 0
    assert len(json.loads(resultado.output)["findings"]) == 2


def test_exit_0_com_completeness_abaixo_do_gate():
    """Decisão 2: completeness é informativa no validate; o gate trava em DEV+."""
    servico = _ServicoFake(
        resultado=_view(completeness=CompletenessResumo(score=12.0, gate_percent=70.0))
    )
    resultado = runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert resultado.exit_code == 0


@pytest.mark.parametrize(
    "erro",
    [
        IdentidadeDivergenteError("basePath", "/letras/v9", "/letras/v2", 417),
        ReguaInalcancavelError(999999, 404),
    ],
)
def test_exit_1_para_falha_tecnica(erro):
    servico = _ServicoFake(erro=erro)
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico))
    assert resultado.exit_code == 1
    assert "Erro:" in resultado.output


def test_exit_3_para_bloqueio_de_governanca():
    """Canal distinto: a esteira ramifica sem ler texto."""
    servico = _ServicoFake(
        erro=GovernanceBlockedError(500, 1402, [{"attributeId": 149, "name": "My new"}])
    )
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico))
    assert resultado.exit_code == 3
    assert "My new" in resultado.output


def test_erro_inesperado_nao_vaza_stack_e_encerra_com_1():
    servico = _ServicoFake(erro=RuntimeError("falha interna qualquer"))
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico))
    assert resultado.exit_code == 1
    assert "Traceback" not in resultado.output
    saida = " ".join(resultado.output.split())
    assert INTERNAL_ERROR_MESSAGE in saida
    assert "falha interna qualquer" not in saida


def test_cli_apenas_traduz_o_exit_code_que_o_erro_carrega():
    class ErroCustomizado(ValidateError):
        exit_code = 3

    servico = _ServicoFake(erro=ErroCustomizado("mensagem de negocio"))
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico))
    assert resultado.exit_code == 3
    assert "mensagem de negocio" in resultado.output


# --- sen diag structure (D-19: oculto, serve a teste, não ao uso diário) ----


def test_diag_structure_e_oculto_no_help():
    resultado = runner.invoke(app, ["sen", "--help"])
    assert "diag" not in resultado.output


def test_diag_structure_descreve_a_estrutura_sem_rede(tmp_path):
    (tmp_path / "api-basic-info.yaml").write_text(
        "apiVersion: api-management.sensedia.com/v1\nkind: ApiBasicInfo\nspec:\n  id: 1\n",
        encoding="utf-8",
    )
    (tmp_path / "all.yaml").write_text("destination:\n  url: https://x\n", encoding="utf-8")
    pasta = tmp_path / "resources" / "tarefas"
    pasta.mkdir(parents=True)
    (pasta / "resource.yaml").write_text('name: "Tarefas"\n', encoding="utf-8")
    (pasta / "get_tarefas.yaml").write_text("path: /tarefas\n", encoding="utf-8")

    resultado = runner.invoke(
        app, ["sen", "diag", "structure", "--repo", str(tmp_path), "-o", "json"]
    )
    assert resultado.exit_code == 0

    doc = json.loads(resultado.output)
    assert doc["completo"] is True
    assert doc["recursos"][0]["slug"] == "tarefas"
    assert doc["recursos"][0]["operacoes"][0]["metodo"] == "GET"


def test_diag_structure_aponta_o_arquivo_base_ausente(tmp_path):
    (tmp_path / "alll.yaml").write_text("destination:\n  url: https://x\n", encoding="utf-8")

    resultado = runner.invoke(
        app, ["sen", "diag", "structure", "--repo", str(tmp_path), "-o", "json"]
    )
    doc = json.loads(resultado.output)
    assert doc["completo"] is False
    assert "all.yaml" in doc["faltando"]
    assert "alll.yaml" in doc["ignorados"]


# --- sen diag draft: api-visibility -----------------------------------------


class _ManagerDoDraft:
    def __init__(self, visibility):
        self.visibility = visibility
        self.chamadas = []

    def get_api_by_id(self, api_id=None):
        self.chamadas.append("get_api_by_id")
        if self.visibility is None:
            raise ManagerApiTransportRejectedError(status_code=404, title="Not Found")
        return {
            "id": api_id,
            "name": "Servico de Letras",
            "revisions": [{"id": 9161, "revisionNumber": 1}],
            "visibility": self.visibility,
        }

    def get_revision(self, revision_id):
        self.chamadas.append("get_revision")
        return {"id": revision_id, "revisionNumber": 1, "interceptors": [], "resources": []}


def _diag_draft(tmp_path, visibility):
    (tmp_path / "api-basic-info.yaml").write_text(
        "apiVersion: api-management.sensedia.com/v1\nkind: ApiBasicInfo\nspec:\n  id: 417\n",
        encoding="utf-8",
    )
    (tmp_path / "all.yaml").write_text("destination:\n  url: https://x\n", encoding="utf-8")
    sessao = LoginSession.model_validate({
        "accessToken": "x", "tokenType": "Bearer", "expiresIn": 3600,
        "scope": "validate", "profile": "developer",
        "userName": "isaac.machado", "userEmail": "isaac.machado@sensedia.com",
        "userGroups": ["APIOps"],
    })
    manager = _ManagerDoDraft(visibility)
    fabrica = lambda: (  # noqa: E731
        manager, SimpleNamespace(modo_pipeline=False), ApiAccessGuard(sessao)
    )
    resultado = runner.invoke(
        app,
        ["sen", "diag", "draft", "--repo", str(tmp_path), "-o", "json"],
        obj={"manager_api_factory": fabrica},
    )
    return resultado, manager


@pytest.mark.parametrize(
    "visibility",
    [{"visibilityType": "GROUP", "groupVisibility": {"name": "Lab-tech"}}, None],
    ids=["invisivel", "inexistente"],
)
def test_diag_draft_de_api_invisivel_responde_como_inexistente(tmp_path, visibility):
    resultado, manager = _diag_draft(tmp_path, visibility)

    assert resultado.exit_code == 1
    assert "API 417 não encontrada ou sem permissão de acesso." in resultado.output
    assert manager.chamadas == ["get_api_by_id"]


def test_diag_draft_de_api_visivel_mostra_a_revisao(tmp_path):
    resultado, manager = _diag_draft(
        tmp_path, {"visibilityType": "GROUP", "groupVisibility": {"name": "APIOps"}}
    )

    assert resultado.exit_code == 0
    assert json.loads(resultado.output)["revision"]["managerId"] == 9161
    assert manager.chamadas == ["get_api_by_id", "get_revision"]


def test_json_sobrevive_a_valor_mais_longo_que_o_console(tmp_path):
    """Regressão: o `rich.Syntax` quebrava a linha na largura do console e
    produzia JSON inválido — justamente no formato que a esteira consome."""
    longa = tmp_path / ("pasta-com-nome-bem-longo-" * 4)
    longa.mkdir(parents=True)
    (longa / "api-basic-info.yaml").write_text("kind: ApiBasicInfo\n", encoding="utf-8")
    (longa / "all.yaml").write_text("destination:\n  url: https://x\n", encoding="utf-8")

    resultado = runner.invoke(
        app, ["sen", "diag", "structure", "--repo", str(longa), "-o", "json"]
    )
    doc = json.loads(resultado.output)
    assert doc["repo"] == str(longa)


# --- progresso e confirmação (apresentação) --------------------------------


def test_progresso_e_injetado_pela_cli():
    """A borda narra as etapas; o serviço só avisa em qual está."""
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "validate", "-o", "json"], obj=_ctx(servico))
    assert callable(servico.chamado_com["progresso"])


@pytest.mark.parametrize("formato", ["json", "yaml"])
def test_progresso_nao_contamina_saida_legivel_por_maquina(formato):
    """Regressão: a narração das etapas invalidava o documento.

    O `_ServicoFake` chama `progresso(...)` justamente para exercitar isto. Uma
    linha de progresso em stdout quebra o parse na esteira, e stderr também não
    salva — muita esteira captura `2>&1`. Em `-o json`/`-o yaml` o progresso
    simplesmente não existe.
    """
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(
        app, ["sen", "validate", "-o", formato], obj=_ctx(servico)
    )
    assert resultado.exit_code == 0
    assert "Lendo o repositório" not in resultado.output
    assert resultado.output.lstrip().startswith("{" if formato == "json" else "schema")


def test_confirmacao_explica_que_grava_um_rascunho_sem_deploy():
    """O texto anterior ("Publicar na revisão N") parecia anunciar um deploy.

    Quem roda `validate` quer validar; precisa entender que a gravação do
    rascunho é o meio, não uma promoção de ambiente.
    """
    capturado = {}

    class _ServicoQuePergunta(_ServicoFake):
        def validate(self, repo_path, *, confirmar, progresso=None):
            capturado["respondeu"] = confirmar(
                "Para validar a sua API, uma versão de rascunho será gravada no "
                "API Manager, na revisão 1 (id 9161).\n"
                "Nenhum ambiente recebe deploy, e nada é promovido."
            )
            return self._resultado

    servico = _ServicoQuePergunta(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico), input="n\n")

    assert "rascunho" in resultado.output
    assert "Nenhum ambiente recebe deploy" in resultado.output
    assert "Deseja prosseguir?" in resultado.output
    assert capturado["respondeu"] is False


@pytest.mark.parametrize(
    "entrada",
    [
        "",                # fim da entrada sem resposta (pipe vazio, Ctrl+D)
        "﻿y\n",       # resposta inválida e depois fim da entrada (PowerShell 5.1)
    ],
)
def test_cancelar_o_prompt_interrompe_com_130_e_sem_relatorio(entrada):
    """Ctrl+C / fim da entrada não é um "não": interrompe o comando.

    O serviço não chega a devolver nada, nenhum relatório é exibido e o
    código de saída distingue "cancelado" (130) de "recusado" (0) e de falha (1).
    """
    class _ServicoQuePergunta(_ServicoFake):
        def validate(self, repo_path, *, confirmar, progresso=None):
            confirmar("Uma versão de rascunho será gravada.")
            raise AssertionError("o comando deveria ter sido interrompido no prompt")

    servico = _ServicoQuePergunta(resultado=_view())
    resultado = runner.invoke(app, ["sen", "validate"], obj=_ctx(servico), input=entrada)
    saida = " ".join(resultado.output.split())

    assert resultado.exit_code == 130
    assert "Validação cancelada. Nada foi gravado." in saida
    assert "Conformidade" not in saida
    assert INTERNAL_ERROR_MESSAGE not in saida


def test_responder_n_encerra_sem_relatorio():
    """Sem a cascata completa não há relatório parcial — só o desfecho."""
    view = _view(publicacao=PublicacaoResultado(attempted=False))
    resultado = runner.invoke(
        app, ["sen", "validate"], obj=_ctx(_ServicoFake(resultado=view))
    )
    saida = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "Validação cancelada. Nada foi gravado." in saida
    assert "Conformidade" not in saida and "Validação  " not in saida
    assert "sobrescreve a regua" not in saida
