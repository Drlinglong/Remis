from collections.abc import Callable


def add_context_release_storage(db_path: str) -> None:
    from scripts.core.context_migration import migrate_context_release_storage

    migrate_context_release_storage(db_path)


def add_context_analysis_batch_storage(db_path: str) -> None:
    from scripts.core.context_analysis_migration import migrate_context_analysis_batch_storage

    migrate_context_analysis_batch_storage(db_path)


def add_context_delivery_memberships(db_path: str) -> None:
    from scripts.core.context_migration import migrate_context_release_storage

    migrate_context_release_storage(db_path)


def add_context_aggregation_phase(db_path: str) -> None:
    from scripts.core.context_analysis_migration import migrate_context_analysis_aggregation_phase

    migrate_context_analysis_aggregation_phase(db_path)


def add_context_release_manifests(db_path: str) -> None:
    from scripts.core.context_release_manifest_migration import migrate_context_release_manifest_storage

    migrate_context_release_manifest_storage(db_path)


def add_atomic_context_publication(db_path: str) -> None:
    from scripts.core.context_publication_migration import migrate_context_publication_storage

    migrate_context_publication_storage(db_path)


def add_context_synthesis_checkpoints(db_path: str) -> None:
    from scripts.core.context_analysis_migration import migrate_context_analysis_synthesis_phase

    migrate_context_analysis_synthesis_phase(db_path)


def add_context_tree_v2_storage(db_path: str) -> None:
    from scripts.core.context_tree_v2_migration import migrate_context_tree_v2_storage

    migrate_context_tree_v2_storage(db_path)


CONTEXT_DB_MIGRATIONS: list[tuple[int, str, Callable[[str], None]]] = [
    (14, "add_context_release_storage", add_context_release_storage),
    (15, "add_context_analysis_batch_storage", add_context_analysis_batch_storage),
    (16, "add_context_delivery_memberships", add_context_delivery_memberships),
    (17, "add_context_aggregation_phase", add_context_aggregation_phase),
    (18, "add_context_release_manifests", add_context_release_manifests),
    (19, "add_atomic_context_publication", add_atomic_context_publication),
    (20, "add_context_synthesis_checkpoints", add_context_synthesis_checkpoints),
    (21, "add_context_tree_v2_storage", add_context_tree_v2_storage),
    (22, "extend_context_tree_v2_results", add_context_tree_v2_storage),
]
