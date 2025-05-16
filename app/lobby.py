from random import choices
import string


def generate_lobby_code(k: int = 6) -> str:
    return "".join(choices(string.ascii_uppercase + string.digits, k=k))


class GameStates:
    WAITING  = "waiting"
    PLAYING  = "playing"
    FINISHED = "finished"


rooms: dict[str, dict] = {}        # runtime-состояния лобби
user_rooms: dict[str, str] = {}    # username -> lobby_code