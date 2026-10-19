"""Erros de negócio do `sen validate`.

Contrato de borda, igual ao de `completeness_exceptions`: cada erro carrega
`message` (PT-BR, acionável) e `exit_code`. A CLI apenas **traduz** — não decide
severidade nem reescreve texto.

Os códigos de saída separam dois canais que a esteira precisa distinguir sem ler
texto humano:

    0  sucesso — inclui achados INFO/WARNING de régua e completeness abaixo do gate
    1  falha técnica ou de gramática
    3  bloqueio do Adaptive Governance

O `2` NÃO é usado: é o código que o Typer/Click reserva para erro de uso da
linha de comando, e o `sen completeness` já o ocupa com outra semântica.
"""

from typing import Any, Dict, List, Optional

from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    UNAVAILABLE_MESSAGE,
)


class ValidateError(Exception):
    """Base dos erros de negócio do `sen validate`."""

    exit_code = 1

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class IdentidadeDivergenteError(ValidateError):
    """`version` ou `basePath` do repositório divergem do Manager (D-11).

    Os dois definem a identidade funcional da API: divergência significa que o
    repositório pode estar apontado para outra API, e a operação aborta **antes**
    de qualquer escrita.
    """

    def __init__(self, campo: str, no_repo: str, no_manager: str, api_id: int):
        super().__init__(
            "Este repositório parece apontar para outra API. O "
            f"`{campo}` declarado aqui é {no_repo!r}, mas a API {api_id} no Manager "
            f"tem {no_manager!r} — e esse campo não muda depois que a API é criada.\n\n"
            "Confira o `id` em `api-basic-info.yaml`. Se o id estiver certo, só um "
            "administrador do Manager pode acertar o valor divergente.\n\n"
            "Nada foi publicado."
        )
        self.campo = campo
        self.no_repo = no_repo
        self.no_manager = no_manager
        self.api_id = api_id


class TemplateAusenteError(ValidateError):
    """`spec.template` vazio (D-12).

    A D-12 revogou o "vazio permitido" da V-11 §1: sem template não há régua, e
    sem régua não há validação.
    """

    def __init__(self):
        super().__init__(
            "Esta API ainda não tem uma API-template vinculada, e é a template que "
            "define o padrão contra o qual o `validate` compara.\n\n"
            "Preencha `spec.template` em `api-basic-info.yaml` com o id da template. "
            "Se não souber qual é, peça ao administrador do Manager."
        )


class LayoutInvalidoError(ValidateError):
    """Arquivo base ausente ou estrutura não reconhecida (V-18 §2.3).

    `all.yaml` e `resource.yaml` são obrigatórios **pelo nome exato**. A ausência
    aborta na E1, antes de rede: a raiz não herda de nenhum escopo, então publicar
    sem ela não preserva nada — apaga o fluxo da revision inteira.
    """

    def __init__(self, caminho_esperado: str, detalhe: Optional[str] = None):
        complemento = f" {detalhe}" if detalhe else ""
        super().__init__(
            f"Não encontrei o arquivo `{caminho_esperado}`, que é "
            f"obrigatório.{complemento}\n\n"
            "O nome precisa ser exatamente esse, inclusive maiúsculas e minúsculas. "
            "O comando parou antes de acessar o Manager."
        )
        self.caminho_esperado = caminho_esperado


class TemplateNaoConfiguradaError(ValidateError):
    """Na esteira, `TEMPLATE_API_ID` não está definida.

    É falha de configuração, não de rede: a esteira não deixa o repositório
    escolher a régua, então sem a variável não há contra o que comparar. É
    detectada antes de qualquer chamada ao Manager.
    """

    def __init__(self):
        super().__init__(
            "TEMPLATE_API_ID não está definida. Na esteira ela é obrigatória para o "
            "validate: é o id da API-template usada como padrão de comparação.\n\n"
            "Defina a variável na configuração da esteira e rode o comando "
            "novamente.\n\nNada foi publicado."
        )


class ArquivoIlegivelError(ValidateError):
    """Um arquivo do repositório existe, mas não pôde ser lido.

    Diferente do arquivo ausente: o dev precisa saber o que corrigir dentro dele
    — linha e coluna do erro de sintaxe —, não que ele "não foi encontrado".
    """

    def __init__(self, caminho: str, motivo: str):
        super().__init__(
            f"O arquivo `{caminho}` não pôde ser lido: {motivo}.\n\n"
            "Corrija o arquivo e rode o comando novamente. O comando parou antes de "
            "acessar o Manager."
        )
        self.caminho = caminho
        self.motivo = motivo


