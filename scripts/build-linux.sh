#!/usr/bin/env bash
# Gera o executável `sen` para Linux e o pacote de entrega em dist/.
#
# Roda dentro do WSL (Ubuntu 22.04, para o binário valer em distros com glibc >= 2.35).
# Do PowerShell, na raiz do repo:
#   wsl bash scripts/build-linux.sh <cliente>
#
# <cliente> é o nome de um arquivo de scripts/clients, sem o `.sen`.
#
# Copia só o necessário do repo para uma pasta do Linux (sem .sen/.sen_session/.env),
# monta um venv limpo, empacota com PyInstaller em arquivo único, confere que nenhum
# segredo entrou no binário e gera, em dist/sen-<versão>/<cliente>/, o
# sen-<versão>-<cliente>-linux-x64.tar.gz (o `sen`, o instalador, o `.sen.example` com os
# endereços do cliente e o README do dev, scripts/README-executavel.md, com a versão e o
# cliente preenchidos). O README vai dentro do tar.gz, o mesmo do pacote Windows.
set -euo pipefail

PYINSTALLER_VERSAO="6.22.3"
PYTHON="${PYTHON:-python3.12}"

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="${HOME}/.cache/sen-build"
FONTE="${BUILD}/fonte"
VENV="${BUILD}/venv"

# Nome de arquivo sensível numa linha do pyi-archive_viewer (nomes vêm entre aspas).
PADRAO_SENSIVEL="[\\/']\.(sen|sen_session[^']*|env)'"

CLIENT="${1:-}"
CLIENTS_DIR="${RAIZ}/scripts/clients"
CLIENT_FILE="${CLIENTS_DIR}/${CLIENT}.sen"
AVAILABLE="$(find "$CLIENTS_DIR" -maxdepth 1 -name '*.sen' -printf '%f\n' | sed 's/\.sen$//' | sort | paste -sd, - | sed 's/,/, /g')"
if [[ -z "$CLIENT" ]]; then
    echo "Informe o cliente: bash scripts/build-linux.sh <cliente>. Disponíveis: ${AVAILABLE}" >&2
    exit 1
fi
if [[ ! "$CLIENT" =~ ^[a-z0-9-]+$ || ! -f "$CLIENT_FILE" ]]; then
    echo "Cliente '${CLIENT}' não existe em scripts/clients. Disponíveis: ${AVAILABLE}" >&2
    exit 1
fi
# O checkout no Windows pode deixar o arquivo do cliente em CRLF.
CLIENT_BLOCK="$(tr -d '\r' <"$CLIENT_FILE")"
for KEY in AUTH_HOST AUTH_LOGIN_PATH; do
    if ! grep -qE "^${KEY}=[\"']?[^\"'[:space:]]" <<<"$CLIENT_BLOCK"; then
        echo "scripts/clients/${CLIENT}.sen não define ${KEY}." >&2
        exit 1
    fi
done
if grep -qE '^[[:space:]]*SEN_CREDENTIALS=' <<<"$CLIENT_BLOCK"; then
    echo "scripts/clients/${CLIENT}.sen não pode definir SEN_CREDENTIALS." >&2
    exit 1
fi

if ! command -v "$PYTHON" >/dev/null || ! command -v objdump >/dev/null; then
    cat >&2 <<'EOF'
Faltam dependências no Linux. Prepare uma vez (pede a senha do sudo):

  sudo apt-get update
  sudo apt-get install -y software-properties-common binutils
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get install -y python3.12 python3.12-venv python3.12-dev
EOF
    exit 1
fi

# O checkout no Windows deixa o pyproject.toml em CRLF: o `\r` sai antes de ler a versão.
VERSAO="$(tr -d '\r' <"${RAIZ}/pyproject.toml" | sed -n 's/^version = "\(.*\)"/\1/p' | head -1)"
NOME="sen-${VERSAO}-${CLIENT}-linux-x64"
echo "Gerando ${NOME}"

