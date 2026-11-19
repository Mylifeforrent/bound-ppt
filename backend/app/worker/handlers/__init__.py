"""Job handler package.

Each handler module registers itself with `app.worker.runner.register`.
The runner imports this package once during application startup.
"""

from app.worker.handlers import generation, maintenance, research  # noqa: F401
