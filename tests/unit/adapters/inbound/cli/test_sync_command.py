"""Borda do `sen sync`: gramática, exit codes, documento e ausência de token na saída."""

from pathlib import Path
import json

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import (
    _difference_rows,
    _interceptor_list_text,
    app,
)
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
)
from apiops_orchestrator.application.exceptions.sync_exceptions import (
    ApiNotFoundError,
    RevisionNotFoundError,
    SyncError,
    WriteFailedError,
)
from apiops_orchestrator.domain.models.sync_view import (
    MODE_CHECK,
    MODE_LOAD,
    SCHEMA_SEN_SYNC_V1,
    SyncView,
)
from apiops_orchestrator.domain.models.interceptor_model import CustomInterceptor
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.services.revision_diff import ABSENT, Difference

runner = CliRunner()


def _view(mode=MODE_LOAD, **overrides):
    base = dict(
        schema=SCHEMA_SEN_SYNC_V1,
        generated_at="2026-11-13T12:00:00Z",
        mode=mode,
        api=ValidateApi(manager_id=425, name="API Lab", version="1.0.0", base_path="/lab/v1"),
        revision=ValidateRevision(manager_id=9999, revision_number=4),
        files=["all.yaml", "api-basic-info.yaml", "resources/a/get_a.yaml", "resources/a/resource.yaml"],
        resources=1,
        operations=1,
        warnings=["recurso Quebra: Log próprio repete um herdado idêntico"],
    )
    base.update(overrides)
    return SyncView(**base)


class _ServiceFake:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []
        self.repo_paths = []
        self.templates = []

    def _run(self, name, repo_path, *, api_id, revision_number, template=None, progress=None):
        self.calls.append((name, api_id, revision_number))
        self.templates.append(template)
        self.repo_paths.append(repo_path)
        if progress is not None:
            progress("Consultando a API no Manager")
        if self._error is not None:
            raise self._error
        return self._result

    def sync(self, repo_path, **kw):
        return self._run("sync", repo_path, **kw)

    def check(self, repo_path, **kw):
        return self._run("check", repo_path, **kw)


def _ctx(service):
    return {"sync_service_factory": lambda: service}


def test_carga_com_id_e_revisao():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "--id", "425", "--revision", "4"], obj=_ctx(service))
    assert result.exit_code == 0, result.output
    assert service.calls == [("sync", 425, 4)]
    assert "API Lab" in result.output and "API Importada" in result.output
    # The text shows the folder and the counts, not the file list nor a next step.
    assert "Pasta" in result.output and "4 arquivos" in result.output
    assert "resources/a/get_a.yaml" not in result.output
    assert "Próximo passo" not in result.output


def test_sem_id_e_erro_de_uso_sem_chamar_o_servico():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "-r", "2"], obj=_ctx(service))
    assert result.exit_code == 2
    assert service.calls == []


def test_revision_e_obrigatoria():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "--id", "425"], obj=_ctx(service))
    assert result.exit_code == 2 and service.calls == []


def test_saida_json_so_com_o_documento():
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "--revision", "4", "-o", "json"], obj=_ctx(_ServiceFake(_view()))
    )
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["schema"] == SCHEMA_SEN_SYNC_V1 and document["mode"] == "load"
    assert document["counts"] == {"files": 4, "resources": 1, "operations": 1}


def test_check_em_sincronia_sai_zero():
    service = _ServiceFake(_view(MODE_CHECK, files=[]))
    result = runner.invoke(app, ["sen", "sync", "--id", "425", "--check", "--revision", "2"], obj=_ctx(service))
    assert result.exit_code == 0, result.output
    assert service.calls == [("check", 425, 2)]
    assert "iguais" in result.output


def test_check_com_diferenca_sai_oito_e_lista_arquivo_campo_e_valores():
    diff = Difference("resources/a/get_a.yaml", "destination.timeout", "30", "99")
    service = _ServiceFake(_view(MODE_CHECK, files=[], differences=[diff]))
    result = runner.invoke(app, ["sen", "sync", "--id", "425", "--check", "-r", "2"], obj=_ctx(service))
    assert result.exit_code == 8
    for piece in ("resources/a/get_a.yaml", "destination.timeout", "30", "99"):
        assert piece in result.output