class RotaDuplicadaError(ValidateError):
    """Duas operações do repositório declaram a mesma rota (I-6).

    A rota `(método, path)` é a identidade da operação, e é por ela que cada
    pasta é ligada ao seu recurso no Manager (V-12a). Repetida, a ligação fica
    ambígua — por isso aborta na E1, antes de rede.
    """

    def __init__(self, repetidas: Dict[str, List[str]]):
        linhas: List[str] = []
        for rota, arquivos in repetidas.items():
            linhas.append(f"`{rota}`, declarada em:")
            linhas.extend(f"  - {arquivo}" for arquivo in arquivos)
        abertura = (
            "A rota abaixo está declarada em mais de um arquivo:"
            if len(repetidas) == 1
            else "As rotas abaixo estão declaradas em mais de um arquivo:"
        )
        super().__init__(
            abertura
            + "\n\n"
            + "\n".join(linhas)
            + "\n\nCada rota pertence a um único recurso. Mantenha um só arquivo para "
            "cada rota. O comando parou antes de acessar o Manager."
        )
        self.repetidas = repetidas


class CustomInexistenteError(ValidateError):
    """O repositório referencia um `Custom` que não existe no tenant (W-2).

    O catálogo é autoridade sobre existência: `404` significa ausente. O conteúdo
    **não** é reposto a partir de revisões antigas — isso ressuscitaria uma
    referência que um administrador apagou de propósito.
    """

    def __init__(self, custom_id: int, escopo: str):
        super().__init__(
            f"O interceptor Custom de id {custom_id}, declarado em {escopo}, não "
            "existe neste ambiente.\n\n"
            "Confira o id na lista de interceptors customizados do Manager.\n\n"
            "Nada foi publicado."
        )
        self.custom_id = custom_id
        self.escopo = escopo


class ReguaInalcancavelError(ValidateError):
    """O `GET` da API-régua falhou (P-2).

    Aborta nos dois modos de execução: é falha técnica, não divergência de padrão.
    Como a plataforma devolve **403** tanto para sessão expirada quanto para id de
    outro tenant — e **não** devolve 401 —, a mensagem nomeia as duas causas em vez
    de escolher uma.
    """

    def __init__(
        self,
        template_id: Any,
        status_code: Optional[int] = None,
        mensagem_padrao: Optional[str] = None,
    ):
        """`mensagem_padrao` é o texto da família da falha (classificação
        compartilhada do Manager); sem ele, a causa assume Manager indisponível.
        """
        if status_code == 404:
            causa = (
                "Essa API não existe neste Manager. Confira o id em "
                "`spec.template`, no `api-basic-info.yaml`."
            )
        elif status_code == 403:
            # Sessão expirada vem primeiro de propósito: é de longe a causa mais
            # comum e a única que o dev resolve sozinho. A plataforma devolve 403
            # para os dois casos, então a ordem é a única ajuda que podemos dar.
            causa = (
                "O acesso foi negado. Normalmente é sessão expirada: rode "
                "`sen login` e tente de novo. Se continuar negado, a template pode "
                "pertencer a outro ambiente."
            )
        else:
            causa = mensagem_padrao or UNAVAILABLE_MESSAGE
        super().__init__(
            f"Não consegui ler a API-template {template_id}, e sem ela não há "
            f"padrão para comparar. {causa}\n\n"
            "Nada foi publicado."
        )
        self.template_id = template_id
        self.status_code = status_code


class PublicacaoDivergenteError(ValidateError):
    """A plataforma aceitou (200) mas o estado publicado não corresponde ao enviado (W-8).

    HTTP 200 não é prova de sucesso: foram observadas três perdas silenciosas
    distintas sob 200. A conferência pós-publicação é obrigatória, e divergência
    é falha.
    """

    def __init__(self, divergencias: List[str]):
        # Lista em linhas, não `; `: com três ou mais divergências a frase única
        # vira um parágrafo corrido em que nada se distingue.
        listadas = (
            "\n".join(f"  - {d}" for d in divergencias)
            if divergencias
            else "  - diferença não detalhada"
        )
        super().__init__(
            "O Manager aceitou a publicação, mas o que ficou gravado não é o que "
            f"foi enviado:\n\n{listadas}\n\n"
            "Parte da alteração se perdeu no caminho. Confira o estado atual da "
            "revisão no Manager antes de publicar de novo."
        )
        self.divergencias = list(divergencias)


