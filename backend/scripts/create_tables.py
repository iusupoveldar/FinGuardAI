from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_DIR = Path(__file__).resolve().parent.parent


def create_tables() -> None:
    """Upgrade the configured database to the latest reviewed migration."""
    print("Applying database migrations...")
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    print("Done")


if __name__ == "__main__":

    create_tables()
