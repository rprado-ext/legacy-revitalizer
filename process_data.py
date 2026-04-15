None
import datetime
import hmac
import json
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable


class PersistenceError(Exception):
    """Raised when the persistence pipeline fails to save data."""


# ---------------------------------------------------------------------------
# Abstractions — Dependency Inversion Principle (DIP)
# High-level classes depend on these interfaces, not on concrete details.
# ---------------------------------------------------------------------------

class StorageBackend(ABC):
    """Abstract interface for persisting the item list."""

    @abstractmethod
    def save(self, items: list[dict]) -> None:
        """Persist the given list of item dicts."""


class CredentialStore(ABC):
    """Abstract interface for validating user credentials."""

    @abstractmethod
    def is_valid(self, username: str, password: str) -> bool:
        """Return True if the credentials are accepted."""


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------

class FileStorageBackend(StorageBackend):
    """Writes the item list to a plain-text file (StorageBackend implementation)."""

    def __init__(self, filepath: str = "data.txt"):
        self._filepath = filepath

    def save(self, items: list[dict]) -> None:
        """Serialize items to the configured file using an atomic write.

        Writes to a temporary file in the same directory, then replaces the
        target file in a single OS-level operation. This guarantees the file
        is never left in a partially-written state if the process is
        interrupted mid-write. Uses JSON for portable, safe serialization.

        Raises:
            OSError: If the file cannot be opened or written to (e.g. bad path,
                     missing directory, full disk, or insufficient permissions).
        """
        target_dir = os.path.dirname(os.path.abspath(self._filepath))
        try:
            fd, tmp_path = tempfile.mkstemp(dir=target_dir)
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(items, f)
                os.replace(tmp_path, self._filepath)
            except OSError:
                os.unlink(tmp_path)
                raise
        except OSError as e:
            raise OSError(f"Failed to write to '{self._filepath}': {e}") from e


class HardcodedCredentialStore(CredentialStore):
    """Validates credentials against a single configured account.

    Security note:
        Credentials are passed at construction time. In production, replace
        this with a store that hashes passwords (e.g., bcrypt) and reads from
        a secure configuration source — never hardcode secrets in source code.
    """

    def __init__(self, username: str, password: str):
        self._username = username
        self._password = password

    def is_valid(self, username: str, password: str) -> bool:
        """Return True only when both username and password match exactly.

        Uses hmac.compare_digest to prevent timing attacks: evaluation time
        is constant regardless of where the strings first differ.
        """
        usernames_match = hmac.compare_digest(username, self._username)
        passwords_match = hmac.compare_digest(password, self._password)
        return usernames_match and passwords_match


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

_MAX_VALUE_LENGTH = 1000


class Item:
    """Represents a single stored item with an id, value, and timestamp.

    Attributes:
        id (int): Auto-assigned sequential identifier.
        value (str): The user-supplied payload.
        created_at (str): ISO-like timestamp of when the item was created.
    """

    def __init__(self, item_id: int, value: str, created_at: str):
        self.id = item_id
        self.value = value
        self.created_at = created_at

    def __str__(self) -> str:
        return f"Item: {self.id} - {self.value} at {self.created_at}"

    def to_dict(self) -> dict:
        """Return a plain dict representation suitable for serialization."""
        return {"id": self.id, "val": self.value, "date": self.created_at}


# ---------------------------------------------------------------------------
# Single-responsibility classes
# ---------------------------------------------------------------------------

class ItemPersistenceService:
    """Owns the full persistence pipeline for Item objects. (SRP: persistence only)

    Serializes a collection of Item domain objects into plain dicts and
    delegates the actual storage operation to the injected StorageBackend.
    Neither the repository nor the backend needs to know about the other.

    Args:
        backend (StorageBackend): Storage strategy to write serialized data to.
    """

    def __init__(self, backend: StorageBackend):
        self._backend = backend

    def persist(self, items: list["Item"]) -> None:
        """Serialize items and forward them to the storage backend.

        Raises:
            PersistenceError: If the backend raises any exception during save.
        """
        try:
            self._backend.save([item.to_dict() for item in items])
        except Exception as e:
            raise PersistenceError(f"Could not persist items: {e}") from e


