from flask import Flask, render_template, redirect, url_for, session, request, flash, Response
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from random import choices, randint
import string, os
from datetime import datetime
from deck import Deck, User, Friend, Card, SqlAlchemyBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*")

deck      = Deck('sqlite:///BD/BD.db')
db_path   = 'sqlite:///BD/BD.db'
engine    = create_engine(db_path)
Session   = sessionmaker(bind=engine)
db_session = Session()

rooms      = {}   # {code: {host, guest, deck, state, last_action}}
user_rooms = {}   # {username: room_code}


class GameStates:
    WAITING  = "waiting"
    PLAYING  = "playing"
    FINISHED = "finished"


def generate_lobby_code() -> str:
    return ''.join(choices(string.ascii_uppercase + string.digits, k=6))


def update_game_state(room_code: str) -> None:
    room = rooms[room_code]
    deck_ = room['deck']
    for pid in (1, 2):
        state = deck_.get_game_state(pid)
        emit('game_update',
             {'game_state': state, 'current_player': deck_.turn_stage + 1},
             room=f"{room_code}_player{pid}")

    if deck_.damage_balance >= 10:
        emit('game_over',
             {'winner': 1},
             room=room_code)

    elif deck_.damage_balance <= -10:
        emit('game_over',
             {'winner': 2},
             room=room_code)


@app.route('/')
def home() -> Response:
    return redirect(url_for('main_menu'))


@app.route("/settings")
def settings() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    return "Настройки настраиваются"  # Заглушка


@app.route('/login', methods=['GET', 'POST'])
def login() -> Response | str:
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        sess = db_session
        user = sess.query(User).filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id']  = user.id
            session['username'] = user.username
            return redirect(url_for('main_menu'))
        flash('Неверные имя пользователя или пароль!')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register() -> Response | str:
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password = generate_password_hash(password)
        sess = db_session
        if sess.query(User).filter_by(username=username).first():
            flash('Пользователь уже существует!')
            # return redirect(url_for('register'))
        sess.add(User(username=username,
                      password=password))
        sess.commit()
        flash('Регистрация прошла успешно!')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route("/logout")
def logout() -> Response:
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('current_player', None)
    session.pop('selected_card', None)
    session.pop('available_cards_p1', None)
    session.pop('available_cards_p2', None)
    return redirect(url_for("login"))


@app.route('/main_menu')
def main_menu() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    return render_template('main_menu.html',
                           username=username)


@app.route('/choose_mode')
def choose_mode() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session.get('username')
    return render_template('choose_mode.html',
                           username=username)


@app.route("/profile")
def profile() -> Response | str:
    if "username" not in session:
        return redirect(url_for("login"))

    username = session['username']
    return f"Профиль игрока {username}"


@app.route("/friends", methods=["GET", "POST"])
def friends() -> Response | str:
    if 'user_id' not in session:
        return redirect(url_for("login"))

    sess = deck.Session()
    user_id = session['user_id']

    if request.method == "POST":
        friend_username = request.form["friend_username"]
        friend = sess.query(User).filter_by(username=friend_username).first()
        if friend and friend.id != user_id:
            existing = sess.query(Friend).filter_by(user_id=user_id, friend_id=friend.id).first()
            if not existing:
                new_friend = Friend(user_id=user_id, friend_id=friend.id)
                sess.add(new_friend)
                sess.commit()

    friends_list = sess.query(User.username).join(
        Friend, User.id == Friend.friend_id
    ).filter(Friend.user_id == user_id).all()
    sess.close()

    return render_template("friends.html",
                           friends=friends_list)


@app.route('/play_self')
def play_self() -> Response:
    return redirect(url_for('play'))


@app.route("/play")
def play() -> Response | str:
    if "user_id" not in session:
        return redirect(url_for('login'))

    current_player = session.get('current_player', 1)
    username = session.get('username')
    card_ids = session.get(f'available_cards_p{current_player}', [])
    cards = [deck.get_card_by_id(cid) for cid in card_ids]

    return render_template("index.html",
                           cards=cards,
                           grid=deck.grid,
                           current_player=current_player,
                           damage_balance=deck.damage_balance,
                           coins=deck.coins,
                           username=username)


@app.route('/lobby')
def lobby() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    return render_template('lobby.html',
                           username=username)


@app.route('/create_lobby')
def create_lobby() -> Response | str:
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


@app.route('/cancel_lobby', methods=['POST'])
def cancel_lobby() -> Response:
    for code, data in list(rooms.items()):
        if data['host'] == session.get('username'):
            del rooms[code]
    return redirect(url_for('choose_mode'))


@app.route('/join_lobby', methods=['GET', 'POST'])
def join_lobby() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('lobby_code', '').upper()
        if code in rooms and rooms[code]['guest'] is None:
            rooms[code]['guest'] = session['username']
            user_rooms[session['username']] = code
            return redirect(url_for('game', lobby_code=code))
        flash('Неправильный код комнаты или она заполнена')

    # GET-запрос просто отрисовывает страницу
    return render_template('join_lobby.html')


@app.route('/game/<lobby_code>')
def game(lobby_code: str) -> Response | str:
    # print(2)
    # print(session)
    # if 'username' not in session:
    #     print(3)
    #     return redirect(url_for('login'))
    if lobby_code not in rooms.keys():
        flash('Лобби не найдено.')
        print(4, lobby_code, rooms.keys())
        return redirect(url_for('lobby'))
    room = rooms[lobby_code]
    username = session['username']
    print(room['host'], room['guest'])
    if username not in [room['host'], room['guest']]:
        flash('You are not in this lobby')
        return redirect(url_for('lobby'))

    player_id = 1 if username == room['host'] else 2
    opponent  = room['host'] if player_id == 2 else room['guest']
    game_state = room['deck'].get_game_state(player_id)

    return render_template('game.html',
                           lobby_code=lobby_code,
                           username=username,
                           opponent=opponent,
                           player_id=player_id,
                           game_state=game_state)


