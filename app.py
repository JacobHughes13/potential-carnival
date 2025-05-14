from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
from random import choices, randint
import string
import os
from datetime import datetime
from deck import Deck, User, Friend, Card, SqlAlchemyBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*")  # , async_mode='eventlet'

# Инициализация базы данных и игры
deck = Deck('sqlite:///BD/BD.db')
db_path = 'sqlite:///BD/BD.db'
engine = create_engine(db_path)
Session = sessionmaker(bind=engine)
db_session = Session()


# Глобальное состояние игры
rooms = {}  # {room_code: {host: str, guest: str, deck: Deck, state: str, last_action: datetime}}
user_rooms = {}  # {username: room_code} для быстрого поиска

class GameStates:
    WAITING = "waiting"
    PLAYING = "playing"
    FINISHED = "finished"


def generate_lobby_code():
    return ''.join(choices(string.ascii_uppercase + string.digits, k=6))


@app.route('/')
def home():
    return redirect(url_for('main_menu'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        session = db_session
        existing_user = session.query(User).filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            password=generate_password_hash(password)
        )
        session.add(new_user)
        session.commit()
        session.close()

        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = db_session
        user = db.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            db.close()
            return redirect(url_for('main_menu'))
        else:
            flash('Invalid username or password')
            db.close()
    return render_template('login.html')


@app.route('/main_menu')
def main_menu():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('main_menu.html', username=session['username'])


@app.route('/lobby')
def lobby():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('lobby.html', username=session['username'])


@app.route('/create_lobby')
def create_lobby():
    if 'username' not in session:
        return redirect(url_for('login'))

    code = generate_lobby_code()
    rooms[code] = {
        'host': session['username'],
        'guest': None,
        'deck': Deck(db_path),
        'state': GameStates.WAITING,
        'last_action': datetime.now()
    }
    user_rooms[session['username']] = code

    return render_template('create_lobby.html', lobby_code=code)


'''@app.route('/join_lobby', methods=['GET', 'POST'])
def join_lobby():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form['lobby_code'].upper()
        if code in rooms and rooms[code]['guest'] is None:
            rooms[code]['guest'] = session['username']
            user_rooms[session['username']] = code
            rooms[code]['state'] = GameStates.PLAYING
            return redirect(url_for('game', lobby_code=code))
        else:
            flash('Invalid lobby code or lobby is full')
    return render_template('join_lobby.html')'''


@app.route('/game/<lobby_code>')
def game(lobby_code):
    if 'username' not in session:
        return redirect(url_for('login'))

    if lobby_code not in rooms:
        flash('Lobby not found')
        return redirect(url_for('lobby'))

    room = rooms[lobby_code]
    username = session['username']

    if username not in [room['host'], room['guest']]:
        flash('You are not in this lobby')
        return redirect(url_for('lobby'))

    player_id = 1 if username == room['host'] else 2
    opponent = room['host'] if player_id == 2 else room['guest']

    return render_template('game.html',
                           lobby_code=lobby_code,
                           username=username,
                           opponent=opponent,
                           player_id=player_id,
                           game_state=room['deck'].get_game_state(player_id))


@socketio.on('connect')
def handle_connect() -> None:
    if 'username' not in session:
        return

    username = session['username']
    room_code = user_rooms.get(username)
    print(f'User {username} connected')

    if room_code and room_code in rooms:
        room = rooms[room_code]

        if username == room['host']:
            room['host_connected'] = True
            player_id = 1
        else:
            room['guest_connected'] = True
            player_id = 2

        join_room(room_code)
        join_room(f"{room_code}_player{player_id}")

        emit('game_update',
             {'game_state': room['deck'].get_game_state(player_id),
              'current_player': room['deck'].turn_stage + 1},
             room=f"{room_code}_player{player_id}")

        emit('player_reconnected',
             {'username': username},
             room=room_code)


@socketio.on('disconnect')
def handle_disconnect() -> None:
    if 'username' not in session:
        return

    username  = session['username']
    room_code = user_rooms.get(username)
    print(f'User {username} disconnected')

    if not room_code or room_code not in rooms:
        return

    room = rooms[room_code]
    if username == room['host']:
        room['host_connected'] = False
    else:
        room['guest_connected'] = False

    emit('player_disconnected', {'username': username}, room=room_code)

    leave_room(room_code)
    leave_room(f"{room_code}_player1")
    leave_room(f"{room_code}_player2")


@socketio.on('game_action')
def handle_game_action(data):
    if 'username' not in session:
        return

    username = session['username']
    room_code = data['room']
    action = data['action']

    if room_code not in rooms:
        return

    room = rooms[room_code]
    deck = room['deck']
    player_id = 1 if username == room['host'] else 2

    try:
        if action == 'place_card':
            card_id = data['card_id']
            col = data['col']
            if deck.place_card(card_id, player_id, col):
                emit('card_placed', {
                    'player_id': player_id,
                    'col': col
                }, room=room_code)

        elif action == 'end_turn':
            winner = deck.battle_phase(player_id)
            if winner:
                emit('game_over', {'winner': winner}, room=room_code)
                return

            deck.move_cards(player_id)
            deck.end_turn(player_id)
            deck.turn_stage = 1 if deck.turn_stage == 0 else 0

            # Add new card
            key = f'available_cards_p{player_id}'
            new_card = deck.get_random_card()
            if new_card:
                if not hasattr(deck, key):
                    setattr(deck, key, [])
                getattr(deck, key).append(new_card.id)

        update_game_state(room_code)

    except Exception as e:
        emit('error', {'message': str(e)})


def update_game_state(room_code):
    room = rooms[room_code]
    deck_ = room['deck']

    # Отправка состояния обоим игрокам
    for player_id in [1, 2]:
        state = deck_.get_game_state(player_id)
        emit('game_update', {
            'game_state': state,
            'current_player': deck_.turn_stage + 1
        }, room=f"{room_code}_player{player_id}")

    # Проверка победы
    if deck_.damage_balance >= 10:
        emit('game_over', {'winner': 1}, room=room_code)
    elif deck_.damage_balance <= -10:
        emit('game_over', {'winner': 2}, room=room_code)


def cleanup_empty_rooms():
    now = datetime.now()
    for code, room in list(rooms.items()):
        if (now - room['last_action']).total_seconds() > 3600:  # 1 час бездействия
            del rooms[code]
            if room['host'] in user_rooms:
                del user_rooms[room['host']]
            if room['guest'] and room['guest'] in user_rooms:
                del user_rooms[room['guest']]



@app.route('/choose_mode')
def choose_mode():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('choose_mode.html', username=session.get('username'))


@app.route('/cancel_lobby', methods=['POST'])
def cancel_lobby():
    for code, data in list(rooms.items()):
        if data['host'] == session.get('username'):
            del rooms[code]
    return redirect(url_for('choose_mode'))


@app.route('/play_self')
def play_self():
    return redirect(url_for('play'))

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


@socketio.on('connect')
def handle_connect():
    if 'username' not in session:
        return False
    username = session['username']
    print(f'User {username} connected')
    # Принудительно отправляем текущее состояние при подключении
    if username in user_rooms:
        room_code = user_rooms[username]
        if room_code in rooms:
            update_game_state(room_code)


@socketio.on('disconnect')
def handle_disconnect():
    if 'username' in session:
        username = session['username']
        print(f'User {username} disconnected')
        # Помечаем игрока как отключённого
        if username in user_rooms:
            room_code = user_rooms[username]
            if room_code in rooms:
                room = rooms[room_code]
                if room['state'] == GameStates.PLAYING:
                    emit('player_disconnected', {'username': username}, room=room_code)


@socketio.on('create_room')
def handle_create_room():
    if 'username' not in session:
        return

    username = session['username']
    if username in user_rooms:
        emit('error', {'message': 'Вы уже в лобби'})
        return

    room_code = generate_lobby_code()
    rooms[room_code] = {
        'host': username,
        'guest': None,
        'deck': Deck(db_path),
        'state': GameStates.WAITING,
        'last_action': datetime.now()
    }
    user_rooms[username] = room_code

    # ► Хост сразу присоединяется к двум комнатам:
    join_room(room_code)  # общая
    join_room(f"{room_code}_player1")  # личная

    emit('room_created', {'room': room_code}, to=request.sid)
    emit('lobby_update', {'status': 'Ожидание игрока…', 'code': room_code}, room=room_code)


@socketio.on('/join_room')
def handle_join_room(data):
    room_code = data['room'].upper()
    username = session.get('username')

    if room_code not in rooms:
        emit('error', {'message': 'Лобби не найдено'})
        return

    if rooms[room_code]['guest']:
        emit('error', {'message': 'Лобби заполнено'})
        return

    rooms[room_code]['guest'] = username
    user_rooms[username] = room_code

    join_room(room_code)
    join_room(f"{room_code}_player2")

    emit('game_start', {'room': room_code}, room=room_code)

    update_game_state(room_code)


@socketio.on('game_action')
def handle_game_action(data):
    """Обработка игровых действий"""
    if 'username' not in session:
        emit('error', {'message': 'Не авторизован'})
        return

    username = session['username']
    room_code = data.get('room', '').upper()
    action_type = data.get('type')

    # Проверка валидности комнаты
    if room_code not in rooms:
        emit('error', {'message': 'Комната не найдена'})
        return

    room = rooms[room_code]
    deck = room['deck']

    # Проверка, что пользователь участник комнаты
    if username not in [room['host'], room['guest']]:
        emit('error', {'message': 'Вы не участник этой комнаты'})
        return

    # Определяем ID игрока
    player_id = 1 if username == room['host'] else 2

    # Проверка, что сейчас ход этого игрока
    if deck.turn_stage == 0 and player_id != 1 or deck.turn_stage == 1 and player_id != 2:
        emit('error', {'message': 'Сейчас не ваш ход'})
        return

    # Обработка различных действий
    try:
        if action_type == 'place_card':
            card_id = int(data['card_id'])
            col = int(data['col'])
            success = deck.place_card(card_id, player_id, col)
            if not success:
                emit('error', {'message': 'Невозможно разместить карту'})
                return

        elif action_type == 'end_turn':
            winner = deck.battle_phase(player_id)
            if winner:
                room['state'] = GameStates.FINISHED
                emit('game_over', {'winner': winner})
                return

            deck.move_cards(player_id)
            deck.end_turn(player_id)
            deck.turn_stage = 1 if deck.turn_stage == 0 else 0

            # Добавляем новую карту игроку
            key = f'available_cards_p{player_id}'
            new_card = deck.get_random_card()
            if new_card:
                if not hasattr(deck, key):
                    setattr(deck, key, [])
                getattr(deck, key).append(new_card.id)

        elif action_type == 'attack': # todo доделать
            attacker_row = int(data['attacker_row'])
            attacker_col = int(data['attacker_col'])
            defender_row = int(data['defender_row'])
            defender_col = int(data['defender_col'])

            # Здесь должна быть логика атаки
            # ...

        else:
            emit('error', {'message': 'Неизвестное действие'})
            return

        # Обновляем состояние игры для всех игроков
        room['last_action'] = datetime.now()
        update_game_state(room_code)

    except Exception as e:
        emit('error', {'message': f'Ошибка: {str(e)}'})


@socketio.on('get_game_state')
def handle_get_game_state(data):
    room_code = data['room']
    if room_code not in rooms:
        return

    room = rooms[room_code]
    username = session['username']

    if username == room['host']:
        player_id = 1
    elif username == room['guest']:
        player_id = 2
    else:
        return

    emit('game_state_response', {
        'game_state': room['deck'].get_game_state(player_id),
        'current_player': room['deck'].turn_stage + 1
    })


@socketio.on('leave_room')
def handle_leave_room(data):
    """Покидание комнаты"""
    if 'username' not in session:
        emit('error', {'message': 'Не авторизован'})
        return

    username = session['username']
    room_code = data.get('room', '').upper()

    if room_code not in rooms:
        emit('error', {'message': 'Комната не найдена'})
        return

    room = rooms[room_code]

    if username not in [room['host'], room['guest']]:
        emit('error', {'message': 'Вы не в этой комнате'})
        return

    leave_room(room_code)
    leave_room(f"{room_code}_host")
    leave_room(f"{room_code}_guest")

    # Удаляем пользователя из комнаты
    if username == room['host']:
        room['host'] = None
    else:
        room['guest'] = None

    # Удаляем комнату, если она пуста
    if room['host'] is None and room['guest'] is None:
        del rooms[room_code]
    else:
        # Уведомляем оставшегося игрока
        emit('player_left', {'username': username})

    if username in user_rooms:
        del user_rooms[username]

    emit('left_room', {'room': room_code})


@app.route("/settings")
def settings():
    return "Настройки настраиваются"  # Заглушка


@app.route("/profile")
def profile():
    if "username" not in session:
        return redirect(url_for("login"))
    return f"Профиль игрока {session['username']}"


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

def main() -> None:
    socketio.run(app=app, port=8080, host='127.0.0.1', debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
