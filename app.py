from flask import Flask, render_template
from deck import Deck, Card

app = Flask(__name__)

# Создаём глобальное игровое поле (для примера)
deck = Deck()

# Добавляем тестовые карты для демонстрации
deck.place_card(Card("Воин", 3, 5, 1), 0)  # Игрок 1, колонка 0
deck.place_card(Card("Лучник", 2, 3, 2), 3)  # Игрок 2, колонка 3

@app.route("/")
def home():
    # Передаём игровое поле в HTML-шаблон
    return render_template("index.html", grid=deck.grid)

if __name__ == "__main__":
    app.run(debug=True)