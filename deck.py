from typing import Optional, List, Dict
import sqlite3
import os
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

        # Проверяем существование файла БД

        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def _check_db_structure(self):
        """Проверка структуры существующей БД"""
        try:
            self.cursor.execute("SELECT name, attack, health, cost FROM cards LIMIT 1")
        except sqlite3.OperationalError:
            # Если таблицы нет, создаём её
            self._init_db()

    def get_card_by_id(self, card_id: int, player_id: int) -> Optional[Card]:
        """Получить карту по ID из существующей БД"""
        self.cursor.execute(
            "SELECT name, attack, health, cost FROM cards WHERE id = ?",
            (card_id,)
        )
        if result := self.cursor.fetchone():
            return Card(*result, player_id)
        return None

    # Остальные методы остаются без изменений
    # place_card, move_cards, battle_phase, remove_dead_cards