rm -rf "$BUILD"
mkdir -p "$FONTE"

echo "[1/5] Ambiente limpo"
tar -C "$RAIZ" \
    --exclude='.sen' --exclude='.sen_session*' --exclude='.env' --exclude='__pycache__' \
    -cf - pyproject.toml README.md requirements.txt src \
    | tar -C "$FONTE" -xf -
"$PYTHON" -m venv "$VENV"
PY="${VENV}/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "${FONTE}/requirements.txt"
"$PY" -m pip install --quiet --no-deps "$FONTE"
"$PY" -m pip install --quiet "pyinstaller==${PYINSTALLER_VERSAO}"

# Nunca coletar dados do pacote apiops_orchestrator (--collect-*/--add-data):
# na máquina de quem gera, o .sen e a .sen_session moram dentro dele.
echo "[2/5] PyInstaller"
"$PY" -m PyInstaller --onefile --clean --noconfirm --log-level WARN \
    --name sen \
    --copy-metadata apiops-orchestrator \
    --collect-data jsonschema_specifications \
    --specpath "$BUILD" \
    --workpath "${BUILD}/work" \
    --distpath "${BUILD}/out" \
    "${FONTE}/src/apiops_orchestrator/main.py"
EXE="${BUILD}/out/sen"

echo "[3/5] Conferindo que nenhum segredo entrou no binário"
CONTEUDO="$("${VENV}/bin/pyi-archive_viewer" --list --recursive "$EXE")"
if VAZADOS="$(grep -E "$PADRAO_SENSIVEL" <<<"$CONTEUDO")"; then
    echo "Arquivo sensível dentro do binário:" >&2
    echo "$VAZADOS" >&2
    exit 1
fi

echo "[4/5] Smoke test"
SAIDA="$("$EXE" --version)"
if ! grep -qF "$VERSAO" <<<"$SAIDA"; then
    echo "sen --version não respondeu ${VERSAO} (saída: ${SAIDA})" >&2
    exit 1
fi

echo "[5/5] Pacote"
PACOTE="${BUILD}/${NOME}"
ENTREGA="${RAIZ}/dist/sen-${VERSAO}/${CLIENT}"
mkdir -p "$PACOTE" "$ENTREGA"
install -m 755 "$EXE" "${PACOTE}/sen"
# Arquivos de texto saem em LF: o checkout no Windows pode tê-los em CRLF.
tr -d '\r' <"${RAIZ}/scripts/install.sh" >"${PACOTE}/install.sh"
# O .sen.example do pacote é o gabarito até a credencial, seguido dos endereços do cliente.
TEMPLATE="$(tr -d '\r' <"${RAIZ}/src/apiops_orchestrator/.sen.example")"
if ! grep -q '^SEN_CREDENTIALS=' <<<"$TEMPLATE"; then
    echo "O .sen.example não tem a linha SEN_CREDENTIALS=." >&2
    exit 1
fi
{
    sed '/^SEN_CREDENTIALS=/q' <<<"$TEMPLATE"
    echo
    echo "$CLIENT_BLOCK"
} >"${PACOTE}/.sen.example"
chmod 755 "${PACOTE}/install.sh"
chmod 644 "${PACOTE}/.sen.example"
# O README entra no tar.gz, com a versão e o cliente preenchidos, para os comandos funcionarem colados.
tr -d '\r' <"${RAIZ}/scripts/README-executavel.md" | sed "s/<versão>/${VERSAO}/g; s/<cliente>/${CLIENT}/g" >"${PACOTE}/README.md"
chmod 644 "${PACOTE}/README.md"
rm -f "${ENTREGA}/README.md"
TARBALL="${ENTREGA}/${NOME}.tar.gz"
tar -C "$BUILD" --owner=0 --group=0 -czf "$TARBALL" "$NOME"

echo "Pronto: ${TARBALL}"
