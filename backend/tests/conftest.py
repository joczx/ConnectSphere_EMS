"""Keep integration tests out of the normal run.

They write to a real Supabase project, so `pytest tests/` stays offline unless
RUN_INTEGRATION_TESTS=1 is set. See tests/integration/conftest.py.
"""

import os

collect_ignore = [] if os.environ.get("RUN_INTEGRATION_TESTS") == "1" else ["integration"]
