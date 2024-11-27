from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import bcrypt
import os
from dotenv import load_dotenv
from bson import ObjectId
import random
import threading
import time
import uuid
import json
import redis
from functools import wraps
from flask_session import Session
from flask_cors import CORS
import pickle

# Load environment variables
load_dotenv()

# Flask setup
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'  # Fallback to filesystem if Redis is not available

# Redis connection with error handling
try:
    # Main Redis client for sessions (no decode_responses for session data)
    redis_client = redis.Redis(
        host='localhost', 
        port=6379, 
        db=0, 
        socket_timeout=2,
        retry_on_timeout=True
    )
    redis_client.ping()  # Test connection
    
    # Redis clients for other purposes (with decode_responses)
    redis_rate_limit = redis.Redis(
        host='localhost', 
        port=6379, 
        db=1, 
        decode_responses=True,
        retry_on_timeout=True
    )
    redis_game = redis.Redis(
        host='localhost', 
        port=6379, 
        db=2, 
        decode_responses=True,
        retry_on_timeout=True
    )
    
    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_REDIS'] = redis_client
    REDIS_AVAILABLE = True
    
except (redis.ConnectionError, redis.RedisError) as e:
    app.logger.warning(f"Redis not available: {str(e)}. Falling back to filesystem session.")
    REDIS_AVAILABLE = False
    redis_client = None
    redis_rate_limit = None
    redis_game = None

# Enable CORS
CORS(app)

# MongoDB setup
try:
    client = MongoClient('mongodb://localhost:27017/')
    db = client['wheel_game']
    # Test connection
    db.command('ping')
except Exception as e:
    app.logger.error(f"MongoDB connection failed: {str(e)}")
    raise

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, timezone)):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        return super().default(obj)

def json_dumps(obj):
    return json.dumps(obj, cls=DateTimeEncoder)