def test_check_com_diferenca_em_json_tambem_sai_oito():
    diff = Difference("all.yaml", "destination.timeout", "30", "45")
    service = _ServiceFake(_view(MODE_CHECK, files=[], differences=[diff]))
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "--check", "-r", "4", "-o", "json"], obj=_ctx(service)
    )
    assert result.exit_code == 8
    document = json.loads(result.stdout)
    assert document["inSync"] is False and document["differences"][0]["field"] == "destination.timeout"


@pytest.mark.parametrize(
    "error, code",
    [
        (SyncError("x"), 1),
        (ApiNotFoundError(425), 3),
        (RevisionNotFoundError(425, 4, [1, 2]), 4),
        (WriteFailedError("caminho longo", "resources/x.yaml"), 6),
        (AuthenticationRejectedError("Sessão inválida ou ausente: faça `sen login`."), 2),
    ],
)
def test_exit_codes_por_categoria(error, code):
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "--revision", "4"], obj=_ctx(_ServiceFake(error=error))
    )
    assert result.exit_code == code, result.output
    assert "Erro:" in result.output


def test_factory_ausente():
    result = runner.invoke(app, ["sen", "sync", "--id", "425", "--revision", "4"], obj={})
    assert result.exit_code == 1 and "indisponível" in result.output


def test_nenhum_token_na_saida():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "--id", "425", "-r", "4"], obj=_ctx(service))
    assert "Bearer" not in result.output and "eyJ" not in result.output


def test_repo_aponta_a_pasta_da_carga(tmp_path):
    service = _ServiceFake(_view())
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "-r", "4", "--repo", str(tmp_path)], obj=_ctx(service)
    )
    assert result.exit_code == 0, result.output
    assert service.repo_paths == [tmp_path]


def test_sem_repo_usa_o_diretorio_atual(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = _ServiceFake(_view())
    runner.invoke(app, ["sen", "sync", "--id", "425", "-r", "4"], obj=_ctx(service))
    assert service.repo_paths == [Path.cwd()]


def test_template_vai_ao_servico_na_carga():
    service = _ServiceFake(_view())
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "-r", "4", "--template", "414"], obj=_ctx(service)
    )
    assert result.exit_code == 0, result.output
    assert service.templates == [414]


def test_template_com_check_e_erro_de_uso():
    service = _ServiceFake(_view(MODE_CHECK, files=[]))
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "-r", "4", "--check", "--template", "414"], obj=_ctx(service)
    )
    assert result.exit_code == 2
    assert "--template" in result.output and service.calls == []


# --- tabela das diferenças --------------------------------------------------------------

F = "resources/health-check/get_health-check.yaml"
CUSTOMS = dict(
    custom_interceptors=[
        CustomInterceptor(id=32, name="Release Notes"),
        CustomInterceptor(id=125, name="Release notes"),
    ],
    outside_catalog=[125],
)


def _check_view(differences, **overrides):
    return _view(MODE_CHECK, files=[], differences=differences, **overrides)


def _rows(differences, **overrides):
    groups = _difference_rows(differences, _check_view(differences, **overrides))
    return [[tuple(cell.plain for cell in row) for row in group] for group in groups]


def test_interceptor_diferente_mostra_as_duas_listas_numeradas_com_o_nome_do_custom():
    repo = [{"type": "Custom", "id": 32}, {"type": "Log"}, {"type": "Mock", "content": {"status": 200}}]
    manager = [{"type": "Custom", "id": 125}, {"type": "Log"}, {"type": "Rate limit"}, {"type": "Payload size"}]
    diff = Difference(F, "interceptors_request", repo, manager)

    assert _rows([diff], **CUSTOMS) == [[(
        "interceptors_request",
        "1. Custom 32 (Release Notes)\n2. Log\n3. Mock",
        "1. Custom 125 (Release notes, fora do catálogo)\n2. Log\n3. Rate limit\n4. Payload size",
    )]]


