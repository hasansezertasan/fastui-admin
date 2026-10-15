"""Look up the version of the installed distribution."""

from importlib.metadata import version

PROJECT_NAME = "fastui-admin"


def version_lookup() -> str:
    """Return the installed distribution version for this project.

    Returns:
        str: The installed distribution version.
    """
    return version(PROJECT_NAME)
