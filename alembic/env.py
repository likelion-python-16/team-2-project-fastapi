from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# 🔧 프로젝트 루트를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

# 🔧 우리 모델들 import
from app.core.config import settings
from app.models.base import Base

# 🔧 모든 모델들을 명시적으로 import (Alembic이 감지할 수 있도록)
from app.models.user import User
from app.models.challenge import Challenge
from app.models.challenge_participant import ChallengeParticipant
from app.models.challenge_round import ChallengeRound
from app.models.round_attendance import RoundAttendance
# 새로운 모델 추가시 여기에 import 추가

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 🔧 환경변수에서 DB URL 가져오기
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 🔧 우리 모델들의 메타데이터 설정
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()