"""Committed Phase-5 Lock-A deployment trust root.

This tiny registry is deliberately separate from the execution sources hashed
inside the public-synthetic client plan.  A reviewed acceptance binds that
fixed plan; a later deployment commit may then register the acceptance digest
here without changing the plan it accepts.  The deployment commit and clean
tree are reviewed independently.  Callers still cannot supply a trust root.
"""

REGISTERED_LOCK_A_ACCEPTANCE_SHA256: str | None = (
    "7621b7c56e1e2f14c504e8a4d3974a657c5a2ead26bd3a91c5294c0f4f8a28b8"
)
