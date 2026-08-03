from scripts.core.strict_json_schema import strict_json_schema


def test_strict_schema_closes_nested_objects_and_requires_nullable_fields():
    source = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "default": [],
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "note": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                    },
                },
            },
        },
    }

    result = strict_json_schema(source)

    assert result["required"] == ["items"]
    assert result["additionalProperties"] is False
    item = result["properties"]["items"]["items"]
    assert item["required"] == ["name", "note"]
    assert item["additionalProperties"] is False
    assert "default" not in result["properties"]["items"]
    assert "default" not in item["properties"]["note"]
    assert source["properties"]["items"]["default"] == []
