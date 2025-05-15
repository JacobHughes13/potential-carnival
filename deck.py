from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from werkzeug.security import generate_password_hash, check_password_hash
from random import choice

SqlAlchemyBase = declarative_base()


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

    ready_to_attack: bool = False


class Deck:
    def __init__(self, db_path: str = 'sqlite:///data/BD.db') -> None:
        self.engine = create_engine(db_path, echo=False)

        SqlAlchemyBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.grid: list[list[Optional[Card]]] = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0

        self.coins   = {1: 1, 2: 1}
        self.income  = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}

        self.available_cards_p1: list[int] = []
        self.available_cards_p2: list[int] = []

    def get_card_by_id(self, card_id: int) -> Optional[Card]:
        session = self.Session()
        card = session.query(Card).filter(Card.id == card_id).first()
        session.close()
        return card

    def get_random_card(self) -> Optional[Card]:
        session = self.Session()
        cards = session.query(Card).all()
        session.close()
        return choice(cards) if cards else None

    def place_card(self, card_id: int, player_id: int, col: int) -> bool:
        card = self.get_card_by_id(card_id)
        if card is None or card.cost > self.coins[player_id]:
            return False

        row = 0 if player_id == 1 else 3
        if self.grid[row][col] is not None:
            return False

        self.coins[player_id] -= card.cost
        card.ready_to_attack = False
        self.grid[row][col] = card

        hand_attr = f'available_cards_p{player_id}'
        if card_id in getattr(self, hand_attr, []):
            getattr(self, hand_attr).remove(card_id)
        return True

    def move_cards(self, player_id: int) -> None:
        if player_id == 1:
            for col in range(5):
                if self.grid[1][col] is None and self.grid[0][col]:
                    self.grid[1][col] = self.grid[0][col]
                    self.grid[0][col] = None
                    self.grid[1][col].ready_to_attack = True
        else:
            for col in range(5):
                if self.grid[2][col] is None and self.grid[3][col]:
                    self.grid[2][col] = self.grid[3][col]
                    self.grid[3][col] = None
                    self.grid[2][col].ready_to_attack = True

    def battle_phase(self, player_id: int) -> Optional[int]:
        for col in range(5):
            attacker = self.grid[1][col] if player_id == 1 else self.grid[2][col]
            defender = self.grid[2][col] if player_id == 1 else self.grid[1][col]

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
        self.turn_count[player_id] += 1
        if self.turn_count[player_id] % 3 == 0:
            self.income[player_id] += 1
        self.coins[player_id] += self.income[player_id]

        hand_attr = f'available_cards_p{player_id}'
        if not hasattr(self, hand_attr):
            setattr(self, hand_attr, [])

        new_card = self.get_random_card()
        if new_card:
            getattr(self, hand_attr).append(new_card.id)

    def get_game_state(self, player_id: int) -> dict:
        opponent_id = 2 if player_id == 1 else 1

        visible_grid: list[list[Optional[dict | None]]] = []
        for r, row in enumerate(self.grid):
            visible_row = []
            for c, card in enumerate(row):
                if card is None:
                    visible_row.append(None)
                else:
                    visible_row.append({
                        'name': card.name,
                        'attack': card.attack,
                        'health': card.health,
                        'ready_to_attack': getattr(card, 'ready_to_attack', False)
                        })
            visible_grid.append(visible_row)

        hand_attr = f'available_cards_p{player_id}'
        hand = getattr(self, hand_attr, [])

        return {
            'grid'           : visible_grid,
            'damage_balance' : self.damage_balance,
            'coins'          : self.coins[player_id],
            'income'         : self.income[player_id],
            'available_cards': hand,
            'opponent_coins' : self.coins[opponent_id],
            'turn_count'     : self.turn_count[player_id]
        }

    def reset(self) -> None:
        self.grid = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0
        self.coins = {1: 1, 2: 1}
        self.income = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}

    def Tralalelo_Tralala(self):
        # шанс уклонения
        pass

    def Bobritto_Bandito(self):
        # раз в 2 хода отбирает деньги от 1 до кол-во монет за ход
        pass

    def Tung_Tung_Tung_Sahur(self):
        # 50 % застанить врага
        pass

    def Bombombini_Gusini(self):
        # получает бафы если есть bombordilo crocodilo рядом
        pass

    def Boneca_Ambamabu(self):
        # передвигается на соседнюю клетку и полусает + 1 к урону к рандомному союзнику
        pass

    def Trippi_Troppi(self):
        # каждые 3 хода копирует себя если есть место на поле, если нет места то хилит рандомного союзника на 2 хп
        pass

    def La_Vaca_Saturno_Saturnita(self):
        # раз в ход с маленькой вероятностью может взорваться и забрать карту перед собой
        pass

    def Talpa_Di_Ferro(self):
        # нельзя ударить не в его ход
        pass

    def Lirili_Larila(self):
        # ходить раз в 2 хода
        pass

    def Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus(self):
        # выбирает свой целью врага последним убившего союзника иначе Выбирает свой целью врага с наибольшим уроном
        pass

    def Cappuccino_Assassino(self):
        # когда противник атакует его, он отходит в сторону сотавляя на своем месте капучино с 0 урона и 1 хп (1 раз за жизнь)
        pass

    def Udin_din_din_din_dun(self):
        # получает -1 к урону есть союзники рядом
        pass

    def Bombardino_Crocodillo(self):
        # бьёт всех врагов стразу
        pass

    def Frigo_camelo(self):
        # двойное попадание по врагу замораживает его на ход
        pass

    def Brr_Brr_Patapim(self):
        # при убийстве врага - 1 к урону
        pass

    def Trulimero_Trulicina(self):
        # каждый ход получает 1 урон
        pass

    def Chimpazini_Bananini(self):
        # при получении крона увеличивает свой на 2 ед
        pass

    def Balerinna_Cappucinna(self):
        # если враг ее убивает то враг получает -2 к урону
        pass
