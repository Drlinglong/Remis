"""Use the same policy for request rejection and OpenAPI discovery."""
from fastapi import HTTPException, Request

from scripts.core.advanced_agent_policy import (
    advanced_experiment_enabled, feature_for_path,
)


def require_advanced_route(request: Request):
    feature = feature_for_path(request.url.path)
    if feature and not advanced_experiment_enabled(feature):
        raise HTTPException(403, detail={"code": "experimental_feature_disabled",
                                        "message": "This unfinished workflow requires developer opt-in."})


def include_advanced_router(app, router):
    for route in router.routes:
        feature = feature_for_path(route.path)
        if feature:
            route.include_in_schema = advanced_experiment_enabled(feature)
    app.include_router(router)
