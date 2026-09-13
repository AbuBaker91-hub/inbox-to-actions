from pathlib import Path

import pytest
from aiforge_core.testing import *  # noqa: F401,F403

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def prompts_dir():
    return str(ROOT / "prompts")


@pytest.fixture
def project_migrations_dir():
    return str(ROOT / "migrations")
