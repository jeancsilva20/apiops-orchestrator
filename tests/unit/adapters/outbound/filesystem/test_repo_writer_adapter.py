"""Escrita atômica da área gerenciada pelo `RepoWriterAdapter`."""

import pytest

from apiops_orchestrator.adapters.outbound.filesystem.repo_writer_adapter import (
    STAGING_FOLDER,
    RepoWriterAdapter,
)
from apiops_orchestrator.domain.ports.repo_writer_port import RepoWriteError
from apiops_orchestrator.domain.services.repo_materializer import MaterializedFile

TREE = [
    MaterializedFile("api-basic-info.yaml", "spec:\n  id: 1\n"),
    MaterializedFile("all.yaml", "destination:\n  url: x\n"),
    MaterializedFile("resources/a/resource.yaml", "name: A\n"),
    MaterializedFile("resources/a/get_a.yaml", "path: /a\n"),
]


def _read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def test_grava_a_arvore_e_remove_o_temporario(tmp_path):
    RepoWriterAdapter(max_path=None).write_managed_area(tmp_path, TREE)
    assert _read(tmp_path, "resources/a/get_a.yaml") == "path: /a\n"
    assert _read(tmp_path, "all.yaml") == "destination:\n  url: x\n"
    assert not (tmp_path / STAGING_FOLDER).exists()


def test_substitui_a_area_gerenciada_por_inteiro(tmp_path):
    stale = tmp_path / "resources" / "velho" / "resource.yaml"
    stale.parent.mkdir(parents=True)
    stale.write_text("name: Velho\n", encoding="utf-8")
    (tmp_path / "all.yaml").write_text("antigo\n", encoding="utf-8")

    RepoWriterAdapter(max_path=None).write_managed_area(tmp_path, TREE)

    assert not stale.exists()
    assert _read(tmp_path, "all.yaml") == "destination:\n  url: x\n"


def test_nao_toca_o_que_esta_fora_da_area_gerenciada(tmp_path):
    wrapper = tmp_path / ".github" / "workflows" / "ci.yml"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("on: push\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("readme\n", encoding="utf-8")

    RepoWriterAdapter(max_path=None).write_managed_area(tmp_path, TREE)

    assert _read(tmp_path, ".github/workflows/ci.yml") == "on: push\n"
    assert _read(tmp_path, "README.md") == "readme\n"


def test_caminho_longo_falha_antes_de_tocar_o_disco(tmp_path):
    (tmp_path / "all.yaml").write_text("antigo\n", encoding="utf-8")
    long_tree = TREE + [MaterializedFile("resources/a/" + "x" * 120 + ".yaml", "path: /x\n")]

    with pytest.raises(RepoWriteError) as info:
        RepoWriterAdapter(max_path=len(str(tmp_path)) + 60).write_managed_area(
            tmp_path, long_tree
        )

    assert "acima do limite" in info.value.reason
    assert info.value.path.startswith("resources/a/xxx")
    assert _read(tmp_path, "all.yaml") == "antigo\n"
    assert not (tmp_path / "resources").exists()
    assert not (tmp_path / STAGING_FOLDER).exists()


def test_falha_de_escrita_vira_sinal_do_port_e_limpa_o_temporario(tmp_path, monkeypatch):
    import shutil

    def boom(*_a, **_k):
        raise PermissionError(13, "Permission denied", str(tmp_path / "all.yaml"))

    monkeypatch.setattr(shutil, "move", boom)
    with pytest.raises(RepoWriteError) as info:
        RepoWriterAdapter(max_path=None).write_managed_area(tmp_path, TREE)
    assert info.value.reason == "sem permissão de escrita"
    assert info.value.path == "all.yaml"
    assert not (tmp_path / STAGING_FOLDER).exists()
