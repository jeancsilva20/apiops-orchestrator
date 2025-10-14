from adapters.inbound.files_importer.local_file_importer_adapter import (
    LocalFileLoaderAdapter,
)
from application.services.file_import_service import FileImportService
from application.services.repo_validator import RepoValidator
from config.settings import Settings
from pathlib import Path


def main() -> None:
    settings = Settings()

    # ###################### #
    # Validar Pasta Artifact #
    # ###################### #
    repo_validator = RepoValidator(settings.ARTIFACTS_FILE_FOLDER_VALIDATION_RULES)

    repo_cep = Path(
        r"C:\Users\Sensedia\Downloads\Projetos\Nexus\apiops-orchestrator\api-repo-cep"  # Mude aqui o repositório na sua máquina.
    )
    artifact_folder = repo_cep / settings.API_REPO_ARTIFACTS_PATH

    try:
        print(f"Folder Location: {artifact_folder}")
        repo_validator.validate_artifact_struct(artifact_folder)
    except Exception as error:
        print(error)

    # ###################### #
    # Importador de Arquivos #
    # ###################### #

    local_file_adapter = LocalFileLoaderAdapter()
    file_importer_service = FileImportService(local_file_adapter)
    files = file_importer_service.load_file_path(artifact_folder)
    print(files)


if __name__ == "__main__":
    main()
