"""Event model + emitter.

The emitter does two things for every event: (1) persist it to the append-only log
(durable episodic memory) and (2) fan it out to live subscribers (the streaming trace).
This is the backbone of the "traceability over magic" principle.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from researchos.persistence.event_log import EventLog


class EventType(StrEnum):
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    PLAN_CREATED = "plan_created"
    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    AGENT_MESSAGE = "agent_message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    PAPERS_FOUND = "papers_found"
    PAPERS_INGESTED = "papers_ingested"
    MEMORY_WRITE = "memory_write"
    ARTIFACT_SAVED = "artifact_saved"


class Event(BaseModel):
    run_id: str
    actor: str
    type: EventType
    payload: dict = Field(default_factory=dict)
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))


Subscriber = Callable[[Event], None]


class EventEmitter:
    """Persists events and notifies live subscribers."""

    def __init__(self, run_id: str, log: EventLog | None = None) -> None:
        self.run_id = run_id
        self._log = log or EventLog()
        self._subscribers: list[Subscriber] = []

    def subscribe(self, fn: Subscriber) -> None:
        self._subscribers.append(fn)

    def emit(self, actor: str, type: EventType, payload: dict | None = None) -> Event:
        event = Event(run_id=self.run_id, actor=actor, type=type, payload=payload or {})
        self._log.append(self.run_id, actor, type.value, event.payload)
        for fn in self._subscribers:
            with contextlib.suppress(Exception):  # a bad subscriber must never break a run
                fn(event)
        return event
