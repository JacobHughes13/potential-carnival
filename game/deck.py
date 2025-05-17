from __future__ import annotations
from random import choice, randint, random
from typing import Optional, Callable
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from game.orm_models import *


AbilityFn = Callable[["Deck", Card, int, int], None]


class Deck:
    # ─── соответствие имён карт ключам ───
    _name2key = {
        "Tralalelo Tralala"                           : "Tralalelo_Tralala",
        "Bobritto Bandito"                            : "Bobritto_Bandito",
        "Tung Tung Tung Sahur"                        : "Tung_Tung_Tung_Sahur",
        "Bombombini Gusini"                           : "Bombombini_Gusini",
        "Boneca Ambamabu"                             : "Boneca_Ambamabu",
        "Trippi Troppi"                               : "Trippi_Troppi",
        "La Vaca Saturno Saturnita"                   : "La_Vaca_Saturno_Saturnita",
        "Talpa Di Ferro"                              : "Talpa_Di_Ferro",
        "Lirili Larila"                               : "Lirili_Larila",
        "Tus-tus-…-Kaktus-…-Kutus Kutus"              : "Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus",
        "Cappuccino Assassino"                        : "Cappuccino_Assassino",
        "Udin din-din-din dun"                        : "Udin_din_din_din_dun",
        "Bombardino Crocodillo"                       : "Bombardino_Crocodillo",
        "Frigo camelo"                                : "Frigo_camelo",
        "Brr Brr Patapim"                             : "Brr_Brr_Patapim",
        "Trulimero Trulicina"                        : "Trulimero_Trulicina",
        "Chimpazini Bananini"                         : "Chimpazini_Bananini",
        "Balerinna Cappucinna"                        : "Balerinna_Cappucinna",
    }

    def _register_abilities(self) -> None:
        self.abilities: dict[str, dict[str, AbilityFn]] = {
            # event   : fn
            "Tralalelo_Tralala":                {"defence": self.ab_tralalelo_tralala},
            "Bobritto_Bandito":                 {"turn_end": self.ab_bobritto_bandito},
            "Tung_Tung_Tung_Sahur":             {"attack":   self.ab_tung_tung_tung_sahur},
            "Bombombini_Gusini":                {"turn_start": self.ab_bombombini_gusini},
            "Boneca_Ambamabu":                  {"turn_end": self.ab_boneca_ambamabu},
            "Trippi_Troppi":                    {"turn_end": self.ab_trippi_troppi},
            "La_Vaca_Saturno_Saturnita":        {"attack":   self.ab_la_vaca_saturno_saturnita},
            "Talpa_Di_Ferro":                   {"defence":  self.ab_talpa_di_ferro},
            "Lirili_Larila":                    {"attack":   self.ab_lirili_larila},
            "Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus": {
                "attack": self.ab_kaktus_targeting},
            "Cappuccino_Assassino":             {"defence":  self.ab_cappuccino_assassino},
            "Udin_din_din_din_dun":             {"attack":   self.ab_udin_din_dun},
            "Bombardino_Crocodillo":            {"attack":   self.ab_bombardino_crocodillo},
            "Frigo_camelo":                     {"attack":   self.ab_frigo_camelo},
            "Brr_Brr_Patapim":                  {"on_kill":  self.ab_brr_brr_patapim},
            "Trulimero_Trulicina":              {"turn_end": self.ab_trulimero_trulicina},
            "Chimpazini_Bananini":              {"turn_start": self.ab_chimpazini_bananini},
            "Balerinna_Cappucinna":             {"on_kill":  self.ab_balerinna_cappucinna},
        }

    # ─── вспомогательный метод ───
    def _ability_key(self, card: Card) -> str:
        """Определяем ключ способности по имени карты."""
        return self._name2key.get(card.name, "")

    def _trigger(self, ev: str, card: Card, row: int, col: int, **kw) -> None:
        key = self._ability_key(card)
        fn  = self.abilities.get(key, {}).get(ev)
        if fn:
            fn(card, row, col, **kw)

    # ---------------- init ----------------
    def __init__(self, db_path: str = "sqlite:///data/BD.db") -> None:
        self.engine = create_engine(db_path, echo=False)
        SqlAlchemyBase.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.grid: list[list[Optional[Card]]] = [[None] * 5 for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0            # 0-й ход игрока-1, 1-й — игрока-2

        self.coins = {1: 1, 2: 1}
        self.income = {1: 1, 2: 1}
        self.turn_count = {1: 0, 2: 0}  # сколько ХОДОВ провёл каждый игрок

        self.available_cards_p1: list[int] = []
        self.available_cards_p2: list[int] = []

        self._register_abilities()      #  таблица способностей

    # ────────────────────────────
    #  Utils
    # ────────────────────────────
    def _iter_board(self):
        """Удобный генератор (card,row,col) по всему полю."""
        for r in range(4):
            for c in range(5):
                card = self.grid[r][c]
                if card:
                    yield card, r, c

    def get_card_by_id(self, card_id: int) -> Optional[Card]:
        with self.Session() as s:
            return s.query(Card).filter(Card.id == card_id).first()

    def get_random_card(self) -> Optional[Card]:
        with self.Session() as s:
            cards = s.query(Card).filter(Card.id > 0).all()
        return choice(cards) if cards else None

    # ────────────────────────────
    #  Place / Move
    # ────────────────────────────
    def place_card(self, card_id: int, player_id: int, col: int) -> bool:
        card = self.get_card_by_id(card_id)
        if card is None or card.cost > self.coins[player_id]:
            return False

        row = 0 if player_id == 1 else 3
        if self.grid[row][col] is not None:
            return False

        card.ready_to_attack = False
        card.player_id = player_id
        card.cooldown = 0
        card.storage = {}
        self.coins[player_id] -= card.cost
        self.grid[row][col] = card

        getattr(self, f"available_cards_p{player_id}").remove(card_id)
        self._on_card_played(card, row, col)
        return True

    def move_cards(self, player_id: int) -> None:
        start_row, next_row = (0, 1) if player_id == 1 else (3, 2)
        step = 1 if player_id == 1 else -1
        rng = range(5)

        for col in rng:
            src_r, dst_r = (start_row, start_row + step)
            if self.grid[dst_r][col] is None and self.grid[src_r][col]:
                card = self.grid[src_r][col]
                self.grid[src_r][col] = None
                self.grid[dst_r][col] = card
                card.ready_to_attack = True

    # ────────────────────────────
    #  Battle phase & damage
    # ────────────────────────────
    def _resolve_attack(self, attacker: Card, ax: int, ay: int, defender: Optional[Card]) -> None:
        # Атакующие абилки
        self._trigger("attack", attacker, ay, ax, defender=defender)

        if defender:
            # Защитные абилки
            self._trigger("defence", defender, ay + (1 if defender.player_id == 2 else -1), ax, attacker=attacker)

        # Если после способности кто-то погиб — прерываем
        if defender and defender.health <= 0:
            self._on_card_killed(defender)
            self.grid[ay + (1 if defender.player_id == 2 else -1)][ax] = None
            # post-kill триггер (для убийцы и жертвы)
            self._trigger("on_kill", attacker, ay, ax, victim=defender)
            self._trigger("on_kill", defender, ay, ax, victim=defender, killer=attacker)
            return

        if defender:
            defender.health -= max(attacker.attack, 0)

            if defender.health <= 0:
                self._on_card_killed(defender)
                self.grid[ay + (1 if defender.player_id == 2 else -1)][ax] = None
                self._trigger("on_kill", attacker, ay, ax, victim=defender)
        else:
            self.damage_balance += attacker.attack if attacker.player_id == 1 else -attacker.attack

    def battle_phase(self, player_id: int) -> Optional[int]:
        row = 1 if player_id == 1 else 2
        for col in range(5):
            attacker = self.grid[row][col]
            defender = self.grid[row + (1 if player_id == 1 else -1)][col]
            if attacker and attacker.ready_to_attack:
                self._resolve_attack(attacker, col, row, defender)

        self.remove_dead_cards()

        if self.damage_balance >= 10:
            return 1
        if self.damage_balance <= -10:
            return 2
        return None

    # ────────────────────────────
    #  ШАГ
    # ────────────────────────────
    def start_turn(self, player_id: int) -> None:
        # turn-based абилки (до розыгрыша карт)
        self._on_turn_start(player_id)

    def end_turn(self, player_id: int) -> None:
        # 1 – инкременты и доход
        self.turn_count[player_id] += 1
        if self.turn_count[player_id] % 3 == 0:
            self.income[player_id] += 1
        self.coins[player_id] += self.income[player_id]

        # 2 – добор карт
        hand_attr = f"available_cards_p{player_id}"
        hand = getattr(self, hand_attr)
        if len(hand) < 3:
            new_card = self.get_random_card()
            if new_card:
                hand.append(new_card.id)

        # 3 – turn-based абилки (после действий игрока)
        self._on_turn_end(player_id)

    # ────────────────────────────
    #  Generic triggers
    # ────────────────────────────

    def _on_card_played(self, card: Card, row: int, col: int) -> None:
        # пока нет абилок при розыгрыше
        pass

    def _on_turn_start(self, player_id: int) -> None:
        for card, r, c in self._iter_board():
            if card.player_id == player_id:
                self._trigger("turn_start", card, r, c)

    def _on_turn_end(self, player_id: int) -> None:
        for card, r, c in self._iter_board():
            if card.player_id == player_id:
                self._trigger("turn_end", card, r, c)

    def _on_card_killed(self, card: Card) -> None:
        # пока пост-эффектов нет, кроме Balerinna / Patapim (через on_kill)
        pass

    # ────────────────────────────
    # Способности
    # ────────────────────────────
    # 1) Tralalelo — уклонение (30 %)
    @staticmethod
    def ab_tralalelo_tralala(card: Card, row: int, col: int, attacker: Card, **kw) -> None:
        if random() < 0.30:
            # полный игнор урона
            attacker.attack = max(attacker.attack - attacker.attack, 0)

    # 2) Bobritto — каждые 2 хода ворует 1…income монет
    def ab_bobritto_bandito(self, card: Card, row: int, col: int, **kw) -> None:
        card.cooldown = (card.cooldown + 1) % 2
        if card.cooldown == 0:
            opp = 2 if card.player_id == 1 else 1
            steal = randint(1, max(self.income[card.player_id], 1))
            self.coins[opp] = max(self.coins[opp] - steal, 0)
            self.coins[card.player_id] += steal

    # 3) Tung — 50 % шанс оглушить защитника (defender.ready_to_attack=False)
    @staticmethod
    def ab_tung_tung_tung_sahur(card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        if defender and random() < 0.5:
            defender.ready_to_attack = False

    # 4) Bombombini — если рядом Bombardino &rarr; +1/+1
    def ab_bombombini_gusini(self, card: Card, row: int, col: int, **kw) -> None:
        if card.storage.get("buffed"):
            return
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                r, c = row + dr, col + dc
                if 0 <= r < 4 and 0 <= c < 5 and (dr or dc):
                    other = self.grid[r][c]
                    if other and other.ability_key == "Bombardino_Crocodillo":
                        card.attack += 1
                        card.health += 1
                        card.storage["buffed"] = True
                        return

    # 5) Boneca — прыжок в соседнюю клетку + баф союзнику
    def ab_boneca_ambamabu(self, card: Card, row: int, col: int, **kw) -> None:
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        empty = [(row + dr, col + dc) for dr, dc in dirs
                 if 0 <= row + dr < 4 and 0 <= col + dc < 5 and self.grid[row + dr][col + dc] is None]
        if empty:
            nr, nc = choice(empty)
            self.grid[row][col], self.grid[nr][nc] = None, card
            # +1 к урону случайному союзнику
            allies = [c for c, _, _ in self._iter_board() if c.player_id == card.player_id and c is not card]
            if allies:
                choice(allies).attack += 1

    # 6) Trippi — каждые 3 хода копирование или хилл
    def ab_trippi_troppi(self, card: Card, row: int, col: int, **kw) -> None:
        card.cooldown = (card.cooldown + 1) % 3
        if card.cooldown == 0:
            empty = [(r, c) for r in range(4) for c in range(5) if self.grid[r][c] is None]
            if empty:
                nr, nc = choice(empty)
                clone = self.get_card_by_id(card.id)   # свежий объект из БД
                clone.player_id = card.player_id
                clone.ready_to_attack = False
                self.grid[nr][nc] = clone
            else:
                allies = [c for c, _, _ in self._iter_board() if c.player_id == card.player_id]
                if allies:
                    choice(allies).health += 2

    # 7) La Vaca — низкий шанс взорваться
    def ab_la_vaca_saturno_saturnita(self, card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        if random() < 0.15 and defender:
            defender.health = 0
            card.health = 0  # самоубийство
            self._on_card_killed(card)
            self._on_card_killed(defender)

    # 8) Talpa — невозможно ударить не в его ход
    def ab_talpa_di_ferro(self, card: Card, row: int, col: int, attacker: Card, **kw) -> None:
        if (self.turn_stage == 0 and card.player_id == 2) or (self.turn_stage == 1 and card.player_id == 1):
            attacker.attack = 0

    # 9) Lirili — бьёт раз в 2 хода
    @staticmethod
    def ab_lirili_larila(card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        card.cooldown = (card.cooldown + 1) % 2
        if card.cooldown != 1:   # атакует только на нечётных счётчиках
            card.attack = 0

    # 10) Kaktus — переопределяем цель (реализовано выбором колонки)
    def ab_kaktus_targeting(self, card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        if defender and defender.attack > 0:
            return  # нормальная цель OK
        # найдём самого сильного врага
        enemies = [(c, r, c2) for c, r, c2 in self._iter_board() if c.player_id != card.player_id]
        if enemies:
            target, tr, tc = max(enemies, key=lambda tpl: tpl[0].attack)
            self._resolve_attack(card, tc, row, target)  # повторная атака
            card.attack = 0  # не бьём дважды по старой ячейке

    # 11) Cappuccino — отскок (1 раз)
    def ab_cappuccino_assassino(self, card: Card, row: int, col: int, attacker: Card, **kw) -> None:
        if card.storage.get("dodged"):
            return
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        empty = [(row + dr, col + dc) for dr, dc in dirs
                 if 0 <= row + dr < 4 and 0 <= col + dc < 5 and self.grid[row + dr][col + dc] is None]
        if empty:
            nr, nc = choice(empty)
            # ставим манекен
            dummy = Card(id=-1, name="Капучино", attack=0, health=1, cost=0, ability_key=None)
            dummy.player_id = card.player_id
            dummy.ready_to_attack = False
            self.grid[row][col] = dummy
            # переносим основную карту
            self.grid[nr][nc] = card
            card.storage["dodged"] = True
            attacker.attack = 0   # удар уходит в молоко

    # 12) Udin — -1 к урону если рядом союзники
    def ab_udin_din_dun(self, card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        allies = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr or dc:
                    r, c = row + dr, col + dc
                    if 0 <= r < 4 and 0 <= c < 5:
                        other = self.grid[r][c]
                        if other and other.player_id == card.player_id:
                            allies += 1
        if allies:
            card.attack = max(card.attack - 1, 0)

    # 13) Bombardino — бьёт всех врагов сразу
    def ab_bombardino_crocodillo(self, card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        for c2, r2, col2 in [(c, r, c2) for c, r, c2 in self._iter_board() if c.player_id != card.player_id]:
            c2.health -= card.attack
            if c2.health <= 0:
                self._on_card_killed(c2)
                self.grid[r2][col2] = None
                self._trigger("on_kill", card, row, col, victim=c2)

        # основной фокус удар отменяем, чтобы не дублировать
        card.attack = 0

    # 14) Frigo — двойной удар + заморозка
    @staticmethod
    def ab_frigo_camelo(card: Card, row: int, col: int, defender: Optional[Card], **kw) -> None:
        if not defender:
            return
        # второй удар
        defender.health -= card.attack
        defender.ready_to_attack = False

    # 15) Patapim — после убийства теряет 1 атаку
    @staticmethod
    def ab_brr_brr_patapim(card: Card, row: int, col: int, victim: Card, killer: Card = None, **kw) -> None:
        if card is killer:
            card.attack = max(card.attack - 1, 0)

    # 16) Trulimero — самоповреждение
    def ab_trulimero_trulicina(self, card: Card, row: int, col: int, **kw) -> None:
        card.health -= 1
        if card.health <= 0:
            self._on_card_killed(card)
            self.grid[row][col] = None

    # 17) Chimpazini — когда игрок получает монеты &rarr; +2 к атаке
    @staticmethod
    def ab_chimpazini_bananini(card: Card, row: int, col: int, **kw) -> None:
        card.attack += 2

    # 18) Balerinna — когда враг её убивает &rarr; -2 к атаке врагу
    @staticmethod
    def ab_balerinna_cappucinna(card: Card, row: int, col: int, victim: Card, killer: Card, **kw) -> None:
        if victim is card and killer:
            killer.attack = max(killer.attack - 2, 0)

    def remove_dead_cards(self) -> None:
        for r in range(4):
            for c in range(5):
                card = self.grid[r][c]
                if card and card.health <= 0:
                    self.grid[r][c] = None

    def get_game_state(self, player_id: int) -> dict:
        opp = 2 if player_id == 1 else 1
        grid_out = []
        for row in self.grid:
            row_out = []
            for card in row:
                row_out.append(None if card is None else {
                    "name": card.name,
                    "attack": card.attack,
                    "health": card.health,
                    "ready_to_attack": card.ready_to_attack,
                    "player_id": card.player_id,
                })
            grid_out.append(row_out)

        hand = []
        for cid in getattr(self, f"available_cards_p{player_id}", []):
            c = self.get_card_by_id(cid)
            hand.append({
                "id": cid,
                "name": c.name, "attack": c.attack, "health": c.health
            })

        return {
            "grid": grid_out,
            "damage_balance": self.damage_balance,
            "coins": self.coins[player_id],
            "income": self.income[player_id],
            "available_cards": hand,
            "opponent_coins": self.coins[opp],
            "turn_count": self.turn_count[player_id],
        }

    def reset(self) -> None:
        self.__init__(str(self.engine.url))