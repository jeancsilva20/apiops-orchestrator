---
name: sen-api-developer
description: >-
  Altera os arquivos YAML de um repositório de API do APIOps (api-basic-info.yaml, all.yaml,
  components.yaml e os arquivos em resources/) no formato que a CLI `sen` aceita, com o ok do usuário
  antes de escrever. Use sempre que o usuário pedir para criar, alterar ou remover rota, recurso,
  response, request body, parâmetro, backend (URL), timeout, interceptor, herança de interceptors,
  apiTags ou componente OpenAPI de uma API gerenciada pelo `sen`, mesmo sem citar arquivo nem o `sen`.
  Exemplos: "adiciona a rota GET /users/{id}/roles", "edita o response de sucesso da rota X pra esta
  estrutura", "muda o timeout do recurso token pra 30", "essa rota não deve executar o interceptor de
  log", "põe a apiTag Domínio = Pagamentos". Use também em pedidos que misturam consulta e mudança
  ("vê o timeout e aumenta pra 30") e para gravar na Draft e obter o veredito da governança. Não use
  para só consultar a API, as revisões ou a completude (use a sen-explore), nem para publicar, fazer
  deploy ou login.
---

# Editor de API com o `sen`

O repositório da API descreve uma API do Sensedia API Manager em arquivos YAML. A CLI `sen` lê esses arquivos, valida e grava no Manager. Seu trabalho é transformar o pedido do usuário numa mudança pequena, no formato que a CLI aceita, e só escrever depois que o usuário souber o que muda e quais são os riscos.

A CLI é a fonte da verdade. O formato e as regras de cada arquivo vêm do `sen schema`, e as mensagens de erro da CLI dizem o que corrigir. Não invente campo nem regra: consulte a CLI.

## Regras de convivência com o `sen`

- **Leia dados com `-o json`.** A saída em texto é para pessoas e muda de forma.
- **Nunca deixe um comando esperando resposta.** O `sen validate` pergunta "Deseja prosseguir?". Rode sempre com a resposta na entrada (`echo n |` ou `echo y |`). Sem resposta, ele sai com código 130 e você não fica sabendo de nada.
- **Não leia o `.sen` nem o `.sen_session`.** Eles guardam a credencial e a sessão do usuário. Você trabalha com a sessão que ele já abriu, sem ver o conteúdo.
- **Não rode `sen login`, `sen publish` nem `sen deploy`.** O login usa a credencial do usuário, então quem faz é ele. Publicação e deploy rodam só na esteira, e a própria CLI recusa fora dela.
- **Erro de sessão ou de configuração** (sessão ausente ou expirada, ou "Configuração incompleta"): peça ao usuário que configure o `sen` e rode `sen login`, e continue só com o que não precisa de rede.
- **Confira a CLI antes de começar.** Rode `sen schema --help`. Se aparecer "No such command", o `sen` instalado é antigo: peça ao usuário que atualize e pare.

## O ciclo

### 1. Localize o alvo

- Confirme que está num repositório de API: existe um `api-basic-info.yaml` na raiz. Se o repositório estiver em outra pasta, os comandos aceitam `--repo <pasta>`.
- Rode `sen diag structure -o json` para ver os recursos, as rotas (método e path) e o arquivo de cada uma. Ele roda sem rede.
- Uma rota é identificada pelo método e pelo path. O arquivo dela é `resources/<recurso>/<método>_<path>.yaml`, com `/` trocado por `_` (por exemplo, `GET /users/{username}/roles` fica em `get_users_{username}_roles.yaml`). O método vem do nome do arquivo e o path vem do campo `path`.
- Se o alvo não for único, liste os candidatos e pergunte, em vez de escolher. Por exemplo: a rota não existe, o path casa com mais de uma rota, ou o pedido diz "response de sucesso" e a rota tem 200 e 201. Escolher errado gera uma mudança que parece certa e não é.

### 2. Leia o schema do arquivo

Antes de criar ou alterar um arquivo, rode `sen schema <tipo>`. O tipo é `basic-info`, `all`, `components`, `resource` ou `operation`, e o `sen schema` sem argumento mostra qual arquivo é de qual tipo.

Leia as `description` dos campos. Elas trazem as regras, entre elas:
- a herança de interceptors (`inherit`);
- a `url` vazia, que herda do escopo acima;
- o `timeout` em segundos, escrito como texto;
- a recusa de extensões `x-*`;
- os campos que não podem mudar.

### 3. Monte o plano e peça o ok

Antes de escrever qualquer coisa, mostre:

