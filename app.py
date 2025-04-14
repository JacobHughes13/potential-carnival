from flask import Flask, render_template, redirect, url_for
from deck import Deck


app = Flask(__name__)
deck = Deck('BD/BD.db')


@app.route("/")
def home() -> str:
    return render_template("index.html", grid=deck.grid)


@app.route("/place_card/<int:player_id>/<int:card_id>/<int:col>")
def place_card(player_id: int, card_id: int, col: int):
    if card := deck.get_card_by_id(card_id, player_id):
        deck.place_card(card, col)
    return redirect(url_for("home"))


@app.route("/end_turn")
def end_turn():
    deck.move_cards()
    damage = deck.battle_phase()
    deck.remove_dead_cards()
    return redirect(url_for("home"))


@app.route("/reset")
def reset():
    deck.grid = [[None for _ in range(4)] for _ in range(4)]
    return redirect(url_for("home"))


def main() -> None:
    app.run(port=8080, host='127.0.0.1', debug=True)


if __name__ == '__main__':
    main()