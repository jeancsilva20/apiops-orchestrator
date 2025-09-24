# Changelog
Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato segue **[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)**  
e este projeto adere a **[Semantic Versioning](https://semver.org/lang/pt-BR/)**.

> Convenção de mensagens (recomendado): **Conventional Commits**.  
> Use os tipos: `feat`, `fix`, `perf`, `refactor`, `docs`, `build`, `ci`, `test`, `chore`.  
> _Breaking changes_ devem incluir `!` (ex.: `feat!:`) **ou** `BREAKING CHANGE:` no rodapé.

---

## [Unreleased]
### Added
- 

### Changed
- 

### Fixed
- 

### Deprecated
- 

### Removed
- 

### Security
- 

---

## [v0.2.0] - 2025-09-24
### Added
- CLI `apiops` com subcomando `plan` para diff de recursos (Typer).
- Geração de **SBOM** (CycloneDX) no pipeline de CI.
- Template de PR padrão com checklist de qualidade.

### Changed
- Padronização de estilo com **ruff** + **black**; pre-commit habilitado.
- Empacotamento com `pyproject.toml` (PEP 621) e `uv/poetry` (conforme o projeto).

### Fixed
- Tratamento de timeouts do Manager API (retry com backoff exponencial).

### Security
- Varredura de segredos e SAST (semgrep/bandit) obrigatória no PR.

---

## [v0.1.0] - 2025-09-18
### Added
- Primeira versão do **apiops-orchestrator**:
  - Composição de templates (basic-api-info, interceptors, resources, overlays).
  - Validação de YAML e placeholders.
  - Comando `sync-openapi` (dry-run).

---

## Política de versões
- **MAJOR**: mudanças incompatíveis (breaking changes).
- **MINOR**: funcionalidades compatíveis.
- **PATCH**: correções compatíveis.

## Notas de release
- **Breaking changes** devem ser listadas no topo da versão, com instruções de migração.
- Mantenha “Unreleased” atualizado durante o desenvolvimento; ao lançar, mova as entradas para a nova versão e crie a **tag** correspondente.
- **Hotfixes**: versionar como `vX.Y.Z`, referenciando o(s) commit(s) de correção.

## Suporte de versão do Python
- Suportar versões **atualmente mantidas** pela PSF.  
- Remoções de suporte a versões EOL devem aparecer em **Deprecated/Removed** com aviso prévio em pelo menos **uma** versão MINOR.

## Como lançar (exemplo)
1. Atualize a versão em `pyproject.toml` (PEP 440), ex.: `version = "0.2.0"`.
2. Mova entradas de **Unreleased** para `v0.2.0` (com data).
3. Crie tag e publique:
   ```bash
   git commit -am "chore(release): v0.2.0"
   git tag v0.2.0
   git push origin main --tags
   ```
4. Gere/atualize o artefato e publique no registro desejado.

---

<!-- Links de comparação (ajuste owner/repo) -->
[Unreleased]: https://bitbucket.org/owner/repo/branches/compare/main..v0.2.0
[v0.2.0]: https://bitbucket.org/owner/repo/branches/compare/v0.2.0..v0.1.0
[v0.1.0]: https://bitbucket.org/owner/repo/commits/tag/v0.1.0