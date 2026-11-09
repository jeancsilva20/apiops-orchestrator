---
name: sen-api-developer
description: >-
  Responde perguntas sobre o repositório local de uma API do Sensedia API Manager, os arquivos YAML
  que a CLI `sen` lê, e o altera. Use para perguntas
  sobre o que está nos arquivos (rotas, backend e timeout de cada rota, interceptors e herança,
  apiTags, componentes) e para criar, alterar ou remover dados da API (nome, versão, base path, descrição), apiTags, recurso, rota,
  response, request body, parâmetro, backend, timeout, interceptor ou componente OpenAPI, mesmo sem
  citar arquivo nem o `sen`, como em "pra qual backend vai cada rota?", "adiciona a rota GET
  /users/{id}/roles", "edita o response de sucesso da rota X pra esta estrutura" ou "essa rota não
  deve executar o interceptor de log". Use também para gravar na Draft e verificar a conformidade dos arquivos e da API. Não use para o que só o Manager sabe, como revisões, ambientes, completude, régua ou o
  conteúdo do que já está no gateway API Manager, nem para publicar, fazer deploy ou login.
---

# Desenvolvimento de API com o `sen`

O repositório da API descreve uma API do Sensedia API Manager em arquivos YAML. A CLI `sen` lê esses arquivos, valida e grava no Manager. Seu trabalho tem dois lados: responder o que está nos arquivos e transformar pedidos de mudança numa mudança pequena, no formato que a CLI aceita. Uma mudança com risco só é escrita depois que o usuário souber o que muda e quais são os riscos.

O escopo é o repositório. O que só o Manager sabe, como revisões, ambientes, régua ou o conteúdo da Draft, fica com a sen-explore. Completude e governança não são desta skill. O Manager só aparece aqui dentro do ciclo de mudança: no pré-check e na gravação na Draft.

A CLI é a fonte da verdade. O formato e as regras de cada arquivo vêm do `sen schema`, e as mensagens de erro da CLI dizem o que corrigir. Não invente campo nem regra: consulte a CLI.

## Regras de convivência com o `sen`

- **Leia dados com `-o json`.** A saída em texto é para pessoas e muda de forma.
- **Nunca deixe um comando esperando resposta.** O `sen validate` pergunta "Deseja prosseguir?". Rode sempre com a resposta na entrada (`echo n |` ou `echo y |`). Sem resposta, ele sai com código 130 e você não fica sabendo de nada.
- **Não leia o `.sen` nem o `.sen_session`.** Eles guardam a credencial e a sessão do usuário. Você trabalha com a sessão que ele já abriu, sem ver o conteúdo.
- **Não rode `sen login`, `sen publish` nem `sen deploy`.** O login usa a credencial do usuário, então quem faz é ele. Publicação e deploy rodam só na esteira, e a própria CLI recusa fora dela.
- **Prefira os comandos citados nesta skill.** Se o pedido precisar de algo que eles não cobrem, confira na ajuda (`sen --help` e `sen <comando> --help`) se existe comando ou opção para isso. Se não existir, diga ao usuário que o `sen` não faz isso hoje e pare, sem inventar comando nem opção. Um comando achado na ajuda que grava algo, ou que você não sabe se grava, só roda depois de perguntar ao usuário.
- **É proibido chamar a API do Manager por fora da CLI**, com curl, script ou qualquer outra requisição, mesmo quando nenhum comando atende o pedido.
- **Erro de sessão ou de configuração** (sessão ausente ou expirada, ou "Configuração incompleta"): peça ao usuário que configure o `sen` e rode `sen login`, e continue só com o que não precisa de rede.
- **Confira a CLI antes de começar.** Rode `sen schema --help`. Se aparecer "No such command", o `sen` instalado é antigo: peça ao usuário que atualize e pare.

## Como ler o repositório

