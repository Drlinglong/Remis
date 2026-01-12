from scripts.utils.system_utils import slugify_to_ascii

def test_slugify_standard():
    assert slugify_to_ascii("Test Mod Name") == "test_mod_name"
    assert slugify_to_ascii("  Leading Trailing  ") == "leading_trailing"
    assert slugify_to_ascii("Multiple___Underscores") == "multiple_underscores"

def test_slugify_chinese():
    # Note: result depends on whether pypinyin is installed in the test environment
    # If pypinyin is not available, it will result in underscores
    result = slugify_to_ascii("一个弱智模组")
    assert result != ""
    assert all(ord(c) < 128 for c in result)

def test_slugify_mixed():
    result = slugify_to_ascii("en-Marshalreich kr奉天重制")
    assert result.startswith("en-marshalreich_kr")
    assert all(ord(c) < 128 for c in result)

def test_slugify_edge_cases():
    # Pure non-ASCII should not be empty
    assert slugify_to_ascii("！！！").startswith("mod_")
    assert slugify_to_ascii("").startswith("unnamed_mod_")

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
