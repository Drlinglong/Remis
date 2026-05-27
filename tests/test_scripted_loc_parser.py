from scripts.core import scripted_loc_parser


def test_scripted_loc_parser_extracts_and_injects_custom_loc(tmp_path):
    source = tmp_path / "customizable_localization.txt"
    source.write_text(
        'customizable_localization = {\n'
        '    add_custom_loc = "Hello Emperor"\n'
        '    ignored = "Leave me alone"\n'
        '    add_custom_loc = "Second line"\n'
        '}\n',
        encoding="utf-8",
    )

    texts, positions, lines = scripted_loc_parser.extract_texts(source)
    patched = scripted_loc_parser.inject_texts(lines, positions, ["Witaj", 'Cytat "bezpieczny"'])

    assert texts == ["Hello Emperor", "Second line"]
    assert '    add_custom_loc = "Witaj"\n' in patched
    assert '    add_custom_loc = "Cytat \\"bezpieczny\\""\n' in patched
