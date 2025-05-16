"""
Пассивные способности карт.
Каждая способность наследуется от Ability и регистрируется
декоратором @ability("Ключ-в-БД").  Ключ кладём в поле
Card.ability_key (VARCHAR) или в json-файл с балансом.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:                       # только для type-hint’ов / подсветки IDE
    # В проекте нет modules.game / modules.models.
    # Используем реальные классы из deck.py:
    from deck import Deck as Game, Card

# -------------------------------------------------
# базовый класс + реестр
# -------------------------------------------------
ABILITY_REGISTRY: dict[str, "type[Ability]"] = {}


def ability(name: str) -> Callable[[type["Ability"]], type["Ability"]]:
    """Декоратор регистрации способности по её ключу в БД."""
    def wrap(cls: type["Ability"]) -> type["Ability"]:
        ABILITY_REGISTRY[name] = cls
        cls.key = name
        return cls
    return wrap


class Ability:
    """Базовый класс.  Потомок обязан определить:
       • trigger – имя события
       • apply(**ctx) – сам эффект
    """
    trigger: str
    key: str                                 # заполняется декоратором

    # основная точка входа каждой способности
    def apply(self, **ctx):                  # pylint: disable=unused-argument
        raise NotImplementedError

    # ──────────────── helpers ────────────────
    @staticmethod
    def yes(p: float) -> bool:
        """Вернёт True с вероятностью p."""
        return random.random() < p

    @staticmethod
    def allies_on_line(game: "Game", player_id: int, row: int) -> list["Card"]:
        return [c for c in game.grid[row] if c and c.player_id == player_id]

    @staticmethod
    def enemies(game: "Game", player_id: int) -> list["Card"]:
        opp_rows = (2, 3) if player_id == 1 else (0, 1)
        return [c for r in opp_rows for c in game.grid[r] if c]

# -------------------------------------------------
#  abilities below
# -------------------------------------------------

# ❖ 1  Tralalelo_Tralala — шанс уклониться (30 %)
@ability("Tralalelo_Tralala")
class Tralalelo(Ability):
    trigger = "before_being_hit"
    def apply(self, *, damage: int, **_):
        return 0 if self.yes(0.30) else damage


# ❖ 2  Bobritto_Bandito — каждые 2 хода ворует монеты (1 … income)
@ability("Bobritto_Bandito")
class Bobritto(Ability):
    trigger = "turn_end"
    def apply(self, *, game: "Game", card: "Card", **_):
        pid = card.player_id
        if game.turn_count[pid] % 2 == 0:
            steal  = random.randint(1, game.income[pid])
            opp    = 2 if pid == 1 else 1
            stolen = min(steal, game.coins[opp])
            game.coins[opp]  -= stolen
            game.coins[pid] += stolen


# ❖ 3  Tung_Tung_Tung_Sahur — 50 % оглушить врага
@ability("Tung_Tung_Tung_Sahur")
class Tung(Ability):
    trigger = "after_attack"
    def apply(self, *, defender: "Card", **_):
        if defender and self.yes(0.5):
            defender.ready_to_attack = False


# ❖ 4  Bombombini_Gusini — рядом с Bombordilo Crocodilo &rarr; +1/+1
@ability("Bombombini_Gusini")
class Bombombini(Ability):
    trigger = "on_play"
    def apply(self, *, game: "Game", card: "Card", col: int, **_):
        row = 0 if card.player_id == 1 else 3
        for dc in (-1, 1):
            if 0 <= col + dc < 5:
                c = game.grid[row][col + dc]
                if c and c.name == "Bombordilo Crocodilo":
                    card.attack += 1
                    card.health += 1
                    break


# ❖ 5  Boneca_Ambamabu — прыжок + баф союзнику
@ability("Boneca_Ambamabu")
class Boneca(Ability):
    trigger = "turn_start"
    def apply(self, *, game: "Game", card: "Card", **_):
        row = 1 if card.player_id == 1 else 2
        for dc in random.sample((-1, 1), 2):
            if 0 <= card.col + dc < 5 and game.grid[row][card.col + dc] is None:
                game.grid[row][card.col + dc] = card
                game.grid[row][card.col]      = None
                card.col += dc
                break
        allies = [c for c in game.grid[row] if c and c.player_id == card.player_id and c is not card]
        if allies:
            random.choice(allies).attack += 1


# ❖ 6  Trippi_Troppi — каждые 3 хода клонируется либо хилит
@ability("Trippi_Troppi")
class Trippi(Ability):
    trigger = "turn_end"
    def apply(self, *, game: "Game", card: "Card", **_):
        pid = card.player_id
        if game.turn_count[pid] % 3:
            return
        empties = [(r, c) for r in (1 if pid == 1 else 2,)
                         for c, cell in enumerate(game.grid[r]) if cell is None]
        if empties:
            r, c = random.choice(empties)
            game.grid[r][c] = card.clone()
        else:
            allies = [c for c in game.grid[1 if pid == 1 else 2] if c and c.player_id == pid]
            if allies:
                random.choice(allies).health += 2


# ❖ 7  La_Vaca_Saturno_Saturnita — шанс взорваться
@ability("La_Vaca_Saturno_Saturnita")
class VacaSaturno(Ability):
    trigger = "turn_end"
    def apply(self, *, game: "Game", card: "Card", **_):
        if self.yes(0.10):
            row_ahead = 2 if card.player_id == 1 else 1
            if game.grid[row_ahead][card.col]:
                game.grid[row_ahead][card.col] = None
            game.grid[card.row][card.col] = None


# ❖ 8  Talpa_Di_Ferro — неуязвима вне своего хода
@ability("Talpa_Di_Ferro")
class Talpa(Ability):
    trigger = "before_being_hit"
    def apply(self, *, game: "Game", card: "Card", **_):
        if game.current_attacker_id != card.player_id:
            return 0


# ❖ 9  Lirili_Larila — атакует через ход
@ability("Lirili_Larila")
class Lirili(Ability):
    trigger = "before_attack"
    def apply(self, *, game: "Game", card: "Card", **_):
        if game.turn_count[card.player_id] % 2:
            card.ready_to_attack = False


# ❖ 10  Tus…Kaktus — приоритет цели
@ability("Tus_tus_tus_tus_tus_Kaktus_tus_tus_kutus_kutus")
class Kaktus(Ability):
    trigger = "choose_target"
    def apply(self, *, game: "Game", card: "Card", **_):
        if game.last_killer and game.last_killer.player_id != card.player_id:
            return game.last_killer
        enemies = self.enemies(game, card.player_id)
        return max(enemies, key=lambda c: c.attack) if enemies else None


# ❖ 11  Cappuccino_Assassino — &laquo;замена&raquo; при первом ударе
@ability("Cappuccino_Assassino")
class Cappuccino(Ability):
    trigger = "before_being_hit"
    def __init__(self):
        self.used = False
    def apply(self, *, game: "Game", card: "Card", damage: int, **_):
        if self.used:
            return damage
        self.used = True
        dummy = card.clone()
        dummy.attack = 0
        dummy.health = 1
        dummy.ready_to_attack = False
        game.grid[card.row][card.col] = dummy
        return 0


# ❖ 12  Udin_din_din_din_dun — -1 ATK, если союзники рядом
@ability("Udin_din_din_din_dun")
class Udin(Ability):
    trigger = "turn_start"
    def apply(self, *, game: "Game", card: "Card", **_):
        row = card.row
        adj = [game.grid[row][c] for c in (card.col - 1, card.col + 1)
                               if 0 <= c < 5 and game.grid[row][c]]
        card.attack = max(0, card.base_attack - 1) if adj else card.base_attack


# ❖ 13  Bombardino_Crocodillo — бьёт всю линию
@ability("Bombardino_Crocodillo")
class Bombardino(Ability):
    trigger = "before_attack"
    def apply(self, *, game: "Game", card: "Card", **_):
        row_def = 2 if card.player_id == 1 else 1
        for def_card in list(game.grid[row_def]):
            if def_card:
                def_card.health -= card.attack
                if def_card.health <= 0:
                    game.grid[row_def][def_card.col] = None
        card.ready_to_attack = False


# ❖ 14  Frigo_camelo — двойной удар + заморозка
@ability("Frigo_camelo")
class Frigo(Ability):
    trigger = "after_attack"
    def apply(self, *, defender: "Card", **_):
        if defender:
            defender.health -= 1
            defender.frozen_for = 1


# ❖ 15  Brr_Brr_Patapim — -1 ATK за каждый килл
@ability("Brr_Brr_Patapim")
class Brr(Ability):
    trigger = "on_kill"
    def apply(self, *, card: "Card", **_):
        card.attack = max(0, card.attack - 1)


# ❖ 16  Trulimero_Trulicina — теряет 1 HP каждый ход
@ability("Trulimero_Trulicina")
class Trulimero(Ability):
    trigger = "turn_end"
    def apply(self, *, card: "Card", **_):
        card.health -= 1


# ❖ 17  Chimpazini_Bananini — +2 ATK при доходе
@ability("Chimpazini_Bananini")
class Chimpazini(Ability):
    trigger = "income"
    def apply(self, *, card: "Card", **_):
        card.attack += 2


# ❖ 18  Balerinna_Cappucinna — убийца теряет 2 ATK
@ability("Balerinna_Cappucinna")
class Balerinna(Ability):
    trigger = "on_death"
    def apply(self, *, killer: "Card", **_):
        if killer:
            killer.attack = max(0, killer.attack - 2)