"""Bridge for the batteries that still read the raw payload of the Manager.

The adapter answers `Api` and `Revision`; the batteries written before the models
read dicts. Wrapping the adapter here keeps them untouched until they migrate.
"""

from apiops_orchestrator.domain.models.api_model import as_wire


class WireManager:
    def __init__(self, inner):
        self._inner = inner

    def get_api_by_id(self, api_id):
        return as_wire(self._inner.get_api_by_id(api_id))

    def get_revision(self, revision_id):
        return as_wire(self._inner.get_revision(revision_id))

    def __getattr__(self, name):
        return getattr(self._inner, name)
