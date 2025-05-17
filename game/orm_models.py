from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base

SqlAlchemyBase = declarative_base()


class User(SqlAlchemyBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class Friend(SqlAlchemyBase):
    __tablename__ = "friends"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    friend_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class Card(SqlAlchemyBase):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    attack = Column(Integer, nullable=False)
    health = Column(Integer, nullable=False)
    cost = Column(Integer, nullable=False)
    # ability_key = Column(String, nullable=True)

    # runtime-поля (НЕ пишутся в БД)
    ready_to_attack: bool = False
    player_id: int = 0
    cooldown: int = 0            # ходов до перезарядки для некоторых абилок
    storage: dict = {}           # на случай уникальных флагов