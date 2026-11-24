"""`sen export api` (escreve em disco) e `sen reveal variable` (desmascara de proposito).

Recortado de `test_navigation_commands.py`, que chegou a 916 linhas cobrindo 36
comandos. Os corpos sao os mesmos; o que mudou foi a casa e a origem dos
helpers, que vieram para `tests/sen_support/`.
"""

import json
from unittest.mock import MagicMock


from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationRevisionNotFound,
)
from apiops_orchestrator.domain.services.repo_materializer import (
    MaterializationResult,
    MaterializedFile,
)
from sen_support.cli_invoke import invocar_navegacao as _invoke


# --------------------------------------------------------------------------- export api


def _export_result():
    return (
        {"id": 400, "name": "Orchestrator Auth API", "version": "1.0.1", "basePath": "/orq-auth/v1",
         "revisions": [], "environments": []},
        {"id": 8948, "revisionNumber": 4, "lifeCycle": "DRAFT"},
        MaterializationResult(
            files=[
                MaterializedFile("api-basic-info.yaml", "kind: ApiBasicInfo\n"),
                MaterializedFile("resources/token/resource.yaml", "name: Token\n"),
            ],
            warnings=["um aviso"],
        ),
    )


def test_export_prints_files_to_stdout_without_dir():
    service = MagicMock()
    service.export.return_value = _export_result()

    result = _invoke(["export", "api", "--id", "400"], service)

    assert result.exit_code == 0, result.output
    out = result.output
    assert "# ==> api-basic-info.yaml" in out and "kind: ApiBasicInfo" in out
    assert "# ==> resources/token/resource.yaml" in out
    assert "AVISO" in out and "um aviso" in out

    result = _invoke(["export", "api", "--id", "400", "-o", "json"], service)
    document = json.loads(result.output)
    assert document["files"][1] == {"path": "resources/token/resource.yaml", "text": "name: Token\n"}
    assert document["revision"]["number"] == 4


def test_export_writes_tree_into_dir_and_refuses_overwrite(tmp_path):
    service = MagicMock()
    service.export.return_value = _export_result()
    target = tmp_path / "repo"

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target)], service)

    assert result.exit_code == 0, result.output
    assert (target / "api-basic-info.yaml").read_text(encoding="utf-8") == "kind: ApiBasicInfo\n"
    assert (target / "resources" / "token" / "resource.yaml").exists()

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target)], service)
    assert result.exit_code == 1
    assert "--force" in result.output

    result = _invoke(["export", "api", "--id", "400", "--dir", str(target), "--force", "-o", "json"], service)
    assert result.exit_code == 0
    assert [f["path"] for f in json.loads(result.output)["files"]] == [
        "api-basic-info.yaml",
        "resources/token/resource.yaml",
    ]
# --------------------------------------------------------------------------- sen reveal variable


def test_reveal_variable_text_raw_and_errors():
    service = MagicMock()
    service.reveal_variable.return_value = {
        "environmentId": 7, "environmentName": "DEV", "map": "Proxy", "mapId": 1,
        "key": "basicAuthManager", "value": "Basic abc", "variableType": "DEFAULT", "sensitive": True,
    }
    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "--map", "Proxy"], service)
    assert result.exit_code == 0, result.output
    out = " ".join(result.output.split())
    assert "basicAuthManager" in out and "Basic abc" in out and "sensível" in out
    service.reveal_variable.assert_called_once_with(7, "basicAuthManager", "Proxy")

    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "--raw"], service)
    assert result.exit_code == 0 and result.output == "Basic abc\n"

    result = _invoke(["reveal", "variable", "--env", "7", "--key", "basicAuthManager", "-o", "json"], service)
    assert json.loads(result.output)["value"] == "Basic abc"

    service.reveal_variable.side_effect = NavigationRevisionNotFound(1, "x", [])
    assert _invoke(["reveal", "variable", "--env", "7", "--key", "k"], service).exit_code == 1

    assert _invoke(["reveal", "variable", "--env", "7"], service).exit_code != 0  # --key obrigatório
    assert _invoke(["reveal"], service).exit_code != 0
