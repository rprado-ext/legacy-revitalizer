import json
import pytest
from unittest.mock import MagicMock, patch, call

from process_data import (
    HardcodedCredentialStore,
    AuthService,
    Item,
    PersistenceError,
    ItemPersistenceService,
    ItemRepository,
    FileStorageBackend,
    Application,
    _MAX_VALUE_LENGTH,
)


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

class InMemoryStorage:
    """StorageBackend stub that captures the last saved payload in memory."""

    def __init__(self):
        self.saved = None

    def save(self, items: list[dict]) -> None:
        self.saved = items


def make_persistence(storage=None) -> ItemPersistenceService:
    return ItemPersistenceService(storage or InMemoryStorage())


def make_repo(persistence=None) -> ItemRepository:
    return ItemRepository(persistence or make_persistence())


# ---------------------------------------------------------------------------
# HardcodedCredentialStore
# ---------------------------------------------------------------------------

class TestHardcodedCredentialStore:
    def test_valid_credentials_return_true(self):
        store = HardcodedCredentialStore("admin", "secret")
        assert store.is_valid("admin", "secret") is True

    def test_wrong_password_returns_false(self):
        store = HardcodedCredentialStore("admin", "secret")
        assert store.is_valid("admin", "wrong") is False

    def test_wrong_username_returns_false(self):
        store = HardcodedCredentialStore("admin", "secret")
        assert store.is_valid("other", "secret") is False

    def test_empty_credentials_do_not_match(self):
        store = HardcodedCredentialStore("admin", "secret")
        assert store.is_valid("", "") is False

    def test_case_sensitive_username(self):
        store = HardcodedCredentialStore("Admin", "secret")
        assert store.is_valid("admin", "secret") is False

    def test_compare_is_timing_safe(self):
        # compare_digest must be used — both branches always evaluated
        import hmac
        store = HardcodedCredentialStore("admin", "secret")
        # Patch compare_digest to confirm it is called for password check
        with patch("process_data.hmac.compare_digest", wraps=hmac.compare_digest) as mock_cd:
            store.is_valid("admin", "secret")
            assert mock_cd.call_count == 2


# ---------------------------------------------------------------------------
# AuthService
# ---------------------------------------------------------------------------

class TestAuthService:
    def test_delegates_to_credential_store(self):
        store = MagicMock()
        store.is_valid.return_value = True
        auth = AuthService(store)
        result = auth.authenticate("user", "pass")
        store.is_valid.assert_called_once_with("user", "pass")
        assert result is True

    def test_returns_false_when_store_rejects(self):
        store = MagicMock()
        store.is_valid.return_value = False
        auth = AuthService(store)
        assert auth.authenticate("user", "bad") is False


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class TestItem:
    def test_str_format(self):
        item = Item(1, "hello", "2026-04-15 10:00:00")
        assert str(item) == "Item: 1 - hello at 2026-04-15 10:00:00"

    def test_to_dict_keys_and_values(self):
        item = Item(3, "world", "2026-04-15 12:00:00")
        assert item.to_dict() == {"id": 3, "val": "world", "date": "2026-04-15 12:00:00"}


# ---------------------------------------------------------------------------
# ItemRepository
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ItemPersistenceService
# ---------------------------------------------------------------------------

