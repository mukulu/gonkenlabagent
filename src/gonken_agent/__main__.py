"""Allow ``python -m gonken_agent`` to use the package CLI."""

from .cli import entrypoint


if __name__ == "__main__":
    entrypoint()
