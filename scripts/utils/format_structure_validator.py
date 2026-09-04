"""Translate a format-contract diff into persisted validation findings."""

from __future__ import annotations

from typing import Any, Dict, List

from scripts.utils.game_format_contract import FormatStructureDiff


def _finding(
    code: str,
    default_message: str,
    classification: str,
    blocking: bool,
    repair_queue: bool,
    review_queue: bool,
    details: str,
) -> Dict[str, Any]:
    return {
        "code": code,
        "default_message": default_message,
        "classification": classification,
        "blocking": blocking,
        "repair_queue": repair_queue,
        "review_queue": review_queue,
        "details": details,
    }


def _balance_findings(diff: FormatStructureDiff) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if diff.source_issue:
        findings.append(_finding(
                "validation_source_format_unbalanced",
                "Source formatting is unbalanced; target repair must not force a matching close marker.",
                "source_defect",
                False,
                False,
                True,
                "Source formatting is not balanced. Keep the source anomaly for source-side review.",
            ))
    if not diff.target.balanced:
        findings.append(_finding(
            "validation_format_structure_mismatch",
            "Target formatting structure is unbalanced.",
            "hard_corruption",
            True,
            not diff.source_issue,
            diff.source_issue,
            "Target formatting has an unmatched close, unclosed opener, or parse error.",
        ))
    return findings


def _protected_findings(diff: FormatStructureDiff) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if (diff.missing_protected or diff.extra_protected) and not diff.runtime_variation_only:
        findings.append(_finding(
            "validation_protected_token_mismatch",
            "Protected runtime tokens differ from the source.",
            "hard_corruption",
            True,
            True,
            False,
            f"Missing protected tokens: {diff.missing_protected}; extra protected tokens: {diff.extra_protected}.",
        ))
    if diff.protected_identity_changes or diff.protected_order_changed:
        findings.append(_finding(
            "validation_protected_token_identity_mismatch",
            "Protected runtime token identity or order differs from the source.",
            "hard_corruption",
            True,
            True,
            False,
            "Protected runtime tokens were changed or rebound.",
        ))
    return findings


def _format_findings(diff: FormatStructureDiff) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    if diff.format_identity_changes:
        findings.append(_finding(
            "validation_format_tag_identity_mismatch",
            "Formatting tag identity differs from the source.",
            "hard_corruption",
            True,
            True,
            False,
            "Formatting openers or marker families were changed, added, or removed incorrectly.",
        ))
    if diff.format_order_changed:
        findings.append(_finding(
            "validation_format_tag_order_mismatch",
            "Formatting tag order differs from the source.",
            "hard_corruption",
            True,
            True,
            False,
            "Formatting markers have the same identities but a different order.",
        ))
    if diff.boundary_changes and not diff.runtime_variation_only:
        findings.append(_finding(
            "validation_format_boundary_mismatch",
            "A formatting span is bound to different protected content.",
            "hard_corruption",
            True,
            True,
            False,
            "A formatting boundary crossed or rebound a protected token.",
        ))
    if diff.nesting_changes:
        findings.append(_finding(
            "validation_format_nesting_mismatch",
            "Formatting tag nesting differs from the source.",
            "hard_corruption",
            True,
            True,
            False,
            "Formatting wrappers are crossed or nested differently.",
        ))
    return findings


def structure_findings(diff: FormatStructureDiff) -> List[Dict[str, Any]]:
    """Return deterministic findings; count variation remains review-only."""
    findings = _balance_findings(diff)
    findings.extend(_protected_findings(diff))
    findings.extend(_format_findings(diff))
    if not diff.hard_issues and diff.possible_variations:
        findings.append(_finding(
            "validation_format_structure_variation",
            "Formatting occurrence count changed and requires semantic review.",
            "possible_reasonable_variation",
            False,
            False,
            True,
            "Known formatting identities remain intact, but their occurrence count changed. Do not auto-repair without semantic evidence.",
        ))
    return findings


__all__ = ["structure_findings"]
