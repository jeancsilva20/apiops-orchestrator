import pytest
from pathlib import Path
from apiops_orchestrator.application.services.repo_validator import RepoValidator

RULES = {
    "Templates": ["basic info.yaml", "default interceptors.yaml"],
    "Resources": ["teste.yaml"],
    "Env-Variables": [],
}


@pytest.fixture
def repo_validator():
    return RepoValidator(rules=RULES)


def create_folder_structure(base_path: Path, structure: dict):
    for name, content in structure.items():
        path = base_path / name
        if isinstance(content, dict):
            path.mkdir()
            create_folder_structure(path, content)
        else:
            path.touch()


def test_validate_artifact_struct_success(repo_validator, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    artifacts_path = repo_path / "artifacts"
    artifacts_path.mkdir()

    for folder, required_files in RULES.items():
        folder_path = artifacts_path / folder
        folder_path.mkdir()
        for filename in required_files:
            (folder_path / filename).touch()

    try:
        repo_validator.validate_artifact_struct(str(repo_path))
    except ValueError:
        pytest.fail("validate_artifact_struct raised ValueError unexpectedly!")


def test_validate_repo_not_found(repo_validator):
    non_existent_repo_path = "non_existent_repo"

    with pytest.raises(
        ValueError,
        match=f"Pasta do repositório não encontrada: {non_existent_repo_path}",
    ):
        repo_validator.validate_artifact_struct(non_existent_repo_path)


def test_validate_artifacts_folder_not_found(repo_validator, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    with pytest.raises(ValueError) as excinfo:
        repo_validator.validate_artifact_struct(str(repo_path))
    assert f"Pasta 'artifacts' não encontrada dentro de {repo_path}" in str(
        excinfo.value
    )


def test_validate_missing_required_folder(repo_validator, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    artifacts_path = repo_path / "artifacts"
    artifacts_path.mkdir()

    # Dynamically select a folder to skip
    folder_to_skip = list(RULES.keys())[0]

    # Create all folders except the one selected to be skipped
    for folder, required_files in RULES.items():
        if folder != folder_to_skip:
            folder_path = artifacts_path / folder
            folder_path.mkdir()
            for filename in required_files:
                (folder_path / filename).touch()

    with pytest.raises(ValueError) as excinfo:
        repo_validator.validate_artifact_struct(str(repo_path))

    assert "Pasta obrigatória ausente" in str(excinfo.value)
    assert str(artifacts_path / folder_to_skip) in str(excinfo.value)


def test_validate_missing_required_file(repo_validator, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    artifacts_path = repo_path / "artifacts"
    artifacts_path.mkdir()

    # Find a folder with files and select one file to skip
    folder_with_missing_file = ""
    file_to_skip = ""
    for f, files in RULES.items():
        if files:
            folder_with_missing_file = f
            file_to_skip = files[-1]  # Select the last file
            break

    if not file_to_skip:
        pytest.skip("No files found in RULES to test missing file scenario")

    for folder, required_files in RULES.items():
        folder_path = artifacts_path / folder
        folder_path.mkdir()
        for filename in required_files:
            if folder == folder_with_missing_file and filename == file_to_skip:
                continue  # Skip this file
            (folder_path / filename).touch()

    with pytest.raises(ValueError) as excinfo:
        repo_validator.validate_artifact_struct(str(repo_path))

    assert "Arquivo obrigatório ausente" in str(excinfo.value)
    assert str(artifacts_path / folder_with_missing_file / file_to_skip) in str(
        excinfo.value
    )


def test_validate_multiple_errors(repo_validator, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    artifacts_path = repo_path / "artifacts"
    artifacts_path.mkdir()

    # Dynamically select what to miss
    if len(RULES.keys()) < 3:
        pytest.skip("RULES does not have enough folders to test multiple errors")

    folder_for_missing_file = ""
    file_to_skip = ""
    for f in list(RULES.keys()):
        if RULES[f]:
            folder_for_missing_file = f
            file_to_skip = RULES[f][0]
            break

    if not folder_for_missing_file:
        pytest.skip("No folder with files found to test missing file scenario")

    folders_to_skip = [f for f in RULES.keys() if f != folder_for_missing_file][:2]
    if len(folders_to_skip) < 2:
        pytest.skip("Not enough other folders to skip for multiple error test")

    # Create structure with missing parts
    for folder, required_files in RULES.items():
        if folder in folders_to_skip:
            continue  # Skip creating this folder

        folder_path = artifacts_path / folder
        folder_path.mkdir()

        for filename in required_files:
            if folder == folder_for_missing_file and filename == file_to_skip:
                continue  # Skip creating this file
            (folder_path / filename).touch()

    with pytest.raises(ValueError) as excinfo:
        repo_validator.validate_artifact_struct(str(repo_path))

    error_message = str(excinfo.value)
    assert "Validação do repositório falhou:" in error_message
    assert (
        f"Arquivo obrigatório ausente: {artifacts_path / folder_for_missing_file / file_to_skip}"
        in error_message
    )
    for skipped_folder in folders_to_skip:
        assert (
            f"Pasta obrigatória ausente: {artifacts_path / skipped_folder}"
            in error_message
        )