- Confirme que está num repositório de API: existe um `api-basic-info.yaml` na raiz. Se o repositório estiver em outra pasta, os comandos aceitam `--repo <pasta>`.
- Rode `sen diag structure -o json` para ver os recursos, as rotas (método e path) e o arquivo de cada uma. Ele roda sem rede.
- Uma rota é identificada pelo método e pelo path. O arquivo dela é `resources/<recurso>/<método>_<path>.yaml`, com `/` trocado por `_` (por exemplo, `GET /users/{username}/roles` fica em `get_users_{username}_roles.yaml`). O método vem do nome do arquivo e o path vem do campo `path`.
- Para saber o que um campo significa e o que vale quando ele está vazio ou ausente, leia a `description` do campo em `sen schema <tipo>`. O tipo é `basic-info`, `all`, `components`, `resource` ou `operation`, e o `sen schema` sem argumento mostra qual arquivo é de qual tipo.

**Valores efetivos.** Backend (`destination.url`), timeout e interceptors podem vir da rota, do `resource.yaml` do recurso ou do `all.yaml`, nessa ordem de precedência.
- Para responder "pra qual backend vai", aplique a regra de herança que a descrição do campo no `sen schema` traz, e diga de onde o valor veio: declarado na rota, herdado do recurso ou herdado do `all.yaml`.
- Valores como `$backend_url` são variáveis de ambiente do Manager, resolvidas em cada ambiente. Mostre o nome da variável, sem inventar o valor.
- Para o fluxo de interceptors de uma rota, siga a regra do `inherit` descrita no `sen schema operation` e no `sen schema resource`, e liste o que vem de cada escopo.

## Perguntas

- **Uma pergunta não vira mudança.** Responda com o que está nos arquivos, sem editar nada. Se uma mudança parecer útil, sugira, e só entre no ciclo se o usuário pedir. Ele fez uma pergunta: uma escrita no meio da resposta seria uma surpresa.
- **Diga que os dados vêm do repositório local.** Nenhum comando traz os detalhes das rotas de uma API no Manager: o `sen diag draft` mostra só o método e o path das rotas da Draft. Se o usuário perguntar das rotas de uma API sem ter o repositório dela, ou de uma revisão publicada, diga que o `sen` não mostra isso hoje.
- **Se a resposta depender do Manager**, use a sen-explore. Se ela não estiver instalada, diga ao usuário que esta skill responde só pelo repositório.

## O ciclo

Para pedidos de mudança, acompanhe as etapas com este checklist. Ele evita pular a confirmação ou a conferência, que são as etapas que protegem o usuário:

```
- [ ] 1. Alvo localizado
- [ ] 2. Schema lido
- [ ] 3. Riscos procurados (com risco: plano mostrado e ok recebido)
- [ ] 4. Edição mínima feita
- [ ] 5. Conferência passou (diag structure e pré-check)
- [ ] 6. Resumo entregue
```

### 1. Localize o alvo

- Criar uma API do zero ainda não é coberto por esta skill, porque o `sen validate` só trabalha com uma API que já existe no Manager. Se o pedido for esse, diga isso ao usuário e pare.
- Ache o arquivo da rota ou do recurso como em "Como ler o repositório".
- Quando o pedido consulta antes de mudar ("vê o timeout e aumenta"), responda com o que está no repositório, como numa pergunta, e siga o ciclo para a mudança.
- Se o alvo não for único, liste os candidatos e pergunte, em vez de escolher. Por exemplo: a rota não existe, o path casa com mais de uma rota, ou o pedido diz "response de sucesso" e a rota tem 200 e 201. Escolher errado gera uma mudança que parece certa e não é.

### 2. Leia o schema do arquivo

Antes de criar ou alterar um arquivo, rode `sen schema <tipo>` do tipo desse arquivo e leia as `description` dos campos. Elas trazem as regras, entre elas:
- a herança de interceptors (`inherit`);
- a `url` vazia, que herda do escopo acima;
- o `timeout` em segundos, escrito como texto;
- a recusa de extensões `x-*`;
- os campos que não podem mudar.