```
Plano
1. <arquivo> — <criar | alterar | remover>: <o que muda, com o trecho novo quando for curto>
2. ...

Riscos
- <risco>: <o que acontece> (ou "Nenhum risco identificado")

Não muda: <o que fica como está e alguém poderia achar que mudaria>

Posso aplicar?
```

Espere o ok. Se o usuário ajustar o pedido, refaça o plano. Se ele já autorizou no próprio pedido ("pode aplicar direto"), mostre o plano e aplique. A exceção é um risco que ele não citou, como um componente compartilhado: nesse caso, pergunte mesmo assim, porque a autorização dele não cobria esse risco.

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
2. Rode o pré-check `echo n | sen validate`. Ele faz a leitura, a validação de contrato, a identidade, a régua e as apiTags, e para antes de gravar.
   - **Passou:** sai com código 0 e "Validação cancelada. Nada foi gravado.". O quadro de confirmação que aparece antes da pergunta traz os avisos do repositório: repasse ao usuário os que tratam do que você mudou.
   - **Erro:** a mensagem diz o arquivo e o que fazer. Corrija nos arquivos que você mudou e rode de novo. Se o erro estiver num arquivo que você não tocou, conte ao usuário em vez de corrigir por conta própria.
   - **Erro de sessão ou de configuração:** diga que só a conferência local rodou e que, depois de um `sen login`, o pré-check confere o resto.

### 6. Resuma

Diga quais arquivos mudaram, o que mudou em cada um e o resultado da conferência. O próximo passo é com o usuário: revisar o diff e commitar, ou pedir a gravação na Draft para ver o veredito da governança.

## Gravar na Draft (só a pedido)

O `sen validate` respondido com `y` grava o repositório na Draft da revisão alvo no Manager, e é assim que o usuário obtém o veredito da governança e a completude. Rode só quando ele pedir ("valida de verdade", "grava na Draft", "quero o veredito").

Antes de rodar:

1. Rode `sen diag draft -o json` para saber a revisão alvo.
2. Explique ao usuário:
   - a gravação vai para a revisão `<número>` (id `<id>`) no Manager da sessão aberta (o ambiente em que ele fez login);
   - o conteúdo dessa Draft passa a refletir o repositório, e o que foi mudado direto no Manager nessa revisão, e não está no repositório, se perde;
   - o swagger da revisão recebe o contrato OpenAPI do repositório;
   - nenhum ambiente recebe deploy.
3. Espere a confirmação.

Depois, rode `echo y | sen validate -o json`. Antes do JSON, a saída traz o quadro de confirmação e a pergunta: o documento começa no primeiro `{` depois de "Deseja prosseguir?". Resuma ao usuário:
- a conformidade com a régua (findings);
- a governança (liberada ou bloqueada, e o que falta);
- a completude (nota, mínimo e sugestões).

## Estrutura informada pelo usuário

Quando o usuário descreve um response ou um body, ele pode mandar um payload de exemplo, uma lista de campos, uma classe do código ou algo como "igual ao Usuario, sem o email". Converta para schema OpenAPI:

- Infira os tipos: texto vira `string`, inteiro vira `integer`, decimal vira `number`, `true`/`false` vira `boolean`, lista vira `array` com `items` e objeto vira `object` com `properties`. Se um valor vier `null` ou vazio e não der para saber o tipo, pergunte.
- Marque em `required` só os campos que o usuário disser que são obrigatórios. Obrigatoriedade inventada vira contrato errado para quem consome a API.
- Quando ele mandar um payload, guarde-o como `example`.

## Exemplos de pedido

| Pedido | O que muda |
|---|---|
| "adiciona a rota GET /users/{username}/roles no recurso user" | Arquivo novo `resources/user/get_users_{username}_roles.yaml` |
| "edita o response de sucesso do GET /users/{username} pra retornar username, nome e email" | O 2xx da rota, ou o componente que ele referencia (ver riscos) |
| "muda o timeout do recurso token pra 30 segundos" | `destination.timeout: "30"` no `resources/token/resource.yaml` |
| "troca a URL do backend da API por $backend_url" | `destination.url` no `all.yaml` |
| "a rota de validação não deve executar o interceptor de log herdado" | `inherit: false` e o fluxo completo que deve executar, na rota |
| "documenta 401 e 404 em todas as rotas do user" | `responses` no `components.yaml` e `$ref` em cada rota |
| "adiciona a apiTag Domínio = Pagamentos" | `apiTags` no `api-basic-info.yaml`. O catálogo de atributos só o pré-check confere |
