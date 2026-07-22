"""Committed Phase-5 Lock-A deployment trust root.

This tiny registry is deliberately separate from the execution sources hashed
inside the public-synthetic client plan.  A reviewed acceptance binds that
fixed plan; a later deployment commit may then register the acceptance digest
here without changing the plan it accepts.  The deployment commit and clean
tree are reviewed independently.  Callers still cannot supply a trust root.
"""

REGISTERED_LOCK_A_ACCEPTANCE_SHA256: str | None = (
    "0fa6b4b239efdc797f918af6adc237f92fa858eebc1b2fb93cd522aed59a2ca3"
)
