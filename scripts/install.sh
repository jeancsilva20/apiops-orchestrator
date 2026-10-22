#!/usr/bin/env bash
# Instala (ou atualiza) o `sen` em ~/.local/share/sen, coloca no PATH e configura a credencial.
# Uso, de dentro da pasta extraída do pacote:  ./install.sh
set -euo pipefail

ORIGEM="$(cd "$(dirname "$0")" && pwd)"
DESTINO="${HOME}/.local/share/sen"
BIN="${HOME}/.local/bin"
SEN_FILE="${DESTINO}/.sen"

credencial_atual() {
    [[ -f "$SEN_FILE" ]] || return 0
    grep -E '^[[:space:]]*SEN_CREDENTIALS=' "$SEN_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' \
        | sed -E "s/^[[:space:]]*['\"]?//; s/['\"]?[[:space:]]*$//"
}

# Base64 de `client_id:client_secret`, sem prefixo `Basic`.
credencial_valida() {
    local decodificado
    [[ -n "$1" ]] || return 1
    decodificado="$(printf '%s' "$1" | base64 -d 2>/dev/null)" || return 1
    [[ "$decodificado" == ?*:?* ]]
}

pedir_credencial() {
    local opcao id secret basic
    while true; do
        echo
        echo "Como você quer informar a credencial?"
        echo "  1) client_id e client_secret"
        echo "  2) Basic (Base64 já pronto)"
        read -r -p "Opção [1]: " opcao
        case "${opcao:-1}" in
            1)
                read -r -p "client_id: " id
                read -r -s -p "client_secret: " secret
                echo
                if [[ -z "$id" || -z "$secret" ]]; then
                    echo "client_id e client_secret são obrigatórios." >&2
                    continue
                fi
                CREDENCIAL="$(printf '%s:%s' "$id" "$secret" | base64 -w0)"
                ;;
            2)
                read -r -s -p "Basic: " basic
                echo
                CREDENCIAL="$(printf '%s' "$basic" | sed -E 's/^[[:space:]]*[Bb][Aa][Ss][Ii][Cc][[:space:]]+//; s/[[:space:]]+$//')"
                ;;
            *)
                echo "Opção inválida." >&2
                continue
                ;;
        esac
        if credencial_valida "$CREDENCIAL"; then
            return 0
        fi
        echo "Credencial inválida: o Basic deve ser o Base64 de client_id:client_secret." >&2
    done
}

if [[ ! -f "${ORIGEM}/sen" || ! -f "${ORIGEM}/.sen.example" ]]; then
    echo "Rode o install.sh de dentro da pasta extraída do pacote do sen." >&2
    exit 1
fi

CREDENCIAL="$(credencial_atual)"
if credencial_valida "$CREDENCIAL"; then
    read -r -p "Manter a credencial atual? [S/n]: " manter
    if [[ "${manter:-s}" =~ ^[nN] ]]; then
        pedir_credencial
    fi
else
    pedir_credencial
fi

mkdir -p "$DESTINO" "$BIN"
if [[ "$ORIGEM" != "$DESTINO" ]]; then
    install -m 755 "${ORIGEM}/sen" "${DESTINO}/sen"
    install -m 755 "${ORIGEM}/install.sh" "${DESTINO}/install.sh"
    install -m 644 "${ORIGEM}/.sen.example" "${DESTINO}/.sen.example"
fi
# O README passou a acompanhar os pacotes, fora deles: o de versões antigas sai.
rm -f "${DESTINO}/README.md"

# O .sen nasce sempre do gabarito da versão instalada, levando só a credencial.
(
    umask 077
    awk -v cred="$CREDENCIAL" '/^SEN_CREDENTIALS=/ { print "SEN_CREDENTIALS=\"" cred "\""; next } { print }' \
        "${DESTINO}/.sen.example" >"${SEN_FILE}.tmp"
)
mv -f "${SEN_FILE}.tmp" "$SEN_FILE"
chmod 600 "$SEN_FILE"

ln -sfn "${DESTINO}/sen" "${BIN}/sen"

ABRIR_TERMINAL=""
case ":${PATH}:" in
    *":${BIN}:"*) ;;
    *)
        LINHA='export PATH="$HOME/.local/bin:$PATH"'
        for rc in "${HOME}/.bashrc" "${HOME}/.zshrc"; do
            if [[ "$rc" == "${HOME}/.bashrc" || -f "$rc" ]] && ! grep -qsF "$LINHA" "$rc"; then
                printf '\n# sen\n%s\n' "$LINHA" >>"$rc"
            fi
        done
        ABRIR_TERMINAL="sim"
        ;;
esac

echo
echo "Instalado: $("${DESTINO}/sen" --version | head -1) em ${DESTINO}"
if [[ -n "$ABRIR_TERMINAL" ]]; then
    echo "Abra um terminal novo e rode: sen login"
else
    echo "Rode: sen login"
fi
