"""Conservative diagnostics; warnings do not authorize semantic rewrites."""
import re

from .surviving_mars_csv import compare_newlines, compare_tags


def emphasis_ranges(text):
    parts, ranges, offset, opened = [], [], 0, None
    for part in re.split(r"(</?em>)", text):
        if part == "<em>":
            opened = offset
        elif part == "</em>":
            if opened is not None:
                ranges.append((opened, offset))
                opened = None
        else:
            plain = re.sub(r"<[^<>]*>", "", part)
            parts.append(plain)
            offset += len(plain)
    return "".join(parts), ranges


def term_emphasis_mismatch(source, translation_plain, ranges, expected, spellings):
    spellings = sorted(set(spellings), key=len, reverse=True)
    expression = r"<em>(?:" + "|".join(re.escape(s) for s in spellings) + r")</em>"
    required = len(re.findall(expression, source, flags=re.I))
    if not required:
        return False
    covered, split = 0, False
    for occurrence in re.finditer(re.escape(expected), translation_plain):
        whole = any(a <= occurrence.start() and b >= occurrence.end() for a, b in ranges)
        covered += whole
        split |= not whole and any(a < occurrence.end() and b > occurrence.start() for a, b in ranges)
    return expected in translation_plain and (split or covered < required)


def check_quality(source, translation, terms=(), adapter=None):
    issues = [issue.as_dict() for issue in adapter.validate(source, translation)] if adapter else []
    if compare_tags(source, translation).is_mismatch or compare_newlines(source, translation).is_mismatch:
        issues.append({"code": "token_integrity_error", "severity": "error"})
    # Check only paired emphasis tags that the source already uses as balanced markup.
    if source.count("<em>") == source.count("</em>"):
        depth = 0
        for tag in re.findall(r"</?em>", translation):
            depth += 1 if tag == "<em>" else -1
            if depth < 0 or depth > 1:
                issues.append({"code": "emphasis_structure_error", "severity": "error"})
                break
        if depth:
            issues.append({"code": "emphasis_structure_error", "severity": "error"})
    for match in re.finditer(r"<percent\([^<>]*\)>\s*(?:名|位|人)", translation):
        issues.append({"code": "percentage_person_unit_review", "severity": "warning", "translation_evidence": match.group(0)})
    plain, ranges = emphasis_ranges(translation)
    for term in terms:
        expected = term["translation"]
        spellings = [term["source"], *term.get("aliases", [])]
        if len(expected) >= 2 and term_emphasis_mismatch(source, plain, ranges, expected, spellings):
            issues.append({"code": "terminology_emphasis_scope_review", "severity": "warning",
                           "concept_id": term["concept_id"], "expected_translation": expected})
    return issues
