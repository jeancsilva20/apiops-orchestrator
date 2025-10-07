# 1. Base leve do Python
FROM python:3.12-slim

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

# 7. Configurar variáveis de ambiente (opcional)
# Se tiver .env no projeto, o usuário pode usar --env-file no docker run
# Exemplo:
# docker run --env-file .env -it meu-projeto:latest
# Não é recomendado copiar o .env direto no Dockerfile por segurança

# 8. Comando padrão do container
# Substitua 'seu_modulo_cli' pelo entrypoint real do seu CLI
CMD ["poetry", "run", "python", "-m", "seu_modulo_cli"]

# 9. Para rodar testes dentro do container:
# docker run --rm -it meu-projeto:latest poetry run pytest
