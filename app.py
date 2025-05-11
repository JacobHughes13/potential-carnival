from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from deck import *
from werkzeug.security import generate_password_hash, check_password_hash
from random import choices
import string

app = Flask(__name__)
app.secret_key = 'SUPER_SECRET_KEY'
deck = Deck('sqlite:///BD/BD.db')

socketio = SocketIO(app)
lobbies = {}  # Словарь: room_code -> [usernames]


def generate_lobby_code() -> str:
    return ''.join(choices(string.ascii_uppercase + string.digits, k=6))


@app.route("/lobby", methods=["GET", "POST"])
def lobby():
    if 'username' not in session:
        return redirect(url_for("login"))

    username = session["username"]
    return render_template("lobby.html",
                           username=username)


@app.route('/choose_mode')
def choose_mode():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('choose_mode.html', username=session.get('username'))


@app.route('/create_lobby')
def create_lobby():
    if 'username' not in session:
        return redirect(url_for('login'))
    code = generate_lobby_code()
    lobbies[code] = {'host': session['username'], 'guest': None}
    return render_template('create_lobby.html', lobby_code=code)


@app.route('/join_lobby', methods=['GET', 'POST'])
def join_lobby():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        code = request.form['lobby_code'].strip().upper()
        if code in lobbies and lobbies[code]['guest'] is None:
            lobbies[code]['guest'] = session['username']
            return redirect(url_for('game', lobby_code=code))  # переход к игре
        else:
            return "Неверный код или лобби уже заполнено", 400
    return render_template('join_lobby.html')


@app.route('/cancel_lobby', methods=['POST'])
def cancel_lobby():
    for code, data in list(lobbies.items()):
        if data['host'] == session.get('username'):
            del lobbies[code]
    return redirect(url_for('choose_mode'))


@app.route('/game/<lobby_code>')
def game(lobby_code: str):
    return f"Игра началась в лобби {lobby_code}"


@app.route('/play_self')
def play_self():
    return redirect(url_for('play'))



@socketio.on("create_room")
def handle_create_room(data):
    username = session.get("username")
    room_code = generate_room_code()
    rooms[room_code] = [username]
    join_room(room_code)
    emit("room_created", {"room": room_code, "users": rooms[room_code]}, room=room_code)


@socketio.on("join_room")
def handle_join_room(data):
    room_code = data["room"]
    username = session.get("username")
    if room_code in rooms:
        if username not in rooms[room_code]:
            rooms[room_code].append(username)
        join_room(room_code)
        emit("room_joined", {"room": room_code, "users": rooms[room_code]}, room=room_code)
    else:
        emit("error", {"message": "Комната не найдена."})


@app.route("/")
@app.route("/home")
def home():
    return redirect(url_for("main_menu"))


@app.route("/main_menu")
def main_menu():
    username = session.get('username')
    return render_template("main_menu.html",
                           username=username)


@app.route("/play")
def play():
    if "user_id" not in session:
        return redirect(url_for('login'))

    current_player = session.get('current_player', 1)
    username = session.get('username')
    card_ids = session.get(f'available_cards_p{current_player}', [])
    cards = [deck.get_card_by_id(card_id) for card_id in card_ids]

    return render_template("index.html",
                           cards=cards,
                           grid=deck.grid,
                           current_player=current_player,
                           damage_balance=deck.damage_balance,
                           coins=deck.coins,
                           username=username)


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
    session.pop('available_cards_p1', None)
    session.pop('available_cards_p2', None)
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
    session.pop('available_cards_p1', None)
    session.pop('available_cards_p2', None)
    return redirect(url_for("login"))


@app.route("/pick_up_the_card/<int:card_id>")
def pick_up_the_card(card_id: int):
    session['selected_card'] = card_id
    return redirect(url_for("play"))


@app.route("/place_card/<int:row>/<int:col>")
def place_card(row: int, col: int):
    current_player = session.get('current_player', 1)
    card_key = f'available_cards_p{current_player}'

    if 'selected_card' in session:
        success = deck.place_card(session['selected_card'], current_player, col)
        if success:
            if card_key in session:
                session[card_key] = [cid for cid in session[card_key]
                                     if cid != session['selected_card']]
            session.pop('selected_card', None)
    return redirect(url_for("play"))



@app.route("/player1_turn")
def player1_turn():
    player_id = 1
    winner = deck.battle_phase(player_id)
    if winner:
        return render_template("winner.html",
                               winner=winner)

    deck.move_cards(player_id)
    deck.end_turn(player_id)

    key = f'available_cards_p{player_id}'
    cards = session.get(key, [])
    if len(cards) < 3:
        new_card = deck.get_random_card()
        if new_card:
            cards.append(new_card.id)
    session[key] = cards

    session['current_player'] = 2
    return redirect(url_for("play"))


@app.route("/player2_turn")
def player2_turn():
    player_id = 2
    winner = deck.battle_phase(player_id)
    if winner:
        return render_template("winner.html",
                               winner=winner)

    deck.move_cards(player_id)
    deck.end_turn(player_id)

    key = f'available_cards_p{player_id}'
    cards = session.get(key, [])
    if len(cards) < 3:
        new_card = deck.get_random_card()
        if new_card:
            cards.append(new_card.id)
    session[key] = cards

    session['current_player'] = 1
    return redirect(url_for("play"))


@app.route("/reset")
def reset():
    deck.reset()
    session['current_player'] = 1
    session.pop('selected_card', None)

    session['available_cards_p1'] = [deck.get_random_card().id]
    session['available_cards_p2'] = [deck.get_random_card().id]

    return redirect(url_for("play"))


def main() -> None:
    socketio.run(app=app, port=8080, host='127.0.0.1', debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
