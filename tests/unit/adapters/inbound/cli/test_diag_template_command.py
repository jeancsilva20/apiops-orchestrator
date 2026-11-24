"""`sen diag template`: o unico comando que estava sem nenhum teste.

Era tambem o unico consumidor de `regua_service_factory` pela borda da CLI — a
chave do `ctx.obj` que nenhum teste tocava — e as suas 63 linhas eram o maior
trecho descoberto de `cli_adapter.py`. Passou despercebido porque esta no grupo
oculto `diag` e porque nada enumerava os comandos registrados; e exatamente o
buraco que `test_cli_tree_contract.py` e `test_option_matrix.py` passam a fechar.

Oculto nao e motivo para nao testar: o comando e alcancavel, le o repositorio
local e `PLANO-NAVEGACAO.md:27` o usa como oraculo de validacao.
"""

from __future__ import annotations

import json

import pytest
import yaml

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    TemplateNotConfiguredError,
)
from apiops_orchestrator.application.services.ruler_service import LoadedRuler
from sen_support.cli_fabricas import fabrica_que_falha
from sen_support.cli_fakes import servico

BASIC_INFO = (
    "apiVersion: api-management.sensedia.com/v1\n"
    "kind: ApiBasicInfo\n"
    "spec:\n"
    "  id: 417\n"
)


@pytest.fixture
def repo(tmp_path):
    """O minimo que o `RepoCanonicalReader` precisa para entregar `basic_info`."""
    (tmp_path / "api-basic-info.yaml").write_text(BASIC_INFO, encoding="utf-8")
    (tmp_path / "all.yaml").write_text("destination:\n  url: https://x\n", encoding="utf-8")
    pasta = tmp_path / "resources" / "tarefas"
    pasta.mkdir(parents=True)
    (pasta / "resource.yaml").write_text('name: "Tarefas"\n', encoding="utf-8")
    (pasta / "get_tarefas.yaml").write_text("path: /tarefas\n", encoding="utf-8")
    return tmp_path


def _regua(warnings=None) -> LoadedRuler:
    return LoadedRuler(
        template_id=414,
        revision_number=3,
        interceptors=[
            {"executionPoint": "FIRST", "type": "Log", "customInterceptorId": None},
            {"executionPoint": "SECOND", "type": "Custom", "customInterceptorId": 31},
        ],
        flow_hash="abc123",
        warnings=list(warnings or []),
    )


def _servico(regua=None, erro=None):
    fake = servico("regua")
    if erro is not None:
        fake.load.side_effect = erro
    else:
        fake.load.return_value = regua if regua is not None else _regua()
    return fake


def test_mostra_a_regua_o_fluxo_e_o_snapshot(repo, invoke_sen, uma_linha):
    fake = _servico()

    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], regua=fake)

    assert resultado.exit_code == 0, resultado.output
    texto = uma_linha(resultado)
    assert "API-template 414" in texto
    assert "revisão #3" in texto
    assert "2 interceptor(es)" in texto
    assert "abc123" in texto
    # O custom aparece com o id do catalogo colado ao tipo.
    assert "Custom#31" in texto
    assert "FIRST" in texto and "SECOND" in texto
    fake.load.assert_called_once()


@pytest.mark.parametrize("formato", ["json", "yaml"])
def test_saida_de_maquina_carrega_regua_fluxo_e_avisos(repo, invoke_sen, formato):
    fake = _servico(_regua(warnings=["a revisão do template mudou"]))

    resultado = invoke_sen(
        ["diag", "template", "--repo", str(repo), "-o", formato], regua=fake
    )

    assert resultado.exit_code == 0, resultado.output
    carregar = json.loads if formato == "json" else yaml.safe_load
    documento = carregar(resultado.output)

    assert documento["ruler"] == {
        "templateId": 414,
        "revisionNumber": 3,
        "flowHash": "abc123",
        "interceptorsCount": 2,
    }
    assert documento["warnings"] == ["a revisão do template mudou"]
    assert documento["flow"] == [
        {"executionPoint": "FIRST", "type": "Log", "customInterceptorId": None},
        {"executionPoint": "SECOND", "type": "Custom", "customInterceptorId": 31},
    ]


def test_aviso_da_regua_aparece_na_saida_de_texto(repo, invoke_sen, uma_linha):
    fake = _servico(_regua(warnings=["o template 414 nao tem revisão publicada"]))

    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], regua=fake)

    assert resultado.exit_code == 0, resultado.output
    texto = uma_linha(resultado)
    assert "WARNING" in texto
    assert "nao tem revisão publicada" in texto


def test_erro_de_regua_sai_com_a_mensagem_acionavel(repo, invoke_sen):
    """O `ValidateError` do servico atravessa com a sua mensagem, nao achatado."""
    fake = _servico(erro=TemplateNotConfiguredError())

    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], regua=fake)

    assert resultado.exit_code == TemplateNotConfiguredError.exit_code == 1
    texto = " ".join(resultado.output.split())
    assert "erro interno" not in texto.lower()
    assert TemplateNotConfiguredError().message.split(".")[0] in texto


def test_exit_code_proprio_da_excecao_e_respeitado(repo, invoke_sen):
    """Nem todo `ValidateError` sai com 1: o comando repassa o codigo da classe.

    `GovernanceBlockedError.exit_code` e 3 — achatar para 1 apagaria, na esteira,
    a diferenca entre "bloqueado pela governanca" e qualquer outra falha.
    """
    fake = _servico(erro=GovernanceBlockedError(139, 420, []))

    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], regua=fake)

    assert resultado.exit_code == 3


def test_erro_inesperado_nao_vaza_texto_cru(repo, invoke_sen):
    fake = _servico(erro=RuntimeError("token=segredo"))

    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], regua=fake)

    assert resultado.exit_code == 1
    assert "segredo" not in resultado.output
    assert "erro interno" in resultado.output.lower()


def test_fabrica_ausente_encerra_com_1(repo, invoke_sen):
    resultado = invoke_sen(["diag", "template", "--repo", str(repo)], obj={})

    assert resultado.exit_code == 1
    assert "indisponível" in resultado.output


def test_falha_ao_montar_o_servico_nao_vaza_texto_cru(repo, invoke_sen):
    """A fabrica existe mas explode ao ser chamada (config ausente, por exemplo)."""
    resultado = invoke_sen(
        ["diag", "template", "--repo", str(repo)],
        regua=fabrica_que_falha(RuntimeError("HOST=https://interno")),
    )

    assert resultado.exit_code == 1
    assert "interno" not in resultado.output.replace("erro interno", "")


def test_repo_sem_api_basic_info_nao_derruba_o_comando(tmp_path, invoke_sen):
    """Repositorio incompleto: o comando responde com erro tratado, nao stack trace."""
    fake = _servico()

    resultado = invoke_sen(["diag", "template", "--repo", str(tmp_path)], regua=fake)

    assert resultado.exit_code in (0, 1), resultado.output
    assert "Traceback" not in resultado.output
