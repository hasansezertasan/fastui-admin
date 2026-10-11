"""Smoke tests for fastui_admin package."""


def test_smoke() -> None:
    """Test that the package can be imported."""
    import fastui_admin  # noqa: PLC0415

    assert fastui_admin is not None
