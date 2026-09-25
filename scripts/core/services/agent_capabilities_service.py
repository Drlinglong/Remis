"""Public Agent capability projection; no credential resolution or state changes."""


def build_capabilities(*, api_version, version, games, languages, providers, shells, policy, context_capabilities):
    from scripts.core.game_adapters.registry import game_capabilities
    from scripts.core.services.game_support_service import get_game_support
    games = [{**game, "capabilities": game_capabilities(game["id"]),
              "game_support": get_game_support(game["id"])} for game in games]
    return {
        "api_version": api_version,
        "remis_version": version,
        "service": "remis-agent-api",
        "transport": {
            "base_url": "/api/agent",
            "localhost_only": True,
            "polling": True,
            "websocket_status": True,
        },
        "games": games,
        "languages": languages,
        "providers": providers,
        "shell_languages": {"supported": True, "target_lang_codes": ["custom"],
            "configuration_field": "custom_lang_config", "shells": shells},
        "steam_workshop": {"supported": True, "base_url": "/api/agent/steam-workshop",
            "workshop_item_id": "explicit_input", "publishes_to_steam": False},
        "baseline_sync": {"supported": True, "endpoint": "/api/agent/jobs/{job_id}/baseline/sync",
            "requires_approval": True, "max_keys": 100, "validation_refreshed": False},
        "actions": policy({
            "inspect_game_support": {"supported": True, "requires_approval": False,
                "endpoint": "/api/agent/projects/{project_id}/game-support"},
            "plan_incremental_translation": {"supported": True, "requires_approval": False,
                "endpoint": "/api/agent/jobs/plan", "request_fields": {"workflow": "incremental"},
                "checkpoint_resume_supported": False},
            "read_projects": {"supported": True, "requires_approval": False},
            "plan_translation": {"supported": True, "requires_approval": False},
            "run_dry_run": {"supported": True, "requires_approval": False},
            "start_translation": {"supported": True, "requires_approval": True},
            "resume_from_checkpoint": {
                "supported": True,
                "requires_approval": True,
            },
            "pause": {
                "supported": False,
                "reason": "The current runner has no safe cooperative pause boundary.",
            },
            "cancel": {"supported": True, "requires_approval": True, "endpoint": "/api/tasks/{task_id}/cancel", "task_kinds": ["initial_translation", "translation", "incremental_translation"]},
            "repair": {"supported": True, "requires_approval": True},
            "export": {"supported": True, "requires_approval": True},
            **context_capabilities,
        }),
        "safety": {
            "api_keys_returned": False,
            "direct_database_writes_allowed": False,
            "direct_localization_file_edits_allowed": False,
            "localization_file_reads_allowed": True,
            "targeted_file_edits": "explicit_user_approval_and_baseline_reconciliation",
            "custom_export_paths_restricted": True,
        },
        "links": {
            "health": "/api/health",
            "preflight": "/api/agent/preflight",
            "openapi": "/openapi.json",
            "docs": "/docs",
            "projects": "/api/agent/projects",
        },
    }
