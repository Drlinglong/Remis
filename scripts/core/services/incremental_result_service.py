"""Persist the incremental engine's entry results in the public task result."""


def build_incremental_task_result(project_id, fields, output_paths, workflow_log_paths, summary):
    counts = dict(summary or {})
    return {
        "types": ["files", "change_summary", "workflow_log"],
        "output_paths": list(dict.fromkeys(output_paths)),
        "summary": (
            f"{counts.get('new', 0)} new, {counts.get('changed', 0)} changed, "
            f"{counts.get('unchanged', 0)} unchanged entries; "
            f"{fields['warning_count']} runtime warning(s)."
        ),
        "metadata": {
            "project_id": project_id,
            "summary_code": "incremental_translation_completed",
            "processed_file_count": len(fields["file_summaries"]),
            "entry_summary": counts,
            "file_summaries": fields["file_summaries"],
            "workflow_log_paths": workflow_log_paths,
            "warning_count": fields["warning_count"],
            "source_advancement": fields["source_advancement"],
            "context": fields["context"],
        },
    }
