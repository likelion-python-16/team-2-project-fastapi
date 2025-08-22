from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "9942e89fde9e"
down_revision: Union[str, Sequence[str], None] = "d0c0e356a69b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols

def upgrade() -> None:
    # --- challenge_rounds ---
    if not _has_column("challenge_rounds", "place_name"):
        op.add_column("challenge_rounds",
                      sa.Column("place_name", sa.String(length=100), nullable=True, comment="장소명"))
    if not _has_column("challenge_rounds", "road_address"):
        op.add_column("challenge_rounds",
                      sa.Column("road_address", sa.String(length=255), nullable=True, comment="도로명 주소"))
    if not _has_column("challenge_rounds", "map_url"):
        op.add_column("challenge_rounds",
                      sa.Column("map_url", sa.Text(), nullable=True, comment="네이버 지도 링크(참여자 노출용)"))

    # --- challenges ---
    if not _has_column("challenges", "max_participation_rate"):
        op.add_column("challenges",
                      sa.Column("max_participation_rate", sa.Integer(), nullable=True, comment="최대 참여율 (%)"))
    if not _has_column("challenges", "mode"):
        op.add_column("challenges",
                      sa.Column("mode", sa.Enum("online", "offline", "hybrid", name="challenge_mode_enum"),
                                nullable=False))
    if not _has_column("challenges", "default_zoom_link"):
        op.add_column("challenges",
                      sa.Column("default_zoom_link", sa.String(length=255), nullable=True))
    if not _has_column("challenges", "default_place_name"):
        op.add_column("challenges",
                      sa.Column("default_place_name", sa.String(length=100), nullable=True))
    if not _has_column("challenges", "default_road_address"):
        op.add_column("challenges",
                      sa.Column("default_road_address", sa.String(length=255), nullable=True))
    if not _has_column("challenges", "default_address"):
        op.add_column("challenges",
                      sa.Column("default_address", sa.String(length=255), nullable=True))

def downgrade() -> None:
    # --- challenges ---
    if _has_column("challenges", "default_address"):
        op.drop_column("challenges", "default_address")
    if _has_column("challenges", "default_road_address"):
        op.drop_column("challenges", "default_road_address")
    if _has_column("challenges", "default_place_name"):
        op.drop_column("challenges", "default_place_name")
    if _has_column("challenges", "default_zoom_link"):
        op.drop_column("challenges", "default_zoom_link")
    if _has_column("challenges", "mode"):
        op.drop_column("challenges", "mode")
    if _has_column("challenges", "max_participation_rate"):
        op.drop_column("challenges", "max_participation_rate")

    # --- challenge_rounds ---
    if _has_column("challenge_rounds", "map_url"):
        op.drop_column("challenge_rounds", "map_url")
    if _has_column("challenge_rounds", "road_address"):
        op.drop_column("challenge_rounds", "road_address")
    if _has_column("challenge_rounds", "place_name"):
        op.drop_column("challenge_rounds", "place_name")
