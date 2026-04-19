from typing import Callable
from dataclasses import dataclass


Unsubscribe = Callable[[], None]


class FileEvent:
    """Base class for file system events."""

    pass


@dataclass(frozen=True)
class FileCreated(FileEvent):
    """File system entry was created."""

    path: str


@dataclass(frozen=True)
class FileDeleted(FileEvent):
    """File system entry was deleted."""

    path: str


@dataclass(frozen=True)
class FileModified(FileEvent):
    """File system entry was modified."""

    path: str


@dataclass(frozen=True)
class FileRenamed(FileEvent):
    """File system entry was renamed."""

    old_path: str
    new_path: str
