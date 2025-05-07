from flask import Flask, render_template, redirect, url_for, session, request, flash
from deck import *
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'
deck = Deck('sqlite:///BD/BD.db')


@app.route("/")
def home():
    return redirect(url_for("main_menu"))


@app.route("/main_menu")
def main_menu():
    return render_template("main_menu.html",
                           username=session.get('username'))


@app.route("/play")
def play():
    if "user_id" not in session:
        return redirect(url_for('login'))

    return render_template("index.html",
                           grid=deck.grid,
                           current_player=session.get('current_player', 1),
                           damage_balance=deck.damage_balance,
                           coins=deck.coins,
                           username=session.get('username'))


@app.route("/settings")
def settings():
    return "Настройки настраиваются"  # Заглушка


@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    return f"Профиль игрока {session['username']}"


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        db_session = deck.Session()
        existing_user = db_session.query(User).filter_by(username=username).first()
        if existing_user:
            db_session.close()
            flash("Пользователь с таким именем уже существует.")
            return redirect(url_for("register"))

        new_user = User(username=username, password=hashed_password)
        db_session.add(new_user)
        db_session.commit()
        db_session.close()

        flash("Регистрация успешна! Теперь войдите в аккаунт.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db_session = deck.Session()
        user = db_session.query(User).filter_by(username=username).first()
        db_session.close()

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

    db_session = deck.Session()
    user_id = session['user_id']

    if request.method == "POST":
        friend_username = request.form["friend_username"]
        friend = db_session.query(User).filter_by(username=friend_username).first()
        if friend and friend.id != user_id:
            existing = db_session.query(Friend).filter_by(user_id=user_id, friend_id=friend.id).first()
            if not existing:
                new_friend = Friend(user_id=user_id, friend_id=friend.id)
                db_session.add(new_friend)
                db_session.commit()

    friends_list = db_session.query(User.username).join(
        Friend, User.id == Friend.friend_id
    ).filter(Friend.user_id == user_id).all()
    db_session.close()

    return render_template("friends.html",
                           friends=friends_list)


@app.route("/logout")
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_player', None)
    session.pop('selected_card', None)
    return redirect(url_for("login"))


@app.route("/pick_up_the_card/<int:card_id>")
def pick_up_the_card(card_id: int):
    session['selected_card'] = card_id
    return redirect(url_for("play"))


@app.route("/place_card/<int:row>/<int:col>")
def place_card(row: int, col: int):
    current_player = session.get('current_player', 1)
    if 'selected_card' in session:
        success = deck.place_card(session['selected_card'], current_player, col)
        if success:
            session.pop('selected_card', None)
    return redirect(url_for("play"))


@app.route("/player1_turn")
def player1_turn():
    player_id = 1
    winner = deck.battle_phase(player_id=player_id)
    deck.move_cards(player_id=player_id)
    deck.end_turn(player_id=player_id)
    session['current_player'] = 2
    if winner:
        return render_template("winner.html",
                               winner=winner)
    return redirect(url_for("play"))


@app.route("/player2_turn")
def player2_turn():
    player_id = 2
    winner = deck.battle_phase(player_id=player_id)
    deck.move_cards(player_id=player_id)
    deck.end_turn(player_id=player_id)
    session['current_player'] = 1
    if winner:
        return render_template("winner.html",
                               winner=winner)
    return redirect(url_for("play"))


@app.route("/reset")
def reset():
    deck.reset()
    session['current_player'] = 1
    session.pop('selected_card', None)
    return redirect(url_for("play"))


def main() -> None:
    app.run(port=8080, host='127.0.0.1', debug=True)


if __name__ == '__main__':
    main()
