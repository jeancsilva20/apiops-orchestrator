# V-16 e V-17 · Nome da pasta do recurso e nome do arquivo de operação

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14, incluindo o orçamento de caminho (§5) |
| Validado com | `exemplos-gerados/` — 6 APIs reais, 143 YAML materializados |
| Ferramenta | `exemplos-gerados/extrair_estrutura.py` (protótipo determinístico, só GET) |

## 1. Regra da pasta (V-16)

```
slug(texto)   NFKD -> ascii · remove '{' '}' · [^A-Za-z0-9] -> '-' · colapsa '-'
              minúsculas · trim · trunca no último '-' antes de MAX_SLUG (60)

pasta         resources/<slug(resource.name)>
              colidiu (case-insensitive) OU truncou?
                 1. tenta sufixo LEGÍVEL: slug do path da operação de menor (path, método)
                 2. ainda colide ou estourou? sufixo MARCA: sha1(operações ordenadas)[:6]
              nome reservado do Windows (CON, PRN, AUX, NUL, COM1..9, LPT1..9) -> '-recurso'
```

A marca deriva das **operações**, não do nome: dois recursos podem ter o mesmo `name` — aconteceu na
417 rev1 — mas nunca a mesma operação (identidade do [V-12 (a)](V-12-identidade-sem-ids.md)).

O orquestrador **avisa** ao desambiguar, distinguindo os dois casos:

```
AVISO: 2 recursos com o MESMO nome 'Letras' — desambiguados no repo
AVISO: 2 recursos cujo nome, truncado em 60 chars, colide em '…' — desambiguados no repo
```

**Estabilidade:** o import não renomeia pasta existente que já contenha as mesmas operações, mesmo que
a regra gerasse outro nome hoje. Nem mudança de `name`, nem ajuste futuro da regra reescrevem o repo.

## 2. Regra do arquivo (V-17)

```
arquivo    <método>_<path completo>.yaml
           '/' vira '_' · {param} PRESERVADO · acentos removidos · minúsculas
           passou de MAX_ARQUIVO (90)? trunca no último '_' + marca sha1(método+path)[:6]
```

O nome carrega a rota inteira, **sem cortar o prefixo do recurso**:

```
resources/letras/delete_letras_{id}.yaml
resources/letras/post_tarefas_{id}_letras.yaml
resources/tarefas/get_tarefas.yaml
resources/tarefas/get_tarefas_{id}.yaml
resources/atribuicao-responsavel/post_tarefas_{id}_atribuicao-responsavel.yaml
```

Decisão do usuário (2026-10-14), substituindo a versão anterior em que o arquivo trazia só o path
relativo ao prefixo comum do recurso (`get.yaml`, `get_id.yaml`). O nome passa a ser lido como a rota.

## 3. O que a materialização provou

| Achado | Evidência |
|---|---|
| Sem limite de comprimento, o layout **não é materializável** | `WinError 206` ao criar a pasta da API 17 (FDX): slug de 95 chars |
| Truncar **cria** colisão | dois recursos da FDX compartilham os primeiros 60 caracteres |
| A marca não pode vir do `name` | os dois `Letras` da 417 rev1 têm nome idêntico — mesma marca, colisão intacta |
| O sufixo legível nem sempre resolve | na FDX, o path das duas operações também colide depois do truncamento → cai na marca |
| Colisão é exceção | 0 colisões em 111 recursos de 40 APIs; o caso real veio de um estado intermediário de reorganização |

## 4. Resultado nas 6 APIs

| Pasta | Recursos | Operações | Arquivos | Maior caminho relativo |
|---|---|---|---|---|
| api-417-rev2 | 4 | 7 | 13 | 78 |
| api-417-rev1 | 6 | 7 | 15 | 78 |
| api-409-rev1 | 6 | 7 | 15 | 89 |
| api-17-rev1 (FDX) | 37 | 56 | 95 | **165** |
| api-2-rev1 | 2 | 9 | 13 | 51 |
| api-5-rev1 | 1 | 1 | 4 | 77 |

## 5. Orçamento de caminho — decidido

Com o path completo no nome do arquivo, o pior caso real (FDX) usa **165 caracteres** de caminho
relativo. O Windows aceita 260 no total, então sobram **95 caracteres para a raiz do clone**.

Na pasta de exemplos (que fica 153 caracteres fundo dentro de `docs/`), **12 dos 95 arquivos da FDX
não puderam ser escritos** — o script avisa e continua, em vez de abortar.

**Decisão (2026-10-14): fica a saída 1 — regra única, path completo, teto de 90.** O caminho longo é
exceção; o caso corrente (um repositório por API, recursos com rótulo) fica bem abaixo do limite.

As três saídas avaliadas, medidas na FDX (56 operações):

| # | Saída | Maior caminho | Média | Sobra p/ a raiz do clone |
|---|---|---|---|---|
| **1** | **path completo, teto 90 — ADOTADA** | **165** | **75** | **95** |
| 2 | path completo, teto 55 | 122 | 71 | 138 |
| 3 | não repetir o prefixo quando `resource.name` já é o path | 88 | 46 | 172 |

Consequências aceitas:

- o repositório precisa ser clonado em caminho **curto** (até ~95 caracteres) para o pior caso caber —
  `C:\git\fdx` dá 176 no total e `C:\Users\fulano\Documents\projetos\fdx` dá 204, ambos dentro do limite;
- `git config --system core.longpaths true` ajuda no clone, mas não cobre o Explorer nem todo editor;
- o extrator **avisa e continua** quando um arquivo não cabe, em vez de abortar a extração.

### 5.1 Varredura do tenant — nenhuma API estoura

Medição das **118 APIs** do tenant (106 com recursos), aplicando a regra adotada:

| id | Recursos | Ops | Regra atual | Plano B | Nome |
|---|---|---|---|---|---|
| 17 | 37 | 56 | **165** | 88 | FDX |
| 313 | 28 | 42 | 114 | 65 | MCP FDX API |
| 30 | 1 | 6 | 103 | 103 | Desafio 3 \| Mock API |
| 288 | 3 | 22 | 90 | 90 | Teste |
| 316 | 7 | 26 | 90 | 90 | API GestaoApolice |
| 409 | 6 | 7 | 89 | 53 | Serviço de Letras |

Distribuição: **1** API acima de 150 chars · **3** acima de 100 · todo o resto abaixo de 90.

Simulação de raiz de clone com o pior caso (FDX, 165 chars):

| Raiz | Total | |
|---|---|---|
| `C:\git\api` (10) | 176 | OK |
| `…\Documents\Projetos\api-letras` (58) | 224 | OK |
| `…\OneDrive - Sensedia\Documentos\` (76) | 242 | OK |

**Nenhuma API do tenant estoura**, nem na raiz com OneDrive. O estouro observado na pasta de exemplos
veio dos 153 caracteres de profundidade de `docs/`, não do layout.

A saída 3 fica registrada como plano B, caso apareça uma API que estoure mesmo em caminho curto.
