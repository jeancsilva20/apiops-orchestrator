#!/usr/bin/env python
"""Regenera a arvore canonica de referencia em `tests/fixtures/repos/`.

O oraculo de `tests/unit/domain/services/test_materializer_oracle.py` compara o
que `materialize()` produz com uma arvore **commitada**. Essa arvore vivia em
`docs/feat-api-estructure/.../exemplos-gerados/saida/`, fora do repositorio: o
`.gitignore` exclui `/docs/` por politica (a documentacao mora em
`../apiops-docs`). Resultado: num clone limpo a comparacao era contra um dict
vazio e o teste falhava sempre, enquanto os irmaos com `skipif` ficavam
permanentemente skipados — escondendo o problema.

Atualizar o golden passa a ser um commit revisavel, nunca efeito colateral de
rodar a suite:

    python scripts/gerar-arvore-de-referencia.py           # confere (exit 1 se divergir)
    python scripts/gerar-arvore-de-referencia.py --write    # reescreve e mostra o que mudou

Rode com `--write` apenas quando a mudanca de saida for INTENCIONAL, e revise o
diff: ele e a unica prova de que a materializacao mudou de proposito.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from apiops_orchestrator.domain.services.repo_materializer import materialize  # noqa: E402

FIXTURES = RAIZ / "tests" / "fixtures" / "manager"
DESTINO = RAIZ / "tests" / "fixtures" / "repos"
CASOS = ("api-417-rev2", "api-400-rev4")


def arvore(nome: str) -> dict[str, str]:
    dados = json.loads((FIXTURES / f"{nome}.json").read_text(encoding="utf-8"))
    resultado = materialize(dados["api"], dados["revision"])
    return {arquivo.file_path: arquivo.text for arquivo in resultado.files}


def commitada(nome: str) -> dict[str, str]:
    base = DESTINO / nome
    if not base.is_dir():
        return {}
    return {
        str(p.relative_to(base)).replace("\\", "/"): p.read_text(encoding="utf-8")
        for p in base.rglob("*.yaml")
    }


def escrever(nome: str, arquivos: dict[str, str]) -> None:
    base = DESTINO / nome
    if base.is_dir():
        shutil.rmtree(base)
    for caminho, texto in arquivos.items():
        alvo = base / caminho
        alvo.parent.mkdir(parents=True, exist_ok=True)
        # newline="" + \n: o checkout e Windows e nao ha regra para *.yaml no
        # .gitattributes; sem isso o golden oscilaria entre CRLF e LF.
        with alvo.open("w", encoding="utf-8", newline="") as fh:
            fh.write(texto)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="reescreve a arvore")
    args = parser.parse_args()

    divergiu = False
    for nome in CASOS:
        gerado, atual = arvore(nome), commitada(nome)
        if gerado == atual:
            print(f"{nome}: {len(gerado)} arquivos, sem diferenca")
            continue
        divergiu = True
        novos = sorted(set(gerado) - set(atual))
        sumidos = sorted(set(atual) - set(gerado))
        mudados = sorted(c for c in set(gerado) & set(atual) if gerado[c] != atual[c])
        print(
            f"{nome}: {len(gerado)} arquivos gerados; "
            f"+{len(novos)} -{len(sumidos)} ~{len(mudados)}"
        )
        for rotulo, lista in (("novo", novos), ("sumiu", sumidos), ("mudou", mudados)):
            for caminho in lista:
                print(f"  {rotulo}: {caminho}")
        if args.write:
            escrever(nome, gerado)
            print(f"  -> {DESTINO / nome} reescrito")

    if divergiu and not args.write:
        print("\nDivergencia. Se for intencional: --write e commite o diff.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
