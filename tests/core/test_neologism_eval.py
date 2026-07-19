from scripts.developer_tools.evaluate_neologism_miner import score_predictions


def test_golden_eval_scoring_tracks_recall_and_grounding():
    source = "The Curia Caelestis enacted the Sublimation Protocol under Pax Remisia."

    result = score_predictions(
        ["The Curia Caelestis", "Sublimation Protocol", "Hallucinated Order"],
        ["The Curia Caelestis", "Sublimation Protocol", "Pax Remisia"],
        source,
    )

    assert result["recall"] == 0.6667
    assert result["missing"] == ["Pax Remisia"]
    assert result["ungrounded"] == ["Hallucinated Order"]
    assert result["grounding_rate"] == 0.6667
