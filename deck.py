from typing import Optional, List, Dict
import sqlite3
from dataclasses import dataclass

@dataclass
class Card:
    name: str
    attack: int
    health: int
    cost: int
    player_id: int

class Deck:
    def __init__(self, db_path: str = 'BD/BD.db'):
        self.grid: List[List[Optional[Card]]] = [[None for _ in range(4)] for _ in range(4)]
        self.db_path = db_path
        # todo conect BD.db
        # self._init_db()

    # def _init_db(self):
    #     with sqlite3.connect(self.db_path) as conn:
    #         conn.execute('''
    #             CREATE TABLE IF NOT EXISTS cards (
    #                 id INTEGER PRIMARY KEY,
    #                 name TEXT NOT NULL,
    #                 attack INTEGER NOT NULL,
    #                 health INTEGER NOT NULL,
    #                 cost INTEGER NOT NULL
    #             )
    #         ''')
    #         if not conn.execute("SELECT 1 FROM cards LIMIT 1").fetchone():
    #             conn.executemany(
    #                 "INSERT INTO cards (name, attack, health, cost) VALUES (?, ?, ?, ?)",
    #                 [("Воин", 3, 5, 1), ("Лучник", 2, 3, 2), ("Маг", 4, 2, 3)]
    #             )

    def get_card_by_id(self, card_id: int, player_id: int) -> Optional[Card]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name, attack, health, cost FROM cards WHERE id = ?",
                (card_id,)
            )
            if result := cursor.fetchone():
                return Card(*result, player_id)
            return None

    def place_card(self, card: Card, col: int) -> bool:
        if card.player_id == 1:
            row = 0
        elif card.player_id == 2:
            row = 3
        else:
            return False

        if self.grid[row][col] is not None:
            return False

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

    def battle_phase(self) -> Dict[int, int]:
        damage = {1: 0, 2: 0}
        for row in [1, 2]:
            for col in range(4):
                if card := self.grid[row][col]:
                    damage[3 - card.player_id] += card.attack
        return damage

    def remove_dead_cards(self) -> None:
        for row in range(4):
            for col in range(4):
                if card := self.grid[row][col]:
                    if card.health <= 0:
                        self.grid[row][col] = None