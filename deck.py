from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

SqlAlchemyBase = declarative_base()


class Card(SqlAlchemyBase):
    __tablename__ = 'cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    attack = Column(Integer, nullable=False)
    health = Column(Integer, nullable=False)
    cost = Column(Integer, nullable=False)
    ready_to_attack: bool = False


class Deck:
    def __init__(self, db_path: str = 'sqlite:///BD/BD.db') -> None:
        self.engine = create_engine(db_path, echo=False)

        SqlAlchemyBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.grid: list[list[Optional[Card]]] = [[None for _ in range(4)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0  # 0: p1 —> p2, 1: p2 -> p1

    def get_card_by_id(self, card_id: int) -> Optional[Card] | None:
        session = self.Session()
        db_card = session.query(Card).filter_by(id=card_id).first()
        session.close()
        if db_card:
            return Card(db_card.id, db_card.name, db_card.attack, db_card.health, db_card.cost)
        return None

    def place_card(self, card_id: int, player_id: int, col: int) -> bool:
        card = self.get_card_by_id(card_id)
        if card is None:
            return False

        row = 0 if player_id == 1 else 3
        if self.grid[row][col] is not None:
            return False

        card.ready_to_attack = False
        self.grid[row][col] = card
        return True

    def move_cards(self, player_id: int) -> None:
        if player_id == 1:
            for col in range(4):
                if self.grid[1][col] is None and self.grid[0][col]:
                    self.grid[1][col] = self.grid[0][col]
                    self.grid[0][col] = None
                    self.grid[1][col].ready_to_attack = True
        elif player_id == 2:
            for col in range(4):
                if self.grid[2][col] is None and self.grid[3][col]:
                    self.grid[2][col] = self.grid[3][col]
                    self.grid[3][col] = None
                    self.grid[2][col].ready_to_attack = True

    def battle_phase(self, player_id: int) -> Optional[int] | None:
        for col in range(4):
            if player_id == 1:
                attacker = self.grid[1][col]
                defender = self.grid[2][col]
            else:
                attacker = self.grid[2][col]
                defender = self.grid[1][col]

            if attacker and attacker.ready_to_attack:
                if defender:
                    defender.health -= attacker.attack
                    if defender.health <= 0:
                        if player_id == 1:
                            self.grid[2][col] = None
                        else:
                            self.grid[1][col] = None
                else:
                    self.damage_balance += attacker.attack if player_id == 1 else -attacker.attack

        self.remove_dead_cards()
        if self.damage_balance >= 10:
            return 1
        elif self.damage_balance <= -10:
            return 2
        return None

    def remove_dead_cards(self) -> None:
        for row in range(4):
            for col in range(4):
                card = self.grid[row][col]
                if card and card.health <= 0:
                    self.grid[row][col] = None

    def reset(self) -> None:
        self.grid = [[None for _ in range(4)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0