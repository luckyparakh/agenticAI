# CODE — Project 1 (CloudDesk), Session 1: Code Companion

> **Provenance for every block:** FROM REPO `anulsasidharan/CloudDesk` at the commit named in each heading.
> - Everything after a `# ◀` marker is **my annotation, added for teaching**. Everything else is the instructor's file, verbatim. I checked this by script: stripping the `# ◀` annotations reproduces config.py, logging.py, core/`__init__.py`, the test file, and the session-time pyproject.toml and .gitignore exactly.
> - The §18 code was **EXECUTED**: `uv sync` + `uv run pytest -q` → **14 passed** (Python 3.11.15 auto-installed by uv from `.python-version`; uv 0.11.7; langchain 1.4.7, pydantic-settings 2.16.1, pydantic 2.14.1).
> - Sections are numbered to match the README's Replay segments.
> - This session has no AI-core code yet (no agents, RAG, or LLM calls), so every walkthrough here is backend/infra tier. Because these are your first Python files in the course, every construct gets a full walkthrough.

---

## CODE §6 — `pyproject.toml`

### Session-time version — `99405d1` (01:04)

```toml
# ◀ [project] = the package's identity + runtime dependencies (≈ the module + require lines in go.mod)
[project]
name = "clouddesk"
version = "0.1.0"
description = "Add your description here"          # ◀ uv's placeholder, never edited
readme = "README.md"
authors = [
    { name = "Anu L Sasidharan", email = "anulsasidharan@gmail.com" }
]
# ◀ Minimum Python. The exact interpreter comes from .python-version (3.11)
requires-python = ">=3.11"
dependencies = [
    # ◀ ">=" is a floor, not a pin. The exact version (1.4.7) lives in uv.lock
    "langchain>=1.4.7",
]

# ◀ Creates a `clouddesk` command that calls main() in the clouddesk package
[project.scripts]
clouddesk = "clouddesk:main"

# ◀ How to build a wheel. uv_build is uv's own build backend. This section is what makes
# ◀ it a *package* (the `uv init --package` layout), not a loose app.
[build-system]
requires = ["uv_build>=0.12.5,<0.13.0"]
build-backend = "uv_build"
```

### P1-1 additions — `70b7862` (02:11)

```toml
dependencies = [
    "langchain>=1.4.7",
    # ◀ Added by `uv add pydantic-settings`; powers config.py (CODE §18)
    "pydantic-settings>=2.16.1",
]

# ◀ Added by `uv add --dev pytest`: dev-only deps, not shipped with the package
[dependency-groups]
dev = [
    "pytest>=9.1.1",
]

# ◀ Lets tests do `from app.core.config import ...`: pytest puts backend/ on the import path
[tool.pytest.ini_options]
pythonpath = ["backend"]
```

**What's happening here**
1. When you run `uv sync` or `uv run`, uv reads `[project]` to learn what to install and `requires-python` to check the interpreter. It then installs the **exact** versions recorded in `uv.lock`.
2. `[project.scripts]` makes uv install a small launcher named `clouddesk`. Running it imports the `clouddesk` package and calls its `main()`.
3. `[build-system]` is only used when the project is *built* (into a wheel) or installed as a package. Because it exists, uv installs your own project into the venv too, so `import clouddesk` works from anywhere.
4. `[dependency-groups] dev` holds tools you need for development but not in production. A production install can skip them (for example `uv sync --no-dev` [Supplementary]).
5. `[tool.pytest.ini_options]` is pytest's own config section; pytest reads it at startup. `pythonpath = ["backend"]` is why the tests can import `app.…` even though the code lives under `backend/app/`.

> 🧩 **First time in the course: dependency groups.** **What:** named sets of extra dependencies. **Why:** keep test and lint tools out of production images. **Without it:** pytest would ship inside your production container, making it bigger, giving it more attack surface, and adding more to patch.

**Repo layout note.** At this point the repo has **two** Python roots:
- `src/clouddesk/`, from `uv init`.
- `backend/app/`, from the spec's layout (CLAUDE.md §4.3).

The real application code goes under `backend/app/`. The `src/clouddesk` stub is uv's default and isn't used yet. Expect it to be cleaned up or repurposed later. *(Observation from the repo, not narrated.)*

---

## CODE §10 — `.gitignore` and the package stub

### `.gitignore` at `99405d1` (01:04, the "Initial commit to the dev branch")

```gitignore
# Python-generated files
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv
```

### `.gitignore` after P1-1, `70b7862` (02:11) — lines added

```gitignore
# Local secrets. .env.example stays committable.
.env
# ◀ Also .env.local, .env.prod, and so on
.env.*
# ◀ "!" re-includes a file that an earlier pattern excluded
!.env.example

# Runtime databases. Settings default to ./data/*.db.
data/
*.db
# ◀ SQLite's temporary side files
*.db-journal
*.db-wal
*.db-shm

# Tool caches
.pytest_cache/
.ruff_cache/
.mypy_cache/
```

**What's happening here.** Git checks each untracked path against these patterns, top to bottom. The *last* matching pattern wins, which is why `!.env.example` can re-include a file that `.env.*` excluded.

