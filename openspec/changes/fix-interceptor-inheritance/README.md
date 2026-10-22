# fix-interceptor-inheritance

A publicação, a conformidade, a conferência pós-publicação e o importador passam a seguir a herança como o Manager a executa, medida em runtime em 21/10/2026 ([V-28](../../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md)): cada escopo guarda só os itens próprios e as marcações `REMOVED` do que deixa de herdar. `inherit: true` com itens deixa de duplicar o herdado, `inherit: false` marca também o item que entra no pai na mesma publicação, e `inherit: false` sem itens vira rota sem interceptors.