def test_na_lista_inteira_so_as_posicoes_diferentes_se_destacam():
    repo = [{"type": "Log"}, {"type": "Mock"}]
    manager = [{"type": "Log"}, {"type": "Rate limit"}, {"type": "Log"}]
    text = _interceptor_list_text(manager, repo, _check_view([]))
    styles = {text.plain[s.start:s.end]: str(s.style) for s in text.spans}
    assert styles == {"1. Log": "grey53", "2. Rate limit": "yellow", "3. Log": "yellow"}


def test_item_alem_do_fim_da_outra_lista_vem_numerado():
    diff = Difference(F, "interceptors_request[6]", {"type": "Log"}, ABSENT)
    assert _rows([diff]) == [[("interceptors_request", "7. Log", "<ausente>")]]


def test_campos_do_mesmo_interceptor_ficam_agrupados_sob_o_titulo():
    diffs = [
        Difference(F, "interceptors_request[2].content.quota", 1000, 500, "Rate limit"),
        Difference(F, "interceptors_request[2].content.interval", "SECOND", "MINUTE", "Rate limit"),
        Difference(F, "interceptors_request[4].content.maxSize", 2048, ABSENT, "Payload size"),
    ]
    assert _rows(diffs) == [
        [
            ("interceptors_request", "3. Rate limit", "3. Rate limit"),
            ("  quota", "1000", "500"),
            ("  interval", "SECOND", "MINUTE"),
        ],
        [
            ("interceptors_request", "5. Payload size", "5. Payload size"),
            ("  maxSize", "2048", "<ausente>"),
        ],
    ]


def test_texto_de_varias_linhas_mostra_so_as_linhas_de_cada_lado():
    changed = Difference(F, "interceptors_request[7].content.list", "10.0.0.1\n10.0.0.2\n8.8.8.8",
                         "10.0.0.1\n8.8.8.8\n10.0.0.3", "IP filtering")
    reordered = Difference(F, "interceptors_request[8].content.list", "a\nb", "b\na", "IP filtering")
    rows = _rows([changed, reordered])
    assert rows[0][1] == ("  list\n    (só as linhas que diferem)", "10.0.0.2", "10.0.0.3")
    assert rows[1][1] == ("  list\n    (mesmas linhas, em outra ordem)", "-", "-")


def test_valores_simples_e_compostos_como_o_yaml_le():
    diffs = [
        Difference(F, "description", "", "Retorna o status"),
        Difference(F, "inherit", False, True),
        Difference(F, "headerKey", ABSENT, None),
        Difference(F, "responses.201.content", {"application/json": {"schema": {"$ref": "#/x"}}}, ABSENT),
    ]
    assert [group[0] for group in _rows(diffs)] == [
        ("description", '""', "Retorna o status"),
        ("inherit", "false", "true"),
        ("headerKey", "<ausente>", "null"),
        ("responses.201.content", "application/json:\n  schema:\n    $ref: '#/x'", "<ausente>"),
    ]


def test_check_mostra_tabela_por_arquivo_e_arquivo_de_um_lado_so_em_linha():
    diffs = [
        Difference("resources/a/get_a.yaml", "inherit", False, True),
        Difference("resources/x/resource.yaml", None, "arquivo presente", ABSENT),
        Difference("resources/y/resource.yaml", None, ABSENT, "arquivo presente"),
    ]
    service = _ServiceFake(_check_view(diffs))
    result = runner.invoke(
        app, ["sen", "sync", "--id", "425", "--check", "-r", "2"], obj=_ctx(service), env={"COLUMNS": "200"}
    )
    assert result.exit_code == 8
    for piece in ("Diferenças  3", "Campo", "Repositório", "Manager", "resources/a/get_a.yaml",
                  "resources/x/resource.yaml  só no repositório", "resources/y/resource.yaml  só no Manager"):
        assert piece in result.output, piece
