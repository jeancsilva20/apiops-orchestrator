"""Revisions of an API, read from `revisions[]` of `GET /apis/{id}`.

The target revision is always resolved by its NUMBER, the one the human sees in
the Manager (V-24); the id is a transport detail resolved here, at the last
moment. Pure logic over the raw payload: the use cases decide the message and
the exit code when nothing is found.
"""

from typing import Any, Dict, List, Optional


def revisions(api: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The revision summaries of the API, in the order the Manager lists them."""
    return [r for r in ((api or {}).get("revisions") or []) if isinstance(r, dict)]


def revision_by_number(api: Dict[str, Any], number: int) -> Optional[Dict[str, Any]]:
    """The summary whose `revisionNumber` is `number` and that has an `id`, or `None`."""
    for revision in revisions(api):
        if revision.get("revisionNumber") == number and revision.get("id") is not None:
            return revision
    return None


def revision_numbers(api: Dict[str, Any]) -> List[Any]:
    """The `revisionNumber` of each revision, for the messages that list them."""
    return [r.get("revisionNumber") for r in revisions(api)]