The first version is uv's default and has **no `.env` rule**. That contradicts the narration's claim that the agent had covered `.env` (README §10). The P1-1 version fixes it, and it also follows a common convention: commit a `.env.example` containing only placeholders so teammates know which variables exist. CLAUDE.md §10.1 requires that file to list every variable.

**Check it yourself:** `git check-ignore -v .env` prints the rule that ignores the file, or nothing if it isn't ignored.

### `src/clouddesk/__init__.py` at `99405d1`

```python
# ◀ "-> None" is a return type hint: this function returns nothing
def main() -> None:
    print("Hello from clouddesk!")
```

> 🐍 **Python: type hints.** In `def main() -> None:` the `-> None` *annotates* the return type. Python does **not** enforce hints at runtime; tools (mypy, IDEs) and libraries like Pydantic read them. *Go contrast:* in Go, types are enforced by the compiler. In Python, hints are documentation that some tools choose to enforce.

> 🐍 **Python: `__init__.py`.** A file with this name makes its folder an importable **package**. Its code runs the first time anything imports the package. *Go analogy:* loosely, a package directory, with `__init__.py` acting like package-level init code plus a place to choose what the package exports.

---

## CODE §18 — P1-1: settings + JSON logging (`70b7862`, merged via PR #1)

**Execution order at runtime:**
1. Something imports `app.core`, so `core/__init__.py` runs.
2. That imports `config.py` and `logging.py`, which define their classes and functions. Nothing reads the environment yet.
3. Later, startup calls `get_settings()`. The first call builds a `Settings` object from the environment and `.env`, then caches it.
4. Startup calls `setup_logging()`. Every log line from then on goes through `JsonFormatter`.

At P1-1 nothing calls steps 3–4 yet; there's no `main.py` until P1-2. Only the tests exercise them.

### 18.1 `backend/app/__init__.py`

```python
"""CloudDesk support API."""
```

A docstring only. Its job is to make `backend/app/` a package named `app`, which works because `backend/` is on the import path.

### 18.2 `backend/app/core/__init__.py`

```python
"""Runtime configuration and JSON logging."""

# ◀ Re-export so callers can write `from app.core import get_settings`
from app.core.config import Settings, get_settings
from app.core.logging import log_context, setup_logging

# ◀ __all__ = the package's public API: what `from app.core import *` exports
__all__ = [
    "Settings",
    "get_settings",
    "log_context",
    "setup_logging",
]
```

> 🐍 **Python: `__all__`.** A list of names that a package declares public. *Go analogy:* Go decides what's exported by capitalization. Python has no enforced privacy; `__all__` plus a leading `_` on names (like `_redact_url`) are conventions meaning "internal, don't import."

### 18.3 `backend/app/core/config.py` — full file