class TestItemPersistenceService:
    def test_persist_serializes_items_to_dicts(self):
        storage = InMemoryStorage()
        service = ItemPersistenceService(storage)
        items = [Item(1, "hello", "2026-04-15 10:00:00")]
        service.persist(items)
        assert storage.saved == [{"id": 1, "val": "hello", "date": "2026-04-15 10:00:00"}]

    def test_persist_empty_list(self):
        storage = InMemoryStorage()
        service = ItemPersistenceService(storage)
        service.persist([])
        assert storage.saved == []

    def test_persist_delegates_to_backend(self):
        backend = MagicMock()
        service = ItemPersistenceService(backend)
        items = [Item(1, "x", "2026-04-15 10:00:00")]
        service.persist(items)
        backend.save.assert_called_once_with([{"id": 1, "val": "x", "date": "2026-04-15 10:00:00"}])

    def test_persist_multiple_items(self):
        storage = InMemoryStorage()
        service = ItemPersistenceService(storage)
        items = [Item(1, "a", "2026-04-15 10:00:00"), Item(2, "b", "2026-04-15 11:00:00")]
        service.persist(items)
        assert len(storage.saved) == 2
        assert storage.saved[1]["val"] == "b"

    def test_persist_wraps_backend_exception_as_persistence_error(self):
        backend = MagicMock()
        backend.save.side_effect = OSError("disk full")
        service = ItemPersistenceService(backend)
        with pytest.raises(PersistenceError, match="disk full"):
            service.persist([Item(1, "x", "2026-04-15 10:00:00")])

    def test_persist_error_preserves_cause(self):
        backend = MagicMock()
        cause = OSError("no space")
        backend.save.side_effect = cause
        service = ItemPersistenceService(backend)
        with pytest.raises(PersistenceError) as exc_info:
            service.persist([])
        assert exc_info.value.__cause__ is cause


# ---------------------------------------------------------------------------

class TestItemRepository:
    def test_add_stores_item(self, capsys):
        repo = make_repo()
        repo.add("test-value")
        assert len(repo._items) == 1
        assert repo._items[0].value == "test-value"

    def test_add_prints_confirmation(self, capsys):
        repo = make_repo()
        repo.add("x")
        assert capsys.readouterr().out.strip() == "Added."

    def test_add_assigns_sequential_ids(self, capsys):
        repo = make_repo()
        repo.add("first")
        repo.add("second")
        assert repo._items[0].id == 1
        assert repo._items[1].id == 2

    def test_add_records_timestamp_format(self, capsys):
        repo = make_repo()
        repo.add("v")
        ts = repo._items[0].created_at
        # Must match YYYY-MM-DD HH:MM:SS
        import re
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", ts)

    def test_add_raises_on_value_exceeding_max_length(self):
        repo = make_repo()
        with pytest.raises(ValueError, match="too long"):
            repo.add("x" * (_MAX_VALUE_LENGTH + 1))

    def test_add_accepts_value_at_exact_max_length(self, capsys):
        repo = make_repo()
        repo.add("x" * _MAX_VALUE_LENGTH)
        assert len(repo._items) == 1

    def test_show_prints_all_items(self, capsys):
        repo = make_repo()
        repo.add("alpha")
        repo.add("beta")
        capsys.readouterr()  # clear "Added." output
        repo.show()
        out = capsys.readouterr().out
        assert "alpha" in out
        assert "beta" in out

    def test_show_empty_repository_prints_nothing(self, capsys):
        repo = make_repo()
        repo.show()
        assert capsys.readouterr().out == ""

    def test_save_delegates_to_storage(self, capsys):
        storage = InMemoryStorage()
        repo = make_repo(make_persistence(storage))
        repo.add("item1")
        capsys.readouterr()
        repo.save()
        assert storage.saved is not None
        assert len(storage.saved) == 1
        assert storage.saved[0]["val"] == "item1"

    def test_save_prints_confirmation(self, capsys):
        repo = make_repo()
        repo.save()
        assert capsys.readouterr().out.strip() == "Saved."

    def test_save_prints_error_when_persistence_fails(self, capsys):
        persistence = MagicMock()
        persistence.persist.side_effect = PersistenceError("backend down")
        repo = ItemRepository(persistence)
        repo.save()
        out = capsys.readouterr().out
        assert "Error" in out
        assert "backend down" in out

    def test_save_does_not_print_saved_on_failure(self, capsys):
        persistence = MagicMock()
        persistence.persist.side_effect = PersistenceError("oops")
        repo = ItemRepository(persistence)
        repo.save()
        assert "Saved." not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# FileStorageBackend
# ---------------------------------------------------------------------------

