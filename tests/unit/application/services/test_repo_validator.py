import pytest
from pathlib import Path
from apiops_orchestrator.application.services.repo_validator import RepoValidator

RULES = {
    "Templates": ["api-basic-info.yaml", "default-interceptors.yaml"],
    "Resources": ["resources.yaml"],
    "Env-Variables": [],
}


@pytest.fixture
def repo_validator():
    return RepoValidator(rules=RULES)


@pytest.fixture
def new_repo_validator():
    return RepoValidator(
        rules={
            "api-info": ["api-basic-info.yaml"],
            "environments": [],
            "revisions": [],
        }
    )


def create_folder_structure(base_path: Path, structure: dict):
    for name, content in structure.items():
        path = base_path / name
        if isinstance(content, dict):
            path.mkdir()
            create_folder_structure(path, content)
        else:
            path.touch()


def test_validate_artifact_struct_success(repo_validator, tmp_path):
    artifacts_path = tmp_path / "artifacts"
    artifacts_path.mkdir()

    for folder, required_files in RULES.items():
        folder_path = artifacts_path / folder
        folder_path.mkdir()
        for filename in required_files:
            (folder_path / filename).touch()

    try:
        repo_validator.validate_artifact_struct(artifacts_path)
    except ValueError:
        pytest.fail("validate_artifact_struct raised ValueError unexpectedly!")


def test_validate_artifact_struct_non_existent_path(repo_validator):
    non_existent_artifacts_path = Path("non_existent_repo/artifacts")

    with pytest.raises(
        ValueError,
        match="Folder 'artifacts' not found.",
    ):
        repo_validator.validate_artifact_struct(non_existent_artifacts_path)


def test_validate_missing_required_folder(repo_validator, tmp_path):
    artifacts_path = tmp_path / "artifacts"
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
        repo_validator.validate_artifact_struct(artifacts_path)

    assert "Mandatory folder missing" in str(excinfo.value)
    assert str(artifacts_path / folder_to_skip) in str(excinfo.value)


def test_validate_missing_required_file(repo_validator, tmp_path):
    artifacts_path = tmp_path / "artifacts"
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
        repo_validator.validate_artifact_struct(artifacts_path)

    assert "Mandatory file missing" in str(excinfo.value)
    assert str(artifacts_path / folder_with_missing_file / file_to_skip) in str(
        excinfo.value
    )


def test_validate_multiple_errors(repo_validator, tmp_path):
    artifacts_path = tmp_path / "artifacts"
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
        repo_validator.validate_artifact_struct(artifacts_path)

    error_message = str(excinfo.value)
    assert "Artifact repository validation failed:" in error_message
    assert (
        f"Mandatory file missing: {artifacts_path / folder_for_missing_file / file_to_skip}"
        in error_message
    )
    for skipped_folder in folders_to_skip:
        assert (
            f"Mandatory folder missing: {artifacts_path / skipped_folder}"
            in error_message
        )


def test_validate_new_structure_success(new_repo_validator, tmp_path):
    # api-info
    api_info_dir = tmp_path / "api-info"
    api_info_dir.mkdir()
    (api_info_dir / "api-basic-info.yaml").touch()

    # environments
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()

    # revisions
    revisions_dir = tmp_path / "revisions"
    revisions_dir.mkdir()
    rev1 = revisions_dir / "1"
    rev1.mkdir()
    (rev1 / "revision.yaml").touch()
    (rev1 / "revision-flow.yaml").touch()

    # resources
    res_dir = rev1 / "resources"
    res_dir.mkdir()
    cep_dir = res_dir / "cep"
    cep_dir.mkdir()
    (cep_dir / "resource.yaml").touch()

    # operations
    ops_dir = cep_dir / "operations"
    ops_dir.mkdir()
    (ops_dir / "get_cep.yaml").touch()

    try:
        new_repo_validator.validate_new_structure(tmp_path)
    except ValueError:
        pytest.fail("validate_new_structure raised ValueError unexpectedly!")


def test_validate_new_structure_missing_operation(new_repo_validator, tmp_path):
    # api-info
    api_info_dir = tmp_path / "api-info"
    api_info_dir.mkdir()
    (api_info_dir / "api-basic-info.yaml").touch()

    # environments
    environments_dir = tmp_path / "environments"
    environments_dir.mkdir()

    # revisions
    revisions_dir = tmp_path / "revisions"
    revisions_dir.mkdir()
    rev1 = revisions_dir / "1"
    rev1.mkdir()
    (rev1 / "revision.yaml").touch()
    (rev1 / "revision-flow.yaml").touch()

    # resources
    res_dir = rev1 / "resources"
    res_dir.mkdir()
    cep_dir = res_dir / "cep"
    cep_dir.mkdir()
    (cep_dir / "resource.yaml").touch()
    
    # operations folder exists but is empty
    ops_dir = cep_dir / "operations"
    ops_dir.mkdir()

    with pytest.raises(ValueError) as excinfo:
        new_repo_validator.validate_new_structure(tmp_path)

    assert "must contain at least one operation" in str(excinfo.value)


def test_validate_new_structure_missing_api_info(new_repo_validator, tmp_path):
    # Missing api-info folder
    revisions_dir = tmp_path / "revisions"
    revisions_dir.mkdir()
    rev1 = revisions_dir / "1"
    rev1.mkdir()

    with pytest.raises(ValueError) as excinfo:
        new_repo_validator.validate_new_structure(tmp_path)

    assert "Mandatory folder missing" in str(excinfo.value)
    assert "api-info" in str(excinfo.value)


def test_validate_new_structure_missing_revisions(new_repo_validator, tmp_path):
    # Missing revisions folder
    api_info_dir = tmp_path / "api-info"
    api_info_dir.mkdir()
    (api_info_dir / "api-basic-info.yaml").touch()

    with pytest.raises(ValueError) as excinfo:
        new_repo_validator.validate_new_structure(tmp_path)

    assert "Mandatory folder missing" in str(excinfo.value)
    assert "revisions" in str(excinfo.value)


def test_validate_new_structure_no_numeric_revisions(new_repo_validator, tmp_path):
    api_info_dir = tmp_path / "api-info"
    api_info_dir.mkdir()
    (api_info_dir / "api-basic-info.yaml").touch()

    revisions_dir = tmp_path / "revisions"
    revisions_dir.mkdir()
    (revisions_dir / "not_a_number").mkdir()

    with pytest.raises(ValueError) as excinfo:
        new_repo_validator.validate_new_structure(tmp_path)

    assert "No numeric revisions found in 'revisions' folder." in str(excinfo.value)


def test_validate_new_structure_missing_revision_files(new_repo_validator, tmp_path):
    api_info_dir = tmp_path / "api-info"
    api_info_dir.mkdir()
    (api_info_dir / "api-basic-info.yaml").touch()

    revisions_dir = tmp_path / "revisions"
    revisions_dir.mkdir()
    rev1 = revisions_dir / "1"
    rev1.mkdir()
    # Missing revision.yaml and revision-flow.yaml

    with pytest.raises(ValueError) as excinfo:
        new_repo_validator.validate_new_structure(tmp_path)

    assert "Mandatory file missing in revision 1: revision.yaml" in str(excinfo.value)
    assert "Mandatory file missing in revision 1: revision-flow.yaml" in str(
        excinfo.value
    )
