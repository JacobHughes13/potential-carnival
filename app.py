from flask import Flask, render_template, redirect, url_for, session
from deck import Deck
import threading


app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'

deck = Deck('BD/BD.db')

deck_lock = threading.Lock()


@app.route("/")
def home() -> str:
    with deck_lock:
        return render_template("index.html", grid=deck.grid, current_player=session.get('current_player', 1))


@app.route("/pick_up_the_card/<int:card_id>")
def pick_up_the_card(card_id: int):
    session['selected_card'] = card_id
    return redirect(url_for("home"))


@app.route("/place_card/<int:row>/<int:col>")  # TODO: избавится от зависимости row
def place_card(row: int, col: int):
    current_player = session.get('current_player', 1)
    if 'selected_card' in session:
        with deck_lock:
            success = deck.place_card(session['selected_card'], current_player, col)
            if success:
                session.pop('selected_card', None)
    return redirect(url_for("home"))


@app.route("/end_turn")
def end_turn():
    with deck_lock:
        deck.remove_dead_cards()
        deck.move_cards()

        if session.get('current_player', 1) == 1:
            session['current_player'] = 2
        else:
            session['current_player'] = 1
    return redirect(url_for("home"))


@app.route("/reset")
def reset():
    with deck_lock:
        deck.grid = [[None for _ in range(4)] for _ in range(4)]
        session['current_player'] = 1
        session.pop('selected_card', None)
    return redirect(url_for("home"))


def main() -> None:
    app.run(port=8080, host='127.0.0.1', debug=True)


if __name__ == '__main__':
    main()