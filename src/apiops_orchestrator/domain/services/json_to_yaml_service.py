import json
import logging
from dataclasses import asdict, is_dataclass
from typing import List, Dict, Any
from uuid import UUID

from apiops_orchestrator.adapters.outbound.files_exporter.local_file_exporter_adapter import LocalFileExporterAdapter
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.models.api_full_model import ApiFull
from apiops_orchestrator.domain.services.json_to_yaml_enum import JsonKind


class _YamlDocumentFactory:
    """Factory for creating standard YAML document structures."""

    @staticmethod
    def create_document(
        kind: str,
        spec: Dict[str, Any],
        version: str
    ) -> Dict[str, Any]:
        """Create a standard YAML document with apiVersion, kind, and spec."""
        return {
            "apiVersion": version,
            "kind": kind,
            "spec": spec
        }

class JsonToYamlService:
    """
    Service to build a complete API YAML structure from a list of JSON data parts.
    """
    def __init__(self, json_full_object: ApiFull, settings: Settings, local_file_exporter: LocalFileExporterAdapter) -> None:
        self.json_full_object = json_full_object
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.local_file_exporter = local_file_exporter

        # Keys for Dictionary Lookup via .get()
        self.KIND_KEY = "kind"
        self.KIND_API = "api"
        self.KIND_METADATA = "metadata"
        self.KIND_FILE_NAME = "fileName"
        self.KIND_SPEC = "spec"
        self.KIND_OPERATION = "operation"

    def build_yaml_parts(self) -> List[Dict[str, Any]]:
        yaml_parts = []
        
        try:
            # 1. Basic info
            yaml_parts = [self._create_basic_info_part()]

            # 2. All/all interceptors
            if self.json_full_object.interceptors:
                yaml_parts.append(self._create_interceptors_part())
            else:
                self.logger.debug("Nenhum interceptador encontrado")

            # 3. Resources and Operations
            if self.json_full_object.resources:
                resources_list, operations_files = self._create_resources_and_ops_parts()

                # Adds resources.yaml (because it is an object list, not a unique dict with spec)
                yaml_parts.append({
                    "kind": JsonKind.RESOURCES.value,
                    "content": resources_list
                })

                # Adds operations files
                yaml_parts.extend(operations_files)
            else:
                self.logger.debug("Nenhum recurso encontrado")

            return yaml_parts
        except Exception as e:
            self.logger.error(f"Erro ao construir YAMLs", exc_info=e)
            raise

    def _create_basic_info_part(self) -> Dict[str, Any]:
        self.logger.debug("Criando parte de informações básicas da API")
        try:
            api_data = self._to_dict(self.json_full_object.api)
            self.logger.debug("Dados da API convertidos para dicionário")
            
            # Cleans unimportant properties
            fields_to_remove = ['revisions', 'deployments', 'creationDate', 'id', 'apiType', 'apiSwaggerConfiguration', 'lastRevision']
            for field in fields_to_remove:
                api_data.pop(field, None)
            self.logger.debug(f"Removidas {len(fields_to_remove)} propriedades desnecessárias")

            spec = {
                "api": api_data,
                "revision": {
                    "workflowId": self.settings.WORKFLOW_ID,
                    "workflowStageId": self.settings.WORKFLOW_STAGE_ID
                }
            }

            result = _YamlDocumentFactory.create_document(
                kind=JsonKind.API_BASIC_INFO.value,
                spec=spec,
                version=self.settings.VERSION
            )
            self.logger.info("Documento YAML de informações básicas criado com sucesso")
            return result
        except Exception as e:
            self.logger.error(f"Erro ao criar informações básicas da API", exc_info=e)
            raise

    def _create_interceptors_part(self) -> Dict[str, Any]:
        self.logger.debug(f"Criando parte de interceptadores ({len(self.json_full_object.interceptors)} total)")
        try:
            interceptors_list = [self._prepare_interceptor(i) for i in self.json_full_object.interceptors]
            self.logger.debug(f"Todos os {len(interceptors_list)} interceptador(es) preparado(s) com sucesso")
            
            spec = {"interceptors": interceptors_list}
            result = _YamlDocumentFactory.create_document(
                kind=JsonKind.INTERCEPTORS.value,
                spec=spec,
                version=self.settings.VERSION
            )
            self.logger.info("Documento YAML de interceptadores criado com sucesso")
            return result
        except Exception as e:
            self.logger.error(f"Erro ao criar parte de interceptadores: {str(e)}", exc_info=True)
            raise

    def _create_resources_and_ops_parts(self):
        self.logger.debug(f"Criando partes de recursos e operações para {len(self.json_full_object.resources)} recurso(s)")
        resources_output_list = []
        operation_files = []

        try:
            for idx, resource in enumerate(self.json_full_object.resources, 1):
                self.logger.debug(f"Processando recurso {idx}/{len(self.json_full_object.resources)}: {resource.name}")
                
                # Makes sure operation will be searched
                ops_list = getattr(resource, 'operations', [])
                self.logger.debug(f"Recurso '{resource.name}' contém {len(ops_list)} operação(ões)")

                # Create operation files and references
                ops_refs, resource_ops_files = self._create_operation_files_and_refs(ops_list)
                operation_files.extend(resource_ops_files)

                # Create resource entry
                resource_entry = self._create_resource_entry(resource, ops_refs)
                resources_output_list.append(resource_entry)
                
                self.logger.debug(f"Recurso '{resource.name}' processado com sucesso")

            self.logger.info(f"Criação de recurso e operações concluída: {len(operation_files)} operação(ões)")
            return resources_output_list, operation_files
        except Exception as e:
            self.logger.error(f"Erro ao criar recursos e operações: {str(e)}", exc_info=True)
            raise

    def _create_operation_files_and_refs(self, operations_list: List[Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Create operation files and their references for resources.yaml.
        
        Returns:
            Tuple of (operation_references, operation_files)
        """
        self.logger.debug(f"Criando arquivos e referências de operações ({len(operations_list)} operação(ões))")
        ops_refs = []
        operation_files = []

        try:
            for idx, op in enumerate(operations_list, 1):
                self.logger.debug(f"Processando operação {idx}/{len(operations_list)}: {op.method} {op.path}")
                
                # Generates file name
                file_name = self.local_file_exporter.generate_filename(op.method, op.path)
                self.logger.debug(f"Nome de arquivo gerado: {file_name}")

                # Creates reference for resources.yaml
                ops_refs.append({
                    "method": op.method,
                    "path": op.path,
                    "file": file_name
                })

                # Prepares operation content
                op_data = self._to_dict(op)

                # Special treatment for interceptors inside operation
                if 'interceptors' in op_data:
                    num_interceptors = len(op.interceptors)
                    op_data['interceptors'] = [
                        self._prepare_interceptor(i) for i in op.interceptors
                    ]
                    self.logger.debug(f"Processados {num_interceptors} interceptador(es) na operação {op.method} {op.path}")

                # Removes fields not present in individual file
                op_data.pop('id', None)

                # Creates structure of operation file
                op_spec = {"operation": [op_data]}
                operation_files.append({
                    "kind": JsonKind.API_OPERATIONS.value,
                    "method": op.method,
                    "path": op.path,
                    "content": _YamlDocumentFactory.create_document(
                        kind=JsonKind.API_OPERATIONS.value,
                        spec=op_spec,
                        version=self.settings.VERSION
                    )
                })
                
                self.logger.debug(f"Operação {op.method} {op.path} processada com sucesso")

            self.logger.debug(f"Criação de operações concluída: {len(ops_refs)} referência(s), {len(operation_files)} arquivo(s)")
            return ops_refs, operation_files
        except Exception as e:
            self.logger.error(f"Erro ao criar arquivos e referências de operações", exc_info=e)
            raise

    def _create_resource_entry(self, resource: Any, ops_refs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a resource entry for resources.yaml.
        
        Args:
            resource: The resource object
            ops_refs: List of operation references for this resource
            
        Returns:
            Resource entry dictionary
        """
        self.logger.debug(f"Criando entrada de recurso: {resource.name} com {len(ops_refs)} referência(s)")
        try:
            entry = {
                "apiVersion": self.settings.VERSION,
                "kind": JsonKind.RESOURCES.value,
                "name": resource.name,
                "description": getattr(resource, 'description', None),
                "operations": ops_refs
            }
            self.logger.debug(f"Entrada de recurso '{resource.name}' criada com sucesso")
            return entry
        except Exception as e:
            self.logger.error(f"Erro ao criar entrada de recurso '{resource.name}': {str(e)}", exc_info=True)
            raise

    # --- Helpers ---

    def _prepare_interceptor(self, interceptor_obj: Any) -> Dict[str, Any]:
        self.logger.debug("Preparando interceptador")
        try:
            i_dict = self._to_dict(interceptor_obj)
            content = i_dict.get('content')

            # Tries to convert string JSON to Dict
            if isinstance(content, str):
                try:
                    i_dict['content'] = json.loads(content)
                    self.logger.debug("Conteúdo JSON do interceptador convertido com sucesso")
                except (json.JSONDecodeError, TypeError) as e:
                    # If it fails, keeps the string
                    self.logger.debug(f"Falha ao converter JSON do interceptador, mantendo como string: {str(e)}")
                    pass

            # If content is a numeric string like ("158"), converts it into int
            if isinstance(i_dict.get('content'), str) and i_dict['content'].isdigit():
                i_dict['content'] = int(i_dict['content'])
                self.logger.debug(f"Conteúdo numérico convertido para inteiro: {i_dict['content']}")

            # Removes internal fields
            i_dict.pop('parent', None)
            i_dict.pop('revision', None)

            self.logger.debug("Interceptador preparado com sucesso")
            return i_dict
        except Exception as e:
            self.logger.error(f"Erro ao preparar interceptador: {str(e)}", exc_info=True)
            raise

    def _to_dict(self, obj: Any, _max_depth: int = 100, _current_depth: int = 0) -> Any:
        """
        Convert objects to dictionaries recursively.

        Handles:
        - Dataclasses (using asdict)
        - Objects with __dict__ attribute
        - Lists and dicts (recursive conversion)
        - Primitives (returned as-is)
        """
        if _current_depth > _max_depth:
            self.logger.warning(f"Profundidade máxima de recursão excedida {_max_depth}")
            raise RecursionError(f"Profundidade máxima de recursão excedida {_max_depth}")

        # Handle dataclasses (fastest path for structured data)
        if is_dataclass(obj) and not isinstance(obj, type):
            try:
                return asdict(obj)
            except Exception as e:
                self.logger.debug(f"Conversão de dataclass usando asdict falhou: {str(e)}")
                # Fallback to __dict__ conversion
                if hasattr(obj, '__dict__'):
                    return self._to_dict(obj.__dict__, _max_depth, _current_depth + 1)

        # Handle lists
        if isinstance(obj, list):
            return [self._to_dict(item, _max_depth, _current_depth + 1) for item in obj]

        # Handle dictionaries
        if isinstance(obj, dict):
            return {
                key: self._to_dict(value, _max_depth, _current_depth + 1)
                for key, value in obj.items()
            }

        # Handle objects with __dict__ attribute
        if hasattr(obj, '__dict__') and not isinstance(obj, (str, int, float, bool, type(None), UUID)):
            return self._to_dict(obj.__dict__, _max_depth, _current_depth + 1)

        # Return primitives as-is (str, int, float, bool, None, UUID, etc.)
        return obj

