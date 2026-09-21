# Probes — saídas capturadas (read-only)

Captura: 2026-09-21 19:01 UTC · conta de produção · token super admin do fluxo `sen` · sem paginação server-side.

| # | Rota | Itens | Achado principal |
|---|---|---|---|
| 1 | `GET /apis` (sem filtro) | 110 | sem `lastRevision`/`lifeCycle`/`revisions[]>0` (0/110) |
| 2 | `GET /apis?filter=BASIC_INFO` | 110 | byte-a-byte IGUAL ao sem filtro (filtro inerte neste deploy) |
| 3 | `GET /revisions/basic` | 450 linhas / 110 apis | `api.revisionNumber` em 100%; `lifeCycle` ausente |
| 4 | `GET /apis/{id}` (400) | 1 | `lastRevision.revisionNumber` + `lifeCycle` presentes (DRAFT) |
| 5 | `GET /apis/{id}/versions` | 0 | array vazio para 400 |

### Contagens do conjunto (110 itens)
```
com lastRevision populado: 0/110
com lifeCycle populado:    0/110
com revisions[]>0:         0/110
```

## 1) Listagem crua — `GET /apis`

- **Rota:** `GET /api-manager/api/v3/apis`
- **Status:** 200 OK · **tamanho da resposta:** 79,892 bytes
- **Itens:** 110

### Amostra (primeiros 2 itens, integral)
```json
{
  "id": 1,
  "name": "oAuth - RFC",
  "description": "Oauth Sensedia API adapted to meet RFC 6749 and RFC 6750",
  "version": "2.0.0",
  "creationDate": "2025-05-06T13:05:16.000+00:00",
  "plans": [
    {
      "id": 1,
      "name": "oAuth - RFC",
      "defaultPlan": true
    }
  ],
  "basePath": "/oauth/v1",
  "privateAPI": false,
  "environments": [],
  "revisions": [],
  "appsCount": 0,
  "lastVersion": false,
  "apiType": "REST",
  "visibility": {
    "id": 6,
    "visibilityType": "ORGANIZATION",
    "owner": "renan.nunes",
    "users": []
  },
  "apiSwaggerConfiguration": {
    "id": 1,
    "showAppRegister": true,
    "showApiBrowser": false,
    "apiSwaggerConfigurationEnvironments": []
  },
  "tags": [],
  "apiTags": [],
  "identityApi": false
}
{
  "id": 2,
  "name": "[Template] Generic API with mandatory interceptors",
  "description": "API Template containing all mandatory security interceptors and also the recommended way to create an API.",
  "version": "1.0.0",
  "creationDate": "2025-05-06T13:06:21.000+00:00",
  "plans": [
    {
      "id": 2,
      "name": "Generic Plan",
      "defaultPlan": true
    }
  ],
  "basePath": "/generic-template/v1",
  "privateAPI": false,
  "environments": [],
  "revisions": [],
  "appsCount": 0,
  "lastVersion": false,
  "apiType": "REST",
  "visibility": {
    "id": 7,
    "visibilityType": "ORGANIZATION",
    "owner": "renan.nunes",
    "users": []
  },
  "apiSwaggerConfiguration": {
    "id": 2,
    "showAppRegister": true,
    "showApiBrowser": false,
    "apiSwaggerConfigurationEnvironments": []
  },
  "tags": [],
  "apiTags": [],
  "identityApi": false
}
```

## 2) Listagem com `?filter=BASIC_INFO`

- **Tamanhos:** sem filtro 80,315 B vs com filtro 80,315 B → idênticos: `True`

## Detalhe dos itens (mesmos achados)

- **Rota:** `GET /api-manager/api/v3/apis?filter=BASIC_INFO`
- **Status:** 200 OK · **tamanho da resposta:** 79,892 bytes
- **Itens:** 110