class GovernanceBlockedError(ValidateError):
    """Bloqueio do Adaptive Governance (V-23).

    Canal e código de saída próprios, para a esteira ramificar sem ler texto. O
    atributo faltante é **calculado** — `exigidos(mustHave) − presentes` —, nunca
    extraído de `messages[]`, que é texto livre.

    Quando o bloqueio só aparece no `PUT` (o workflow que valida não é o gravado
    na revisão — V-23 §3), o faltante não é calculável e a saída degrada para o
    repasse dos `motivos` da plataforma, literais: evidência, nunca fonte
    (V-23 §5, item 3 — "nunca engole o erro").
    """

    exit_code = 3

    def __init__(
        self,
        workflow_id: Optional[int],
        stage_id: Optional[int],
        missing: List[Dict[str, Any]],
        raw: Optional[Dict[str, Any]] = None,
        motivos: Optional[List[str]] = None,
    ):
        nomes = [str(m.get("name") or m.get("attributeId")) for m in missing]
        motivos = [m for m in (motivos or []) if m]
        # Cada item na sua linha: numa lista separada por vírgula, o nome
        # quebra no meio quando o terminal é estreito ("My \nnew") e fica
        # ilegível — justamente o dado que o dev precisa copiar.
        if nomes or not motivos:
            faltantes = (
                "\n".join(f"  - {nome}" for nome in nomes)
                if nomes
                else "  - atributo não identificado"
            )
            corpo = (
                "A governança do Manager não liberou a publicação. A API precisa ter "
                f"estes atributos antes de subir:\n\n{faltantes}\n\n"
                "Adicione em `apiTags`, no `api-basic-info.yaml`, e rode o comando "
                "novamente."
            )
        else:
            # O motivo é texto livre e não é só atributo faltante (completude,
            # por exemplo): não presumir o que o dev deve ajustar.
            listados = "\n".join(f"  - {motivo}" for motivo in motivos)
            corpo = (
                "A governança do Manager não liberou a publicação. Motivo informado "
                f"pela plataforma:\n\n{listados}\n\n"
                "Corrija conforme o motivo acima e rode o comando novamente."
            )
        onde = f"workflow {workflow_id}" + (
            f", stage {stage_id}" if stage_id is not None else ""
        )
        super().__init__(f"{corpo}\n\nNada foi publicado. ({onde})")
        self.workflow_id = workflow_id
        self.stage_id = stage_id
        self.missing = list(missing)
        self.raw = raw or {}
        self.motivos = motivos


class TagInvalidaError(ValidateError):
    """Tag declarada em `apiTags` que não existe na lista do atributo (pré-check).

    Aborta **antes** da escrita: o Manager aceita a gravação com 200 e apaga
    todas as `apiTags` da API, sem erro e sem a governança barrar. É erro de
    conteúdo do repositório, não bloqueio de governança — por isso `exit 1`.
    """

    def __init__(self, invalidas: List[Any]):
        listadas = "\n".join(
            f"  - `{i.tag}` em `{i.attribute_name}` "
            f"(tags possíveis: {', '.join(i.validas)})"
            for i in invalidas
        )
        super().__init__(
            "Estas tags não existem no atributo em que foram declaradas, em "
            f"`apiTags`:\n\n{listadas}\n\n"
            "Corrija o `api-basic-info.yaml` e rode o comando de novo.\n\n"
            "Nada foi publicado."
        )
        self.invalidas = list(invalidas)


class PublicacaoRecusadaError(ValidateError):
    """O Manager recusou a gravação do rascunho (`PUT` da revisão), fora da governança.

    É erro de subida: o motivo que a plataforma deu é o que o dev precisa para
    corrigir o repositório, então é exibido quando existe. Sem motivo, vale a
    mensagem padrão da família da falha (sessão, acesso, erro interno).
    """

    def __init__(
        self,
        mensagem_padrao: str,
        motivos: Optional[List[str]] = None,
        alvo: str = "do rascunho",
    ):
        # `alvo` nomeia o que foi gravado: o `validate` grava o rascunho; o
        # `publish`, a revisão de um ambiente.
        motivos = [m for m in (motivos or []) if m]
        if motivos:
            listados = "\n".join(f"  - {motivo}" for motivo in motivos)
            corpo = (
                f"O Manager recusou a gravação {alvo}:\n\n{listados}\n\n"
                "Corrija o repositório conforme o motivo acima e rode o comando de novo."
            )
        else:
            corpo = mensagem_padrao
        super().__init__(f"{corpo}\n\nNada foi publicado.")
        self.motivos = motivos
