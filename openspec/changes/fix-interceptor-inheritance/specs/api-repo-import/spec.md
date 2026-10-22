## MODIFIED Requirements

### Requirement: Import materializes removals as complete explicit lists

Quando o estado remoto indicar que um escopo deixa de executar um item herdado, o importador SHALL
gravar `inherit: false` com **a lista completa** dos itens que valem: o herdado não marcado, depois
os itens próprios. O importador MUST NOT registrar a remoção apenas em comentário, porque comentário
não é publicável e a republicação perderia a remoção.

Escopo com itens próprios e sem marcações SHALL ser materializado com `inherit: true` e os itens
próprios, porque na plataforma ele executa o herdado e depois os próprios. Escopo em que todo o
herdado está marcado e não há itens próprios SHALL ser materializado com `inherit: false` sem itens,
que significa escopo sem interceptors. Em todos os casos, publicar o repositório de volta MUST NOT
mudar o que cada escopo executa.

#### Scenario: Remoção vira lista, não comentário
- **WHEN** uma rota remota executa oito dos nove itens herdados
- **THEN** o arquivo da operação declara `inherit: false` com os oito itens, e nenhum comentário é a
  única fonte da remoção

#### Scenario: Lista própria sem marcações vira append
- **WHEN** uma rota remota tem um item próprio e nenhuma marcação
- **THEN** o arquivo declara `inherit: true` com esse item, e publicar o repositório de volta mantém
  a rota executando o herdado e depois o item

#### Scenario: Tudo marcado e nada próprio
- **WHEN** uma rota remota marca todos os itens herdados e não tem itens próprios
- **THEN** o arquivo declara `inherit: false` sem itens, com comentário dizendo que o ponto não
  executa nenhum interceptor
