from flask import Flask
from flask_socketio import SocketIO
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import SECRET_KEY, DB_URI

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

socketio = SocketIO(app, cors_allowed_origins="*")

# единая точка доступа к DB-сессиям для HTTP-роутов и сокетов
engine = create_engine(DB_URI, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# регистрируем модули, чтобы их декораторы выполнились
from . import routes, sockets  # noqa: E402, F401