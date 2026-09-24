import json
from pathlib import Path
from typing import List

import pytest

from apiops_orchestrator.domain.models.api_collection_model import (
    ApiCollection,
    InvalidWindowError,
    last_revision_number,
    life_cycle_of,
)

FIXTURE_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "apis_sample.json"
VISIBILITY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[3] / "fixtures" / "apis_visibility_sample.json"
)


def _load_fixture() -> List[dict]:
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_visibility_fixture() -> List[dict]:
    with open(VISIBILITY_FIXTURE_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def collection() -> ApiCollection:
    return ApiCollection.from_raw(_load_fixture())


class TestFilteredBy:
    def test_accent_folded_match_case_insensitive(self, collection):
        rows = collection.filtered_by("autenticacao").rows()
        names = [row["name"] for row in rows]

        assert "Autenticação do Consumidor" in names
        assert "Orchestrator Auth API" in names

    def test_matches_description_field(self, collection):
        rows = collection.filtered_by("entregas").rows()

        assert [row["id"] for row in rows] == [512]

    def test_no_results_yields_empty_collection(self, collection):
        assert len(collection.filtered_by("zzz-inexistente")) == 0

    def test_none_query_is_no_op_preserving_order(self, collection):
        passthrough = collection.filtered_by(None)

        assert passthrough.rows() == collection.rows()


class TestSortedById:
    def test_fixture_arrives_shuffled_sorted_output_asc(self, collection):
        ids_before = [row["id"] for row in collection.rows()]
        ids_after = [row["id"] for row in collection.sorted_by_id().rows()]

        assert ids_before == [400, 530, 312, 512, 401]
        assert ids_after == [312, 400, 401, 512, 530]

    def test_non_numeric_ids_go_last(self):
        messy = [{"id": "abc", "name": "A"}, {"id": 7, "name": "B"}, {"name": "C"}]

        ids = [row["name"] for row in ApiCollection(messy).sorted_by_id().rows()]

        assert ids == ["B", "A", "C"]


class TestWindow:
    def test_window_slices_after_position(self, collection):
        ids = [row["id"] for row in collection.window(offset=2, limit=2).rows()]

        assert ids == [312, 512]

    def test_offset_beyond_total_returns_empty_zero_error(self, collection):
        assert len(collection.window(offset=99, limit=5)) == 0

    def test_limit_below_or_equal_zero_raises_domain_error(self, collection):
        with pytest.raises(InvalidWindowError):
            collection.window(offset=0, limit=0)
        with pytest.raises(InvalidWindowError):
            collection.window(offset=1, limit=-3)

    def test_negative_offset_raises_domain_error_symmetric_with_limit(self, collection):
        with pytest.raises(InvalidWindowError):
            collection.window(offset=-1, limit=5)
        with pytest.raises(InvalidWindowError):
            collection.window(offset=-2)

    def test_zero_offset_is_accepted_start_of_page(self, collection):
        ids = [row["id"] for row in collection.window(offset=0, limit=2).rows()]

        # Fixture chega embaralhada ([400, 530, ...]): janela sem sort pega a
        # página crua a partir da posição 0.
        assert ids == [400, 530]

    def test_without_limit_offset_alone_starts_from_offset(self, collection):
        ids = [row["id"] for row in collection.window(offset=3).rows()]

        assert ids == [512, 401]


class TestPipeline:
    def test_full_chain_filter_then_sort_then_window(self, collection):
        result = (
            collection.filtered_by("o")
            .sorted_by_id()
            .window(offset=0, limit=2)
            .rows()
        )

        assert [row["id"] for row in result] == [312, 400]

    def test_pipeline_does_not_mutate_source_items(self, collection):
        original = [dict(row) for row in collection.rows()]

        collection.filtered_by("autenticacao").sorted_by_id().window(0, 2)

        assert [row["id"] for row in collection.rows()] == [
            row["id"] for row in original
        ]
        assert collection.rows()[0]["name"] == original[0]["name"]


@pytest.fixture
def vis_collection() -> ApiCollection:
    return ApiCollection.from_raw(_load_visibility_fixture())


class TestProjectionRules:
    def test_last_revision_prefers_dedicated_field(self):
        api = {"lastRevision": {"id": 8882, "revisionNumber": 3}}

        assert last_revision_number(api) == 3

    def test_last_revision_falls_back_to_last_revision_entry(self):
        api = {"revisions": [{"revisionNumber": 1}, {"revisionNumber": 4}]}

        assert last_revision_number(api) == 4

    def test_last_revision_absent_returns_none(self):
        assert last_revision_number({}) is None
        assert last_revision_number({"revisions": []}) is None

    def test_life_cycle_present_and_absent(self):
        assert life_cycle_of({"lifeCycle": "DRAFT"}) == "DRAFT"
        assert life_cycle_of({"lifeCycle": ""}) is None
        assert life_cycle_of({}) is None


class TestVisibleTo:
    def test_super_admin_sees_everything(self, vis_collection):
        result = vis_collection.visible_to(
            "isaac.machado", ["APIOps"], super_admin=True
        )

        assert len(result) == len(vis_collection)

    def test_developer_sees_org_group_and_own_me(self, vis_collection):
        names = [
            row["name"]
            for row in vis_collection.visible_to(
                "isaac.machado", ["APIOps"]
            ).rows()
        ]

        assert "Org Public API" in names                       # ORGANIZATION
        assert "Api Minha ME" in names                         # ME próprio
        assert "Api Minha ME Casefold" in names                # ME trim/casefold
        assert "Grupo Casa API" in names                       # GROUP do meu grupo
        assert "Grupo Casa Casefold API" in names              # GROUP trim/casefold
        assert "Api Alheia ME" not in names                    # ME de outro
        assert "Grupo Alheio API" not in names                 # GROUP que não participo
        assert "Sem Visibilidade API" not in names             # sem visibility
        assert "Tipo Desconhecido API" not in names            # tipo fora da tabela

    def test_group_owner_does_not_grant_visibility(self, vis_collection):
        names = [
            row["name"] for row in vis_collection.visible_to(
                "isaac.machado", ["APIOps"]
            ).rows()
        ]

        # GROUP de grupo que NÃO participo, mesmo sendo owner → oculta
        assert "Grupo Alheio Meu Owner API" not in names

    def test_group_membership_requires_matching_group_name(self, vis_collection):
        names = [
            row["name"] for row in vis_collection.visible_to(
                "isaac.machado", ["APIOps"]
            ).rows()
        ]

        assert "Grupo Alheio API" not in names                 # Lab-tech
        assert "Grupo Casa API" in names                       # APIOps

    def test_whitespace_and_case_tolerance(self, vis_collection):
        names = [
            row["name"] for row in vis_collection.visible_to(
                " ISAAC.MACHADO ", [" Apiops "]
            ).rows()
        ]

        assert "Grupo Casa API" in names
        assert "Api Minha ME Casefold" in names

    def test_unknown_groups_hide_group_apis_but_keep_org(self, vis_collection):
        names = [
            row["name"] for row in vis_collection.visible_to(
                "isaac.machado", ["Outro-Time"]
            ).rows()
        ]

        assert "Grupo Casa API" not in names
        assert "Org Public API" in names

    def test_empty_groups_hides_personal_access(self, vis_collection):
        names = [
            row["name"]
            for row in vis_collection.visible_to("isaac.machado", []).rows()
        ]

        assert "Grupo Casa API" not in names
        assert "Api Alheia ME" not in names
        assert "Api Minha ME" in names                         # owner continua íntegro

    def test_missing_visibility_argument_denies_all_except_org(self, vis_collection):
        names = [
            row["name"] for row in vis_collection.visible_to(None, None).rows()
        ]

        assert names == ["Org Public API"]

    def test_pipeline_visible_then_query_then_window(self, vis_collection):
        result = (
            vis_collection.visible_to("isaac.machado", ["APIOps"])
            .filtered_by("api")
            .sorted_by_id()
            .window(offset=0, limit=3)
            .rows()
        )

        names = [row["name"] for row in result]
        assert "Org Public API" in names
        assert "Grupo Alheio Meu Owner API" not in names
