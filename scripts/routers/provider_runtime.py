from fastapi import HTTPException

from scripts.core.services.provider_runtime import (
    provider_task_fields,
    resolve_provider_runtime,
)


def resolve_runtime_or_400(selection_id: str, model_id: str | None = None):
    try:
        return resolve_provider_runtime(selection_id, model_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "provider_profile_not_available",
                "message": str(exc),
                "selection_id": selection_id,
            },
        ) from exc


__all__ = ["provider_task_fields", "resolve_runtime_or_400"]
