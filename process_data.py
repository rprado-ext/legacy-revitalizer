None
import datetime
from abc import ABC, abstractmethod


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
        """Serialize items to the configured file using a context manager."""
        with open(self._filepath, "w") as f:
            f.write(str(items))


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
        """Return True only when both username and password match exactly."""
        return username == self._username and password == self._password


# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

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

class ItemRepository:
    """Manages an in-memory collection of Items. (SRP: data management only)

    All persistence is delegated to the injected StorageBackend, so this
    class never needs to change when the storage medium changes (OCP).

    Args:
        storage (StorageBackend): Backend used by :meth:`save`.
    """

    def __init__(self, storage: StorageBackend):
        self._items: list[Item] = []
        self._storage = storage

    @staticmethod
    def _current_timestamp() -> str:
        """Return the current local time as a formatted string."""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add(self, value: str) -> None:
        """Append a new Item with the current timestamp and print confirmation."""
        item = Item(len(self._items) + 1, value, self._current_timestamp())
        self._items.append(item)
        print("Added.")

    def show(self) -> None:
        """Print all stored items to stdout."""
        for item in self._items:
            print(item)

    def save(self) -> None:
        """Persist all items via the storage backend and print confirmation."""
        self._storage.save([item.to_dict() for item in self._items])
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
        self._commands: dict[str, callable] = {
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
        """Prompt for a value and delegate to the repository."""
        value = input("Value: ")
        self._repository.add(value)


# ---------------------------------------------------------------------------
# Entry point — guarded to prevent execution on import
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    storage = FileStorageBackend("data.txt")
    credentials = HardcodedCredentialStore("admin", "12345")
    repository = ItemRepository(storage)
    auth = AuthService(credentials)
    app = Application(auth, repository)
    app.run()
