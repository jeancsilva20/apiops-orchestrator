## Context

O `sen validate` já implementa a escrita na plataforma: monta o payload denso a partir do repositório
e do estado remoto, faz um único `PUT /revisions/{id}` e confere o resultado por `GET`. Ele escreve
na Draft, porque o objetivo dele é o diagnóstico.

O `sen publish` é a mesma escrita apontada para a revisão do ambiente, sem o diagnóstico em volta.
Restrições fechadas que não se renegociam aqui:

- revisão alvo pelo número, nunca pelo id; local só na 1 (V-24);
- criar revisão é ato humano: nunca `POST /revisions` (D-005 §9);
- `workflowId`/`workflowStageId` lidos da revisão alvo e reenviados intactos (D-020);
- HTTP 200 não é prova de sucesso: conferir sempre (W-8);
- o AG atua no `PUT /revisions/{id}`; não escrever em `PUT /apis/{id}` (W-7, D-14).

## Goals / Non-Goals

**Goals:**

- Dar à esteira um comando que grava a revisão do ambiente e devolve um veredito legível por máquina.
- Reusar, não duplicar, a escrita do `validate`.

**Non-Goals:**

- Conformidade com a API-template e completeness — são do `validate` (§6 do plano).
- Reconciliação antes de escrever — decisão canônica do §7.
- Deploy, promoção ou criação de revisão.
- Ligar as esteiras ao comando.

## Decisions

### 1. Fluxo

```
E1   carregar o repositório                 sem rede     LayoutInvalidoError        exit 1
     revisão alvo pelo número               sem rede     P-1 / P-2                  exit 1
E2   GET /apis/{spec.id}                                  P-10 / P-3                 exit 1
     guarda de identidade (version, basePath)             P-4                        exit 1
     GET /revisions/{id} + montagem do payload
     Custom referenciados existem                         CustomInexistenteError     exit 1
     pré-check: tags válidas e governança                 TagInvalida / Governance   exit 1 / 3
     confirmação (só local)
E3   PUT /revisions/{id}                    ESCRITA      412 → exit 3; demais → exit 1
E3.1 GET /revisions/{id} + conferência                    PublicacaoDivergenteError  exit 1
```

A revisão alvo é resolvida **antes** de qualquer chamada quando o problema é de configuração (P-1,
P-2): uma esteira mal configurada não deve gastar autenticação para descobrir isso.

### 2. Peça compartilhada `RevisionWriter`

Saem do `ValidateService`, sem mudança de comportamento: carga do repositório com o erro de layout,
guarda de identidade, `Custom` referenciados, resolução da revisão por número e gravação com
conferência e tradução das recusas. O `ValidateService` e o `PublishService` passam a compô-la.

**Alternativa descartada:** `PublishService` herdar de `ValidateService`. Arrastaria a régua e o
completeness para um comando que não os usa, e acoplaria os dois a cada mudança do diagnóstico.

### 3. `TARGET_REVISION_NUMBER` opcional em `Settings`

Com default `1`, "ausente" e "1" são indistinguíveis, e a P-1 não é implementável. A variável passa a
`int | None = None`. O `validate` mantém o comportamento atual (ausente ⇒ 1); o `publish` aplica a
P-1 em `pipeline`.

### 4. Mensagens

A recusa da gravação no `validate` fala em "rascunho". No `publish` o alvo é a revisão de um ambiente,
então a mensagem nomeia a revisão (`a revisão 2`). A `PublicacaoRecusadaError` recebe o alvo como
parâmetro, com default que preserva o texto do `validate`.

### 5. Contrato `apiops.sen-publish/v1`

```
schema, generatedAt, executionMode,
api { managerId, name, version, basePath },
revision { managerId, revisionNumber },
governance { workflowId, stageId, required[], missing[], blocked },
publication { attempted, accepted, verified, divergences[] },
warnings[]   ← avisos da montagem e do pré-check
```

Reusa as dataclasses do `validate_view` para API, revisão, governança e publicação.

