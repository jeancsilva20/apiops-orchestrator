import logging
import json
from pathlib import Path
from jsonschema import validate, exceptions
from apiops_orchestrator.domain.ports.local_file_importer_port import LocalFileImporterPort
from apiops_orchestrator.infrastructure.observability.logging import (
    log_duration,
    set_span_id,
    set_status,
)


class SchemaValidator:
    def __init__(self, file_importer: LocalFileImporterPort, schema_folder: Path):
        self.file_importer = file_importer
        self.schema_folder = schema_folder
        self.logger = logging.getLogger(__name__)

    def validate(self, yaml_data: dict, schema_name: str, target_path: Path):
        schema_path = self.schema_folder / schema_name
        set_span_id()
        with log_duration(__name__):
            try:
                if not self.file_importer.exists(str(schema_path)):
                    set_status("FAILURE")
                    raise FileNotFoundError(f"Schema file not found at {schema_path}")

                schema = self.file_importer.read(str(schema_path))
            except FileNotFoundError as e:
                set_status("FAILURE")
                raise FileNotFoundError(f"Schema file not found at {schema_path}: {e}")
            except Exception as e:
                set_status("FAILURE")
                raise ValueError(f"Error reading schema file {schema_path}: {e}")

            try:
                # Ensure data is JSON-compatible (e.g., convert dates to strings)
                json_compatible_data = json.loads(
                    json.dumps(yaml_data, default=str)
                )
                validate(instance=json_compatible_data, schema=schema)
            except exceptions.ValidationError as e:
                if e.validator == "type" and e.instance is None:
                    message = "Cannot be null"
                else:
                    message = e.message
                field_path = ".".join(str(p) for p in e.path)
                field_msg = f" for field '{field_path}'" if field_path else ""
                set_status("FAILURE")
                raise exceptions.ValidationError(
                    f"Schema validation failed for file {str(target_path)}{field_msg}: {message}"
                )
            return True


# ---------------------------------------------------------------------------
# Despacho por CAMINHO (catalog.json v2)
#
# O layout canônico não pode ser despachado por `kind`: só `api-basic-info.yaml`
# carrega `apiVersion`/`kind`. `all.yaml`, `resource.yaml` e os arquivos de
# operação são planos, e um despacho por `kind` os ignoraria em silêncio —
# arquivo sem schema é arquivo sem validação, e ninguém saberia.
# ---------------------------------------------------------------------------

import fnmatch as _fnmatch
from typing import Any as _Any, Dict as _Dict, List as _List, Optional as _Optional, Tuple as _Tuple


def escolher_schema(
    caminho_relativo: str, catalogo: _Dict[str, _Any]
) -> _Optional[str]:
    """Schema que valida um arquivo, pelo seu caminho. Primeira correspondência vence.

    A ordem do `layout` no catálogo é significativa: `resources/*/resource.yaml`
    precisa vir antes de `resources/*/*.yaml`, senão todo recurso seria validado
    como operação.
    """
    alvo = caminho_relativo.replace("\\", "/").strip("/")
    segmentos = alvo.split("/")
    for regra in catalogo.get("layout") or []:
        padrao = regra.get("pattern")
        if not padrao:
            continue
        partes = padrao.split("/")
        # `fnmatch` deixa `*` atravessar `/`, o que faria `resources/*/*.yaml`
        # casar com `resources/a/b/c.yaml`. O layout é de profundidade fixa, então
        # o casamento é segmento a segmento.
        if len(partes) != len(segmentos):
            continue
        if all(_fnmatch.fnmatchcase(s, p) for s, p in zip(segmentos, partes)):
            return regra.get("schema")
    return None


class CatalogSchemaValidator:
    """Valida um repositório inteiro contra o layout declarado no catálogo."""

    def __init__(self, validator: "SchemaValidator", catalogo: _Dict[str, _Any]):
        self._validator = validator
        self._catalogo = catalogo

    def validar(
        self, arquivos: _List[_Tuple[str, _Dict[str, _Any]]]
    ) -> _List[str]:
        """Devolve a lista de problemas; vazia significa conforme.

        Recebe pares `(caminho_relativo, conteúdo já lido)` — não toca disco, para
        que a E1 continue sendo uma leitura só.
        """
        problemas: _List[str] = []
        for caminho, dados in arquivos:
            schema = escolher_schema(caminho, self._catalogo)
            if schema is None:
                # Sem schema não é erro: é arquivo que o layout não governa.
                continue
            try:
                self._validator.validate(
                    yaml_data=dados, schema_name=schema, target_path=Path(caminho)
                )
            except Exception as exc:
                problemas.append(f"{caminho}: {exc}")
        return problemas
