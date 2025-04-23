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
        return render_template("index.html",
                               grid=deck.grid,
                               current_player=session.get('current_player', 1),
                               damage_balance=deck.damage_balance)


@app.route("/pick_up_the_card/<int:card_id>")
def pick_up_the_card(card_id: int):
    session['selected_card'] = card_id
    return redirect(url_for("home"))


@app.route("/place_card/<int:row>/<int:col>")
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

        if deck.turn_stage == 0:
            deck.turn_stage = 1
            session['current_player'] = 2
        else:
            winner = deck.battle_phase()
            deck.turn_stage = 0
            session['current_player'] = 1
            if winner:
                return render_template("winner.html", winner=winner)

    return redirect(url_for("home"))


@app.route("/reset")
def reset():
    with deck_lock:
        deck.reset()
        session['current_player'] = 1
        session.pop('selected_card', None)
    return redirect(url_for("home"))


def main() -> None:
    app.run(port=8080, host='127.0.0.1', debug=True)


if __name__ == '__main__':
    main()
