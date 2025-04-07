from typing import Optional, List, Dict


class Card:
    def __init__(self, name: str, attack: int, health: int, player_id: int):
        self.name = name
        self.attack = attack
        self.health = health
        self.player_id = player_id  # 1 или 2 (чтобы знать, куда двигать)


class Deck:
    def __init__(self):
        # Игровое поле 4x4 (None - пустая клетка)
        self.grid: List[List[Optional[Card]]] = [[None for _ in range(4)] for _ in range(4)]

    def place_card(self, card: Card, col: int) -> bool:
        """Поместить карту на поле вступления (строка 0 для игрока 1, строка 3 для игрока 2)."""
        if card.player_id == 1:
            row = 0
        elif card.player_id == 2:
            row = 3
        else:
            return False  # Некорректный игрок

        if self.grid[row][col] is not None:
            return False  # Клетка занята

        self.grid[row][col] = card
        return True

    def move_cards(self) -> None:
        """Переместить все карты на 1 клетку ближе к полю битвы."""
        # Движение карт игрока 1 (вниз: 0 → 1 → 2)
        for col in range(4):
            if self.grid[0][col] is not None and self.grid[1][col] is None:
                self.grid[1][col] = self.grid[0][col]
                self.grid[0][col] = None
            elif self.grid[1][col] is not None and self.grid[2][col] is None:
                self.grid[2][col] = self.grid[1][col]
                self.grid[1][col] = None

        # Движение карт игрока 2 (вверх: 3 → 2 → 1)
        for col in range(4):
            if self.grid[3][col] is not None and self.grid[2][col] is None:
                self.grid[2][col] = self.grid[3][col]
                self.grid[3][col] = None
            elif self.grid[2][col] is not None and self.grid[1][col] is None:
                self.grid[1][col] = self.grid[2][col]
                self.grid[2][col] = None

    def battle_phase(self) -> Dict[int, int]:
        """Фаза битвы: все карты на строках 1 и 2 атакуют.
        Возвращает урон, нанесённый каждому игроку."""
        damage = {1: 0, 2: 0}  # Урон по игроку 1 и 2

        # Карты игрока 1 (строка 1 и 2) атакуют игрока 2
        for row in [1, 2]:
            for col in range(4):
                card = self.grid[row][col]
                if card is not None and card.player_id == 1:
                    damage[2] += card.attack

        # Карты игрока 2 (строка 1 и 2) атакуют игрока 1
        for row in [1, 2]:
            for col in range(4):
                card = self.grid[row][col]
                if card is not None and card.player_id == 2:
                    damage[1] += card.attack

        return damage

    def remove_dead_cards(self) -> None:
        """Удалить карты с health <= 0."""
        for row in range(4):
            for col in range(4):
                card = self.grid[row][col]
                if card is not None and card.health <= 0:
                    self.grid[row][col] = None

    def __str__(self) -> str:
        """Визуализация поля (для отладки)."""
        output = []
        for row in self.grid:
            output.append(" | ".join(
                f"{card.name}({card.health})" if card else "Empty"
                for card in row
            ))
        return "\n".join(output)