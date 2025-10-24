"""Minimal smoke tests for the compliance service scaffolding."""


def test_package_importable() -> None:
    """Ensure the top-level package exposes the expected namespace."""
    import compliance_service  # noqa: F401  # Imported for side effects
