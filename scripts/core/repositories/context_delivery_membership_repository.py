"""Focused SQLite helpers for immutable context delivery memberships."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from typing import Iterable

from scripts.schemas.context import ContextDeliveryMembership


def validate_memberships(
    connection: sqlite3.Connection,
    memberships: Iterable[ContextDeliveryMembership],
    aggregate_ids: set[str],
    project_id: str,
) -> list[ContextDeliveryMembership]:
    values = list(memberships)
    if len({(item.aggregate_id, item.source_item_id) for item in values}) != len(values):
        raise ValueError("Context delivery memberships must be unique per aggregate and source")
    for item in values:
        if item.aggregate_id not in aggregate_ids:
            raise ValueError("Context delivery membership references an aggregate outside the release")
        aggregate = connection.execute(
            "SELECT project_id, aggregate_type FROM context_aggregates WHERE aggregate_id = ?",
            (item.aggregate_id,),
        ).fetchone()
        if aggregate is None or aggregate["project_id"] != project_id:
            raise ValueError("Context delivery membership references an aggregate outside the project")
        if aggregate["aggregate_type"] != "event":
            raise ValueError("Context delivery membership must target an event aggregate")
        row = connection.execute(
            "SELECT project_id FROM context_source_items WHERE source_item_id = ?",
            (item.source_item_id,),
        ).fetchone()
        if row is None or row["project_id"] != project_id:
            raise ValueError("Context delivery membership references a source outside the project")
    return values


def insert_memberships(
    connection: sqlite3.Connection,
    release_id: str,
    memberships: Iterable[ContextDeliveryMembership],
) -> None:
    connection.executemany(
        """
        INSERT INTO context_release_delivery_memberships (
            release_id, aggregate_id, source_item_id, role,
            confidence, provenance, reasoning
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                release_id,
                item.aggregate_id,
                item.source_item_id,
                item.role,
                item.confidence,
                item.provenance,
                item.reasoning,
            )
            for item in memberships
        ],
    )


def list_memberships(
    connection: sqlite3.Connection,
    release_id: str,
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT membership.aggregate_id, membership.source_item_id,
               membership.role, membership.confidence, membership.provenance,
               membership.reasoning, aggregate.aggregate_key,
               aggregate.aggregate_type, source.source_ref,
               source.metadata_json, source.content
        FROM context_release_delivery_memberships AS membership
        JOIN context_release_aggregates AS aggregate
          ON aggregate.release_id = membership.release_id
         AND aggregate.aggregate_id = membership.aggregate_id
        JOIN context_source_items AS source
          ON source.source_item_id = membership.source_item_id
        WHERE membership.release_id = ?
        ORDER BY aggregate.aggregate_key, source.source_ref
        """,
        (release_id,),
    ).fetchall()
    return [
        {
            "aggregate": {
                "aggregate_id": row["aggregate_id"],
                "aggregate_key": row["aggregate_key"],
                "aggregate_type": row["aggregate_type"],
            },
            "membership": {
                "source_item_id": row["source_item_id"],
                "role": row["role"],
                "confidence": row["confidence"],
                "provenance": row["provenance"],
                "reasoning": row["reasoning"],
            },
            "source_item": {
                "source_item_id": row["source_item_id"],
                "source_ref": row["source_ref"],
                "content": row["content"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
            },
        }
        for row in rows
    ]


def counts_by_aggregate(
    connection: sqlite3.Connection,
    release_id: str,
) -> dict[str, dict]:
    rows = connection.execute(
        """
        SELECT aggregate_id, role, COUNT(*) AS count
        FROM context_release_delivery_memberships
        WHERE release_id = ?
        GROUP BY aggregate_id, role
        """,
        (release_id,),
    ).fetchall()
    grouped: dict[str, Counter] = {}
    for row in rows:
        grouped.setdefault(row["aggregate_id"], Counter())[row["role"]] = row["count"]
    return {
        aggregate_id: {"count": sum(counts.values()), "role_counts": dict(counts)}
        for aggregate_id, counts in grouped.items()
    }
