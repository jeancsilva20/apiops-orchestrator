# sen — Sensedia API Orchestrator CLI

CLI do APIOps Orchestrator. Requer Linux 64 bits com glibc 2.35 ou mais nova (Ubuntu 22.04+, Debian 12+, Fedora 36+); nada mais precisa estar instalado.

## Instalar

```bash
tar -xzf sen-<versão>-linux-x64.tar.gz
cd sen-<versão>-linux-x64
./install.sh
```

O instalador pede a credencial: `client_id` e `client_secret`, ou o Basic já pronto. Depois, abra um terminal novo.

## Usar

```bash
sen login
sen --help
```

## Atualizar ou trocar a credencial

- **Nova versão:** rode o `./install.sh` do pacote novo. A credencial e a sessão são mantidas.
- **Trocar a credencial:** rode `~/.local/share/sen/install.sh` e responda `n` em "Manter a credencial atual?".
