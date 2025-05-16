from __future__ import annotations

from typing import Optional, Any, Generator
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from random import choice
from copy import deepcopy

# ──────────────── внешние модули ────────────────
from abilities import ABILITY_REGISTRY, Ability

SqlAlchemyBase = declarative_base()


# ──────────────── SQL-таблицы ────────────────
class User(SqlAlchemyBase):
    __tablename__ = 'users'

    id       = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class Friend(SqlAlchemyBase):
    __tablename__ = 'friends'

    id        = Column(Integer, primary_key=True, autoincrement=True)
    user_id   = Column(Integer, ForeignKey('users.id'), nullable=False)
    friend_id = Column(Integer, ForeignKey('users.id'), nullable=False)


class Card(SqlAlchemyBase):
    __tablename__ = 'cards'

    id     = Column(Integer, primary_key=True, autoincrement=True)
    name   = Column(String,  nullable=False)
    attack = Column(Integer, nullable=False)
    health = Column(Integer, nullable=False)
    cost   = Column(Integer, nullable=False)

    ability_key = Column(String, nullable=True)

    ready_to_attack: bool = False
    player_id      : int  | None = None
    row            : int  | None = None
    col            : int  | None = None
    __allow_unmapped__ = True

    # ──────────────── helpers ────────────────
    @property
    def ability(self) -> Ability | None:
        """создаём объект-способность."""
        if not self.ability_key:
            return None
        if "_ability_obj" not in self.__dict__:
            cls = ABILITY_REGISTRY.get(self.ability_key)
            self.__dict__["_ability_obj"] = cls() if cls else None
        return self.__dict__["_ability_obj"]

    @property
    def base_attack(self) -> int:
        return self.__dict__.setdefault("_base_attack", self.attack)

    def clone(self) -> "Card":
        new = deepcopy(self)
        new.id = None  # чтоб не конфликтовало в БД
        if new.ability_key:
            new.__dict__["_ability_obj"] = ABILITY_REGISTRY[new.ability_key]()
        return new