### Amostra (primeiros 2 itens, integral)
```json
{
  "id": 1,
  "name": "oAuth - RFC",
  "description": "Oauth Sensedia API adapted to meet RFC 6749 and RFC 6750",
  "version": "2.0.0",
  "creationDate": "2025-05-06T13:05:16.000+00:00",
  "plans": [
    {
      "id": 1,
      "name": "oAuth - RFC",
      "defaultPlan": true
    }
  ],
  "basePath": "/oauth/v1",
  "privateAPI": false,
  "environments": [],
  "revisions": [],
  "appsCount": 0,
  "lastVersion": false,
  "apiType": "REST",
  "visibility": {
    "id": 6,
    "visibilityType": "ORGANIZATION",
    "owner": "renan.nunes",
    "users": []
  },
  "apiSwaggerConfiguration": {
    "id": 1,
    "showAppRegister": true,
    "showApiBrowser": false,
    "apiSwaggerConfigurationEnvironments": []
  },
  "tags": [],
  "apiTags": [],
  "identityApi": false
}
{
  "id": 2,
  "name": "[Template] Generic API with mandatory interceptors",
  "description": "API Template containing all mandatory security interceptors and also the recommended way to create an API.",
  "version": "1.0.0",
  "creationDate": "2025-05-06T13:06:21.000+00:00",
  "plans": [
    {
      "id": 2,
      "name": "Generic Plan",
      "defaultPlan": true
    }
  ],
  "basePath": "/generic-template/v1",
  "privateAPI": false,
  "environments": [],
  "revisions": [],
  "appsCount": 0,
  "lastVersion": false,
  "apiType": "REST",
  "visibility": {
    "id": 7,
    "visibilityType": "ORGANIZATION",
    "owner": "renan.nunes",
    "users": []
  },
  "apiSwaggerConfiguration": {
    "id": 2,
    "showAppRegister": true,
    "showApiBrowser": false,
    "apiSwaggerConfigurationEnvironments": []
  },
  "tags": [],
  "apiTags": [],
  "identityApi": false
}
```

## 3) `/revisions/basic` — goldmine do LAST REV

- **Linhas:** 450 · **apis distintas:** 110 · `api.revisionNumber` presente em 450/450
- `lifeCycle`: **ausente** em todas as linhas (só existe em `RevisionBean`, por revisão)
- Extra: cada linha traz `workflowId`/`workflowStageId` — útil para a grade de drill-down futura

## Saída bruta (amostra)

- **Rota:** `GET /api-manager/api/v3/revisions/basic`
- **Status:** 200 OK · **tamanho da resposta:** 106,343 bytes
- **Itens:** 450

### Amostra (primeiros 2 itens, integral)
```json
{
  "id": 1,
  "api": {
    "id": 1,
    "revisionNumber": 1,
    "name": "oAuth - RFC",
    "description": "Oauth Sensedia API adapted to meet RFC 6749 and RFC 6750",
    "version": "2.0.0"
  },
  "workflowId": 139,
  "workflowStageId": 420
}
{
  "id": 7,
  "api": {
    "id": 2,
    "revisionNumber": 1,
    "name": "[Template] Generic API with mandatory interceptors",
    "description": "API Template containing all mandatory security interceptors and also the recommended way to create an API.",
    "version": "1.0.0"
  },
  "workflowId": 139,
  "workflowStageId": 420
}
```

## 4) Detalhe `GET /apis/400`

- `lastRevision.revisionNumber`: 4 · `lastRevision.lifeCycle`: `DRAFT`

## Saída bruta (item único)

- **Rota:** `GET /api-manager/api/v3/apis/400`
- **Status:** 200 OK · **tamanho da resposta:** 89,344 bytes
- **Itens:** 0

### Amostra (primeiros 2 itens, integral)
```json
```

## 5) `GET /apis/400/versions` (retornou vazio)

- **Rota:** `GET /api-manager/api/v3/apis/400/versions`
- **Status:** 200 OK · **tamanho da resposta:** 2 bytes
- **Itens:** 0

### Amostra (primeiros 2 itens, integral)
```json
```