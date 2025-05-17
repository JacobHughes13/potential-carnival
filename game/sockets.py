from flask_socketio import join_room, leave_room
from flask import session, request
from config import *
from game.helpers import *
from datetime import datetime as dt


@socketio.on('send_invite')
def send_invite(data):
    friend = data['friend']
    code   = data['room']

    emit('receive_invite',
         {'room': code, 'host': session['username']},
         room=friend)

@socketio.on('connect')
def handle_connect() -> None:
    username = session.get('username')
    if not username or username not in user_rooms:
        return

    room_code = user_rooms[username]
    if room_code not in rooms:
        return

    room = rooms[room_code]
    pid  = 1 if room['host'] == username else 2

    room['connected'][pid] = True
    room['disconnect_timer'][pid] = None

    join_room(room_code)
    join_room(f"{room_code}_player{pid}")

    update_game_state(room_code)


@socketio.on('disconnect')
def handle_disconnect() -> None:
    username = session.get('username')
    if not username or username not in user_rooms:
        return

    room_code = user_rooms[username]
    room = rooms.get(room_code)
    if not room:
        return

    pid = 1 if room['host'] == username else 2
    room['connected'][pid] = False
    room['disconnect_timer'][pid] = dt.now()


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
        'host'            : username,
        'guest'           : None,
        'deck'            : Deck(db_path),
        'state'           : GameStates.WAITING,
        'last_action'     : dt.now(),
        'connected'       : {1: True, 2: False},
        'disconnect_timer': {1: None, 2: None}
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

    username = session['username']
    room_code = data.get('room', '').upper()
    action_type = data.get('action')

    if room_code not in rooms:
        emit('error',
             {'message': 'Комната не найдена'})
        return

    room = rooms[room_code]
    deck_ = room['deck']
    room_members = (room['host'], room['guest'])

    if username not in room_members:
        emit('error',
             {'message': 'Вы не участник этой комнаты'})
        return

    player_id = 1 if username == room['host'] else 2
    if (deck_.turn_stage == 0 and player_id != 1) or (deck_.turn_stage == 1 and player_id != 2):
        emit('error',
             {'message': 'Сейчас не ваш ход'})
        return

    try:
        if action_type == 'place_card':
            if not deck_.place_card(int(data['card_id']), player_id, int(data['col'])):
                emit('error',
                     {'message': 'Невозможно разместить карту'})
                return

        elif action_type == 'end_turn':
            winner = deck_.battle_phase(player_id)
            if winner:
                room['state'] = GameStates.FINISHED
                emit('game_over',
                     {'winner': winner},
                     room=room_code)
                return

            deck_.move_cards(player_id)
            deck_.end_turn(player_id)

            deck_.turn_stage = 1 if deck_.turn_stage == 0 else 0

        elif action_type == 'attack':
            winner = deck_.battle_phase(player_id)
            if winner:
                room['state'] = GameStates.FINISHED
                emit('game_over',
                     {'winner': winner},
                     room=room_code)
                return

        elif action_type == 'surrender':
            room['state'] = GameStates.FINISHED
            emit('game_over',
                 {'winner': 2 if player_id == 1 else 1},
                 room=room_code)
            return

        else:
            emit('error',
                 {'message': 'Неизвестное действие'})
            return

        room['last_action'] = dt.now()
        update_game_state(room_code)

    except Exception as e:
        emit('error', {'message': f'Ошибка: {str(e)}'})


@socketio.on('join_game')
def handle_join_game(data) -> None:
    lobby_code = data.get('lobby_code', '').upper()
    username = session.get('username')
    player_id = data.get('player_id')

    if not (username and lobby_code in rooms):
        emit('error',
             {'message': 'Лобби не найдено'})
        return

    join_room(lobby_code)
    join_room(f"{lobby_code}_player{player_id}")

    rooms[lobby_code]['connected'][player_id] = True
    rooms[lobby_code]['last_action'] = dt.now()

    update_game_state(lobby_code)


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