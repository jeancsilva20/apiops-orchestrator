import pytest
import yaml
from pathlib import Path
from apiops_orchestrator.application.services.new_structure_repository_reader import NewStructureRepositoryReader
from apiops_orchestrator.config.settings import Settings

@pytest.fixture
def settings():
    return Settings(
        HOST="localhost",
        AUTHORIZATION="auth",
        OAUTH_CLIENT_ID="id",
        OAUTH_CLIENT_SECRET="secret",
        REQUEST_TIMEOUT=30,
        API_ID="123"
    )

@pytest.fixture
def reader(settings):
    return NewStructureRepositoryReader(settings)

def create_fake_repo(repo_path: Path):
    # api-info
    api_info_dir = repo_path / "api-info"
    api_info_dir.mkdir()
    with open(api_info_dir / "api-basic-info.yaml", "w") as f:
        yaml.dump({
            "apiVersion": "v1",
            "kind": "ApiBasicInfo",
            "spec": {
                "id": 231,
                "name": "API CEP",
                "version": "v1",
                "basePath": "/api.cep/v1",
                "creationDate": "2026-01-18",
                "lastUpdate": "2026-01-18"
            }
        }, f)

    # revisions
    revisions_dir = repo_path / "revisions"
    revisions_dir.mkdir()
    
    # Revision 1
    rev1 = revisions_dir / "1"
    rev1.mkdir()
    (rev1 / "revision.yaml").touch()
    with open(rev1 / "revision-flow.yaml", "w") as f:
        yaml.dump({
            "apiVersion": "v1",
            "kind": "RevisionFlow",
            "spec": {
                "interceptors": [{"position": 1, "type": "Log"}]
            }
        }, f)
    
    # Revision 2
    rev2 = revisions_dir / "2"
    rev2.mkdir()
    (rev2 / "revision.yaml").touch()
    with open(rev2 / "revision-flow.yaml", "w") as f:
        yaml.dump({
            "apiVersion": "v1",
            "kind": "RevisionFlow",
            "spec": {
                "interceptors": [{"position": 1, "type": "Custom", "content": 8}]
            }
        }, f)
    
    # Resources for Revision 2
    resources_dir = rev2 / "resources"
    resources_dir.mkdir()
    
    cep_dir = resources_dir / "cep"
    cep_dir.mkdir()
    with open(cep_dir / "resource.yaml", "w") as f:
        yaml.dump({
            "apiVersion": "v1",
            "kind": "Resource",
            "items": [{
                "name": "CEP",
                "description": "Recurso CEP"
            }]
        }, f)
    
    ops_dir = cep_dir / "operations"
    ops_dir.mkdir()
    with open(ops_dir / "get_cep.yaml", "w") as f:
        yaml.dump({
            "apiVersion": "v1",
            "kind": "ApiOperations",
            "spec": {
                "operation": [{
                    "method": "GET",
                    "path": "/cep/{cep}"
                }]
            }
        }, f)

def test_get_latest_revision(reader, tmp_path):
    create_fake_repo(tmp_path)
    assert reader._get_latest_revision(tmp_path) == 2

def test_load_normalized_documents(reader, tmp_path):
    create_fake_repo(tmp_path)
    docs = reader.load_normalized_documents(tmp_path)
    
    # Check ApiBasicInfo
    api_info = next(d for d in docs if d["kind"] == "ApiBasicInfo")
    assert api_info["spec"]["api"]["name"] == "API CEP"
    assert "id" not in api_info["spec"]["api"]
    assert "creationDate" not in api_info["spec"]["api"]
    assert "lastUpdate" not in api_info["spec"]["api"]
    
    # Check Interceptors
    interceptors = next(d for d in docs if d["kind"] == "Interceptors")
    assert interceptors["spec"]["interceptors"][0]["type"] == "Custom"
    
    # Check ResourcesList
    res_list = next(d for d in docs if d["kind"] == "ResourcesList")
    assert len(res_list["items"]) == 1
    assert res_list["items"][0]["name"] == "CEP"
    assert res_list["items"][0]["operations"][0]["file"] == "cep/get_cep.yaml"
    
    # Check ApiOperations
    ops = [d for d in docs if d["kind"] == "ApiOperations"]
    assert len(ops) == 1
    assert ops[0]["metadata"]["fileName"] == "cep/get_cep.yaml"

def test_load_specific_revision(reader, tmp_path):
    create_fake_repo(tmp_path)
    docs = reader.load_normalized_documents(tmp_path, revision_number=1)
    
    interceptors = next(d for d in docs if d["kind"] == "Interceptors")
    assert interceptors["spec"]["interceptors"][0]["type"] == "Log"
