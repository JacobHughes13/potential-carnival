from typing import Optional
import sqlite3
import os
from dataclasses import dataclass


@dataclass
class Card:
    id: int
    name: str
    attack: int
    health: int
    cost: int
    ready_to_attack: bool = False


class Deck:
    def __init__(self, db_path: str = 'BD/BD.db') -> None:
        self.grid: list[list[Optional[Card]]] = [[None for _ in range(4)] for _ in range(4)]
        self.db_path = db_path
        self.turn_stage = 0  # 0 -> p1, 1 -> p2
        self.damage_balance = 0
        self._init_db_connection()

    def _init_db_connection(self) -> None:
        self.con = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cur = self.con.cursor()
        if not os.path.exists(self.db_path):
            self.init_db()
        else:
            self.check_db_structure()

    def init_db(self) -> None:
        self.cur.execute('''
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                attack INTEGER NOT NULL,
                health INTEGER NOT NULL,
                cost INTEGER NOT NULL
            )
        ''')
        self.con.commit()

    def check_db_structure(self) -> None:
        try:
            self.cur.execute('SELECT name, attack, health, cost FROM cards LIMIT 1')
        except sqlite3.OperationalError:
            self.init_db()

    def get_card_by_id(self, card_id: int) -> Optional[Card]:
        self.cur.execute('SELECT id, name, attack, health, cost FROM cards WHERE id = ?', (card_id,))
        result = self.cur.fetchone()
        if result:
            return Card(*result)
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

    def move_cards(self) -> None:
        for col in range(4):
            if self.grid[1][col] is None and self.grid[0][col]:
                self.grid[1][col] = self.grid[0][col]
                self.grid[0][col] = None
                self.grid[1][col].ready_to_attack = True

            if self.grid[2][col] is None and self.grid[3][col]:
                self.grid[2][col] = self.grid[3][col]
                self.grid[3][col] = None
                self.grid[2][col].ready_to_attack = True

    def battle_phase(self) -> Optional[int]:
        for col in range(4):
            attacker1 = self.grid[1][col]
            defender2 = self.grid[2][col]
            if attacker1 and attacker1.ready_to_attack:
                if defender2:
                    defender2.health -= attacker1.attack
                    if defender2.health <= 0:
                        self.grid[2][col] = None
                else:
                    self.damage_balance += attacker1.attack

            attacker2 = self.grid[2][col]
            defender1 = self.grid[1][col]
            if attacker2 and attacker2.ready_to_attack:
                if defender1:
                    defender1.health -= attacker2.attack
                    if defender1.health <= 0:
                        self.grid[1][col] = None
                else:
                    self.damage_balance -= attacker2.attack

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

    def reset(self):
        self.grid = [[None for _ in range(4)] for _ in range(4)]
        self.damage_balance = 0
        self.turn_stage = 0
