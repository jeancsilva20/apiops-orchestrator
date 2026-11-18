# Exemplos gerados — o layout aplicado a APIs reais do tenant

| Meta | Valor |
|---|---|
| Gerado em | 2026-10-14 |
| Como | `extrair_estrutura.py` — script autocontido (só biblioteca padrão), token e `API_ID` em constantes no topo |
| Escrita na plataforma | nenhuma |
| Serve para | validar as regras dos itens V-01, V-12, V-16 e V-17 contra dado real antes de virarem código |

> As pastas abaixo são **saída de máquina**. Reexecutar `extrair_estrutura.py` as recria idênticas — se não
> recriar, a regra não é determinística, que é justamente o que este exercício testa.

## Cenários escolhidos

| Pasta | API | Cenário |
|---|---|---|
| `api-417-rev2/` | 417 rev2 | rótulos livres; recurso sem prefixo comum (`Letras`); destino/timeout nos 3 escopos |
| `api-417-rev1/` | 417 rev1 | **colisão**: dois `Letras` e dois `Tarefas` na mesma API |
| `api-409-rev1/` | 409 rev1 | `name` = path em todos os recursos; tombstone e override |
| `api-17-rev1/` | 17 (FDX) | 37 recursos, paths longos — estresse de comprimento de caminho |
| `api-2-rev1/` | 2 | names com espaço: `free access`, `Resource operations` |
| `api-5-rev1/` | 5 | name com espaço e maiúsculas |

## Resultado

| Pasta | Recursos | Operações | Arquivos | Maior caminho |
|---|---|---|---|---|
| api-417-rev2 | 4 | 7 | 13 | 46 |
| api-417-rev1 | 6 | 7 | 15 | 48 |
| api-409-rev1 | 6 | 7 | 15 | 57 |
| api-17-rev1 | 37 | 56 | 95 | **90** |
| api-2-rev1 | 2 | 9 | 13 | 44 |
| api-5-rev1 | 1 | 1 | 4 | 38 |

Cada pasta traz `api-basic-info.yaml` (D-003 §3), `all-all.yaml` (escopo revision) e a árvore
`resources/`. **155 YAML gerados no total.** ⚠️ *Corrigido em 2026-10-15:* a afirmação original ("todos parseiam") estava errada — dois arquivos de `api-400-rev4` emitiam `replaceChar: *****` sem aspas e **não eram parseáveis** (`yaml.safe_load` tentava ler um alias). O defeito foi reparado e os exemplos foram regerados pelo materializador de produção (`domain/services/repo_materializer.py`); hoje todos parseiam de fato.

Fluxos classificados: **3 append · 3 override · 3 tombstone**. Colisões não resolvidas pela regra:
**nenhuma**. Slugs truncados pelo orçamento de caminho: **76**.

## As regras que o exercício fixou

```python
MAX_SLUG = 60

slug(txt)   = NFKD -> ascii, remove '{' '}', [^A-Za-z0-9] -> '-', colapsa '-', minúsculas, trim
              + trunca no último '-' antes de MAX_SLUG

pasta       = resources/<slug(resource.name)>
              colidiu ou truncou? -> sufixo LEGÍVEL: slug do path da 1ª operação
              ainda colide ou estourou MAX_SLUG? -> sufixo MARCA: sha1(operações)[:6]

arquivo     = <método>[_<slug(path relativo ao prefixo comum do recurso, 40)>].yaml
```

## O que só apareceu porque geramos de verdade

**1. O Windows recusou criar a pasta.** Com o slug derivado do `name` sem limite, a API FDX produziu
`WinError 206 — o nome do arquivo ou a extensão é muito grande`. O caminho mais longo era de
**213 caracteres** só na parte relativa; somado à raiz do repositório, passa dos 260 que o Windows
aceita por padrão (248 para diretório). **O layout não era materializável.** Com o limite de 60 e o
nome de arquivo relativo ao prefixo comum, o pior caso caiu para **90**.

**2. Truncar cria colisão.** Dois recursos da FDX compartilham os primeiros 60 caracteres
(`/payment-initiation-parties/{…}/payment-methods` e `/payment-initiation-parties/{…}/payment-methods/{…}`).
Truncar sem desambiguar junta recursos distintos na mesma pasta — por isso a marca entra **sempre que
houve truncamento**, não só quando há colisão de nome.

**3. A desambiguação é híbrida — legível primeiro, marca por último.** Na 417 rev1 o sufixo legível
resolve e fica compreensível: `letras-letras-id`, `letras-tarefas-id-letras`, `tarefas-tarefas-id`,
`tarefas-tarefas`. Na FDX ele **não** resolve: os dois recursos têm paths que, truncados, produzem
exatamente o mesmo sufixo — ali entra a marca (`…-payment-d2e8d3` e `…-payment-f6d1fd`).

**3.1 A marca não pode derivar do `name`.** Primeira tentativa usou `sha1(name)`, e os dois `Letras` da
rev1 têm o **mesmo nome** — mesma marca, mesma pasta, colisão intacta. A marca passou a derivar do
**conjunto de operações**, que é a identidade do recurso (V-12a): dois recursos nunca têm a mesma
operação. Resultado: `letras-84380a` e `letras-a121a7`, `tarefas-02b142` e `tarefas-3b6e1f`.

**4. Append e override só se distinguem olhando o `content`.** Classificando por
`(executionPoint, type, customInterceptorId)`, o `Log` cifrado que a `POST /…/atribuicao-responsavel`
acrescenta é lido como cópia do `Log` herdado — e um append vira override. Com o `content` na chave,
a classificação ficou correta (3 append, 3 override). É o mesmo requisito já registrado no
[V-11 conformidade](../V-11-conformidade-com-a-regua.md) §4.

**5. O nome de arquivo encurtou muito.** Usando o path relativo ao prefixo comum do recurso:
`get.yaml`, `get_id.yaml`, `post.yaml`, `delete_letras-id.yaml`. O nome longo sobrevive só onde é
informação — `letras/post_tarefas-id-letras.yaml`, porque esse recurso não tem prefixo comum.

## Como reexecutar

```python
# extrair_estrutura.py — constantes no topo do arquivo
HOST  = "https://platform-production.sensedia.com"
TOKEN = "<access token de superadmin>"
API_ID = 417
REVISION_NUMBER = 2        # None = revisão corrente
DESTINO = "saida"
```

```bash
python extrair_estrutura.py
```

Sem `.env`, sem `requests`, sem `PyYAML` — só biblioteca padrão. Faz apenas `GET`.
O script avisa quando desambigua uma pasta, distinguindo **nome idêntico** de **colisão por
truncamento**.

## Pendências visíveis nos arquivos

- **Tombstone** (`V-25`): `api-417-rev2/resources/tarefas/get.yaml` e os equivalentes na 409 trazem um
  comentário `# TOMBSTONE: remove do fluxo herdado -> XSS threat protection`, porque a representação
  no YAML ainda não foi decidida.
- **Custo do override**: `health-check/get.yaml` reproduz 6 itens para derrubar 1 (`Custom #178`).
