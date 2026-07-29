import asyncio
import json

from sqlalchemy import event

from app.models.user import User, UserRole
from app.routers.analytics import reps_data
from app.routers.api.master import _format_beat_item, resolve_user_hierarchy_beats


def _query_count(engine):
    state = {"count": 0}

    def before_cursor_execute(*_args, **_kwargs):
        state["count"] += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    return state, before_cursor_execute


def test_rep_analytics_query_count_is_constant_with_page_size(
    db_session, acceptance_data
):
    extra_reps = [
        User(
            email=f"query-count-{index}@example.test",
            username=f"query-count-{index}",
            full_name=f"Query Count Rep {index:02d}",
            role=UserRole.field_rep,
            is_active=True,
        )
        for index in range(25)
    ]
    db_session.add_all(extra_reps)
    db_session.commit()

    state, listener = _query_count(db_session.bind)
    try:
        response = asyncio.run(
            reps_data(
                current_user=acceptance_data["users"]["admin"],
                db=db_session,
                days=30,
                page=1,
                per_page=25,
            )
        )
    finally:
        event.remove(db_session.bind, "before_cursor_execute", listener)

    payload = json.loads(response.body)
    assert len(payload["reps"]) == 25
    # At most one identity refresh plus count, page, and four batched aggregates.
    # Crucially, this is constant for 25 representatives rather than 5N queries.
    assert state["count"] <= 7


def test_beat_collection_eager_loads_nested_positions_users_and_outlets(
    db_session, acceptance_data
):
    state, listener = _query_count(db_session.bind)
    try:
        beats, total = resolve_user_hierarchy_beats(
            acceptance_data["users"]["admin"], db_session, page=1, per_page=100
        )
        payload = [_format_beat_item(beat) for beat in beats]
    finally:
        event.remove(db_session.bind, "before_cursor_execute", listener)

    assert total == 2
    assert len(payload) == 2
    # identity refresh + count/page and three select-in relationship queries.
    assert state["count"] <= 7