### 3. Procure os riscos e, se houver, peça o ok

Antes de escrever, procure os riscos da tabela abaixo.

- **Sem risco, com alvo identificado (sem ambiguidade) e com tudo o que a mudança precisa no pedido ou nos arquivos:** aplique direto e mostre no resumo o que mudou. Por exemplo, trocar um timeout ou incluir um campo num componente que só essa rota usa. A mudança é local e o usuário a revisa no diff.
- **Falta informação ou o alvo é ambíguo:** pergunte, em vez de supor. Por exemplo, o backend ou o response de uma rota nova, ou "a rota de token" quando há duas. Um valor suposto vira contrato.
- **Com risco:** mostre o plano e espere o ok. Um risco muda mais do que o usuário pediu, como outras rotas ou o fluxo herdado, e ele precisa saber antes.

Se o usuário pedir para ver o plano antes de toda mudança, faça isso também nas mudanças sem risco.

O plano:

```
Plano
1. <arquivo> — <criar | alterar | remover>: <o que muda, com o trecho novo quando for curto>
2. ...

Riscos
- <risco>: <o que acontece> (ou "Nenhum risco identificado")

Não muda: <o que fica como está e alguém poderia achar que mudaria>

Posso aplicar?
```

Espere o ok. Se o usuário ajustar o pedido, refaça o plano. Um "pode aplicar direto" no pedido não dispensa a pergunta sobre um risco que ele não citou, como um componente compartilhado, porque a autorização dele não cobria esse risco.

**Riscos que você precisa procurar e nomear:**

| Situação | Por que importa | Como conferir |
|---|---|---|
| Componente usado por outras rotas | Mudar `#/components/...` muda todas as rotas que o referenciam | Procure o `$ref` exato em `resources/` e no `components.yaml`. Se outra rota usa, pergunte: mudar para todas ou criar um componente novo só para esta rota |
| `inherit: false` | A rota (ou recurso) deixa de executar todo o fluxo herdado e executa só o que declara | Leia o fluxo do `all.yaml` e do `resource.yaml` e liste os interceptors que deixam de executar e os que passam a ser declarados |
| Remoção | Rota, response ou parâmetro somem do contrato. `apiTags: []` remove todas as apiTags no Manager, e `apiTags` ausente as mantém | Diga o que some |
| `apiResponsible` | A alteração não é publicada | Avise antes de mudar |
| `id`, `version` ou `basePath` do `api-basic-info.yaml` | O `sen validate` aborta quando divergem do Manager | Não altere. Explique que essa mudança é feita no Manager |

### 4. Edite o mínimo

- Altere só o que o pedido exige. Mantenha os outros códigos de response, as descrições, os comentários e a ordem das chaves. Edite o texto no lugar, sem reescrever o arquivo inteiro a partir de um YAML carregado, porque isso apaga comentários e reordena chaves.
- Siga o estilo do repositório. Se as rotas vizinhas usam `$ref` para `components.yaml`, faça igual. Se escrevem o schema dentro da própria rota, faça igual.
- Não use `$ref` em `parameters` de rota nem de recurso: eles são escritos por inteiro.

### 5. Confira

1. Rode `sen diag structure -o json`. Ele precisa mostrar `completo: true`, sem nada em `faltando`, `ignorados` nem `ilegiveis`, e a rota nova (se houver) com o método e o path certos.
2. Rode o pré-check `echo n | sen validate -o json`. Ele faz a leitura, a validação de contrato, a identidade, a régua e as apiTags, e para antes de gravar.
   - **Passou:** sai com código 0 e "Validação cancelada. Nada foi gravado.". O quadro de confirmação que aparece antes da pergunta traz os avisos do repositório: repasse ao usuário os que tratam do que você mudou.
   - **Erro:** a mensagem, em texto, diz o arquivo e o que fazer. Corrija nos arquivos que você mudou e rode as duas conferências de novo, até passarem. Se o erro estiver num arquivo que você não tocou, conte ao usuário em vez de corrigir por conta própria.
   - **Erro de sessão ou de configuração:** diga que só a conferência local rodou e que, depois de um `sen login`, o pré-check confere o resto.

