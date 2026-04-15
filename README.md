# legacy-revitalizer

A hands-on refactoring project that takes a single legacy Python script (`legacy.py`) and progressively transforms it into clean, well-structured code using GitHub Copilot as an AI pair programmer.

## What this project demonstrates

- **Code analysis** — identifying inputs, outputs, side effects, and code smells in an existing script
- **Documentation** — generating docstrings for all functions and classes
- **SOLID refactoring** — applying Single Responsibility, Open/Closed, and Dependency Inversion principles; eliminating global variables and adding an `if __name__ == "__main__"` guard
- **Naming** — replacing cryptic identifiers (`l`, `d`, `fn`) with descriptive names
- **Readability** — decomposing large methods into smaller, focused functions
- **Unit testing** — building a pytest suite (42 tests) that covers all classes and edge cases
- **Error handling** — adding layered `try/except` blocks with a custom `PersistenceError` domain exception
- **Security & performance** — fixing a timing attack, non-atomic file writes, unsafe serialization (`str()` → JSON), unbounded input, and a deprecated type hint

## Files

| File | Description |
|---|---|
| `legacy.py` | Original unmodified legacy script (preserved for reference) |
| `process_data.py` | Fully refactored version of the same script |
| `test_process_data.py` | pytest test suite for `process_data.py` |
| `LOG.md` | Step-by-step log of every Copilot prompt and the changes it produced |

## Running the tests

```bash
python3 -m pytest test_process_data.py -v
```

## Running the app

```bash
python3 process_data.py
```