@socketio.on('connect')
def handle_connect() -> None:
    if 'username' not in session:
        return

    username = session['username']
    if username in user_rooms:
        room_code = user_rooms[username]
        if room_code in rooms:
            join_room(room_code)
            pid = 1 if rooms[room_code]['host'] == username else 2
            join_room(f"{room_code}_player{pid}")
            update_game_state(room_code)
    print(f'Пользователь {username} подключился.')


@socketio.on('disconnect')
def handle_disconnect() -> None:
    username = session.get('username')
    if not username:
        return

    print(f'Пользователь {username} временно отключился.')

    if username in user_rooms:
        room_code = user_rooms[username]
        room = rooms.get(room_code)
        if room:
            room['last_action'] = datetime.now()


@socketio.on('create_room')
def handle_create_room() -> None:
    if 'username' not in session:
        return

    username = session['username']
    if username in user_rooms:
        emit('error',
             {'message': 'Вы уже в лобби'})
        return

    room_code = generate_lobby_code()
    rooms[room_code] = {
        'host'       : username,
        'guest'      : None,
        'deck'       : Deck(db_path),
        'state'      : GameStates.WAITING,
        'last_action': datetime.now()
    }
    user_rooms[username] = room_code
    join_room(room_code)
    join_room(f"{room_code}_player1")
    emit('room_created',
         {'room': room_code},
         to=request.sid)


@socketio.on('join_room')
def handle_join_room(data) -> None:
    room_code = data.get('room', '').upper()
    username = session.get('username')

    if not username:
        emit('error',
             {'message': 'Требуется авторизация'})
        return

    if room_code not in rooms:
        emit('error',
             {'message': 'Лобби не найдено'},
             to=request.sid)
        return

    room = rooms[room_code]

    if room['guest']:
        emit('error',
             {'message': 'Лобби заполнено'},
             to=request.sid)
        return

    room['guest'] = username
    user_rooms[username] = room_code

    join_room(room_code)
    join_room(f"{room_code}_player2")

    emit('game_start',
         {'room': room_code},
         room=room_code)

    emit('room_update', {
        'host': room['host'],
        'guest': room['guest'],
        'status': 'ready'
    }, room=room_code)

    emit('redirect',
         {'url': f'/game/{room_code}'},
         to=request.sid)

    update_game_state(room_code)


@socketio.on('game_action')
def handle_game_action(data) -> None:
    if 'username' not in session:
        emit('error',
             {'message': 'Не авторизован'})
        return

    username   = session['username']
    room_code  = data.get('room', '').upper()
    action_type = data.get('type')
    if room_code not in rooms:
        emit('error',
             {'message': 'Комната не найдена'})
        return

    room = rooms[room_code]
    deck = room['deck']
    if username not in [room['host'], room['guest']]:
        emit('error',
             {'message': 'Вы не участник этой комнаты'})
        return

    player_id = 1 if username == room['host'] else 2
    if deck.turn_stage == 0 and player_id != 1 or deck.turn_stage == 1 and player_id != 2:
        emit('error',
             {'message': 'Сейчас не ваш ход'})
        return

    try:
        if action_type == 'place_card':
            if not deck.place_card(int(data['card_id']), player_id, int(data['col'])):
                emit('error',
                     {'message': 'Невозможно разместить карту'})
                return

        elif action_type == 'end_turn':
            winner = deck.battle_phase(player_id)
            if winner:
                room['state'] = GameStates.FINISHED
                emit('game_over',
                     {'winner': winner},
                     room=room_code)
                return

            deck.move_cards(player_id)
            deck.end_turn(player_id)
            deck.turn_stage = 1 if deck.turn_stage == 0 else 0
            key      = f'available_cards_p{player_id}'
            new_card = deck.get_random_card()
            if new_card:
                getattr(deck, key, []).append(new_card.id)
        else:
            emit('error',
                 {'message': 'Неизвестное действие'})
            return

        room['last_action'] = datetime.now()
        update_game_state(room_code)
    except Exception as e:
        emit('error',
             {'message': f'Ошибка: {str(e)}'})


@socketio.on('get_game_state')
def handle_get_game_state(data) -> None:
    room_code = data.get('room', '').upper()
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

    emit('game_state_response',
         {
             'game_state'    : room['deck'].get_game_state(player_id),
             'current_player': room['deck'].turn_stage + 1
         })


@socketio.on('leave_room')
def handle_leave_room(data) -> None:
    if 'username' not in session:
        emit('error',
             {'message': 'Не авторизован'})
        return

    username  = session['username']
    room_code = data.get('room', '').upper()
    if room_code not in rooms:
        emit('error',
             {'message': 'Комната не найдена'})
        return

    room = rooms[room_code]
    if username not in [room['host'], room['guest']]:
        emit('error',
             {'message': 'Вы не в этой комнате'})
        return

    leave_room(room_code)
    leave_room(f"{room_code}_player1")
    leave_room(f"{room_code}_player2")

    if username == room['host']:
        room['host'] = None
    else:
        room['guest'] = None

    if room['host'] is None and room['guest'] is None:
        del rooms[room_code]
    else:
        emit('player_left',
             {'username': username}, room=room_code)

    user_rooms.pop(username, None)
    emit('left_room',
         {'room': room_code},
         to=request.sid)


def main() -> None:
    socketio.run(app=app, host='127.0.0.1', port=8080,
                 debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()