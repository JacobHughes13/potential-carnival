from flask import render_template, redirect, url_for, session, request, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
from game.helpers import _init_hands
from game.sockets import *
from game.orm_models import *
from game.deck import Deck


@app.route('/')
def home() -> Response:
    return redirect(url_for('main_menu'))


@app.route("/settings")
def settings() -> Response | str:
    return render_template("settings.html")


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
            return redirect(url_for('register'))

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
    return f"Профиль игрока {username}."


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


@app.route("/invite/<friend_username>")
def invite_friend(friend_username: str) -> Response:
    if 'username' not in session:
        return redirect(url_for('login'))

    host = session['username']
    if host == friend_username:
        flash("Нельзя пригласить себя :)")
        return redirect(url_for('friends'))

    code = generate_lobby_code()
    rooms[code] = {
        'host'            : host,
        'guest'           : None,
        'deck'            : Deck(db_path),
        'state'           : GameStates.WAITING,
        'last_action'     : dt.now(),
        'connected'       : {1: True, 2: False},
        'disconnect_timer': {1: None, 2: None}
    }
    user_rooms[host] = code
    _init_hands(rooms[code]['deck'])

    return redirect(url_for('game',
                            lobby_code=code))


@app.route('/play_self')
def play_self() -> Response:
    return redirect(url_for('play'))


@app.route("/play")
def play() -> Response | str:
    if "user_id" not in session:
        return redirect(url_for('login'))

    current_player: int = session.get('current_player', 1)
    username: str       = session['username']

    hand_key = f'available_cards_p{current_player}'
    deck_hand: list[int] = getattr(deck, hand_key)
    sess_hand: list[int] = session.get(hand_key, [])

    if not sess_hand:
        card = deck.get_random_card()
        if card:
            sess_hand = [card.id]
            session[hand_key] = sess_hand
            deck_hand.clear()
            deck_hand.append(card.id)
    else:
        deck_hand.clear()
        deck_hand.extend(sess_hand)

    cards = [deck.get_card_by_id(cid) for cid in sess_hand]
    game_state = deck.get_game_state(current_player)

    return render_template(
        "index.html",
        cards=cards,
        game_state=game_state,
        current_player=current_player,
        grid=game_state["grid"],
        damage_balance=game_state["damage_balance"],
        coins=deck.coins,
        username=username
    )


@app.route("/pick_up_the_card/<int:card_id>")
def pick_up_the_card(card_id: int) -> Response:
    session['selected_card'] = card_id
    return redirect(url_for("play"))


@app.route("/place_card/<int:row>/<int:col>")
def place_card(row: int, col: int) -> Response:
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
def player1_turn() -> Response:
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
def player2_turn() -> Response:
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
def reset() -> Response:
    deck.reset()
    session['current_player'] = 1
    session.pop('selected_card', None)

    c1 = deck.get_random_card()
    c2 = deck.get_random_card()

    deck.available_cards_p1 = [c1.id] if c1 else []
    deck.available_cards_p2 = [c2.id] if c2 else []

    session['available_cards_p1'] = deck.available_cards_p1.copy()
    session['available_cards_p2'] = deck.available_cards_p2.copy()

    return redirect(url_for("play"))


@app.route('/create_lobby')
def create_lobby() -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    code = generate_lobby_code()
    rooms[code] = {
        'host'            : session['username'],
        'guest'           : None,
        'deck'            : Deck(db_path),
        'state'           : GameStates.WAITING,
        'last_action'     : dt.now(),
        'connected'       : {1: True, 2: False},
        'disconnect_timer': {1: None, 2: None}
    }
    user_rooms[session['username']] = code
    _init_hands(rooms[code]['deck'])

    return render_template('create_lobby.html',
                           lobby_code=code)


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
        flash('Неправильный код комнаты или она заполнена.')

    return render_template('join_lobby.html')


@app.route('/game/<lobby_code>')
def game(lobby_code: str) -> Response | str:
    if 'username' not in session:
        return redirect(url_for('login'))

    if lobby_code not in rooms.keys():
        flash('Лобби не найдено.')
        return redirect(url_for('lobby'))

    room = rooms[lobby_code]
    username = session['username']
    if username not in [room['host'], room['guest']]:
        flash('Вы не находитесь в этом лобби.')
        return redirect(url_for('lobby'))

    player_id = 1 if username == room['host'] else 2
    opponent  = room['host'] if player_id == 2 else room['guest']
    game_state = room['deck'].get_game_state(player_id)
    card_ids = session.get(f'available_cards_p{player_id}', [])
    cards = [deck.get_card_by_id(cid) for cid in card_ids]

    return render_template('game.html',
                           cards=cards,
                           lobby_code=lobby_code,
                           username=username,
                           opponent=opponent,
                           player_id=player_id,
                           game_state=game_state)