```python
"""Process settings loaded from the environment and an optional ``.env`` file.

``get_settings()`` is cached for the life of the process. Restart the server
after a ``.env`` change. Secret fields and URL passwords are omitted from
``repr`` and redacted in ``model_dump()``. Read ``database_url`` and
``redis_url`` from the object when opening a connection.
"""

# ◀ The standard library's memoization decorator (see "lru_cache" below)
from functools import lru_cache
# ◀ Object-oriented filesystem paths (≈ Go's path/filepath, but as objects)
from pathlib import Path
# ◀ Literal["a","b"] = only these exact values are allowed
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_serializer, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> core -> app -> backend -> repository root
# ◀ __file__ = this file's path. .resolve() makes it absolute. .parents[3] walks up 4 levels.
# ◀ The "/" operator on a Path joins path segments, so this is <repo>/.env
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

# ◀ A tuple: an immutable list. The leading "_" marks it module-private by convention
_SECRET_FIELDS = (
    "jwt_secret",
    "supabase_jwt_secret",
    "llm_api_key",
    "qdrant_api_key",
    "langchain_api_key",
)


def _redact_url(url: str) -> str:
    """Hide userinfo in a URL. SQLite paths and empty values stay unchanged."""
    # ◀ Fast exit: no scheme or no "@" means there are no credentials to hide
    if "://" not in url or "@" not in url:
        return url
    # ◀ Splits into (scheme, netloc, path, query, fragment)
    parts = urlsplit(url)
    if parts.username is None and parts.password is None:
        return url
    host = parts.hostname or ""
    if parts.port is not None:
        # ◀ f-string: {expr} is evaluated and inserted, like fmt.Sprintf("%s:%d", ...)
        host = f"{host}:{parts.port}"
    # ◀ Rebuild the URL with "***@host" in place of "user:pass@host"
    return urlunsplit((parts.scheme, f"***@{host}", parts.path, parts.query, parts.fragment))


# ◀ Inheriting BaseSettings is what makes the class load its fields from env vars
class Settings(BaseSettings):
    """Environment contract from ``CLAUDE.md`` section 10.1."""

    # ◀ Class-wide config for pydantic-settings
    model_config = SettingsConfigDict(
        # ◀ Read .env only if it exists ("X if cond else Y" is Python's ternary)
        env_file=str(_ENV_FILE) if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        # ◀ Unknown env vars and .env keys are ignored, not errors
        extra="ignore",
    )

    # ◀ Each line is `field_name: type = default`. The env var is the field name,
    # ◀ matched case-insensitively, so DEMO_MODE fills demo_mode
    # ◀ Strings like "false" or "0" are converted to bool by Pydantic
    demo_mode: bool = True
    environment: str = "development"
    # ◀ A comma-separated string; parsed by cors_origin_list below
    cors_origins: str = "http://localhost:3000"

    # ◀ SecretStr wraps the value so printing shows ********** instead of the secret
    # ◀ repr=False drops the field from repr() entirely
    jwt_secret: SecretStr = Field(default=SecretStr(""), repr=False)
    supabase_jwt_secret: SecretStr = Field(default=SecretStr(""), repr=False)

    # ◀ Async SQLite by default. Postgres in the cloud via asyncpg
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/support.db",
        repr=False,
    )
    checkpoint_db_path: str = "./data/checkpoints.db"

    # ◀ Empty means "use fakeredis" (see uses_fake_redis)
    redis_url: str = Field(default="", repr=False)
    use_fake_redis: bool = False

    # ◀ Offline-first: the fake LLM needs no key (F14)
    llm_provider: str = "fake"
    llm_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    llm_model: str = ""

    embedding_provider: str = "fake"
    embedding_model: str = ""
    embedding_dimensions: int = 384

    # ◀ Any other value fails validation at startup
    vector_store: Literal["memory", "qdrant"] = "memory"
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    qdrant_collection: str = "clouddesk_knowledge"

    # ◀ Refunds always need approval by default
    approval_required_for_refunds: bool = True
    # ◀ 0 means every refund needs approval
    max_refund_without_approval: float = 0
    tool_timeout_seconds: float = 30

    rate_limit_per_minute: int = 120
    sample_data_dir: str = "sample_data"

    # ◀ LangSmith tracing, off by default
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    langchain_project: str = "clouddesk-support"

    # ◀ Runs BEFORE type conversion for these four fields
    @field_validator("llm_provider", "embedding_provider", "vector_store", "environment", mode="before")
    # ◀ Pydantic validators are class methods: they receive the class (cls), not an instance
    @classmethod
    def _normalize_token(cls, value: object) -> object:
        # ◀ "OpenAI " becomes "openai"; non-strings pass through
        if isinstance(value, str):
            return value.strip().lower()
        return value

    # ◀ "*" unpacks the tuple into 5 separate arguments
    @field_serializer(*_SECRET_FIELDS)
    def _serialize_secret(self, value: SecretStr) -> str:
        # ◀ model_dump() calls this for each secret field
        if value.get_secret_value():
            # ◀ A set secret shows as stars...
            return "**********"
        # ◀ ...an unset one shows as "", so you can tell "configured" from "missing"
        return ""

    # ◀ model_dump() hides URL passwords. The attribute itself keeps the real URL
    @field_serializer("database_url", "redis_url")
    def _serialize_url(self, value: str) -> str:
        return _redact_url(value)

    # ◀ @property: called like an attribute (settings.effective_jwt_secret), with no ()
    @property
    def effective_jwt_secret(self) -> str:
        """Supabase JWT secret when set, otherwise ``JWT_SECRET``."""
        supabase = self.supabase_jwt_secret.get_secret_value()
        if supabase:
            return supabase
        return self.jwt_secret.get_secret_value()

    @property
    def cors_origin_list(self) -> list[str]:
        # ◀ A list comprehension: split on commas, strip spaces, drop empty pieces
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def uses_fake_redis(self) -> bool:
        """Fakeredis when ``USE_FAKE_REDIS`` is set or ``REDIS_URL`` is empty."""
        return self.use_fake_redis or self.redis_url.strip() == ""


# ◀ Memoize: the first call builds Settings, every later call returns the same object
@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process settings. Cached until restart; tests call ``cache_clear()``."""
    # ◀ Reads env vars + .env now, and validates every field
    return Settings()
```

**What's happening here (execution order)**
1. **On import:** Python runs the file top to bottom.
   - It computes `_ENV_FILE`, the repo-root `.env` path, whether or not the file exists.
   - It defines `_redact_url`.
   - It defines `Settings`. While doing so, it decides once whether `.env` will be read, based on `_ENV_FILE.is_file()` at that moment.
   - It defines `get_settings`, wrapped by `lru_cache`.
   - Nothing reads the environment yet.
2. **First `get_settings()` call:**
   - `lru_cache` finds no cached result, so the function body runs `Settings()`.
   - pydantic-settings collects values for each field. Explicit constructor arguments win, then real environment variables, then `.env`, then the defaults in the class.
   - The `mode="before"` validator lowercases and strips four fields.
   - Pydantic converts the strings to typed values ("false" → `False`, "384" → `384`) and rejects invalid ones: `vector_store="pinecone"` raises a `ValidationError`.
   - The object is cached.
3. **Later calls** return the *same object*. That's why changing an env var has no effect until `get_settings.cache_clear()` or a restart. One test proves exactly this.
4. **Printing or dumping:**
   - `repr(settings)` skips every `repr=False` field.
   - `settings.model_dump()` (dict export) calls the two `field_serializer`s: secrets become `"**********"` or `""`, and URL passwords become `***`.
   - The attributes themselves still hold real values (`settings.database_url`), so connection code works.

