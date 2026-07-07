import queue
from dataclasses import dataclass, field
from typing import Any, List


@dataclass
class EmberAppState:
    engine: Any
    phidata_engine: Any
    global_sync_queue: queue.Queue = field(default_factory=queue.Queue)
    active_websockets: List[Any] = field(default_factory=list)


state: EmberAppState | None = None


def init_state(engine: Any, phidata_engine: Any) -> EmberAppState:
    global state
    state = EmberAppState(engine=engine, phidata_engine=phidata_engine)
    return state


def get_state() -> EmberAppState:
    if state is None:
        raise RuntimeError("Ember app state has not been initialized.")
    return state
