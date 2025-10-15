# apiops-orchestrator

Orquestrador APIOps em Python para compor, validar, planejar e aplicar mudanças de APIs no Sensedia Manager a partir de artefatos (ex.: OpenAPI). O código segue princípios de Arquitetura Hexagonal (adapters, application, domain, infrastructure).

> Status: em desenvolvimento

## Sumário
- [Visão Geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Como Rodar](#como-rodar)
- [Estrutura de Pastas](#estrutura-de-pastas)
- [Tecnologias](#tecnologias)
- [Contribuidores](#contribuidores)

## Visão Geral

O Orquestrador APIOps é uma ferramenta em Python para compor, validar e processar artefatos de API (ex.: OpenAPI) para o Sensedia Manager. Atualmente, o projeto opera como um script que requer configuração manual para validar a estrutura de repositórios de API. A interface de linha de comando (CLI) foi temporariamente desativada para focar no desenvolvimento da lógica de negócio principal.

## Funcionalidades

- **Validação de Estrutura:** Verifica se a pasta de artefatos (`artifacts`) de um repositório de API segue as regras de estrutura de pastas e arquivos pré-definidas.
- **Importação de Arquivos:** Lista todos os caminhos de arquivo dentro da pasta de artefatos para processamento futuro.

## Como Rodar

### Pré-requisitos
- Python 3.10+
- Poetry (gerenciador de dependências)

### 1. Instalação

1.  **Instale o Poetry** (caso ainda não o tenha):
    Siga as instruções oficiais de instalação para o seu sistema operacional [aqui](https://python-poetry.org/docs/#installation).

2.  **Clone o repositório** (se ainda não o fez):
    ```bash
    git clone https://bitbucket.org/sensedia/apiops-orchestrator
    cd apiops-orchestrator
    ```

3.  **Instale as dependências do projeto**:
    O Poetry criará um ambiente virtual automaticamente e instalará tudo o que é necessário.
    ```bash
    poetry install
    ```

### 2. Configuração

Antes de executar, você **precisa** configurar o caminho do repositório da API que deseja processar.

1.  Abra o arquivo `src/apiops_orchestrator/main.py`.
2.  Encontre e edite a variável `repo_cep` para que aponte para o **caminho absoluto** do seu repositório de API local (ex: `api-repo-cep`).
    ```python
    repo_cep = Path(
        r"C:\caminho\absoluto\para\seu\api-repo-cep"  # Mude aqui o repositório na sua máquina.
    )
    ```

### 3. Execução

Execute o script a partir da raiz do projeto:
```bash
poetry run python src/apiops_orchestrator/main.py
```
O script irá imprimir a localização da pasta de artefatos, validar sua estrutura e listar os arquivos encontrados.

### Testes

Para rodar os testes de unidade, execute:
```bash
pytest
```

## Estrutura de Pastas
- `src/apiops_orchestrator/main.py` — Ponto de entrada principal do script de orquestração.
- `src/apiops_orchestrator/config/settings.py` — Configurações e variáveis de ambiente.
- `src/apiops_orchestrator/adapters/*` — Camadas de adaptação (inbound/outbound).
- `src/apiops_orchestrator/application/*` — Casos de uso e serviços da aplicação.
- `src/apiops_orchestrator/domain/*` — Modelos, portas e serviços de domínio.
- `src/apiops_orchestrator/infrastructure/*` — Integrações de infraestrutura.
- `tests/unit/...` — Testes de unidade.

## Tecnologias
- Python 3.10+
- Pydantic Settings (configuração por ambiente/.env)
- Pytest (testes)
- Poetry (gerenciamento de dependências)

## Contribuidores
- Augusto
- Danilo Amaral
- Matheus Alves Giroto

---
Consulte também `CHANGELOG.md` para o histórico de mudanças.

