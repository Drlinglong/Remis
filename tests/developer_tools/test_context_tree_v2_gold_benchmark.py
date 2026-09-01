from scripts.developer_tools.context_tree_v2_gold_benchmark import score


def test_route_aware_gold_scores_narrative_and_supporting_text_separately():
    tree = {
        "tree_id": "tree-1",
        "release_id": "release-1",
        "groups": [{"group_id": "group-1", "fragment_ids": ["fragment-1"]}],
        "unit_routes": [
            {
                "local_unit_id": "unit_0",
                "route": "narrative",
                "fragment_ids": ["fragment-1"],
            },
            {
                "local_unit_id": "unit_1",
                "route": "reference_asset",
                "fragment_ids": [],
            },
        ],
    }
    gold = {
        "fixture": {"path": "fixture.yml"},
        "assignments": [
            {
                "unit_id": "unit_0",
                "group_key": "event.1",
                "chain": "event_chain",
                "relation": "primary_member",
            },
            {
                "unit_id": "unit_1",
                "group_key": "tech_event_reward",
                "chain": "supporting_text",
                "relation": "reference_asset",
            },
        ],
    }

    result = score(tree, gold)

    assert result["benchmark_version"] == "route-aware-gold-v2/tree-v2-projection-v1"
    assert result["metrics"]["route_accuracy"] == 1.0
    assert result["metrics"]["routes"] == {"exact": 2}
    assert result["metrics"]["primary_only"]["unit_count"] == 1
    assert result["errors"]["wrong_route"] == []


def test_route_aware_gold_reports_reference_asset_sent_to_event_chain():
    tree = {
        "groups": [{"group_id": "group-1", "fragment_ids": ["fragment-1"]}],
        "unit_routes": [
            {
                "local_unit_id": "unit_0",
                "route": "narrative",
                "fragment_ids": ["fragment-1"],
            }
        ],
    }
    gold = {
        "assignments": [
            {
                "unit_id": "unit_0",
                "group_key": "named_weapon",
                "chain": "supporting_text",
                "relation": "reference_asset",
            }
        ]
    }

    result = score(tree, gold)

    assert result["metrics"]["route_accuracy"] == 0.0
    assert result["errors"]["wrong_route"][0]["expected_route"] == "reference_asset"
    assert result["errors"]["wrong_route"][0]["predicted_route"] == "narrative"
