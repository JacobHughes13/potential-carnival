from flask_socketio import SocketIO
from flask import Flask
import os
from game.deck import Deck
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())
socketio = SocketIO(app, cors_allowed_origins="*")
db_path   = 'sqlite:///data/BD.db'
deck      = Deck(db_path)
engine    = create_engine(db_path)
Session   = sessionmaker(bind=engine)
db_session = Session()

rooms      = {}   # {code: {host, guest, deck, state, last_action}}
user_rooms = {}   # {username: room_code}


class GameStates:
    WAITING  = "waiting"
    PLAYING  = "playing"
    FINISHED = "finished"