**EXECUTED demo output** (my script against this file, with a fake key; timestamps removed):
```text
dump: ********** postgresql+asyncpg://***@db:5432/support fake True
attr: postgresql+asyncpg://user:pw@db:5432/support
```

> 🧩 **First time in the course: pydantic-settings `BaseSettings`.**
> - **What:** a Pydantic model whose fields are filled from environment variables and `.env`, with type conversion and validation.
> - **Why:** one typed, validated config contract instead of `os.getenv("X")` calls scattered through the code returning untyped strings or `None`.
> - **Without it:** typos in variable names fail silently, "false" is a truthy string, and a bad `VECTOR_STORE` surfaces deep in a request instead of at boot.
> - *Go analogy:* `envconfig`/`viper` decoding into a struct with tags, plus validation, in one step.

> 🧩 **First time: `SecretStr`.**
> - **What:** a string wrapper whose `str()` and `repr()` print `**********`. You must call `.get_secret_value()` to read it.
> - **Why:** secrets leak through `print(settings)`, error messages, and debug logs.
> - **Without it:** one careless log line puts your LLM key in your log aggregator.
> - *Go analogy:* a named type with a `String()` method that returns a mask.

> 🧩 **First time: Pydantic `Field`, `field_validator`, `field_serializer`.**
> - `Field(...)` attaches options to a field (default, `repr=False`).
> - A **validator** transforms or checks *incoming* values.
> - A **serializer** controls *outgoing* values when the model is dumped.
> - **Why:** keep input cleanup and output redaction declared next to the field, not scattered through call sites.

> 🧩 **First time: `@lru_cache`.**
> - **What:** a decorator that remembers a function's result per argument set. With no arguments and `maxsize=1`, it makes a process-wide singleton.
> - **Why:** parse and validate config once, not on every request.
> - **Trade-off:** you must restart (or `cache_clear()`) after config changes. CLAUDE.md says exactly that.
> - *Go analogy:* `sync.Once` around a package-level config variable.

> 🐍 **Python: decorators (`@something` above a `def`).** A decorator is a function that takes a function and returns a replacement. `@lru_cache(maxsize=1)` above `get_settings` means `get_settings = lru_cache(maxsize=1)(get_settings)`. Stacked decorators apply bottom-up, which is why `@classmethod` sits *under* `@field_validator`: the method becomes a classmethod first, then gets registered as a validator. *Go analogy:* middleware wrapping, `h = withCache(h)`, written declaratively.

> 🐍 **Python: `@classmethod` vs `@property`.**
> - A classmethod's first parameter is the class (`cls`), not an instance.
> - A property turns a method into a read-only computed attribute: `settings.cors_origin_list`, no parentheses.
> - *Go analogy:* a property ≈ a getter method you call without `()`.

> 🐍 **Python: `*` in a call — `field_serializer(*_SECRET_FIELDS)`.** The `*` spreads the tuple into separate positional arguments, equivalent to writing the five names out. *Go analogy:* `f(names...)`.

> 🐍 **Python: list comprehension** — `[origin.strip() for origin in s.split(",") if origin.strip()]`. Read it as: "for each `origin` in the split pieces, *if* it's non-empty after stripping, keep `origin.strip()`." *Go equivalent:* a `for` loop that appends to a slice. Comprehensions are the idiomatic Python form.

> 🐍 **Python: `Literal[...]` and `X if cond else Y`.** `Literal["memory", "qdrant"]` is a type hint that Pydantic *enforces*: other values raise a `ValidationError`. `a if cond else b` is Python's ternary expression.

**Code review notes** (my observations, not narrated)
- **IPv6 redaction edge case** [EXECUTED]: `_redact_url("postgresql+asyncpg://u:p@[::1]:5432/db")` returns `…//***@::1:5432/db`. The IPv6 brackets are lost because `hostname` strips them. It's cosmetic, since this only affects the redacted dump, not real connections, but it's a nice example for "read the edge cases of the stdlib API you call."
- **Money as float** [Supplementary]: `max_refund_without_approval: float`. Floats can't represent decimal money exactly; `Decimal` is the usual choice for currency. It's harmless at the default `0`, but worth raising in a design review once refund amounts are compared against it.
- **`.env` is read only if it existed at import time.** `env_file` is decided when the class is defined. Create `.env` after the app has started and it's ignored until a restart. That's consistent with the "restart after .env change" rule.

### 18.4 `backend/app/core/logging.py` — full file

