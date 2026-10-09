"""Explicit opt-in for unfinished Agent APIs; mature advanced APIs stay available."""
import os

from .batch_repository import BatchConflict

EXPERIMENTAL_FLAGS = {
    "translation_trials": "REMIS_ENABLE_TRANSLATION_TRIALS",
    "terminology_coverage": "REMIS_ENABLE_TERMINOLOGY_COVERAGE",
    "localization_reviews": "REMIS_ENABLE_LOCALIZATION_REVIEWS",
    "mars_base_patch": "REMIS_ENABLE_MARS_BASE_PATCH",
}
EXPERIMENTAL_PATHS = {
    "/api/agent/translation-trials": "translation_trials",
    "/api/agent/terminology-coverage": "terminology_coverage",
    "/api/agent/localization-reviews": "localization_reviews",
    "/api/agent/mars-base-patch": "mars_base_patch",
}


def advanced_experiment_enabled(feature):
    flag = EXPERIMENTAL_FLAGS[feature]
    return os.getenv(flag, "").strip().lower() in {"1", "true", "yes", "on"}


def require_advanced_experiment(feature):
    if not advanced_experiment_enabled(feature):
        raise BatchConflict("experimental_feature_disabled",
                            "This unfinished Agent workflow requires explicit developer opt-in.", 403)


def project_experimental_capabilities(capabilities):
    for feature, flag in EXPERIMENTAL_FLAGS.items():
        capability = capabilities[feature]
        if advanced_experiment_enabled(feature):
            capability.update(supported=True, enabled=True, audience="advanced_agent", opt_in_flag=flag)
        else:
            capabilities[feature] = {"supported": False, "enabled": False, "experimental": True,
                                     "gui": False, "reason": "Explicit developer opt-in is required."}
    for feature in ("batch_jobs", "chinese_conversion"):
        capabilities[feature].update(audience="advanced_agent", gui=False)
    return capabilities


def feature_for_path(path):
    return next((feature for prefix, feature in EXPERIMENTAL_PATHS.items()
                 if path == prefix or path.startswith(prefix + "/")), None)
