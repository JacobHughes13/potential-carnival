import string
from random import choices
from config import rooms
from flask_socketio import emit
import time
from datetime import datetime as dt
from game.deck import Deck


def generate_lobby_code() -> str:
    return ''.join(choices(string.ascii_uppercase + string.digits, k=6))


def _init_hands(d: Deck) -> None:
    d.available_cards_p1 = [d.get_random_card().id]
    d.available_cards_p2 = [d.get_random_card().id]


def update_game_state(room_code: str) -> None:
    room = rooms[room_code]
    deck_ = room['deck']
    for pid in (1, 2):
        state = deck_.get_game_state(pid)
        emit('game_update',
             {
                 'game_state': state,
                 'current_player': deck_.turn_stage + 1
             },
             room=f"{room_code}_player{pid}")

    if deck_.damage_balance >= 10:
        emit('game_over',
             {'winner': 1},
             room=room_code)

    elif deck_.damage_balance <= -10:
        emit('game_over',
             {'winner': 2},
             room=room_code)

def disconnect_watcher() -> None:
    while True:
        now = dt.now()
        for code, room in list(rooms.items()):
            for pid in (1, 2):
                ts = room['disconnect_timer'].get(pid)
                if ts and (now - ts).total_seconds() > 60:
                    if pid == 1:
                        room['host'] = None
                    else:
                        room['guest'] = None
                    room['disconnect_timer'][pid] = None
                    room['connected'][pid] = False

                    emit('player_left',
                         {'username': 'Игрок'},
                         room=code)

            if room['host'] is None and room['guest'] is None:
                rooms.pop(code, None)
        time.sleep(5)