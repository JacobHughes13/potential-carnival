from typing import Optional
import sqlite3
import os
from dataclasses import dataclass


@dataclass
class Card:
    name: str
    attack: int
    health: int
    cost: int


class Deck:
    def __init__(self, db_path: str = 'BD/BD.db'):
        self.grid: list[list[Optional[Card]]] = [[None for _ in range(4)] for _ in range(4)]
        self.db_path = db_path

        self.con = sqlite3.connect(self.db_path)
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
            self.cur.execute('''SELECT name, damage, health, cost
                                  FROM cards
                                 LIMIT 1
                             ''')
        except sqlite3.OperationalError:
            self.init_db()

    def get_card_by_id(self, card_id: int, player_id: str) -> Optional[Card]:
        self.cur.execute('''SELECT name, damage, health, cost
                                  FROM cards
                                 WHERE id = ?
                             ''', (card_id,)
                         )
        result = self.cur.fetchone()
        if result:
            return Card(*result, player_id)
        return None

    def place_card(self, card: Card, player_id: int, col: int) -> bool:
        print(player_id)
        if player_id == 1:
            row = 0
        elif player_id == 2:
            row = 3
        else:
            return False

        if self.grid[row][col] is not None:
            return False
        else:
            self.grid[row][col] = card
            return True

    def move_cards(self) -> None:
        for col in range(4):
            if self.grid[0][col] and not self.grid[1][col]:
                self.grid[1][col] = self.grid[0][col]
                self.grid[0][col] = None
            elif self.grid[1][col] and not self.grid[2][col]:
                self.grid[2][col] = self.grid[1][col]
                self.grid[1][col] = None

        for col in range(4):
            if self.grid[3][col] and not self.grid[2][col]:
                self.grid[2][col] = self.grid[3][col]
                self.grid[3][col] = None
            elif self.grid[2][col] and not self.grid[1][col]:
                self.grid[1][col] = self.grid[2][col]
                self.grid[2][col] = None

    def battle_phase(self, player_id) -> dict[int, int]:
        damage = {1: 0, 2: 0}
        for row in [1, 2]:
            for col in range(4):
                card = self.grid[row][col]
                if card:
                    damage[player_id] += card.attack
        return damage

    def remove_dead_cards(self) -> None:
        for row in range(4):
            for col in range(4):
                card = self.grid[row][col]
                if card:
                    if card.health <= 0:
                        self.grid[row][col] = None
