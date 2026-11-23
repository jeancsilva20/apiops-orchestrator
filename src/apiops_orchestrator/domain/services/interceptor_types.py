"""Referência dos tipos de interceptor e do `content` que cada um carrega.

Fonte: mapeamento APIM (doc 06 — tabela de `content` por tipo, doc 15 — customs)
e a varredura das revisões reais do tenant CONSULTING (chaves observadas por
tipo e ponto de execução, 2026-11-01). Serve a `sen get interceptor-type` e à
conferência de campos em `sen get interceptors --item`: um campo fora da
referência não é erro, é algo que a referência ainda não conhece.

Convenções do wire:

* `content` viaja como STRING JSON;
* `ignoreBodyValidationMultiPartFormData` aparece em quase todo tipo e é
  omitido das listas abaixo (está em `COMMON_FIELDS`);
* pontos: `FIRST` = request (antes do backend), `SECOND` = response,
  `THIRD` = ponto extra, visto só em `Custom`.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

COMMON_FIELDS = ("ignoreBodyValidationMultiPartFormData",)

POINT_LABELS = {"FIRST": "request", "SECOND": "response", "THIRD": "third"}


@dataclass(frozen=True)
class InterceptorType:
    name: str
    group: str
    points: Sequence[str]
    fields: Dict[str, str] = field(default_factory=dict)
    example: Optional[Dict[str, Any]] = None
    note: str = ""


_TYPES: List[InterceptorType] = [
    InterceptorType(
        "Log", "Tracing", ("FIRST", "SECOND"),
        {"acceptedTerms": "bool — aceite dos termos de log", "encryptContent": "bool — cifra o corpo no log",
         "encryptPathAndParameters": "bool — cifra path e parâmetros"},
        {"acceptedTerms": True, "encryptContent": False, "encryptPathAndParameters": False},
    ),
    InterceptorType(
        "Log obfuscation", "Tracing", ("FIRST", "SECOND"),
        {"location": "BODY | HEADER | QUERY", "attr": "nome do atributo/header", "regexToReplace": "regex do trecho",
         "replaceChar": "texto que substitui"},
        {"location": "HEADER", "attr": "authorization", "regexToReplace": "\\w.*", "replaceChar": "*****"},
    ),
    InterceptorType(
        "Data obfuscation", "Tracing", ("FIRST", "SECOND"),
        {"location": "BODY | HEADER | QUERY", "attr": "atributo", "replaceChar": "texto que substitui"},
    ),
    InterceptorType(
        "Mock", "Traffic", ("FIRST",),
        {"body": "str — corpo devolvido", "headers": "str — 'Chave: valor' por linha", "status": "str — status HTTP"},
        {"body": "{\"ok\":true}", "headers": "Content-Type: application/json", "status": "200"},
        "O Manager guarda body e status como TEXTO (fix da 0.1.1).",
    ),
    InterceptorType(
        "Rate limit", "Traffic", ("FIRST",),
        {"quota": "str — chamadas", "interval": "SECOND | MINUTE | HOUR | DAY | MONTH",
         "limitBy": "TOTAL_CALLS | IP | HEADER", "headerKey": "header usado com limitBy=HEADER",
         "noHeaderBehavior": "comportamento sem o header", "rateLimitHeader": "bool — expõe headers de limite",
         "soft": "bool — limite suave", "softvalue": "valor do limite suave"},
        {"quota": "100", "interval": "MINUTE", "limitBy": "TOTAL_CALLS"},
    ),
    InterceptorType("Spike arrest", "Traffic", ("FIRST",), {"limit": "chamadas", "interval": "janela"}),
    InterceptorType("Payload size", "Traffic", ("FIRST",), {"maxSize": "tamanho máximo do corpo"}),
    InterceptorType("Time allowed", "Traffic", ("FIRST",), {}, note="Campos não observados no tenant."),
    InterceptorType(
        "OAuth", "Security", ("FIRST",),
        {"grantTypes": "lista: CLIENT_CREDENTIALS | AUTHORIZATION_CODE | PASSWORD | IMPLICIT",
         "location": "onde ler o token", "name": "nome do header/parâmetro"},
        {"grantTypes": ["CLIENT_CREDENTIALS"]},
    ),
    InterceptorType(
        "Access token validation", "Security", ("FIRST",),
        {"grantTypes": "grant types aceitos", "location": "ANY | HEADER | QUERY", "name": "nome",
         "responseContentType": "APPLICATION_JSON | …"},
    ),
    InterceptorType(
        "Client ID validation", "Security", ("FIRST",),
        {"location": "ANY | HEADER | QUERY", "name": "nome do campo (client_id)",
         "responseContentType": "APPLICATION_JSON | …"},
        {"location": "ANY", "name": "client_id", "responseContentType": "APPLICATION_JSON"},
    ),
    InterceptorType(
        "Client ID secret encoded validation", "Security", ("FIRST",),
        {"location": "ANY | HEADER | QUERY", "name": "nome", "responseContentType": "tipo da resposta"},
    ),
    InterceptorType("JWT validation", "Security", ("FIRST",), {"location": "onde ler", "name": "nome"}),
    InterceptorType("CSRF validation", "Security", ("FIRST",), {"location": "onde ler", "name": "nome"}),
    InterceptorType("CSRF generator", "Security", ("SECOND",), {}),
    InterceptorType("Time token validation", "Security", ("FIRST",), {"location": "onde ler", "name": "nome"}),
    InterceptorType("Time token generator", "Security", ("SECOND",), {"location": "onde escrever", "name": "nome"}),
    InterceptorType("Digital signature", "Security", ("FIRST",), {"algorithm": "algoritmo", "location": "onde ler"}),
    InterceptorType("Encrypt", "Security", ("FIRST",), {"idHeaderName": "header com o id da chave"}),
    InterceptorType("IP filtering", "Security", ("FIRST",), {"listType": "ALLOW | DENY", "list": "lista de IPs/CIDR"}),
    InterceptorType("Restrict access", "Security", ("FIRST",), {"payloadSize": "number", "ipFiltering": "texto"},
                    note="Schema extraído do bundle da UI (doc 06); não observado no tenant."),
    InterceptorType(
        "XSS threat protection", "Security", ("FIRST",), {"regexList": "lista de regex bloqueadas"},
    ),
    InterceptorType(
        "SQL threat protection", "Security", ("FIRST",),
        {"sqlThreatProtectionBody": "bool", "sqlThreatProtectionHeaders": "bool", "sqlThreatProtectionCookies": "bool",
         "sqlThreatProtectionPathParams": "bool", "sqlThreatProtectionQueryParams": "bool",
         "replaceableSentences": "sentenças substituíveis"},
    ),
    InterceptorType("JSON threat protection", "Security", ("FIRST",), {}),
    InterceptorType("XML threat protection", "Security", ("FIRST",), {}),
    InterceptorType(
        "JSON schema validation", "Transformation", ("FIRST",),
        {"jsonSchema": "str — JSON Schema do corpo"}, {"jsonSchema": "{\"type\":\"object\"}"},
    ),
    InterceptorType("Header", "Mediation", ("FIRST", "SECOND"), {"headerList": "lista {name, value, action}"}),
    InterceptorType("Query param", "Mediation", ("FIRST",), {"name": "nome", "attribute": "atributo", "tokenType": "tipo"}),
    InterceptorType("HTTP method", "Mediation", ("FIRST",), {"method": "método para o backend"}),
    InterceptorType("Additional Info", "Mediation", ("FIRST", "SECOND"), {"attributes": "lista de atributos extra"}),
    InterceptorType("Transaction ID", "Tracing", ("FIRST",), {"location": "onde escrever", "name": "nome do header"}),
    InterceptorType("GZip pack", "Transformation", ("FIRST", "SECOND"), {}),
    InterceptorType("GZip unpack", "Transformation", ("FIRST", "SECOND"), {}),
    InterceptorType("XML to JSON", "Transformation", ("FIRST", "SECOND"), {"forceString": "bool"}),
    InterceptorType("JSON to XML", "Transformation", ("FIRST", "SECOND"), {}),
    InterceptorType("JSON to TXT", "Transformation", ("FIRST", "SECOND"), {}),
    InterceptorType("TXT to JSON", "Transformation", ("FIRST", "SECOND"), {}),
    InterceptorType("XSLT", "Transformation", ("FIRST", "SECOND"), {"xsl": "str — folha XSLT"}),
    InterceptorType(
        "Cache read", "Traffic", ("FIRST",),
        {"cacheName": "nome do cache", "cacheWrite": "bool — grava se não achar", "executionPoint": "eco", "id": "eco", "type": "eco"},
    ),
    InterceptorType(
        "Cache write", "Traffic", ("SECOND",),
        {"cacheName": "nome do cache", "numTTL": "TTL", "includeHeader": "bool", "headers": "headers na chave",
         "includeQuery": "bool", "query": "query na chave"},
    ),
    InterceptorType("Cache invalidation", "Traffic", ("FIRST",), {"cacheName": "nome do cache"}),
    InterceptorType(
        "Service callout", "Mediation", ("FIRST",),
        {"url": "URL chamada", "method": "método", "headers": "headers", "body": "corpo", "timeout": "ms",
         "async": "bool", "fireAndForget": "bool", "expectedHttpStatus": "status esperado",
         "preserveBody": "bool", "preserveHeaders": "bool", "preserveMethod": "bool", "preserveQueryString": "bool",
         "variableName": "variável que recebe a resposta", "previousVariableName": "variável anterior"},
    ),
    InterceptorType(
        "Internal api call", "Mediation", ("FIRST",),
        {"apiId": "API interna", "revisionId": "revisão", "resourceId": "recurso", "operationId": "operação",
         "body": "corpo", "preserveBody": "bool", "preserveHeaders": "bool", "preservePathParam": "bool",
         "preserveQueryString": "bool", "variableName": "variável", "previousVariableName": "variável anterior"},
    ),
    InterceptorType("Access token metric", "Traffic", ("FIRST",), {}),
    InterceptorType("Client ID metric", "Traffic", ("FIRST",), {}),
    InterceptorType("Billing hits", "Traffic", ("FIRST",), {}),
    InterceptorType("Date time", "Traffic", ("FIRST",), {}),
    InterceptorType("String match condition", "Traffic", ("FIRST",), {}),
    InterceptorType("Destination", "Mediation", ("FIRST",), {}),
    InterceptorType("Service mashup", "Mediation", ("FIRST",), {}),
    InterceptorType("Rate limit AI Tokens", "AI", ("FIRST",), {}),
    InterceptorType(
        "Custom", "Custom (JavaScript)", ("FIRST", "SECOND", "THIRD"),
        {"id": "id do custom no catálogo (= customInterceptorId)", "name": "nome", "script": "código JavaScript",
         "abort": "bool — aborta a requisição se falhar", "debug": "bool", "tags": "tags", "visibility": "visibilidade"},
        note="O repositório referencia o Custom por `customInterceptorId`; o script vive no tenant (sen get custom).",
    ),
    InterceptorType(
        "Java", "Custom (Java)", ("FIRST", "SECOND"),
        {"id": "id do custom Java", "name": "nome", "classNameList": "classes do jar", "selectClass": "classe escolhida",
         "params": "parâmetros", "abort": "bool"},
    ),
]

_BY_NAME = {t.name.lower(): t for t in _TYPES}


def all_types() -> List[InterceptorType]:
    return sorted(_TYPES, key=lambda t: (t.group.lower(), t.name.lower()))


def find_type(name: Optional[str]) -> Optional[InterceptorType]:
    if not name:
        return None
    return _BY_NAME.get(str(name).strip().lower())


def describe_type(kind: InterceptorType) -> Dict[str, Any]:
    return {
        "type": kind.name,
        "group": kind.group,
        "executionPoints": [POINT_LABELS.get(p, p.lower()) for p in kind.points],
        "fields": [{"name": n, "meaning": m} for n, m in kind.fields.items()],
        "commonFields": list(COMMON_FIELDS),
        "example": kind.example,
        "note": kind.note or None,
    }


def check_fields(type_name: Optional[str], content: Any) -> Optional[Dict[str, Any]]:
    """Campos do `content` contra a referência: conhecidos, fora dela e esperados ausentes."""
    kind = find_type(type_name)
    if kind is None or not isinstance(content, dict):
        return None
    present = set(content.keys())
    known = set(kind.fields) | set(COMMON_FIELDS)
    return {
        "type": kind.name,
        "known": sorted(present & known),
        "unknown": sorted(present - known),
        "missing": sorted(set(kind.fields) - present),
    }
