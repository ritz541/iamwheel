from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from datetime import datetime, timedelta
import bcrypt
import os
from dotenv import load_dotenv
from bson import ObjectId
import random
import threading
import time
import uuid

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=1)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['wheel_game']

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Socket.IO setup
socketio = SocketIO(app)

# Game state
class GameState:
    def __init__(self):
        self.players = []
        self.is_joining_phase = True
        self.timer = 300  # 5 minutes in seconds
        self.timer_thread = None
        self.lock = threading.Lock()

    def reset(self):
        self.players = []
        self.is_joining_phase = True
        self.timer = 300

game_state = GameState()

class User(UserMixin):
    def __init__(self, user_data):
        self.user_data = user_data
        self.id = str(user_data['_id'])
        
    def get_id(self):
        return str(self.user_data['_id'])

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = db.users.find_one({'_id': ObjectId(user_id)})
        return User(user_data) if user_data else None
    except:
        return None

# Timer function
def countdown_timer():
    while game_state.timer > 0 and game_state.is_joining_phase:
        socketio.emit('countdown', {'time': game_state.timer})
        time.sleep(1)
        with game_state.lock:
            game_state.timer -= 1

    if game_state.timer <= 0:
        end_game()

def end_game():
    with game_state.lock:
        game_state.is_joining_phase = False
        
        if len(game_state.players) <= 1:
            # Refund if only one or no players
            for player in game_state.players:
                refund_amount = 10  # Entry fee
                db.users.update_one(
                    {'_id': ObjectId(player['id'])},
                    {'$inc': {'wallet_balance': refund_amount}}
                )
            socketio.emit('game_status', {
                'message': 'Game cancelled - Not enough players',
                'canJoin': True
            })
        else:
            # Select winner and distribute prize
            total_prize = len(game_state.players) * 10
            winner_prize = int(total_prize * 0.8)  # 80% of total prize pool
            
            winner = random.choice(game_state.players)
            degrees = random.randint(720, 1440) + (360 / len(game_state.players)) * game_state.players.index(winner)
            
            # Update winner's wallet
            db.users.update_one(
                {'_id': ObjectId(winner['id'])},
                {'$inc': {'wallet_balance': winner_prize}}
            )
            
            # Emit spin wheel event
            socketio.emit('spin_wheel', {
                'degrees': degrees,
                'winner': {
                    'username': winner['username'],
                    'prize': winner_prize
                }
            })

        # Reset game state after delay
        time.sleep(6)  # Wait for wheel animation
        game_state.reset()
        start_new_game()

def start_new_game():
    game_state.reset()
    game_state.timer_thread = threading.Thread(target=countdown_timer)
    game_state.timer_thread.daemon = True
    game_state.timer_thread.start()
    
    socketio.emit('game_status', {
        'message': 'New game starting! Join now!',
        'canJoin': True
    })

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    emit('game_status', {
        'message': 'Waiting for players...',
        'canJoin': game_state.is_joining_phase
    })
    emit('players_update', {'players': game_state.players})
    emit('countdown', {'time': game_state.timer})

@socketio.on('join_game')
@login_required
def handle_join_game():
    if not game_state.is_joining_phase:
        emit('game_status', {
            'message': 'Cannot join now, wait for next game',
            'canJoin': False
        })
        return

    # Check if player has enough balance
    user_data = db.users.find_one({'_id': ObjectId(current_user.id)})
    if user_data['wallet_balance'] < 10:
        emit('game_status', {
            'message': 'Insufficient balance',
            'canJoin': False
        })
        return

    # Check if player already joined
    if any(p['id'] == current_user.id for p in game_state.players):
        emit('game_status', {
            'message': 'You already joined this game',
            'canJoin': False
        })
        return

    # Deduct entry fee and add player
    db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$inc': {'wallet_balance': -10}}
    )

    with game_state.lock:
        game_state.players.append({
            'id': current_user.id,
            'username': current_user.user_data['username']
        })

    socketio.emit('players_update', {'players': game_state.players})
    socketio.emit('game_status', {
        'message': f'{len(game_state.players)} players joined',
        'canJoin': True
    })

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        if db.users.find_one({'$or': [{'username': username}, {'phone': phone}]}):
            flash('Username or phone number already exists')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        user_data = {
            'username': username,
            'phone': phone,
            'password': hashed_password,
            'wallet_balance': 0,
            'created_at': datetime.utcnow()
        }
        
        result = db.users.insert_one(user_data)
        user_data['_id'] = result.inserted_id
        
        user = User(user_data)
        login_user(user)
        flash('Registration successful!')
        return redirect(url_for('game'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        user_data = db.users.find_one({'phone': phone})
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password']):
            user = User(user_data)
            session.permanent = True
            login_user(user)
            return redirect(url_for('game'))
        
        flash('Invalid phone number or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/game')
@login_required
def game():
    return render_template('game.html')

@app.route('/wallet')
@login_required
def wallet():
    # Get user's transactions
    transactions = list(db.transactions.find(
        {'user_id': ObjectId(current_user.id)}
    ).sort('created_at', -1))
    
    # Add status color for badges
    for transaction in transactions:
        if transaction['status'] == 'completed':
            transaction['status_color'] = 'success'
        elif transaction['status'] == 'pending':
            transaction['status_color'] = 'warning'
        else:
            transaction['status_color'] = 'danger'
    
    return render_template('wallet.html', transactions=transactions)

@app.route('/request_deposit', methods=['POST'])
@login_required
def request_deposit():
    amount = int(request.form.get('amount', 0))
    
    # Validate amount
    if amount < 20 or amount > 1000:
        flash('Invalid deposit amount. Must be between ₹20 and ₹1000')
        return redirect(url_for('wallet'))
    
    # Create transaction record
    transaction = {
        'user_id': ObjectId(current_user.id),
        'type': 'deposit',
        'amount': amount,
        'status': 'pending',
        'created_at': datetime.utcnow(),
        'transaction_id': str(uuid.uuid4()),
        'username': current_user.user_data['username']
    }
    
    db.transactions.insert_one(transaction)
    flash('Deposit request submitted successfully! Admin will verify and update your balance.')
    return redirect(url_for('wallet'))

@app.route('/request_withdrawal', methods=['POST'])
@login_required
def request_withdrawal():
    amount = int(request.form.get('amount', 0))
    bank_account = request.form.get('bank_account')
    ifsc_code = request.form.get('ifsc_code')
    account_holder = request.form.get('account_holder')
    
    # Validate amount
    if amount < 50 or amount > 500:
        flash('Invalid withdrawal amount. Must be between ₹50 and ₹500')
        return redirect(url_for('wallet'))
    
    # Check if user has sufficient balance
    if current_user.user_data['wallet_balance'] < amount:
        flash('Insufficient balance')
        return redirect(url_for('wallet'))
    
    # Create transaction record
    transaction = {
        'user_id': ObjectId(current_user.id),
        'type': 'withdrawal',
        'amount': amount,
        'status': 'pending',
        'created_at': datetime.utcnow(),
        'transaction_id': str(uuid.uuid4()),
        'username': current_user.user_data['username'],
        'bank_details': {
            'account_number': bank_account,
            'ifsc_code': ifsc_code,
            'account_holder': account_holder
        }
    }
    
    # Deduct amount from wallet immediately for withdrawal
    db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$inc': {'wallet_balance': -amount}}
    )
    
    db.transactions.insert_one(transaction)
    flash('Withdrawal request submitted successfully!')
    return redirect(url_for('wallet'))

if __name__ == '__main__':
    start_new_game()
    socketio.run(app, debug=True)