class TestFileStorageBackend:
    def test_writes_string_representation_to_file(self, tmp_path):
        filepath = tmp_path / "out.txt"
        backend = FileStorageBackend(str(filepath))
        items = [{"id": 1, "val": "hello", "date": "2026-04-15 10:00:00"}]
        backend.save(items)
        content = filepath.read_text()
        assert "hello" in content
        # Must be valid JSON, not a Python repr string
        loaded = json.loads(content)
        assert loaded == items

    def test_overwrites_existing_file(self, tmp_path):
        filepath = tmp_path / "out.txt"
        filepath.write_text("old content")
        backend = FileStorageBackend(str(filepath))
        backend.save([])
        assert json.loads(filepath.read_text()) == []

    def test_write_is_atomic_no_partial_file_on_error(self, tmp_path):
        filepath = tmp_path / "data.txt"
        filepath.write_text("original")
        backend = FileStorageBackend(str(filepath))
        # Simulate a write failure after open by making json.dump raise
        with patch("process_data.json.dump", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                backend.save([{"id": 1}])
        # Original file must be untouched
        assert filepath.read_text() == "original"

    def test_raises_os_error_on_invalid_path(self):
        backend = FileStorageBackend("/nonexistent_dir/out.txt")
        with pytest.raises(OSError):
            backend.save([])

    def test_os_error_message_includes_filepath(self):
        backend = FileStorageBackend("/no/such/path/out.txt")
        with pytest.raises(OSError, match="/no/such/path/out.txt"):
            backend.save([])


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class TestApplication:
    def _make_app(self, auth_result=True):
        auth = MagicMock()
        auth.authenticate.return_value = auth_result
        repo = MagicMock()
        app = Application(auth, repo)
        return app, auth, repo

    def test_run_prints_wrong_on_failed_login(self, capsys):
        app, _, _ = self._make_app(auth_result=False)
        with patch("builtins.input", side_effect=["user", "bad"]):
            app.run()
        assert "Wrong!" in capsys.readouterr().out

    def test_run_prints_welcome_on_successful_login(self, capsys):
        app, _, _ = self._make_app(auth_result=True)
        with patch("builtins.input", side_effect=["user", "pass", "exit"]):
            app.run()
        assert "Welcome" in capsys.readouterr().out

    def test_run_does_not_enter_loop_on_failed_login(self, capsys):
        app, _, repo = self._make_app(auth_result=False)
        with patch("builtins.input", side_effect=["user", "bad"]):
            app.run()
        repo.show.assert_not_called()
        repo.save.assert_not_called()

    def test_show_command_calls_repository_show(self, capsys):
        app, _, repo = self._make_app()
        with patch("builtins.input", side_effect=["user", "pass", "show", "exit"]):
            app.run()
        repo.show.assert_called_once()

    def test_save_command_calls_repository_save(self, capsys):
        app, _, repo = self._make_app()
        with patch("builtins.input", side_effect=["user", "pass", "save", "exit"]):
            app.run()
        repo.save.assert_called_once()

    def test_add_command_prompts_for_value_and_calls_repository(self, capsys):
        app, _, repo = self._make_app()
        with patch("builtins.input", side_effect=["user", "pass", "add", "my-value", "exit"]):
            app.run()
        repo.add.assert_called_once_with("my-value")

    def test_add_command_prints_error_on_value_too_long(self, capsys):
        app, _, repo = self._make_app()
        repo.add.side_effect = ValueError("Value too long")
        with patch("builtins.input", side_effect=["user", "pass", "add", "x" * 1001, "exit"]):
            app.run()
        assert "Error" in capsys.readouterr().out

    def test_unknown_command_prints_error(self, capsys):
        app, _, _ = self._make_app()
        with patch("builtins.input", side_effect=["user", "pass", "??", "exit"]):
            app.run()
        assert "Unknown command" in capsys.readouterr().out

    def test_exit_terminates_loop(self, capsys):
        app, _, repo = self._make_app()
        with patch("builtins.input", side_effect=["user", "pass", "exit"]):
            app.run()  # must not raise StopIteration or loop forever
        repo.show.assert_not_called()
