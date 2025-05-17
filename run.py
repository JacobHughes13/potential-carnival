from game.routes import *
from threading import Thread


def main() -> None:
    Thread(target=disconnect_watcher, daemon=True).start()
    # socketio.run(app=app)
    socketio.run(app=app, host='127.0.0.1', port=8080, debug=True, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()