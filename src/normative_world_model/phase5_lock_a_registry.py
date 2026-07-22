"""Committed Phase-5 Lock-A deployment trust root.

This tiny registry is deliberately separate from the execution sources hashed
inside the public-synthetic client plan.  A reviewed acceptance binds that
fixed plan; a later deployment commit may then register the acceptance digest
here without changing the plan it accepts.  The deployment commit and clean
tree are reviewed independently.  Callers still cannot supply a trust root.
"""

REGISTERED_LOCK_A_ACCEPTANCE_SHA256: str | None = (
    "63620c0147b15e6e16d93d36580b0a44e6f6bb60ba31fe4094aa0197e339a27e"
)
