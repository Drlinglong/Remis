"""Coordinate candidate governance without growing the legacy workflow hotspot."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from scripts.core.neologism_extraction import AnalysisScope


_MISSING = object()


def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    dumper = getattr(value, "model_dump", None)
    if callable(dumper):
        try:
            return dict(dumper(mode="json"))
        except TypeError:
            return dict(dumper())
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {}


def _match_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _flag(value: Any) -> bool:
    """Read an explicit governance flag without deriving one from counts."""

    return value is True


@dataclass(frozen=True)
class ContextCandidateGovernanceResult:
    """Stable integration view over the future governance-core result."""

    raw: Any | None
    candidates: tuple[Any, ...]
    policy_by_aggregate_key: Mapping[str, Any]
    governed_extractions: tuple[Any, ...]
    synthesis_eligible_aggregate_keys: frozenset[str]
    glossary_eligible_match_keys: frozenset[str]
    report: dict[str, Any]
    available: bool = False
    _resolver: Callable[[Any], Any] | None = field(
        default=None, repr=False, compare=False,
    )

    def aggregate_key_for_surface(self, surface: Any) -> str:
        if self.available and self._resolver is not None:
            key = self._resolver(surface)
            if key:
                return str(key)
        return f"entity:{_match_key(surface)}"

    def candidate_aggregate_keys(self) -> frozenset[str]:
        keys = {str(key) for key in self.policy_by_aggregate_key}
        for candidate in self.candidates:
            key = _read(candidate, "aggregate_key")
            if not key:
                surface = next(
                    (
                        _read(candidate, name)
                        for name in (
                            "canonical_display_name", "surface", "original", "name",
                        )
                        if _read(candidate, name)
                    ),
                    None,
                )
                key = self.aggregate_key_for_surface(surface)
            if key:
                keys.add(str(key))
        return frozenset(keys)

    def candidate_for_aggregate(self, aggregate_key: str) -> Any | None:
        for candidate in self.candidates:
            candidate_key = _read(candidate, "aggregate_key")
            if not candidate_key:
                surface = next(
                    (
                        _read(candidate, name)
                        for name in (
                            "canonical_display_name", "surface", "original", "name",
                        )
                        if _read(candidate, name)
                    ),
                    None,
                )
                candidate_key = self.aggregate_key_for_surface(surface)
            if str(candidate_key) == aggregate_key:
                return candidate
        return None

    def policy_for_aggregate(self, aggregate_key: str) -> Any | None:
        return self.policy_by_aggregate_key.get(aggregate_key)

    def is_audit_only(self, aggregate_key: str) -> bool:
        policy = self.policy_for_aggregate(aggregate_key)
        candidate = self.candidate_for_aggregate(aggregate_key)
        policy_flag = _read(policy, "audit_only", _MISSING)
        if policy_flag is not _MISSING:
            return _flag(policy_flag)
        return _flag(_read(candidate, "audit_only", False))

    def is_summary_eligible(self, aggregate_key: str) -> bool:
        policy = self.policy_for_aggregate(aggregate_key)
        candidate = self.candidate_for_aggregate(aggregate_key)
        policy_flag = _read(policy, "summary_eligible", _MISSING)
        if policy_flag is not _MISSING:
            return _flag(policy_flag)
        return _flag(_read(candidate, "summary_eligible", False))

    def is_glossary_eligible(self, aggregate_key: str) -> bool:
        policy = self.policy_for_aggregate(aggregate_key)
        candidate = self.candidate_for_aggregate(aggregate_key)
        policy_flag = _read(policy, "glossary_eligible", _MISSING)
        if policy_flag is not _MISSING:
            return _flag(policy_flag)
        return _flag(_read(candidate, "glossary_eligible", False))

    def glossary_eligible_aggregate_keys(self) -> frozenset[str]:
        return frozenset(
            key for key in self.candidate_aggregate_keys()
            if self.is_glossary_eligible(key)
        )

    def payload_for_aggregate(
        self, aggregate_key: str, contribution_count: int,
    ) -> dict[str, Any]:
        candidate = self.candidate_for_aggregate(aggregate_key)
        policy = self.policy_for_aggregate(aggregate_key)
        payload = {
            "active_contribution_count": contribution_count,
            **_mapping(candidate),
            **_mapping(policy),
        }
        canonical = payload.get("canonical_display_name") or aggregate_key
        normalized = payload.get("normalized_match_key") or _match_key(canonical)
        payload.update({
            "canonical_display_name": canonical,
            "normalized_match_key": normalized,
            "aliases": list(payload.get("aliases") or []),
            "candidate_kind": payload.get("candidate_kind"),
            "tier": payload.get("tier"),
            "policy_reasons": list(
                payload.get("policy_reasons")
                or payload.get("promotion_reasons")
                or []
            ),
            "summary_eligible": payload.get("summary_eligible"),
            "glossary_eligible": payload.get("glossary_eligible"),
            "audit_only": payload.get("audit_only"),
            "override_provenance": payload.get("override_provenance"),
        })
        for metric in (
            "source_item_coverage", "local_unit_coverage",
            "event_chain_coverage", "policy_coverage",
        ):
            payload.setdefault(metric, 0)
        payload.setdefault("mention_count", 0)
        coverage = payload.get("coverage_metrics") or payload.get("coverage")
        if isinstance(coverage, Mapping):
            payload["coverage_metrics"] = dict(coverage)
        return payload

    def counts(self) -> dict[str, Any]:
        aggregate_keys = self.candidate_aggregate_keys()
        return {
            "available": self.available,
            "candidate_count": len(self.candidates),
            "candidate_aggregate_count": len(aggregate_keys),
            "audit_only_candidate_count": sum(
                _flag(_read(candidate, "audit_only", False))
                for candidate in self.candidates
            ),
            "audit_only_aggregate_count": sum(
                self.is_audit_only(key) for key in aggregate_keys
            ),
            "summary_eligible_candidate_count": sum(
                _flag(_read(candidate, "summary_eligible", False))
                for candidate in self.candidates
            ),
            "glossary_eligible_candidate_count": sum(
                _flag(_read(candidate, "glossary_eligible", False))
                for candidate in self.candidates
            ),
            "synthesis_eligible_aggregate_count": len(
                self.synthesis_eligible_aggregate_keys
            ),
            "glossary_eligible_match_key_count": len(
                self.glossary_eligible_match_keys
            ),
            "governed_extraction_count": len(self.governed_extractions),
        }

    def report_payload(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "counts": self.counts(),
            "report": dict(self.report),
        }


class ContextCandidateGovernanceIntegrationService:
    """Load and normalize the parallel governance core at one boundary."""

    def __init__(self, governance_service: Any | None = None):
        self.governance_service = (
            governance_service
            if governance_service is not None
            else self._load_default_service()
        )

    @staticmethod
    def _load_default_service() -> Any | None:
        try:
            from scripts.core.services.context_candidate_governance_service import (
                ContextCandidateGovernanceService,
            )
        except ModuleNotFoundError as error:
            if error.name == "scripts.core.services.context_candidate_governance_service":
                return None
            raise
        return ContextCandidateGovernanceService()

    def govern(
        self,
        *,
        project_id: str,
        extractions: Sequence[Any],
        analysis_scope: AnalysisScope,
        source_items: Sequence[Any] = (),
        local_units: Sequence[Any] = (),
        reconciled: Any | None = None,
        duplicate_index: Mapping[str, Any] | None = None,
        source_language: str | None = None,
    ) -> ContextCandidateGovernanceResult:
        if self.governance_service is None:
            return ContextCandidateGovernanceResult(
                raw=None,
                candidates=(),
                policy_by_aggregate_key={},
                governed_extractions=tuple(extractions),
                synthesis_eligible_aggregate_keys=frozenset(),
                glossary_eligible_match_keys=frozenset(),
                report={},
            )
        raw = self._invoke_govern(
            self.governance_service,
            project_id,
            extractions,
            analysis_scope,
            source_items,
            local_units,
            reconciled,
            duplicate_index or {},
            source_language,
        )
        resolver = getattr(raw, "aggregate_key_for_surface", None)
        if resolver is None and isinstance(raw, Mapping):
            resolver = raw.get("aggregate_key_for_surface")
        if not callable(resolver):
            raise TypeError(
                "ContextCandidateGovernanceService.govern() must return "
                "aggregate_key_for_surface(surface)"
            )
        governed = _read(raw, "governed_extractions", _MISSING)
        return ContextCandidateGovernanceResult(
            raw=raw,
            candidates=tuple(_read(raw, "candidates", ()) or ()),
            policy_by_aggregate_key=dict(
                _read(raw, "policy_by_aggregate_key", {}) or {}
            ),
            governed_extractions=tuple(
                extractions if governed is _MISSING else (governed or ())
            ),
            synthesis_eligible_aggregate_keys=frozenset(
                str(key) for key in (_read(raw, "synthesis_eligible_aggregate_keys", ()) or ())
            ),
            glossary_eligible_match_keys=frozenset(
                _match_key(key)
                for key in (_read(raw, "glossary_eligible_match_keys", ()) or ())
            ),
            report=_mapping(_read(raw, "report", {})),
            available=True,
            _resolver=resolver,
        )

    @staticmethod
    def _invoke_govern(
        service: Any,
        project_id: str,
        extractions: Sequence[Any],
        analysis_scope: AnalysisScope,
        source_items: Sequence[Any],
        local_units: Sequence[Any],
        reconciled: Any | None,
        duplicate_index: Mapping[str, Any],
        source_language: str | None,
    ) -> Any:
        method = service.govern
        values = {
            "project_id": project_id,
            "extractions": extractions,
            "local_extractions": extractions,
            "analysis_scope": analysis_scope,
            "source_items": source_items,
            "local_units": local_units,
            "reconciled": reconciled,
            "event_reconciliation": reconciled,
            "duplicate_index": duplicate_index,
            "source_language": source_language,
        }
        final_assignments = list(
            _read(reconciled, "delivery_assignments", ()) or ()
        )
        values.update({
            "final_delivery_assignments": final_assignments,
            "final_assignments": final_assignments,
            "final_delivery_links": final_assignments,
            "final_local_unit_delivery_links": final_assignments,
        })
        try:
            parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
            return method(extractions)
        accepts_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        kwargs = dict(values) if accepts_kwargs else {
            name: values[name] for name in parameters if name in values
        }
        extraction_name = next(
            (
                name for name in ("extractions", "local_extractions")
                if name in parameters
            ),
            None,
        )
        if extraction_name and parameters[extraction_name].kind is inspect.Parameter.KEYWORD_ONLY:
            kwargs[extraction_name] = extractions
            return method(**kwargs)
        return method(extractions, **{
            name: value for name, value in kwargs.items()
            if name not in {"extractions", "local_extractions"}
        })


class _ReviewProgressMiner:
    """Keep candidate-adapter review calls observable without changing its API."""

    def __init__(
        self,
        miner: Any,
        on_batch: Callable[..., None],
        usage_ledger: Any | None = None,
    ):
        self._miner = miner
        self._on_batch = on_batch
        self._batch_number = 0
        self._usage_ledger = usage_ledger

    @property
    def batch_count(self) -> int:
        return self._batch_number

    def review_terms(self, candidates: Sequence[dict[str, Any]], **kwargs: Any) -> Any:
        self._batch_number += 1
        batch_id = f"reviewing:{self._batch_number}"
        try:
            result = self._miner.review_terms(candidates, **kwargs)
        except Exception as error:
            self._on_batch(
                batch_id,
                success=False,
                conflict_review_count=len(candidates),
                error=str(error),
            )
            raise
        finally:
            if self._usage_ledger is not None:
                self._usage_ledger.capture(
                    getattr(self._miner, "client", None), "term_review",
                )
        self._on_batch(
            batch_id,
            success=True,
            conflict_review_count=len(candidates),
        )
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._miner, name)


class ContextCandidateGovernanceFlowService:
    """Run governance, eligible candidate review, and synthesis filtering."""

    def __init__(
        self,
        *,
        candidate_adapter: Any,
        status_service: Any,
        batch_store: Any | None = None,
        governance_service: Any | None = None,
    ):
        self.candidate_adapter = candidate_adapter
        self.status_service = status_service
        self.batch_store = batch_store
        self.integration = ContextCandidateGovernanceIntegrationService(
            governance_service,
        )

    def govern(self, **kwargs: Any) -> ContextCandidateGovernanceResult:
        return self.integration.govern(**kwargs)

    def govern_and_process_terms(
        self,
        *,
        governance_kwargs: Mapping[str, Any],
        process_kwargs: Mapping[str, Any],
    ) -> tuple[ContextCandidateGovernanceResult, dict[str, Any]]:
        governance = self.govern(**dict(governance_kwargs))
        terms = self.process_terms(governance=governance, **dict(process_kwargs))
        return governance, terms

    def process_terms(
        self,
        project_id: str,
        parsed_files: Sequence[Any],
        extractions: Sequence[Any],
        miner: Any,
        duplicate_index: Mapping[str, Any],
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
        governance: ContextCandidateGovernanceResult,
        *,
        task_id: str | None = None,
        source_snapshot_hash: str | None = None,
        analysis_scope: Mapping[str, Any] | AnalysisScope | None = None,
        analysis_config: Mapping[str, Any] | None = None,
        run_id: str | None = None,
        usage_ledger: Any | None = None,
    ) -> dict[str, Any]:
        self.status_service.begin_stage(project_id, task_id, "reviewing", 0)
        review_miner = _ReviewProgressMiner(
            miner,
            lambda batch_id, **details: self.status_service.record_batch(
                project_id, task_id, "reviewing", batch_id, **details
            ),
            usage_ledger,
        )
        result = self.candidate_adapter.process_terms(
            project_id,
            parsed_files,
            extractions,
            review_miner,
            dict(duplicate_index),
            source_lang,
            target_lang,
            game_name,
            review_language,
            task_id=task_id,
            source_snapshot_hash=source_snapshot_hash,
            analysis_scope=analysis_scope,
            analysis_config=analysis_config,
            run_id=run_id,
            batch_store=self.batch_store,
            governance=governance,
        )
        self.status_service.complete_stage(
            project_id,
            task_id,
            "reviewing",
            skipped=review_miner.batch_count == 0,
        )
        return result

    @staticmethod
    def synthesis_eligible_aggregates(
        aggregates: Sequence[Any],
        governance: ContextCandidateGovernanceResult,
    ) -> list[Any]:
        if not governance.available:
            return list(aggregates)
        candidate_keys = governance.candidate_aggregate_keys()
        eligible_keys = {
            aggregate_key
            for aggregate_key in governance.synthesis_eligible_aggregate_keys
            if aggregate_key in candidate_keys
            and governance.is_summary_eligible(aggregate_key)
        }
        return [
            aggregate
            for aggregate in aggregates
            if aggregate.aggregate_type in {"event", "project"}
            or aggregate.aggregate_key in eligible_keys
        ]
