"""SQLAlchemy 2.0 modeli za Food.com dataset i korisnicke podatke."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # Email se uvek cuva malim slovima (normalizacija je posao servisnog sloja).
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Recipe(Base):
    __tablename__ = "recipes"

    # id dolazi iz dataseta - namerno bez autoincrement-a.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    minutes: Mapped[int | None] = mapped_column(Integer)
    contributor_id: Mapped[int | None] = mapped_column(BigInteger)
    submitted: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    n_steps: Mapped[int | None] = mapped_column(SmallInteger)
    n_ingredients: Mapped[int | None] = mapped_column(SmallInteger)

    steps: Mapped[list] = mapped_column(JSONB, nullable=False)
    ingredients: Mapped[list] = mapped_column(JSONB, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False)

    # nutrition lista iz dataseta, raspakovana u sedam kolona
    calories: Mapped[float | None] = mapped_column(Float)
    total_fat_pdv: Mapped[float | None] = mapped_column(Float)
    sugar_pdv: Mapped[float | None] = mapped_column(Float)
    sodium_pdv: Mapped[float | None] = mapped_column(Float)
    protein_pdv: Mapped[float | None] = mapped_column(Float)
    saturated_fat_pdv: Mapped[float | None] = mapped_column(Float)
    carbohydrates_pdv: Mapped[float | None] = mapped_column(Float)

    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_rating: Mapped[float | None] = mapped_column(Float)
    popularity_rank: Mapped[int] = mapped_column(Integer, nullable=False)

    image: Mapped["RecipeImage | None"] = relationship(
        back_populates="recipe", lazy="selectin", uselist=False
    )

    __table_args__ = (
        Index("ix_recipes_popularity_rank", "popularity_rank"),
        Index("ix_recipes_minutes", "minutes"),
        # Trigram indeks za pretragu po nazivu (ILIKE '%...%').
        Index(
            "ix_recipes_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    ingredient: Mapped[str | None] = mapped_column(Text)
    ingredient_norm: Mapped[str | None] = mapped_column(Text)
    tokens: Mapped[list[str] | None] = mapped_column(ARRAY(Text))

    __table_args__ = (
        Index("ix_recipe_ingredients_tokens", "tokens", postgresql_using="gin"),
        Index("ix_recipe_ingredients_norm", "ingredient_norm"),
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    # Normalizovana fraza (izlaz iz normalize_ingredient).
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    recipe_count: Mapped[int | None] = mapped_column(Integer)


class RecipeTag(Base):
    __tablename__ = "recipe_tags"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(Text, primary_key=True)

    __table_args__ = (Index("ix_recipe_tags_tag_recipe", "tag", "recipe_id"),)


class Tag(Base):
    __tablename__ = "tags"

    tag: Mapped[str] = mapped_column(Text, primary_key=True)
    recipe_count: Mapped[int | None] = mapped_column(Integer)


class UserRating(Base):
    __tablename__ = "user_ratings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_user_ratings_rating_range"),
        Index("ix_user_ratings_recipe_id", "recipe_id"),
    )


class UserFavorite(Base):
    __tablename__ = "user_favorites"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_user_favorites_recipe_id", "recipe_id"),)


class RecipeImage(Base):
    __tablename__ = "recipe_images"

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey("recipes.id", ondelete="CASCADE"), primary_key=True
    )
    # url je NULL kada je pretraga obavljena ali fotografija nije nadjena -
    # to omogucava da se Pexels batch nastavi tamo gde je stao.
    url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text, server_default="pexels")
    source_url: Mapped[str | None] = mapped_column(Text)
    photographer: Mapped[str | None] = mapped_column(Text)
    photographer_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recipe: Mapped["Recipe"] = relationship(back_populates="image")