```python
"""JSON logs. Every line includes ``request_id`` and ``workflow_id``.

Call ``setup_logging()`` once at process startup. Bind the ids for the current
task with ``log_context`` (request middleware and workflow runs). Unset ids are
JSON ``null``. Extra log attributes are not copied onto the line.
"""

# ◀ Per-task "global" variables that are safe under asyncio concurrency
import contextvars
import json
# ◀ Python's standard logging framework (≈ log/slog)
import logging
from collections.abc import Iterator
# ◀ Turns a generator function into a `with`-block helper
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import TextIO


# ◀ Type hint: a ContextVar holding "str or None". Default None = "not set in this context"
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)
workflow_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workflow_id",
    default=None,
)


# ◀ A sentinel type: lets log_context tell "argument not passed" apart from "passed None"
class _Unset:
    """Marks a ``log_context`` argument the caller did not pass."""


# ◀ The one sentinel instance
_UNSET = _Unset()


# ◀ A Filter runs on every record before formatting. Returning True keeps the record
class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # ◀ Only fill the ids if the caller didn't set them via extra=...
        if getattr(record, "request_id", None) is None:
            record.request_id = request_id_var.get()
        if getattr(record, "workflow_id", None) is None:
            record.workflow_id = workflow_id_var.get()
        return True


# ◀ A Formatter turns a LogRecord into the final string
class JsonFormatter(logging.Formatter):
    """One JSON object per line, with a fixed set of keys."""

    def format(self, record: logging.LogRecord) -> str:
        # ◀ Prefer an id set on the record; otherwise fall back to the context
        request_id = getattr(record, "request_id", None)
        if request_id is None:
            request_id = request_id_var.get()
        workflow_id = getattr(record, "workflow_id", None)
        if workflow_id is None:
            workflow_id = workflow_id_var.get()
        # ◀ A FIXED key set: arbitrary extra= attributes (like api_key) never reach the line
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            # ◀ Applies %-style args: log.info("x=%s", 1)
            "message": record.getMessage(),
            "request_id": request_id,
            "workflow_id": workflow_id,
        }
        # ◀ logger.exception(...) attaches exc_info
        if record.exc_info and record.exc_info[0] is not None:
            # ◀ The traceback becomes one JSON string; json escapes the newlines
            payload["exception"] = self.formatException(record.exc_info)
        # ◀ Newlines become \n inside the string, so it's always ONE line
        return json.dumps(payload, ensure_ascii=True)


def _coerce_level(level: int | str) -> int:
    if isinstance(level, int):
        return level
    try:
        # ◀ "info" becomes 20. getLevelNamesMapping is new in Python 3.11
        return logging.getLevelNamesMapping()[level.strip().upper()]
    except KeyError as exc:
        # ◀ Re-raise as a clearer error, keeping the original as the cause
        raise ValueError(f"Unknown log level: {level}") from exc


def setup_logging(level: int | str = logging.INFO, stream: TextIO | None = None) -> None:
    """Attach a single JSON handler to the root logger."""
    # ◀ The root logger is the ancestor of every logger in the process
    root = logging.getLogger()
    # ◀ [:] iterates over a copy, because we mutate the list while looping
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    # ◀ stream=None means stderr. Tests pass a StringIO buffer
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(_ContextFilter())
    root.addHandler(handler)
    root.setLevel(_coerce_level(level))


@contextmanager
def log_context(
    # ◀ A bare * means every parameter after it must be passed by name
    *,
    request_id: str | None | _Unset = _UNSET,
    workflow_id: str | None | _Unset = _UNSET,
) -> Iterator[None]:
    """Bind ids for the current context. Omitted arguments are left unchanged."""
    # ◀ Remember how to undo each set() call
    tokens: list[tuple[contextvars.ContextVar[str | None], contextvars.Token[str | None]]] = []
    if not isinstance(request_id, _Unset):
        # ◀ set() returns a Token used to restore the previous value
        tokens.append((request_id_var, request_id_var.set(request_id)))
    if not isinstance(workflow_id, _Unset):
        tokens.append((workflow_id_var, workflow_id_var.set(workflow_id)))
    try:
        # ◀ The body of the caller's `with` block runs here
        yield
    finally:
        # ◀ Always undo, even if the with-body raised. Undo in reverse order
        for var, token in reversed(tokens):
            var.reset(token)
```

**What's happening here (execution order)**
1. **On import:** two `ContextVar`s are created, each defaulting to `None`. The classes are defined.
2. **`setup_logging()` at startup:**
   - It strips every existing root handler, so you never get duplicate or plain-text lines.
   - It installs one `StreamHandler` with the JSON formatter and the context filter.
   - It sets the level. Anything below it, for example DEBUG when the level is INFO, is dropped before formatting.
3. **During a request**, middleware does `with log_context(request_id="abc"): ...`:
   - The context manager runs up to `yield`, setting `request_id_var` to `"abc"` *for this async task only*.
   - The `with` body runs. Every `logger.info(...)` inside it:
     1. creates a `LogRecord`,
     2. passes through `_ContextFilter`, which copies the ids onto the record,
     3. reaches `JsonFormatter.format`, which builds a fixed-key dict and dumps it as one JSON line.
   - On exit, even after an exception, the `finally` block resets the variable to its previous value.
4. **Nesting works.** An inner `log_context(workflow_id="wf")` adds the workflow id; leaving it restores the outer state. A test proves this.

**EXECUTED demo output:**
```text
{"timestamp": "<ts>", "level": "INFO", "logger": "clouddesk", "message": "outside", "request_id": null, "workflow_id": null}
{"timestamp": "<ts>", "level": "INFO", "logger": "clouddesk", "message": "inner", "request_id": "req-1", "workflow_id": "wf-9"}
```

> 🧩 **First time: `contextvars`.**
> - **What:** variables whose value is per *execution context*. Each asyncio task gets its own copy.
> - **Why:** FastAPI serves many requests concurrently on one thread. A plain global `current_request_id` would be overwritten by whichever request ran last, mixing ids across requests.
> - **Without it:** you'd pass `request_id` through every function signature by hand.
> - *Go analogy:* `context.Context` carrying a request-scoped value. Python stores it implicitly instead of making you pass `ctx` everywhere.