# Initialize Flask-Session
Session(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Rate limiting decorator with fallback
def rate_limit(limit=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not REDIS_AVAILABLE:
                return f(*args, **kwargs)  # Skip rate limiting if Redis is down
                
            if current_user.is_authenticated:
                key = f"rate_limit:{current_user.id}:{request.endpoint}"
                try:
                    current = redis_rate_limit.get(key)
                    if current is None:
                        redis_rate_limit.setex(key, window, 1)
                    elif int(current) >= limit:
                        return jsonify({'error': 'Rate limit exceeded'}), 429
                    else:
                        redis_rate_limit.incr(key)
                except redis.RedisError as e:
                    app.logger.error(f"Rate limiting failed: {str(e)}")
                    return f(*args, **kwargs)  # Continue without rate limiting
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Game state management with fallback to MongoDB
class GameState:
    def __init__(self):
        self.game_key = "current_game"
        self.reset_game()
    
    def reset_game(self):
        game_data = {
            'status': 'joining',
            'players': [],
            'timer': 300,
            'game_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc)
        }
        
        # Always store in MongoDB for persistence
        db.game_history.insert_one(game_data)
        
        if REDIS_AVAILABLE:
            try:
                # Store temporary game state in Redis with 5-minute expiry
                redis_game.setex(self.game_key, 300, json_dumps(game_data))
            except redis.RedisError as e:
                app.logger.error(f"Redis game state storage failed: {str(e)}")
    
    def get_game_state(self):
        if REDIS_AVAILABLE:
            try:
                state = redis_game.get(self.game_key)
                if state:
                    return json.loads(state)
            except redis.RedisError as e:
                app.logger.error(f"Redis game state retrieval failed: {str(e)}")
        
        # Fallback to MongoDB
        state = db.game_history.find_one({}, sort=[('created_at', -1)])
        if state:
            # Convert ObjectId to string for JSON serialization
            state['_id'] = str(state['_id'])
        return state or {'status': 'error'}

    def update_game_state(self, updates):
        # Update MongoDB first for persistence
        current = self.get_game_state()
        current.update(updates)
        
        # Remove _id before updating MongoDB
        if '_id' in current:
            del current['_id']
            
        db.game_history.update_one(
            {'game_id': current['game_id']},
            {'$set': updates}
        )
        
        if REDIS_AVAILABLE:
            try:
                redis_game.setex(self.game_key, 300, json_dumps(current))
            except redis.RedisError as e:
                app.logger.error(f"Redis game state update failed: {str(e)}")

# Socket.IO setup with Redis if available
if REDIS_AVAILABLE:
    socketio = SocketIO(
        app,
        message_queue='redis://localhost:6379/3',
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True
    )
else:
    socketio = SocketIO(app, cors_allowed_origins="*")

# Rate limiting decorator with fallback
def rate_limit(limit=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not REDIS_AVAILABLE:
                return f(*args, **kwargs)  # Skip rate limiting if Redis is down
                
            if current_user.is_authenticated:
                key = f"rate_limit:{current_user.id}:{request.endpoint}"
                try:
                    current = redis_rate_limit.get(key)
                    if current is None:
                        redis_rate_limit.setex(key, window, 1)
                    elif int(current) >= limit:
                        return jsonify({'error': 'Rate limit exceeded'}), 429
                    else:
                        redis_rate_limit.incr(key)
                except redis.RedisError as e:
                    app.logger.error(f"Rate limiting failed: {str(e)}")
                    return f(*args, **kwargs)  # Continue without rate limiting
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Game state management with fallback to MongoDB
class GameState:
    def __init__(self):
        self.game_key = "current_game"
        self.reset_game()
    
    def reset_game(self):
        game_data = {
            'status': 'joining',
            'players': [],
            'timer': 300,
            'game_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc)
        }
        
        # Always store in MongoDB for persistence
        db.game_history.insert_one(game_data)
        
        if REDIS_AVAILABLE:
            try:
                # Store temporary game state in Redis with 5-minute expiry
                redis_game.setex(self.game_key, 300, json_dumps(game_data))
            except redis.RedisError as e:
                app.logger.error(f"Redis game state storage failed: {str(e)}")
    
    def get_game_state(self):
        if REDIS_AVAILABLE:
            try:
                state = redis_game.get(self.game_key)
                if state:
                    return json.loads(state)
            except redis.RedisError as e:
                app.logger.error(f"Redis game state retrieval failed: {str(e)}")
        
        # Fallback to MongoDB
        state = db.game_history.find_one({}, sort=[('created_at', -1)])
        if state:
            # Convert ObjectId to string for JSON serialization
            state['_id'] = str(state['_id'])
        return state or {'status': 'error'}

    def update_game_state(self, updates):
        # Update MongoDB first for persistence
        current = self.get_game_state()
        current.update(updates)
        
        # Remove _id before updating MongoDB
        if '_id' in current:
            del current['_id']
            
        db.game_history.update_one(
            {'game_id': current['game_id']},
            {'$set': updates}
        )
        
        if REDIS_AVAILABLE:
            try:
                redis_game.setex(self.game_key, 300, json_dumps(current))
            except redis.RedisError as e:
                app.logger.error(f"Redis game state update failed: {str(e)}")

# Socket.IO setup with Redis if available
if REDIS_AVAILABLE:
    socketio = SocketIO(
        app,
        message_queue='redis://localhost:6379/3',
        cors_allowed_origins="*",
        logger=True,
        engineio_logger=True
    )
else:
    socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('place_bet')
@rate_limit(limit=5, window=10)  # Limit to 5 bets per 10 seconds
def handle_bet(data):
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}
        
    # Process bet logic here
    emit('bet_placed', {'user': current_user.id, 'amount': data.get('amount')}, broadcast=True)

@socketio.on('spin_wheel')
@rate_limit(limit=1, window=5)  # Limit to 1 spin per 5 seconds
def handle_spin(data):
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}
        
    # Process spin logic here
    result = random.randint(0, 36)
    emit('wheel_result', {'result': result}, broadcast=True)

# Example of rate-limited API endpoint
@app.route('/api/place_bet', methods=['POST'])
@login_required
@rate_limit(limit=5, window=10)
def place_bet():
    # Bet processing logic here
    return jsonify({'success': True})

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        self._load_user_data()

    def _load_user_data(self):
        # Load user data directly from MongoDB
        user_data = db.users.find_one({'_id': ObjectId(self.id)})
        self.user_data = user_data if user_data else {}

    @property
    def is_active(self):
        return not self.user_data.get('is_blocked', False)

    @staticmethod
    def get(user_id):
        if not user_id:
            return None
        return User(user_id)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

def update_game_timer():
    while True:
        try:
            with app.app_context():
                game_data = game_state.get_game_state()
                
                if game_data.get('status') == 'joining':
                    if game_data.get('timer', 0) > 0:
                        game_state.update_game_state({'timer': game_data['timer'] - 1})
                        socketio.emit('timer', {'time': game_data['timer'] - 1})
                        
                        if game_data['timer'] <= 1:
                            players = game_data.get('players', [])
                            if players:
                                winner_idx = random.randint(0, len(players) - 1)
                                winner = players[winner_idx]
                                
                                # Calculate prize
                                total_pool = len(players) * 10
                                winner_prize = int(total_pool * 0.8)
                                
                                # Update winner's wallet
                                db.users.update_one(
                                    {'username': winner['username']},
                                    {'$inc': {'wallet_balance': winner_prize}}
                                )
                                
                                # Record game in database
                                db.games.insert_one({
                                    'players': players,
                                    'winner': winner['username'],
                                    'total_pool': total_pool,
                                    'winner_prize': winner_prize,
                                    'platform_fee': total_pool - winner_prize,
                                    'created_at': datetime.now(),
                                    'status': 'completed',
                                    'game_id': game_data.get('game_id')
                                })
                                
                                socketio.emit('game_end', {
                                    'winner': winner['username'],
                                    'prize': winner_prize
                                })
                            else:
                                socketio.emit('game_end', {'winner': None})
                            
                            # Reset game state
                            game_state.reset_game()
                            
                            # Notify all clients of new game state
                            new_state = game_state.get_game_state()
                            socketio.emit('game_status', {
                                'status': new_state['status'],
                                'players': new_state['players'],
                                'timer': new_state['timer']
                            })
            
            socketio.sleep(1)
        except Exception as e:
            print(f"Timer error: {str(e)}")
            socketio.sleep(1)

# Start timer thread
timer_thread = None

@socketio.on('connect')
def handle_connect():
    global timer_thread
    
    if timer_thread is None or not timer_thread.is_alive():
        timer_thread = socketio.start_background_task(update_game_timer)
    
    game_data = game_state.get_game_state()
    emit('game_status', {
        'status': game_data['status'],
        'players': game_data['players'],
        'timer': game_data['timer']
    })

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_game')
def handle_join_game():
    if not current_user.is_authenticated:
        emit('join_game_response', {'success': False, 'message': 'Please login first'})
        return

    game_data = game_state.get_game_state()
    
    # Check if player already joined
    if any(p['id'] == str(current_user.id) for p in game_data.get('players', [])):
        emit('join_game_response', {'success': False, 'message': 'Already joined the game'})
        return

    # Check wallet balance
    if current_user.user_data.get('wallet_balance', 0) < 10:
        emit('join_game_response', {'success': False, 'message': 'Insufficient balance'})
        return

    # Add player to game
    player_info = {
        'id': str(current_user.id),
        'username': current_user.user_data['username']
    }
    game_state.update_game_state({'players': game_data.get('players', []) + [player_info]})

    # Deduct entry fee
    db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$inc': {'wallet_balance': -10}}
    )

    # Get updated game state
    updated_game_data = game_state.get_game_state()

    # Notify all clients
    socketio.emit('game_status', {
        'status': updated_game_data['status'],
        'players': updated_game_data['players'],
        'timer': updated_game_data['timer']
    })

    socketio.emit('player_joined', {
        'success': True,
        'message': 'Successfully joined the game',
        'players': updated_game_data['players'],
        'player_count': len(updated_game_data['players'])
    })

    # Show wheel for first player
    if len(updated_game_data['players']) == 1:
        socketio.emit('show_wheel')

    emit('join_game_response', {'success': True, 'message': 'Successfully joined the game'})

