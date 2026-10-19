"""Carga do repositório pelo `RevisionWriter`: o que aborta antes de rede."""

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    RotaDuplicadaError,
)
from apiops_orchestrator.application.services.revision_writer import RevisionWriter


class _ManagerQueNaoPodeSerChamado:
    def __getattr__(self, nome):
        raise AssertionError(f"a carga não deveria acessar o Manager ({nome})")


def _repo(tmp_path, arquivos):
    (tmp_path / "api-basic-info.yaml").write_text("spec: {}\n", encoding="utf-8")
    (tmp_path / "all.yaml").write_text("inherit: false\n", encoding="utf-8")
    for caminho, conteudo in arquivos.items():
        destino = tmp_path / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
    return tmp_path


def _writer():
    return RevisionWriter(
        _ManagerQueNaoPodeSerChamado(), LocalFileImporterAdapter(), comando="validate"
    )


def test_rota_em_duas_pastas_aborta_nomeando_os_dois_arquivos(tmp_path):
    """I-6: a rota é a identidade da operação; repetida, a ligação com o
    Manager fica ambígua."""
    repo = _repo(tmp_path, {
        "resources/tarefas/resource.yaml": 'name: "Tarefas"\n',
        "resources/tarefas/get_tarefas.yaml": "path: /tarefas\n",
        "resources/tarefas 2/resource.yaml": 'name: "Tarefas"\n',
        "resources/tarefas 2/get_tarefas.yaml": "path: /tarefas\n",
    })

    with pytest.raises(RotaDuplicadaError) as capturado:
        _writer().carregar(repo)

    assert capturado.value.exit_code == 1
    assert capturado.value.message == (
        "A rota abaixo está declarada em mais de um arquivo:\n\n"
        "`GET /tarefas`, declarada em:\n"
        "  - resources/tarefas/get_tarefas.yaml\n"
        "  - resources/tarefas 2/get_tarefas.yaml\n\n"
        "Cada rota pertence a um único recurso. Mantenha um só arquivo para cada "
        "rota. O comando parou antes de acessar o Manager."
    )


def test_mesmo_path_com_metodos_diferentes_nao_e_duplicado(tmp_path):
    repo = _repo(tmp_path, {
        "resources/tarefas/resource.yaml": 'name: "Tarefas"\n',
        "resources/tarefas/get_tarefas.yaml": "path: /tarefas\n",
        "resources/tarefas/post_tarefas.yaml": "path: /tarefas\n",
    })
    assert _writer().carregar(repo).total_operacoes == 2


def test_nomes_repetidos_com_rotas_distintas_carregam(tmp_path):
    """Homônimos são válidos — a 409 rev1 tem dois `Letras`."""
    repo = _repo(tmp_path, {
        "resources/letras-a/resource.yaml": 'name: "Letras"\n',
        "resources/letras-a/get_letras_{id}.yaml": "path: /letras/{id}\n",
        "resources/letras-b/resource.yaml": 'name: "Letras"\n',
        "resources/letras-b/post_tarefas_{id}_letras.yaml": "path: /tarefas/{id}/letras\n",
    })
    assert len(_writer().carregar(repo).recursos) == 2