### 6. Resuma

Diga quais arquivos mudaram, o que mudou em cada um e o resultado da conferência. O próximo passo é com o usuário: revisar o diff e commitar, ou pedir a gravação na Draft para ver o resultado da validação no Manager.

## Gravar na Draft (só a pedido)

O `sen validate` respondido com `y` grava o repositório na Draft da revisão alvo no Manager, e é assim que o usuário obtém o resultado da validação no Manager. Rode só quando ele pedir ("valida de verdade", "grava na Draft", "quero o veredito").

Antes de rodar:

1. Rode `sen diag draft -o json` para saber a revisão alvo.
2. Explique ao usuário:
   - a gravação vai para a revisão `<número>` (id `<id>`) no Manager da sessão aberta (o ambiente em que ele fez login);
   - o conteúdo dessa Draft passa a refletir o repositório, e o que foi mudado direto no Manager nessa revisão, e não está no repositório, se perde;
   - o swagger da revisão recebe o contrato OpenAPI do repositório;
   - nenhum ambiente recebe deploy.
3. Espere a confirmação.

Depois, rode `echo y | sen validate -o json`. Antes do JSON, a saída traz o quadro de confirmação e a pergunta: o documento começa no primeiro `{` depois de "Deseja prosseguir?". Resuma ao usuário o que vier no resultado:
- a conformidade com a régua (findings);
- a governança (liberada ou bloqueada, e o que falta), se vier;
- a completude (nota, mínimo e sugestões), se vier.

Governança e completude dependem do Adaptive Governance, que nem todo cliente tem. Se não vierem no resultado, não fale delas.

## Estrutura informada pelo usuário

Quando o usuário descreve um response ou um body, ele pode mandar um payload de exemplo, uma lista de campos, uma classe do código ou algo como "igual ao Usuario, sem o email". Converta para schema OpenAPI:

- Se um valor vier `null` ou vazio e não der para saber o tipo, pergunte, em vez de chutar.
- Marque em `required` só os campos que o usuário disser que são obrigatórios. Obrigatoriedade inventada vira contrato errado para quem consome a API.
- Quando ele mandar um payload, guarde-o como `example`.

## Exemplos de pedido

| Pedido | O que muda |
|---|---|
| "pra qual backend vai cada rota?" | Nada: responda pelos arquivos, com a origem de cada valor |
| "qual a nota da última revisão?" | Nada: é do Manager. Use a sen-explore |
| "adiciona a rota GET /users/{username}/roles no recurso user" | Arquivo novo `resources/user/get_users_{username}_roles.yaml` |
| "edita o response de sucesso do GET /users/{username} pra retornar username, nome e email" | O 2xx da rota, ou o componente que ele referencia (ver riscos) |
| "muda o timeout do recurso token pra 30 segundos" | `destination.timeout: "30"` no `resources/token/resource.yaml` |
| "troca a URL do backend da API por $backend_url" | `destination.url` no `all.yaml` |
| "a rota de validação não deve executar o interceptor de log herdado" | `inherit: false` e o fluxo completo que deve executar, na rota |
| "documenta 401 e 404 em todas as rotas do user" | `responses` no `components.yaml` e `$ref` em cada rota |
| "adiciona a apiTag Domínio = Pagamentos" | `apiTags` no `api-basic-info.yaml`. O catálogo de atributos só o pré-check confere |
| "cadastra um app pra consumir essa API" | Nada: nenhum arquivo nem comando faz isso. Diga que o `sen` não faz isso hoje |