# Socket.IO error handling
@socketio.on_error_default
def default_error_handler(e):
    print(f'SocketIO Error: {str(e)}')
    socketio.emit('error', {'message': 'An error occurred'})

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
        
        if db.users.find_one({'phone': phone}):
            flash('Phone number already registered')
            return redirect(url_for('register'))
        
        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user document
        user = {
            'username': username,
            'phone': phone,
            'password': hashed_password,
            'wallet_balance': 0,
            'is_admin': False,
            'is_blocked': False,
            'created_at': datetime.now(timezone.utc),
            'last_active': datetime.now(timezone.utc)
        }
        
        # First user is automatically an admin
        if db.users.count_documents({}) == 0:
            user['is_admin'] = True
        
        result = db.users.insert_one(user)
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        user_data = db.users.find_one({'phone': phone})
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password']):
            user = User(str(user_data['_id']))
            login_user(user, remember=remember)
            
            # Update last active time
            now = datetime.now(timezone.utc)
            
            # Update MongoDB
            db.users.update_one(
                {'_id': user_data['_id']},
                {'$set': {'last_active': now}}
            )
            
            # Store minimal session data
            session['user_id'] = str(user_data['_id'])
            session['last_active'] = now.isoformat()
            
            return redirect(url_for('game'))
        
        flash('Invalid phone number or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Clear session
    session.clear()
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
        'created_at': datetime.now(timezone.utc),
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
        'created_at': datetime.now(timezone.utc),
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

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.user_data.get('is_admin', False):
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Admin routes
@app.route('/admin')
@login_required
def admin():
    if not current_user.user_data.get('is_admin', False):
        return redirect(url_for('game'))

    # Get recent transactions
    transactions = list(db.transactions.find().sort('created_at', -1).limit(50))

    # Get all users with proper last_active field
    users = []
    for user in db.users.find():
        # Convert last_active to datetime if it exists
        if 'last_active' in user:
            try:
                user['last_active'] = datetime.strptime(str(user['last_active']), '%Y-%m-%d %H:%M:%S.%f')
            except (ValueError, TypeError):
                user['last_active'] = None
        else:
            user['last_active'] = None
        users.append(user)

    # Calculate platform earnings (20% of total pool from completed games)
    total_pool = sum(game.get('total_pool', 0) for game in db.games.find({'status': 'completed'}))
    platform_earnings = int(total_pool * 0.2) if total_pool else 0

    # Calculate stats
    week_ago = datetime.now() - timedelta(days=7)
    stats = {
        'total_games': db.games.count_documents({'status': 'completed'}),
        'total_players': db.users.count_documents({}),
        'platform_earnings': platform_earnings,
        'active_players': db.users.count_documents({
            'last_active': {'$gte': week_ago}
        })
    }

    return render_template('admin.html', 
                         transactions=transactions,
                         users=users,
                         stats=stats)

@app.route('/admin/transaction/<action>/<transaction_id>', methods=['POST'])
@login_required
@admin_required
def handle_transaction(action, transaction_id):
    transaction = db.transactions.find_one({'transaction_id': transaction_id})
    if not transaction:
        return jsonify({'success': False, 'message': 'Transaction not found'})
    
    if transaction['status'] != 'pending':
        return jsonify({'success': False, 'message': 'Transaction is not pending'})
    
    if action == 'approve':
        # Update transaction status
        db.transactions.update_one(
            {'transaction_id': transaction_id},
            {'$set': {'status': 'completed'}}
        )
        
        # Update user's wallet balance for deposits
        if transaction['type'] == 'deposit':
            db.users.update_one(
                {'_id': transaction['user_id']},
                {'$inc': {'wallet_balance': transaction['amount']}}
            )
        
        return jsonify({'success': True, 'message': 'Transaction approved'})
    
    elif action == 'reject':
        # Update transaction status
        db.transactions.update_one(
            {'transaction_id': transaction_id},
            {'$set': {'status': 'rejected'}}
        )
        
        # Refund user's wallet balance for withdrawals
        if transaction['type'] == 'withdrawal':
            db.users.update_one(
                {'_id': transaction['user_id']},
                {'$inc': {'wallet_balance': transaction['amount']}}
            )
        
        return jsonify({'success': True, 'message': 'Transaction rejected'})
    
    return jsonify({'success': False, 'message': 'Invalid action'})

@app.route('/admin/user/<action>/<user_id>', methods=['POST'])
@login_required
@admin_required
def handle_user(action, user_id):
    user = db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    if action == 'block':
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_blocked': True}}
        )
        return jsonify({'success': True, 'message': 'User blocked'})
    
    elif action == 'unblock':
        db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'is_blocked': False}}
        )
        return jsonify({'success': True, 'message': 'User unblocked'})
    
    return jsonify({'success': False, 'message': 'Invalid action'})

game_state = GameState()

if __name__ == '__main__':
    try:
        socketio.run(app, debug=True, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Server Error: {str(e)}")
