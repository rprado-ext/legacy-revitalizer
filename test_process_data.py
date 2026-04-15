import pytest
from unittest.mock import MagicMock, patch, call

from process_data import (
    HardcodedCredentialStore,
    AuthService,
    Item,
    ItemRepository,
    FileStorageBackend,
    Application,
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


def make_repo(storage=None) -> ItemRepository:
    return ItemRepository(storage or InMemoryStorage())


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
        repo = make_repo(storage)
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

    def test_overwrites_existing_file(self, tmp_path):
        filepath = tmp_path / "out.txt"
        filepath.write_text("old content")
        backend = FileStorageBackend(str(filepath))
        backend.save([])
        assert filepath.read_text() == "[]"


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
