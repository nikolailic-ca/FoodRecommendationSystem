"""initial schema

Rucno pisana migracija (ne autogenerate) zbog pg_trgm ekstenzije i GIN
opclass-ova koje autogenerate ne prepoznaje.

Revision ID: 0001
Revises:
Create Date: 2026-09-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Trigram pretraga po nazivu recepta.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ---------------------------------------------------------------- recipes
    op.create_table(
        "recipes",
        # id dolazi iz Food.com dataseta - bez autoincrement-a.
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("contributor_id", sa.BigInteger(), nullable=True),
        sa.Column("submitted", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("n_steps", sa.SmallInteger(), nullable=True),
        sa.Column("n_ingredients", sa.SmallInteger(), nullable=True),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ingredients", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("total_fat_pdv", sa.Float(), nullable=True),
        sa.Column("sugar_pdv", sa.Float(), nullable=True),
        sa.Column("sodium_pdv", sa.Float(), nullable=True),
        sa.Column("protein_pdv", sa.Float(), nullable=True),
        sa.Column("saturated_fat_pdv", sa.Float(), nullable=True),
        sa.Column("carbohydrates_pdv", sa.Float(), nullable=True),
        sa.Column("rating_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("avg_rating", sa.Float(), nullable=True),
        sa.Column("popularity_rank", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_recipes"),
    )
    op.create_index("ix_recipes_popularity_rank", "recipes", ["popularity_rank"])
    op.create_index("ix_recipes_minutes", "recipes", ["minutes"])
    op.create_index(
        "ix_recipes_name_trgm",
        "recipes",
        ["name"],
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )

    # ----------------------------------------------------- recipe_ingredients
    op.create_table(
        "recipe_ingredients",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("ingredient", sa.Text(), nullable=True),
        sa.Column("ingredient_norm", sa.Text(), nullable=True),
        sa.Column("tokens", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name="fk_recipe_ingredients_recipe_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("recipe_id", "position", name="pk_recipe_ingredients"),
    )
    op.create_index(
        "ix_recipe_ingredients_tokens",
        "recipe_ingredients",
        ["tokens"],
        postgresql_using="gin",
    )
    op.create_index("ix_recipe_ingredients_norm", "recipe_ingredients", ["ingredient_norm"])

    # ------------------------------------------------------------ ingredients
    op.create_table(
        "ingredients",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("recipe_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("name", name="pk_ingredients"),
    )

    # ------------------------------------------------------------ recipe_tags
    op.create_table(
        "recipe_tags",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name="fk_recipe_tags_recipe_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("recipe_id", "tag", name="pk_recipe_tags"),
    )
    op.create_index("ix_recipe_tags_tag_recipe", "recipe_tags", ["tag", "recipe_id"])

    # ------------------------------------------------------------------- tags
    op.create_table(
        "tags",
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("recipe_count", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("tag", name="pk_tags"),
    )

    # ----------------------------------------------------------- user_ratings
    op.create_table(
        "user_ratings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_user_ratings_rating_range"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_ratings_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name="fk_user_ratings_recipe_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", name="pk_user_ratings"),
    )
    op.create_index("ix_user_ratings_recipe_id", "user_ratings", ["recipe_id"])

    # --------------------------------------------------------- user_favorites
    op.create_table(
        "user_favorites",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_favorites_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name="fk_user_favorites_recipe_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "recipe_id", name="pk_user_favorites"),
    )
    op.create_index("ix_user_favorites_recipe_id", "user_favorites", ["recipe_id"])

    # ---------------------------------------------------------- recipe_images
    op.create_table(
        "recipe_images",
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        # NULL url = pretrazeno, fotografija nije nadjena (batch moze da nastavi).
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), server_default=sa.text("'pexels'"), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("photographer", sa.Text(), nullable=True),
        sa.Column("photographer_url", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["recipe_id"], ["recipes.id"], name="fk_recipe_images_recipe_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("recipe_id", name="pk_recipe_images"),
    )


def downgrade() -> None:
    op.drop_table("recipe_images")

    op.drop_index("ix_user_favorites_recipe_id", table_name="user_favorites")
    op.drop_table("user_favorites")

    op.drop_index("ix_user_ratings_recipe_id", table_name="user_ratings")
    op.drop_table("user_ratings")

    op.drop_table("tags")

    op.drop_index("ix_recipe_tags_tag_recipe", table_name="recipe_tags")
    op.drop_table("recipe_tags")

    op.drop_table("ingredients")

    op.drop_index("ix_recipe_ingredients_norm", table_name="recipe_ingredients")
    op.drop_index("ix_recipe_ingredients_tokens", table_name="recipe_ingredients")
    op.drop_table("recipe_ingredients")

    op.drop_index("ix_recipes_name_trgm", table_name="recipes")
    op.drop_index("ix_recipes_minutes", table_name="recipes")
    op.drop_index("ix_recipes_popularity_rank", table_name="recipes")
    op.drop_table("recipes")

    op.drop_table("users")

    # pg_trgm se namerno ne brise: ekstenzija je bezopasna i moze je koristiti
    # nesto drugo u istoj bazi.
