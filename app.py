from flask import Flask, render_template, redirect, url_for, session, request, flash
from deck import *
from werkzeug.security import generate_password_hash, check_password_hash
import threading

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'
deck = Deck('sqlite:///BD/BD.db')
deck_lock = threading.Lock()


@app.route("/")
def home() -> str:
    if "user_id" not in session:
        return redirect(url_for('login'))

    with deck_lock:
        return render_template("index.html",
                               grid=deck.grid,
                               current_player=session.get('current_player', 1),
                               damage_balance=deck.damage_balance,
                               username=session.get('username'))

'''
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        session_db = deck.Session()
        existing_user = session_db.query(User).filter_by(username=username).first()
        if existing_user:
            session_db.close()
            flash("Пользователь с таким именем уже существует.")
            return redirect(url_for("register"))

        new_user = User(username=username, password=hashed_password)
        session_db.add(new_user)
        session_db.commit()
        session_db.close()

        flash("Регистрация успешна! Теперь войдите в аккаунт.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        session_db = deck.Session()
        user = session_db.query(User).filter_by(username=username).first()
        session_db.close()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for("home"))
        else:
            flash("Неверное имя пользователя или пароль.")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/friends", methods=["GET", "POST"])
def friends():
    if 'user_id' not in session:
        return redirect(url_for("login"))

    session_db = deck.Session()
    user_id = session['user_id']

    if request.method == "POST":
        friend_username = request.form["friend_username"]
        friend = session_db.query(User).filter_by(username=friend_username).first()
        if friend and friend.id != user_id:
            existing = session_db.query(Friend).filter_by(user_id=user_id, friend_id=friend.id).first()
            if not existing:
                new_friend = Friend(user_id=user_id, friend_id=friend.id)
                session_db.add(new_friend)
                session_db.commit()

    friends_list = session_db.query(User.username).join(
        Friend, User.id == Friend.friend_id
    ).filter(Friend.user_id == user_id).all()
    session_db.close()

    return render_template("friends.html", friends=friends_list)


@app.route("/logout")
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_player', None)
    session.pop('selected_card', None)
    return redirect(url_for("login"))
'''


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


@app.route("/player1_turn")
def player1_turn():
    with deck_lock:
        player_id = 1
        winner = deck.battle_phase(player_id=player_id)
        deck.move_cards(player_id=player_id)
        session['current_player'] = 2
        if winner:
            return render_template("winner.html",
                                   winner=winner)
    return redirect(url_for("home"))


@app.route("/player2_turn")
def player2_turn():
    with deck_lock:
        player_id = 2
        winner = deck.battle_phase(player_id=player_id)
        deck.move_cards(player_id=player_id)
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
