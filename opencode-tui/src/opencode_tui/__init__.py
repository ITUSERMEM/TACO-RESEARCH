from importlib.metadata import version as _v, PackageNotFoundError

try:
    __version__ = _v("opencode-tui")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
