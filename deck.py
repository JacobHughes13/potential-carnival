from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

SqlAlchemyBase = declarative_base()


class User(SqlAlchemyBase):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)


class Friend(SqlAlchemyBase):
    __tablename__ = 'friends'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    friend_id = Column(Integer, ForeignKey('users.id'), nullable=False)


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
        self.grid: list[list[Optional[Card]]] = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0  # 0: p1 —> p2, 1: p2 -> p1
        self.coins = {1: 1, 2: 1}
        self.income = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}

    def get_card_by_id(self, card_id: int) -> Optional[Card] | None:
        session = self.Session()
        db_card = session.query(Card).filter_by(id=card_id).first()
        session.close()
        if db_card:
            return db_card
        return None

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
        return True

    def move_cards(self, player_id: int) -> None:
        if player_id == 1:
            for col in range(5):
                if self.grid[1][col] is None and self.grid[0][col]:
                    self.grid[1][col] = self.grid[0][col]
                    self.grid[0][col] = None
                    self.grid[1][col].ready_to_attack = True
        elif player_id == 2:
            for col in range(5):
                if self.grid[2][col] is None and self.grid[3][col]:
                    self.grid[2][col] = self.grid[3][col]
                    self.grid[3][col] = None
                    self.grid[2][col].ready_to_attack = True

    def battle_phase(self, player_id: int) -> Optional[int] | None:
        for col in range(5):
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
            for col in range(5):
                card = self.grid[row][col]
                if card and card.health <= 0:
                    self.grid[row][col] = None

    def reset(self) -> None:
        self.grid = [[None for _ in range(5)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0
        self.coins = {1: 1, 2: 1}
        self.income = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}

    def end_turn(self, player_id: int) -> None:
        self.turn_count[player_id] += 1
        if self.turn_count[player_id] % 3 == 0:
            self.income[player_id] += 1
        self.coins[player_id] += self.income[player_id]
        
    def Boneca_Ambamabu(self):
        # передвигается на соседнюю клетку
        pass

    def Serbinyo_Carshippinyo(self):
        # ХЗ
        pass

    def Purri_Purrani_Nyankani(self):
        # все обязаны атакават его
        pass

    def Babadubababadududubadududubadu(self):
        # камикадзе
        pass

    def Talpa_Di_Ferro(self):
        # нельзя ударить не в его ход
        pass

    def Lirili_Larila(self):
        # ходить раз в 2 хода
        pass
    def Coccodrillo_Formaggioso(self):
        # когда его бьют враг хилится + каждый ход отдает по хп союзникам по бокам
        pass

    def Baranito_Tankito(self):
        # стреляет по ближайшему врагу, чем дальше враг тем меньше урона. Не способен стрелять по игроку пока есть враги
        pass

    def Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus(self):
        # выбирает свой целью врага последним убившего союзника иначе Выбирает свой целью врага с наибольшим уроном
        pass

    def Pot_hotspot(self):
        # ворует 1 урон и 1 хп у каждого союзника рядом, не может убить союзника
        pass

    def Udin_din_din_din_dun(self):
        # получает -1 к урону есть союзники рядом
        pass

    def Dangerito_Bearito(self):
        # забирает 1 урон и 1 хп у соседних врагов
        pass

    def Bombombini_Gusini(self):
        # получает бафы если есть bombordilo crocodilo рядом
        pass

    def Tung_Tung_Tung_Sahur(self):
        # 50 % застанить врага
        pass

    def Bobritto_Bandito(self):
        # при атаке отбирает деньги
        pass

    def Tralalelo_Tralala(self):
        # шанс уклонения
        pass

    def Bombardino_Crocodillo(self):
        # бьёт всех врагов стразу
        pass