## Risks / Trade-offs

- **[Dois escritores na mesma revisão]** → risco aceito na D-15; a conferência por `GET` detecta a
  sobrescrita só se ela cair entre o `PUT` e o `GET`.
- **[Retry em 5xx]** → o adapter faz até 3 tentativas. A P-7 pede "sem retry longo"; 3 tentativas
  curtas foram consideradas dentro disso.
- **[Pré-check sem stage]** → quando a revisão não tem workflow, o veredito fica com o `PUT`, e o
  aviso entra em `warnings[]`.

### 6. Avisos de remoção na confirmação

O `PUT` grava a revisão inteira: recurso, rota ou interceptor que está no Manager e não está no
repositório é apagado. Isso não bloqueia — remover pode ser a intenção —, mas é avisado, com texto
que nomeia o que sai ("serão apagados do Manager"). Rotas removidas ganham aviso próprio; as de um
recurso removido inteiro não se repetem.

Em `local` os avisos vão **na caixa de confirmação**, antes do `s/n`, e não se repetem no resultado:
exibidos só depois, o dev confirmaria sem saber o que perde. Em `pipeline` não há pergunta, e eles
saem no resultado (`warnings[]`). Vale para `validate` e `publish`.

### 6.1 Recusa e cancelamento na confirmação (D-18)

A D-18 fixou que só a cascata completa produz relatório. Responder `n` encerra sem gravar e **sem
relatório**: só "Validação cancelada" / "Publicação cancelada. Nada foi gravado.", com exit 0. Ctrl+C
(ou fim da entrada) no prompt não é um "não": interrompe o comando com a mesma mensagem e exit 130.
Corrige o T-21 do plano, que ainda descrevia a premissa revogada pela D-18 ("reporta o que E1/E2 já
coletaram"). Vale para `validate` e `publish`.

### 7. Correção encontrada no smoke: o repositório prevalece em `content` e ordem

O smoke contra a revisão 2 da API 417 (2026-10-16) mostrou que alterar o `content` de um interceptor
**existente** era descartado: o item remoto era reaproveitado inteiro, e a conferência — que comparava
o publicado com o payload — dava verde. A ordem declarada também se perdia: o item reusado mantinha a
`position` remota e o novo ia para o fim.

Nenhuma decisão sustentava isso. V-22 §3 manda reconstruir do YAML o que é governado; V-11 §4 diz que
no nativo o `content` **é** a configuração; a D14 do `add-sen-validate` declara que o repositório
sobrescreve a plataforma. Correção, em código compartilhado com o `validate`:

- do item existente reaproveita-se só a identidade técnica (`id`, `idTemp`, `status`, `parentType`);
  o `content` de tipo nativo vem do YAML; o de `Custom` continua o do Manager (V-11 §4);
- os números de `position` que o escopo já ocupa, mais `max + 1` para os novos, são redistribuídos na
  ordem do YAML, por execution point — sem renumerar 1..N (W-3);
- a conferência passa a comparar o publicado com o **fluxo declarado** (tipo, ordem e `content`
  normalizado), e não só com o payload.

### 8. Conformidade: posição e escopos herdados

A comparação por sequência transformava um item que só mudou de lugar em dois achados falsos — "não é
executado aqui" e "não existe na template". O par passa a ser reconhecido e vira um achado só:
"executa em outra posição: na template é o Nº, aqui é o Mº". Continua `WARNING`: a ordem muda o
comportamento.

Todos os escopos continuam comparados (D-13), mas o que só herda executa o fluxo do escopo acima e
repetiria os mesmos achados. Eles saem uma vez, no escopo dono do fluxo, com quantos recursos e rotas
também o executam. No caso real da 417, 23 achados viraram 2.

## Open Questions

Nenhuma. O `sen validate` grava na revisão 1 em `local` e na de `TARGET_REVISION_NUMBER` em
`pipeline` (confirmado pelo usuário em 2026-10-16); ausente em `pipeline`, assume 1.