# ──────────────── игровая колода / поле ────────────────
class Deck:
    def __init__(self, db_path: str = 'sqlite:///data/BD.db') -> None:
        self.engine = create_engine(db_path, echo=False)
        SqlAlchemyBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.grid : list[list[Optional[Card]]] = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0           # +10 победа P1 ; −10 победа P2
        self.turn_stage     = 0           # 0 — ход P1, 1 — ход P2

        self.coins   = {1: 1, 2: 1}
        self.income  = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}

        self.last_killer          : Card | None = None
        self.current_attacker_id  : int  | None = None

        self.available_cards_p1 : list[int] = []
        self.available_cards_p2 : list[int] = []

    # ──────────────── DB helpers ────────────────
    def get_card_by_id(self, card_id: int) -> Optional[Card]:
        session = self.Session()
        card = session.query(Card).filter(Card.id == card_id).first()
        session.close()
        return card

    def get_random_card(self) -> Optional[Card]:
        session = self.Session()
        cards = session.query(Card).filter(Card.id > 0).all()
        session.close()
        return choice(cards) if cards else None

    # ──────────────── ability ────────────────
    def _iter_cards(self) -> Generator[Card, None, None]:
        for row in self.grid:
            for card in row:
                if card:
                    yield card

    def _trigger(self, event: str, **ctx: Any) -> Any:
        for card in self._iter_cards():
            ab = card.ability
            if ab and ab.trigger == event:
                result = ab.apply(game=self, card=card, **ctx)
                if event.startswith("before_") and result is not None:
                    return result
        return None

    # ──────────────── игровые действия ────────────────
    def place_card(self, card_id: int, player_id: int, col: int) -> bool:
        card = self.get_card_by_id(card_id)
        if card is None or card.cost > self.coins[player_id]:
            return False

        row = 0 if player_id == 1 else 3
        if self.grid[row][col] is not None:
            return False

        self.coins[player_id] -= card.cost
        card.ready_to_attack = False
        card.player_id = player_id
        card.row, card.col = row, col
        self.grid[row][col] = card
        getattr(self, f'available_cards_p{player_id}').remove(card_id)

        # on_play
        self._trigger("on_play", card=card, col=col)
        return True

    def move_cards(self, player_id: int) -> None:
        if player_id == 1:
            for col in range(5):
                if self.grid[1][col] is None and self.grid[0][col]:
                    self.grid[1][col] = self.grid[0][col]
                    self.grid[0][col] = None
                    c = self.grid[1][col]
                    c.ready_to_attack = True
                    c.row, c.col = 1, col
        else:
            for col in range(5):
                if self.grid[2][col] is None and self.grid[3][col]:
                    self.grid[2][col] = self.grid[3][col]
                    self.grid[3][col] = None
                    c = self.grid[2][col]
                    c.ready_to_attack = True
                    c.row, c.col = 2, col

    def battle_phase(self, player_id: int) -> Optional[int]:
        self.last_killer = None
        front_row = 1 if player_id == 1 else 2
        back_row  = 2 if player_id == 1 else 1

        for col in range(5):
            attacker = self.grid[front_row][col]
            defender = self.grid[back_row][col]

            if not (attacker and attacker.ready_to_attack):
                continue

            self.current_attacker_id = attacker.player_id

            self._trigger("before_attack", attacker=attacker)

            override = self._trigger("choose_target", game=self, card=attacker)
            if override is not None:
                defender = override

            if not attacker.ready_to_attack:
                self.current_attacker_id = None
                continue

            raw_damage = attacker.attack

            if defender:
                # before_being_hit
                res = self._trigger("before_being_hit", card=defender, damage=raw_damage)
                raw_damage = res if res is not None else raw_damage

                defender.health -= raw_damage
                if defender.health <= 0:
                    self.grid[defender.row][defender.col] = None
                    self.last_killer = attacker
                    self._trigger("on_kill", card=attacker)
                    self._trigger("on_death", killer=attacker)
            else:
                # удар по базе
                self.damage_balance += raw_damage if player_id == 1 else -raw_damage

            # after_attack
            self._trigger("after_attack", attacker=attacker, defender=defender)

            self.current_attacker_id = None

        self.remove_dead_cards()
        if self.damage_balance >= 10:
            return 1
        if self.damage_balance <= -10:
            return 2
        return None

    def remove_dead_cards(self) -> None:
        for row in range(4):
            for col in range(5):
                card = self.grid[row][col]
                if card and card.health <= 0:
                    self.grid[row][col] = None

    def end_turn(self, player_id: int) -> None:
        """Фаза дохода и прочих end-triggers."""
        self._trigger("turn_end")

        self.turn_count[player_id] += 1
        if self.turn_count[player_id] % 3 == 0:
            self.income[player_id] += 1
        self.coins[player_id] += self.income[player_id]

        # income-триггер (Chimpanzini и др.)
        self._trigger("income")

        hand = getattr(self, f'available_cards_p{player_id}')
        if len(hand) < 3:
            new_card = self.get_random_card()
            if new_card:
                hand.append(new_card.id)

    def get_game_state(self, player_id: int) -> dict:
        opp = 2 if player_id == 1 else 1

        grid_out = []
        for row in self.grid:
            row_out = []
            for card in row:
                row_out.append(None if card is None else {
                    'name'           : card.name,
                    'attack'         : card.attack,
                    'health'         : card.health,
                    'ready_to_attack': card.ready_to_attack,
                    'player_id'      : card.player_id,
                    'ability_key'    : card.ability_key
                })
            grid_out.append(row_out)

        hand = []
        for cid in getattr(self, f'available_cards_p{player_id}', []):
            c = self.get_card_by_id(cid)
            hand.append({'id': cid, 'name': c.name,
                         'attack': c.attack, 'health': c.health})

        return {
            'grid'           : grid_out,
            'damage_balance' : self.damage_balance,
            'coins'          : self.coins[player_id],
            'income'         : self.income[player_id],
            'available_cards': hand,
            'opponent_coins' : self.coins[opp],
            'turn_count'     : self.turn_count[player_id]
        }

    # ──────────────── прочее ────────────────
    def reset(self) -> None:
        self.grid = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0
        self.coins   = {1: 1, 2: 1}
        self.income  = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}
        self.last_killer = None
        self.current_attacker_id = None

        for c in self._iter_cards():
            c.__dict__.pop("_ability_obj", None)