> 🧩 **First time: `logging.Filter` / `logging.Formatter` / handlers.** Python logging is a pipeline: logger → (filters) → handler → formatter → output stream. *Go analogy:* `slog` with a custom `Handler` that adds attributes and encodes JSON.

> 🐍 **Python: context managers, `with`, and `@contextmanager`.**
> - `with x:` guarantees setup *and* cleanup around a block, like Go's `defer` but scoped to the block.
> - `@contextmanager` lets you write one as a generator: code before `yield` = setup, code after (in `finally`) = cleanup.
> - **Without `finally`:** an exception inside the block would leave the old ids bound, and later log lines would carry the wrong request id.

> 🐍 **Python: `yield`.** A function containing `yield` is a *generator*: it pauses at `yield` and resumes later. Here `@contextmanager` drives that pause and resume around the `with` body. You'll meet `yield` again in pytest fixtures (18.5) and later for streaming LLM tokens.

> 🐍 **Python: keyword-only parameters (a bare `*`) and `str | None`.**
> - In `def log_context(*, request_id=...)`, the bare `*` forces callers to write `log_context(request_id="x")`. Positional calls are rejected, which prevents swapping the two ids by accident.
> - `str | None` (Python 3.10+) is a union type: "a string or None."

> 🐍 **Python: the sentinel pattern (`_UNSET`).** Here `None` is a *meaningful* value ("explicitly clear the id"), so a different default is needed to mean "not passed." A unique private object does that job. *Go analogy:* using a pointer, or a `(value, ok)` pair, to tell "zero value" from "not provided."

> 🐍 **Python: `try / except … as exc` and `raise … from exc`.** This catches a specific error and raises a clearer one while chaining the original as its cause, so tracebacks show both. *Go analogy:* `fmt.Errorf("unknown log level %q: %w", lvl, err)`.

### 18.5 `tests/unit/test_config_logging.py` — full file (EXECUTED: 14 passed)

