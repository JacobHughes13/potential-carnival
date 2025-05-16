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
        self.last_killer = None

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

        # Активация способностей при размещении
        self._activate_placement_abilities(card, row, col, player_id)

        hand_attr = f'available_cards_p{player_id}'
        if card_id in getattr(self, hand_attr, []):
            getattr(self, hand_attr).remove(card_id)
        return True

    def _activate_placement_abilities(self, card, row, col, player_id):
        """Активирует способности при размещении карты"""
        if card.name == "Bombombini Gusini":
            self._activate_bombombini_gusini(row, col, player_id)
        elif card.name == "Boneca Ambamabu":
            self._activate_boneca_ambamabu(row, col, player_id) # у него каждый ход

    def move_cards(self, player_id: int) -> None:
        if player_id == 1:
            for col in range(5):
                if self.grid[1][col] is None and self.grid[0][col]:
                    self.grid[1][col] = self.grid[0][col]
                    self.grid[0][col] = None
                    self.grid[1][col].ready_to_attack = True
                    # Активируем способности при движении
                    self._activate_movement_abilities(1, col, player_id)
        else:
            for col in range(5):
                if self.grid[2][col] is None and self.grid[3][col]:
                    self.grid[2][col] = self.grid[3][col]
                    self.grid[3][col] = None
                    self.grid[2][col].ready_to_attack = True
                    # Активируем способности при движении
                    self._activate_movement_abilities(2, col, player_id)

    def _activate_movement_abilities(self, row, col, player_id):
        """Активирует способности при движении карты"""
        card = self.grid[row][col]
        if card and card.name == "Udin din din din dun":
            self.Udin_din_din_din_dun(card, player_id)

    def battle_phase(self, player_id: int) -> Optional[int]:

        # Активируем способности перед атакой
        self._activate_pre_battle_abilities(player_id)

        for col in range(5):
            attacker = self.grid[1][col] if player_id == 1 else self.grid[2][col]
            defender = self.grid[2][col] if player_id == 1 else self.grid[1][col]
            if attacker and defender:
                # При убийстве карты
                if defender.health <= 0:
                    self.last_killer = attacker

                if attacker and attacker.ready_to_attack:
                    # Применяем способности перед атакой
                    self._apply_attacker_abilities(attacker, defender, player_id, col)

                    if defender:
                        defender.health -= attacker.attack
                        if defender.health <= 0:
                            # Применяем способности при убийстве
                            self._apply_kill_abilities(attacker, defender, player_id, col)
                            if player_id == 1:
                                self.grid[2][col] = None
                            else:
                                self.grid[1][col] = None
                    else:
                        self.damage_balance += attacker.attack if player_id == 1 else -attacker.attack

        # Активируем способности после атаки
        self._activate_post_battle_abilities(player_id)

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

    def Tralalelo_Tralala(self, card):
        """Шанс уклонения"""
        import random
        return random.random() < 0.3  # 30% шанс уклонения

    def Bobritto_Bandito(self, card, player_id):
        """Раз в 2 хода отбирает деньги"""
        if self.turn_count[player_id] % 2 == 0:
            stolen = min(self.income[player_id], self.coins[3 - player_id])
            self.coins[player_id] += stolen
            self.coins[3 - player_id] -= stolen
            return stolen
        return 0

    def Tung_Tung_Tung_Sahur(self, card, defender):
        """50% шанс оглушить врага"""
        import random
        if random.random() < 0.5:
            defender.ready_to_attack = False
            return True
        return False

    def Bombombini_Gusini(self, row, col, player_id):
        """Получает баффы если есть Bombordilo Crocodilo рядом"""
        for r in range(max(0, row - 1), min(4, row + 2)):
            for c in range(max(0, col - 1), min(5, col + 2)):
                if (r != row or c != col) and self.grid[r][c] and self.grid[r][c].name == "Bombordilo Crocodillo":
                    self.grid[row][col].attack += 2
                    self.grid[row][col].health += 2
                    return

    def Boneca_Ambamabu(self, row, col, player_id):
        """Передвигается и даёт +1 к урону союзнику"""
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dr, dc in directions:
            new_r, new_c = row + dr, col + dc
            if 0 <= new_r < 4 and 0 <= new_c < 5 and self.grid[new_r][new_c] is None:
                self.grid[new_r][new_c] = self.grid[row][col]
                self.grid[row][col] = None
                # Даём +1 к урону случайному союзнику
                self._buff_random_ally(player_id, 1, 0)
                break

    def Trippi_Troppi(self, card, player_id):
        """Копирует себя или лечит"""
        empty_slots = sum(1 for row in self.grid for cell in row if cell is None)
        if empty_slots > 0:
            # Копируем себя
            new_card = Card(
                name=card.name,
                attack=card.attack,
                health=card.health,
                cost=card.cost
            )
            for r in range(4):
                for c in range(5):
                    if self.grid[r][c] is None:
                        self.grid[r][c] = new_card
                        return
        else:
            # Лечим случайного союзника
            self._buff_random_ally(player_id, 0, 2)

    def La_Vaca_Saturno_Saturnita(self, card):
        """Может взорваться и убить врага"""
        import random
        if random.random() < 0.1:  # 10% шанс
            card.health = 0
            return True
        return False

    def Talpa_Di_Ferro(self, card):
        """Нельзя атаковать не в его ход"""
        card.ready_to_attack = False  # Сбрасываем возможность атаки

    def Lirili_Larila(self, card, player_id):
        """Атакует раз в 2 хода"""
        if self.turn_count[player_id] % 2 == 0:
            card.ready_to_attack = True
        else:
            card.ready_to_attack = False

    def Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus(self, card, player_id):
        """Выбирает цель по приоритету"""
        # Реализация логики выбора цели
        pass

    def Cappuccino_Assassino(self, card):
        """Оставляет капучино при атаке"""
        if not hasattr(card, 'cappuccino_used'):
            card.cappuccino_used = False

        if not card.cappuccino_used:
            card.cappuccino_used = True
            # Создаём карту-капучино
            return Card(name="Cappuccino", attack=0, health=1, cost=0)
        return None

    def Udin_din_din_din_dun(self, card, player_id):
        """Получает -1 к урону если есть союзники рядом"""
        if self._has_allies_nearby(card, player_id):
            card.attack = max(0, card.attack - 1)

    def Bombardino_Crocodillo(self, card, player_id):
        """Атакует всех врагов сразу"""
        for c in range(5):
            defender = self.grid[2][c] if player_id == 1 else self.grid[1][c]
            if defender:
                defender.health -= card.attack
        return True  # Помечаем что атака уже выполнена

    def Frigo_camelo(self, card, defender): #todo чтото фигня какаято
        """Замораживает врага"""
        if defender and card.attack >= defender.health:
            defender.ready_to_attack = False  # Замораживаем

    def Brr_Brr_Patapim(self, card):
        """-1 к урону при убийстве"""
        if not hasattr(card, 'base_attack'):
            card.base_attack = card.attack
        card.attack = max(0, card.base_attack - 1)

    def Trulimero_Trulicina(self, card):
        """-1 HP каждый ход"""
        card.health -= 1


    def Chimpazini_Bananini(self, card):
        """+2 к урону при получении урона"""
        if not hasattr(card, 'base_attack'):
            card.base_attack = card.attack
        card.attack = card.base_attack + 2


    def Balerinna_Cappucinna(self, card):
        """Даёт -2 к урону убийце"""
        if not hasattr(card, 'debuff_applied'):
            card.debuff_applied = False
        return card.debuff_applied


    # Вспомогательные методы:

    def _buff_random_ally(self, player_id, attack_buff, health_buff):
        """Усиливает случайного союзника"""
        allies = []
        for r in range(4):
            for c in range(5):
                if self.grid[r][c] and ((player_id == 1 and r < 2) or (player_id == 2 and r >= 2)):
                    allies.append((r, c))

        if allies:
            import random
            r, c = random.choice(allies)
            self.grid[r][c].attack += attack_buff
            self.grid[r][c].health += health_buff

    def _activate_pre_battle_abilities(self, player_id):
        """Активирует способности перед фазой боя"""
        for row in range(4):
            for col in range(5):
                card = self.grid[row][col]
                if card and ((player_id == 1 and row < 2) or (player_id == 2 and row >= 2)):
                    # Bobritto Bandito - ворует монеты раз в 2 хода
                    if card.name == "Bobritto Bandito":
                        stolen = self.Bobritto_Bandito(card, player_id)
                        if stolen > 0:
                            print(f"Bobritto Bandito украл {stolen} монет!")

                    # Talpa Di Ferro - нельзя атаковать не в его ход
                    elif card.name == "Talpa Di Ferro":
                        self.Talpa_Di_Ferro(card)

                    # Lirili Larila - атакует раз в 2 хода
                    elif card.name == "Lirili Larila":
                        self.Lirili_Larila(card, player_id)

                    # Trulimero Trulicina - теряет 1 HP каждый ход #todo как будто происходит не в нужныйм момент
                    elif card.name == "Trulimero Trulicina":
                        self.Trulimero_Trulicina(card)
                        if card.health <= 0:
                            self.grid[row][col] = None

                    # Trippi Troppi - копирует себя или лечит каждые 3 хода
                    elif card.name == "Trippi Troppi" and self.turn_count[player_id] % 3 == 0:
                        self.Trippi_Troppi(card, player_id)

    def _activate_post_battle_abilities(self, player_id):
        """Активирует способности после фазы боя"""
        for row in range(4):
            for col in range(5):
                card = self.grid[row][col]
                if card and ((player_id == 1 and row < 2) or (player_id == 2 and row >= 2)):
                    # Boneca Ambamabu - двигается и баффает союзника
                    if card.name == "Boneca Ambamabu":
                        self.Boneca_Ambamabu(row, col, player_id)

                    # Chimpazini Bananini - получает +2 к атаке если был атакован
                    elif card.name == "Chimpazini Bananini" and getattr(card, 'was_attacked', False):
                        self.Chimpazini_Bananini(card)
                        card.was_attacked = False

    def _apply_attacker_abilities(self, attacker, defender, player_id, col):
        """Применяет способности атакующей карты"""
        if attacker.name == "Tralalelo Tralala":
            if self.Tralalelo_Tralala(attacker):
                print(f"{attacker.name} уклонился от контратаки!")
                return False  # Атака отменена из-за уклонения

        if attacker.name == "Tung Tung Tung Sahur" and defender:
            if self.Tung_Tung_Tung_Sahur(attacker, defender):
                print(f"{attacker.name} оглушил {defender.name}!")

        if attacker.name == "Bombardino Crocodillo":
            if self.Bombardino_Crocodillo(attacker, player_id):
                print(f"{attacker.name} атаковал всех врагов!")
                return False  # Атака уже выполнена

        if attacker.name == "Frigo camelo" and defender:
            self.Frigo_camelo(attacker, defender)

        return True

    def _apply_kill_abilities(self, attacker, defender, player_id, col):
        """Применяет способности после убийства"""
        if attacker.name == "Brr Brr Patapim":
            self.Brr_Brr_Patapim(attacker)
            print(f"{attacker.name} потерял 1 к атаке за убийство!")

        if defender.name == "Balerinna Cappucinna":
            if not getattr(defender, 'debuff_applied', False):
                attacker.attack = max(0, attacker.attack - 2)
                defender.debuff_applied = True
                print(f"{defender.name} уменьшил атаку убийцы на 2!")

        if attacker.name == "La Vaca Saturno Saturnita":
            if self.La_Vaca_Saturno_Saturnita(attacker):
                defender.health -= 4
                print(f"{attacker.name} взорвалась!")

        if attacker.name == "Cappuccino Assassino":
            cappuccino = self.Cappuccino_Assassino(attacker)
            if cappuccino:
                # Размещаем капучино на текущей клетке
                row = 1 if player_id == 1 else 2
                self.grid[row][col] = cappuccino
                print(f"{attacker.name} оставил Cappuccino!")


    def _has_allies_nearby(self, row, col, player_id):
        """Проверяет есть ли союзники рядом с картой"""
        for r in range(max(0, row - 1), min(4, row + 2)):
            for c in range(max(0, col - 1), min(5, col + 2)):
                if (r != row or c != col) and self.grid[r][c] is not None:
                    if (player_id == 1 and r < 2) or (player_id == 2 and r >= 2):
                        return True
        return False

    def _activate_placement_abilities(self, card, row, col, player_id):
        """Активирует способности при размещении карты"""
        if card.name == "Bombombini Gusini":
            self._check_bombombini_buff(row, col, player_id)
        elif card.name == "Boneca Ambamabu":
            self._move_and_buff_ally(row, col, player_id)

    def _get_target_enemy(self, card, player_id):
        """
        Для карты Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus
        Выбирает цель по приоритету:
        1. Последний убийца союзника
        2. Враг с наибольшей атакой
        """
        enemies = []
        enemy_rows = range(2, 4) if player_id == 1 else range(0, 2)

        # Находим всех врагов
        for row in enemy_rows:
            for col in range(5):
                if self.grid[row][col]:
                    enemies.append((row, col, self.grid[row][col]))

        if not enemies:
            return None

        # Сначала ищем убийцу последнего союзника
        if hasattr(self, 'last_killer') and self.last_killer:
            for row, col, enemy in enemies:
                if enemy == self.last_killer:
                    return (row, col, enemy)

        # Если убийца не найден, берём с максимальной атакой
        return max(enemies, key=lambda x: x[2].attack)


    def _check_bombombini_buff(self, row, col, player_id):
        """Проверяет наличие Bombordilo Crocodilo рядом для баффа"""
        for r in range(max(0, row - 1), min(4, row + 2)):
            for c in range(max(0, col - 1), min(5, col + 2)):
                if (r != row or c != col) and self.grid[r][c] and self.grid[r][c].name == "Bombordilo Crocodillo":
                    self.grid[row][col].attack += 2
                    self.grid[row][col].health += 2
                    print(f"Bombombini Gusini получил бафф от Bombordilo Crocodillo!")
                    return

    def _move_and_buff_ally(self, row, col, player_id):
        """Перемещает Boneca Ambamabu и усиливает союзника"""
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]
        for dr, dc in directions:
            new_r, new_c = row + dr, col + dc
            if 0 <= new_r < 4 and 0 <= new_c < 5 and self.grid[new_r][new_c] is None:
                # Перемещаем карту
                self.grid[new_r][new_c] = self.grid[row][col]
                self.grid[row][col] = None

                # Усиливаем случайного союзника
                allies = []
                for r in range(4):
                    for c in range(5):
                        if self.grid[r][c] and ((player_id == 1 and r < 2) or (player_id == 2 and r >= 2)):
                            allies.append((r, c))

                if allies:
                    import random
                    r, c = random.choice(allies)
                    self.grid[r][c].attack += 1
                    print(f"Boneca Ambamabu усилила союзника на клетке ({r}, {c})!")
                break