class ItemRepository:
    """Manages an in-memory collection of Items. (SRP: data management only)

    Persistence is fully delegated to the injected ItemPersistenceService,
    so this class has no knowledge of how or where data is stored.

    Args:
        persistence (ItemPersistenceService): Service used by :meth:`save`.
    """

    def __init__(self, persistence: ItemPersistenceService):
        self._items: list[Item] = []
        self._persistence = persistence

    @staticmethod
    def _current_timestamp() -> str:
        """Return the current local time as a formatted string."""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add(self, value: str) -> None:
        """Append a new Item with the current timestamp and print confirmation.

        Raises:
            ValueError: If value exceeds _MAX_VALUE_LENGTH characters.
        """
        if len(value) > _MAX_VALUE_LENGTH:
            raise ValueError(
                f"Value too long: {len(value)} characters (max {_MAX_VALUE_LENGTH})."
            )
        item = Item(len(self._items) + 1, value, self._current_timestamp())
        self._items.append(item)
        print("Added.")

    def show(self) -> None:
        """Print all stored items to stdout."""
        for item in self._items:
            print(item)

    def save(self) -> None:
        """Persist all items via the persistence service and print confirmation."""
        try:
            self._persistence.persist(self._items)
        except PersistenceError as e:
            print(f"Error: could not save data. {e}")
            return
        print("Saved.")


class AuthService:
    """Handles user authentication. (SRP: auth logic only)

    Args:
        store (CredentialStore): Credential validation strategy.
    """

    def __init__(self, store: CredentialStore):
        self._store = store

    def authenticate(self, username: str, password: str) -> bool:
        """Return True if the provided credentials are valid."""
        return self._store.is_valid(username, password)


class Application:
    """Orchestrates the CLI interaction loop. (SRP: user I/O only)

    Args:
        auth (AuthService): Service used to authenticate the operator.
        repository (ItemRepository): Repository for item management.
    """

    def __init__(self, auth: AuthService, repository: ItemRepository):
        self._auth = auth
        self._repository = repository
        # OCP: register new commands here without touching any other method.
        self._commands: dict[str, Callable[[], None]] = {
            "add": self._handle_add,
            "show": self._repository.show,
            "save": self._repository.save,
        }

    def run(self) -> None:
        """Entry point: authenticate the operator, then start the command loop."""
        if self._login():
            self._run_command_loop()

    def _login(self) -> bool:
        """Prompt for credentials and return True if authentication succeeds."""
        username = input("User: ")
        password = input("Pass: ")
        if self._auth.authenticate(username, password):
            print("Welcome")
            return True
        print("Wrong!")
        return False

    def _run_command_loop(self) -> None:
        """Repeatedly prompt for a command and dispatch it until 'exit' is entered."""
        while True:
            cmd = input("What to do? (add/show/save/exit): ")
            if cmd == "exit":
                break
            action = self._commands.get(cmd)
            if action:
                action()
            else:
                print(f"Unknown command: {cmd!r}")

    def _handle_add(self) -> None:
        """Prompt for a value, validate it, and delegate to the repository."""
        value = input("Value: ")
        try:
            self._repository.add(value)
        except ValueError as e:
            print(f"Error: {e}")


# ---------------------------------------------------------------------------
# Entry point — guarded to prevent execution on import
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    storage = FileStorageBackend("data.txt")
    persistence = ItemPersistenceService(storage)
    credentials = HardcodedCredentialStore("admin", "12345")
    repository = ItemRepository(persistence)
    auth = AuthService(credentials)
    app = Application(auth, repository)
    app.run()
