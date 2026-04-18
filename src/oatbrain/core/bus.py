from typing import TypeVar, Callable, Any
from collections import defaultdict

T = TypeVar("T")


class EventBus:
    """Simple event bus for decouple state changes from side effects."""

    def __init__(self) -> None:
        self._listeners: dict[type[Any], list[Callable[[Any], None]]] = defaultdict(
            list
        )

    def subscribe(self, event_type: type[T], listener: Callable[[T], None]) -> None:
        self._listeners[event_type].append(listener)

    def publish(self, event: Any) -> None:
        event_type = type(event)
        for listener in self._listeners[event_type]:
            listener(event)


class CommandRouter:
    """Routes commands to handlers that update state."""

    def __init__(self) -> None:
        self._handlers: dict[type[Any], Callable[[Any], None]] = {}
        self._command_names: dict[type[Any], str] = {}

    def register(
        self, command_type: type[T], handler: Callable[[T], None], name: str = ""
    ) -> None:
        self._handlers[command_type] = handler
        self._command_names[command_type] = name or command_type.__name__

    def dispatch(self, command: Any) -> None:
        command_type = type(command)
        handler = self._handlers.get(command_type)
        if handler:
            handler(command)
        else:
            raise ValueError(f"No handler for command {command_type}")

    def list_commands(self) -> list[tuple[type[Any], str]]:
        """Returns a list of (command_type, human_name) for registered commands."""
        return list(self._command_names.items())
