# =========================
# 🏗️ STAGE 1 — BUILD
# =========================
FROM python:3.12-slim AS stage1 

# 2. Definir diretório de trabalho
WORKDIR /app

# 3. Copiar arquivos de dependências primeiro (para cache de build)
COPY pyproject.toml poetry.lock ./ 

# 4. Instalar Poetry
RUN pip install --no-cache-dir poetry

# 5. Instalar dependências via Poetry
# Sem criar virtualenv extra, apenas no container
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --without dev
    
# 6. Copiar todo o código-fonte
COPY . . 

# =========================
# 🚀 STAGE 2 — RUNTIME
# =========================
FROM python:3.12-slim AS stage2


# 7. Adicionar metadados para rastreabilidade e boas práticas
LABEL maintainer="Seu Nome <seu.email@sensedia.com>" \
      org.opencontainers.image.title="apiops-orchestrator" \
      org.opencontainers.image.description="Orquestrador APIOps com suporte a execução via container Docker." \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Sensedia" 

# 8. Definir diretório de trabalho no runtime
WORKDIR /app

# 9. Copiar apenas o necessário do builder (sem dependências extras)
COPY --from=stage1 /app /app 

# 10. Definir usuário não-root (melhor segurança)
RUN useradd -m appuser
USER appuser

# 11. Comando padrão (ajuste conforme o entrypoint real)
CMD ["python", "-m", "apiops_cli_exemplo"]