from __future__ import annotations

import os
from typing import Any

from nexus_core.observability import get_logger


logger = get_logger("nexus.sentry")
_SENTRY = None
_INITIALIZED = False


def sentry_enabled() -> bool:
    return bool(os.getenv("SENTRY_DSN", "").strip()) and os.getenv(
        "NEXUS_SENTRY_ENABLED", "1"
    ).strip().lower() in {"1", "true", "yes", "on"}


def init_sentry(*, module: str = "nexus") -> bool:
    global _SENTRY, _INITIALIZED
    if _INITIALIZED:
        return _SENTRY is not None
    _INITIALIZED = True
    if not sentry_enabled():
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except Exception as exc:
        logger.warning("Sentry SDK unavailable: %s", exc)
        return False

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", "").strip(),
        environment=os.getenv("NEXUS_ENV", "local"),
        release=os.getenv("NEXUS_RELEASE", "local"),
        traces_sample_rate=float(os.getenv("NEXUS_SENTRY_TRACES_SAMPLE_RATE", "0")),
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(event_level=None),
        ],
    )
    sentry_sdk.set_tag("module", module)
    sentry_sdk.set_tag("autonomy_level", os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED"))
    _SENTRY = sentry_sdk
    return True


def add_breadcrumb(
    message: str, *, category: str = "nexus", data: dict[str, Any] | None = None
) -> None:
    if not init_sentry(module=category):
        return
    _SENTRY.add_breadcrumb(category=category, message=message, data=data or {})


def capture_exception(
    exc: BaseException,
    *,
    module: str,
    tags: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    if not init_sentry(module=module):
        return
    with _SENTRY.push_scope() as scope:
        _apply_scope(scope, module=module, tags=tags, context=context)
        _SENTRY.capture_exception(exc)


def capture_message(
    message: str,
    *,
    module: str,
    level: str = "error",
    tags: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    if not init_sentry(module=module):
        return
    with _SENTRY.push_scope() as scope:
        _apply_scope(scope, module=module, tags=tags, context=context)
        _SENTRY.capture_message(message, level=level)


def _apply_scope(
    scope: Any,
    *,
    module: str,
    tags: dict[str, Any] | None,
    context: dict[str, Any] | None,
) -> None:
    scope.set_tag("module", module)
    scope.set_tag("autonomy_level", os.getenv("NEXUS_AUTONOMY_LEVEL", "GUARDED"))
    for key, value in (tags or {}).items():
        if value is not None:
            scope.set_tag(key, str(value))
    if context:
        scope.set_context(module, context)
