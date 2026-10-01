"""Celery helpers (ADR-0001 section 6).

Every task that touches business data is declared with ``@tenant_task``: its
first argument is the business ID and its body runs inside tenant_context(),
so row-level security applies exactly as in a request. tests/test_code_rules.py
fails if a task in apps/*/tasks.py is declared any other way without a
"# platform-scope: <reason>" marker.
"""

import functools
from collections.abc import Callable
from typing import Any

from celery import shared_task

from apps.core.tenant_context import tenant_context


def tenant_task(func: Callable[..., Any] | None = None, **task_options: Any) -> Any:
    def decorate(f: Callable[..., Any]) -> Any:
        @functools.wraps(f)
        def run(business_id: str, *args: Any, **kwargs: Any) -> Any:
            with tenant_context(business_id):
                return f(business_id, *args, **kwargs)

        return shared_task(name=f"{f.__module__}.{f.__name__}", **task_options)(run)

    return decorate(func) if func is not None else decorate