```python
"""F14 offline settings, and JSON logs that always carry request and workflow ids."""

import io
import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.logging import JsonFormatter, log_context, setup_logging

# ◀ The env contract from CLAUDE.md §10.1, duplicated ON PURPOSE as a test oracle
_ENV_KEYS = (
    "DEMO_MODE",
    "ENVIRONMENT",
    "CORS_ORIGINS",
    "JWT_SECRET",
    "SUPABASE_JWT_SECRET",
    "DATABASE_URL",
    "CHECKPOINT_DB_PATH",
    "REDIS_URL",
    "USE_FAKE_REDIS",
    "LLM_PROVIDER",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_PROVIDER",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "VECTOR_STORE",
    "QDRANT_URL",
    "QDRANT_API_KEY",
    "QDRANT_COLLECTION",
    "APPROVAL_REQUIRED_FOR_REFUNDS",
    "MAX_REFUND_WITHOUT_APPROVAL",
    "TOOL_TIMEOUT_SECONDS",
    "RATE_LIMIT_PER_MINUTE",
    "SAMPLE_DATA_DIR",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_PROJECT",
)


# ◀ autouse=True: this fixture wraps EVERY test in the file automatically
@pytest.fixture(autouse=True)
def _clear_settings_cache():
    # ◀ Before each test: start with a clean cache
    get_settings.cache_clear()
    # ◀ The test runs here
    yield
    # ◀ After each test: don't leak cached settings into the next one
    get_settings.cache_clear()


# ◀ Opt-in: only tests that NAME `log_buffer` as a parameter get it
@pytest.fixture
def log_buffer():
    root = logging.getLogger()
    # ◀ Snapshot the global logging state...
    saved_handlers = root.handlers[:]
    saved_level = root.level
    # ◀ ...then capture logs into an in-memory "file"
    buffer = io.StringIO()
    setup_logging(stream=buffer)
    # ◀ The test receives `buffer` as its argument
    yield buffer
    # ◀ Teardown: restore the global state exactly
    root.handlers.clear()
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


# ◀ **extra collects any keyword arguments into a dict
def _record(message: str, **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        # ◀ Simulates logger.info(..., extra={...})
        setattr(record, key, value)
    return record


def _isolated_settings(**overrides: object) -> Settings:
    # ◀ _env_file=None ignores any local .env; **overrides spreads the dict into keyword args
    return Settings(_env_file=None, **overrides)


def test_settings_fields_match_env_contract():
    # ◀ Set comprehension: the field names, uppercased, must EXACTLY equal the contract
    assert {name.upper() for name in Settings.model_fields} == set(_ENV_KEYS)


# ◀ monkeypatch = pytest's tool for temporary env/attribute changes, auto-undone after the test
def test_f14_offline_defaults_need_no_api_key(monkeypatch: pytest.MonkeyPatch):
    for key in _ENV_KEYS:
        # ◀ Wipe the real environment, so only defaults apply
        monkeypatch.delenv(key, raising=False)
    settings = _isolated_settings()
    assert settings.demo_mode is True
    assert settings.llm_provider == "fake"
    assert settings.embedding_provider == "fake"
    assert settings.llm_api_key.get_secret_value() == ""
    assert settings.vector_store == "memory"
    assert settings.embedding_dimensions == 384
    assert settings.qdrant_collection == "clouddesk_knowledge"
    assert settings.approval_required_for_refunds is True
    assert settings.max_refund_without_approval == 0
    assert settings.rate_limit_per_minute == 120
    assert settings.langchain_tracing_v2 is False
    assert settings.langchain_project == "clouddesk-support"
    assert settings.database_url == "sqlite+aiosqlite:///./data/support.db"
    assert settings.checkpoint_db_path == "./data/checkpoints.db"
    assert settings.uses_fake_redis is True
    assert settings.cors_origin_list == ["http://localhost:3000"]
    assert settings.effective_jwt_secret == ""


def test_settings_read_demo_mode_and_llm_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    # ◀ Mixed case on purpose, to exercise the validator
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    settings = get_settings()
    # ◀ The string "false" became the bool False
    assert settings.demo_mode is False
    assert settings.llm_provider == "openai"
    # ◀ `is` = same object, which proves the cache
    assert get_settings() is settings


def test_get_settings_keeps_cached_values_until_cleared(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    get_settings.cache_clear()
    assert get_settings().llm_provider == "fake"
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    # ◀ STILL "fake": the cached object wins
    assert get_settings().llm_provider == "fake"
    get_settings.cache_clear()
    # ◀ Only after clearing does the new env value apply
    assert get_settings().llm_provider == "anthropic"


def test_effective_jwt_secret_prefers_supabase_secret():
    local_only = _isolated_settings(jwt_secret="local-secret")
    assert local_only.effective_jwt_secret == "local-secret"
    both = _isolated_settings(jwt_secret="local-secret", supabase_jwt_secret="supabase-secret")
    assert both.effective_jwt_secret == "supabase-secret"


def test_uses_fake_redis_when_forced_or_url_missing():
    assert _isolated_settings(redis_url="redis://redis:6379/0").uses_fake_redis is False
    forced = _isolated_settings(redis_url="redis://redis:6379/0", use_fake_redis=True)
    assert forced.uses_fake_redis is True


def test_cors_origins_split_on_commas():
    settings = _isolated_settings(cors_origins="http://localhost:3000, http://127.0.0.1:3000")
    assert settings.cors_origin_list == ["http://localhost:3000", "http://127.0.0.1:3000"]


def test_vector_store_rejects_unknown_backend():
    # ◀ The test passes only if this block raises ValidationError
    with pytest.raises(ValidationError):
        _isolated_settings(vector_store="pinecone")


def test_repr_and_dump_hide_secrets_and_url_passwords():
    settings = _isolated_settings(
        jwt_secret="jwt-secret-value",
        # ◀ A fake test value, not a real key
        llm_api_key="sk-live-123",
        database_url="postgresql+asyncpg://user:s3cret-pass@localhost:5432/support",
        redis_url="redis://:redis-pass@localhost:6379/0",
    )
    # ◀ !r = repr(), !s = str()
    rendered = f"{settings!r} {settings!s}"
    assert "jwt-secret-value" not in rendered
    assert "sk-live-123" not in rendered
    assert "s3cret-pass" not in rendered
    assert "redis-pass" not in rendered
    dumped = settings.model_dump()
    assert dumped["jwt_secret"] == "**********"
    assert dumped["llm_api_key"] == "**********"
    assert dumped["database_url"] == "postgresql+asyncpg://***@localhost:5432/support"
    assert dumped["redis_url"] == "redis://***@localhost:6379/0"
    # ◀ The real values are still usable for connecting
    assert settings.database_url == "postgresql+asyncpg://user:s3cret-pass@localhost:5432/support"
    assert settings.jwt_secret.get_secret_value() == "jwt-secret-value"


def test_json_formatter_includes_ids_and_ignores_extra_fields():
    formatter = JsonFormatter()
    # ◀ An extra attribute on the record (api_key) must NOT appear in the output
    record = _record("hello\nworld", api_key="sk-live-should-not-appear", request_id="req-extra")
    with log_context(request_id="req-context", workflow_id="wf-1"):
        line = formatter.format(record)
    # ◀ One physical line, even though the message contains a newline
    assert "\n" not in line
    assert "sk-live-should-not-appear" not in line
    payload = json.loads(line)
    assert payload["message"] == "hello\nworld"
    # ◀ The record's own id beats the context's
    assert payload["request_id"] == "req-extra"
    assert payload["workflow_id"] == "wf-1"
    assert set(payload) == {
        "timestamp",
        "level",
        "logger",
        "message",
        "request_id",
        "workflow_id",
    }


def test_log_context_restores_outer_ids():
    formatter = JsonFormatter()
    with log_context(request_id="req"):
        with log_context(workflow_id="wf"):
            inner = json.loads(formatter.format(_record("inner")))
        outer = json.loads(formatter.format(_record("outer")))
    outside = json.loads(formatter.format(_record("outside")))
    assert inner["request_id"] == "req"
    assert inner["workflow_id"] == "wf"
    assert outer["request_id"] == "req"
    # ◀ The inner block's workflow id was reset on exit
    assert outer["workflow_id"] is None
    assert outside["request_id"] is None
    assert outside["workflow_id"] is None


# ◀ Naming the parameter `log_buffer` makes pytest inject that fixture
def test_setup_logging_writes_one_json_line(log_buffer: io.StringIO):
    with log_context(request_id="req-42", workflow_id="wf-7"):
        logging.getLogger("clouddesk").warning("ticket queued")
    # ◀ Below the INFO level, so it's dropped
    logging.getLogger("clouddesk").debug("hidden")
    lines = [line for line in log_buffer.getvalue().splitlines() if line]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "clouddesk"
    assert payload["message"] == "ticket queued"
    assert payload["request_id"] == "req-42"
    assert payload["workflow_id"] == "wf-7"


def test_setup_logging_includes_exception_on_one_line(log_buffer: io.StringIO):
    logger = logging.getLogger("clouddesk")
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        # ◀ Logs at ERROR level and attaches the traceback
        logger.exception("failed")
    line = log_buffer.getvalue().splitlines()[-1]
    assert "\n" not in line
    payload = json.loads(line)
    assert "RuntimeError: boom" in payload["exception"]
    assert payload["request_id"] is None
    assert payload["workflow_id"] is None


def test_setup_logging_replaces_previous_handlers(log_buffer: io.StringIO):
    # ◀ Calling it twice must not stack handlers (no duplicate lines)
    setup_logging(stream=log_buffer)
    root = logging.getLogger()
    assert len(root.handlers) == 1
```

