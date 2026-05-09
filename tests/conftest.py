"""
Root-level pytest configuration.

POSTGRES_PASSWORD has no default in Settings (intentional fail-fast for production).
Setting it here at module level — before any test module is imported — ensures
`settings = Settings()` succeeds when src.core.config is first imported during
test collection.  Using os.environ.setdefault means a real password from the
shell environment (integration tests against a live DB) is never overridden.
"""

import os

os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
