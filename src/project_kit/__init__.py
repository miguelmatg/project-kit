"""project-kit: define, plan and set up a project before handing off to Spec Kit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("project-kit-cli")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