**What's happening here (execution order)**
1. You run `uv run pytest -q`. pytest reads `[tool.pytest.ini_options]`, puts `backend/` on the import path, and collects every `test_*` function: 14 tests.
2. **For each test**, pytest looks at the parameter names and supplies matching fixtures: `monkeypatch` (built in) and `log_buffer` (defined here). The autouse `_clear_settings_cache` wraps every test regardless.
3. **Each fixture runs up to its `yield`** (setup), the test body runs, then the code after `yield` runs (teardown), even if the test failed.
4. **Plain `assert`** statements are the checks. pytest rewrites them to print both sides on failure; that's how you got the `SecretStr('**********') == '**********'` message in break-it experiment 1.
5. **The first test is the clever one:** it compares the *set* of field names to the env contract. If anyone adds an env var to CLAUDE.md without adding a field, or the reverse, the test fails. This is the "spec drift" defence in code.

**EXECUTED result:** `14 passed in 0.16s`. That matches the instructor's MEMORY.md note: "14 passed on this machine."

> 🧩 **First time: pytest fixtures.**
> - **What:** functions that provide setup and teardown, injected into tests by parameter name.
> - **Why:** shared, guaranteed-cleanup test state without repeating setup in every test.
> - **Without it:** every test would copy the handler save/restore code, and one forgotten restore would break unrelated tests later in the run (logging config is process-global).
> - *Go analogy:* a `setup(t)` helper that calls `t.Cleanup(...)`, injected automatically.

> 🧩 **First time: `monkeypatch`.** Temporarily sets or deletes env vars and attributes, and reverts them after the test. *Go analogy:* `t.Setenv(...)`.

> 🧩 **First time: `pytest.raises`.** A context manager that passes only if its block raises the given exception. *Go analogy:* checking `err != nil` plus `errors.As`.

> 🐍 **Python: `**kwargs` and `**dict` in a call.**
> - In a *definition*, `def f(**extra)` collects any keyword arguments into a dict.
> - In a *call*, `Settings(**overrides)` spreads a dict back out into keyword arguments.
> - *Go analogy:* there's no direct equivalent; the closest is passing an options struct.

> 🐍 **Python: set comprehension** — `{name.upper() for name in Settings.model_fields}`. This is the list-comprehension syntax with `{}`, and it produces a set, where order doesn't matter and duplicates collapse. `set(a) == set(b)` checks "same members."

> 🐍 **Python: `f"{x!r}"`.** `!r` formats with `repr()` (the debug form) and `!s` with `str()`. The test checks that neither form leaks secrets.

---

## Constructs introduced this session

These are already in the README Glossary; repeated here as your code vocabulary.

| Construct | One-line meaning |
|---|---|
| `[project.scripts]` / `[build-system]` / `[dependency-groups]` / `[tool.pytest.ini_options]` | Entry-point command / how to build / dev-only deps / pytest config |
| `BaseSettings` + `SettingsConfigDict` | Typed config loaded from env + `.env` |
| `SecretStr` / `.get_secret_value()` | Masked string / explicitly read the secret |
| `Field(default=…, repr=False)` | Field options (hide from repr) |
| `@field_validator(…, mode="before")` | Clean incoming values before type conversion |
| `@field_serializer(…)` | Control values in `model_dump()` |
| `@lru_cache` / `.cache_clear()` | Memoize (singleton config) / reset |
| `contextvars.ContextVar` / `.set()` / `.reset(token)` | Per-task variable / bind / restore |
| `logging.Filter` / `logging.Formatter` / `StreamHandler` | Enrich records / render a line / write to a stream |
| `@contextmanager` + `yield` + `try/finally` | Write a `with` helper with guaranteed cleanup |
| `@pytest.fixture(autouse=True)` / `yield` fixtures | Setup/teardown injected into tests |
| `monkeypatch.setenv/delenv` / `pytest.raises` | Temporary env changes / expect an exception |