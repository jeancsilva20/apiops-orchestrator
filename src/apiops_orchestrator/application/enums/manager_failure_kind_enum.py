from enum import Enum


class ManagerFailureKind(str, Enum):
    """Family of a Manager failure, shared by every command that queries it.

    The family decides the user-facing message; the exit code stays with each
    command's own exception hierarchy.
    """

    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    INTERNAL = "internal"
    UNAVAILABLE = "unavailable"
