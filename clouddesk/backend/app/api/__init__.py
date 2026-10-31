"""HTTP routes.

This layer does HTTP, validation, auth, RBAC and background tasks — and no
business rules (CLAUDE.md §4.2). Routers mount under `/api/v1`, except the
health routes, which are unprefixed because probes call them directly.
"""
