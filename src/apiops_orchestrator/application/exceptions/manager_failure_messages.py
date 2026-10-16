"""Standard PT-BR texts of the Manager failure families.

Kept next to the exception hierarchies (not in a service) so that every
command's exceptions can reuse them without depending on the service layer.
The family → text mapping lives in `manager_failure_translator`.
"""

INTERNAL_ERROR_MESSAGE = (
    "Ocorreu um erro interno na consulta. Tente novamente em instantes; "
    "se persistir, acione o suporte."
)

UNAUTHORIZED_MESSAGE = "Sessão inválida ou expirada. Faça `sen login` novamente."

# The platform also answers 403 for an expired session (see ReguaInalcancavelError),
# so the message names re-login first, the only cause the user fixes alone.
FORBIDDEN_MESSAGE = (
    "Acesso negado pelo Manager. Rode `sen login` e tente de novo; "
    "se continuar negado, acione o time de acesso."
)

UNAVAILABLE_MESSAGE = (
    "Manager indisponível no momento. Verifique sua rede e tente novamente "
    "em instantes."
)
