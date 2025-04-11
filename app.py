from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from werkzeug.middleware.proxy_fix import ProxyFix
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
from functools import wraps
from flask_session import Session
from flask_cors import CORS
from werkzeug.security import generate_password_hash
import razorpay
from authlib.integrations.flask_client import OAuth
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from pymongo.collection import ReturnDocument

# Load environment variables
load_dotenv()

# Access the variables
SECRET_KEY = os.getenv('SECRET_KEY')
MONGO_URI = os.getenv('MONGO_URI')

# Flask setup with optimized settings
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config.update(
    DEBUG=False,
    ENV='production',
    SECRET_KEY=os.getenv('SECRET_KEY', 'your-secret-key'),
    SESSION_TYPE='filesystem',  # Use filesystem for sessions
    SESSION_COOKIE_SECURE=True,  # Only send cookies over HTTPS
    SESSION_COOKIE_HTTPONLY=True,  # Prevent JavaScript access to session cookie
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    SESSION_REFRESH_EACH_REQUEST=False,  # Reduce session writes
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),  # Limit session lifetime
    JSON_SORT_KEYS=False,  # Reduce CPU usage on JSON responses
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # Limit upload size to 5MB
    RAZORPAY_KEY_ID='rzp_test_2GVU69GqDPjQSs',
    RAZORPAY_KEY_SECRET='YBzsWdwHnjITQe19BpsWTpQD',
    GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID'),
    GOOGLE_CLIENT_SECRET=os.getenv('GOOGLE_CLIENT_SECRET')
)

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v3/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # explicitly set
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'  # ✅ THIS is the key
)

# Enable CORS
CORS(app)

# MongoDB setup with optimized connection pooling
try:
    mongo_uri = os.getenv('MONGO_URI')
    client = MongoClient(
        mongo_uri,
        maxPoolSize=10,  # Limit max connections
        minPoolSize=5,   # Maintain minimum connections
        maxIdleTimeMS=45000,  # Close idle connections after 45s
        serverSelectionTimeoutMS=5000,  # Fail fast if can't connect
        connectTimeoutMS=2000,
        retryWrites=True
    )
    db = client['wheel_game']
    db.command('ping')  # Test connection
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

# Helper to dump JSON using custom encoder
def json_dumps(obj):
    return json.dumps(obj, cls=DateTimeEncoder)

# Add the make_serializable function definition here
def make_serializable(data):
    """Recursively converts datetime and ObjectId to strings in dicts/lists."""
    if isinstance(data, dict):
        return {k: make_serializable(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [make_serializable(i) for i in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, bytes):
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return repr(data) # Fallback for non-utf8 bytes
    else:
        return data

# Initialize Flask-Session
Session(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET'])
)

# Rate limiting decorator - simplified version without Redis
def rate_limit(limit=10, period=60):
    def decorator(f):
        # Simple in-memory rate limiting
        rate_limits = {}

        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_authenticated:
                key = f"rate_limit:{current_user.id}:{request.endpoint}"
                now = time.time()
                
                # Clean up old entries
                rate_limits[key] = [t for t in rate_limits.get(key, []) if now - t < period]
                
                # Check if limit exceeded
                if len(rate_limits.get(key, [])) >= limit:
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                
                # Add current request
                if key not in rate_limits:
                    rate_limits[key] = []
                rate_limits[key].append(now)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Game state management with fallback to MongoDB
class GameState:
    def __init__(self):
        self.wheel_game = {
            'status': 'joining',
            'players': [],
            'timer': 90,
            'break_timer': 15,
            'is_break': False,
            'game_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc),
            'game_type': 'wheel'
        }
        self.dice_game = {
            'status': 'waiting',
            'players': [],
            'timer': 60,
            'game_id': str(uuid.uuid4()),
            'created_at': datetime.now(timezone.utc),
            'game_type': 'dice'
        }
        self._save_initial_states()
        # Initial reset
        self.reset_game('wheel')
        self.reset_game('dice')
    
    def _save_initial_states(self):
        # Store initial states in MongoDB
        db.games.insert_many([self.wheel_game, self.dice_game])
    
    def get_game_state(self, game_type='wheel'):
        # Get state from memory
        state = self.wheel_game if game_type == 'wheel' else self.dice_game
        
        # Fallback to MongoDB if needed
        if not state:
            state = db.games.find_one(
                {'game_type': game_type},
                sort=[('created_at', -1)]
            )
            if state:
                state['_id'] = str(state['_id'])
                if game_type == 'wheel':
                    self.wheel_game = state
                else:
                    self.dice_game = state
        return state or {'status': 'error'}

    def update_game_state(self, updates, game_type='wheel'):
        # Get current state
        current = self.get_game_state(game_type)
        current.update(updates)
        
        # Remove _id before updating
        if '_id' in current:
            del current['_id']
            
        # Update MongoDB
        db.games.update_one(
            {'game_id': current['game_id']},
            {'$set': updates}
        )
        
        # Update in-memory cache
        if game_type == 'wheel':
            self.wheel_game = current
        else:
            self.dice_game = current

    def verify_joining_fee(self, user_id, amount=100):
        """Verify user has sufficient balance for joining fee"""
        user = db.users.find_one({'_id': ObjectId(user_id)})
        if not user or user.get('user_data', {}).get('wallet_balance', 0) < amount:
            return False
        return True
            
    def deduct_joining_fee(self, user_id, amount=100):
        """Deduct joining fee from user's wallet"""
        result = db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$inc': {'user_data.wallet_balance': -amount}}
        )
        # Return True if the update modified a document, False otherwise
        return result.modified_count > 0 

    def reset_game(self, game_type='wheel'):
        """Reset game state for a new round"""
        if game_type == 'wheel':
            self.wheel_game = {
                'status': 'joining',
                'players': [],
                'timer': 90,
                'break_timer': 15,
                'is_break': False,
                'game_id': str(uuid.uuid4()), # Generate new ID
                'created_at': datetime.now(timezone.utc),
                'game_type': 'wheel'
            }
            # Persist reset state if necessary
            # self._save_initial_states() 
        elif game_type == 'dice':
            self.dice_game = {
                'status': 'waiting',
                'players': [],
                'timer': 120,
                'player_timer': 10,
                'current_round': 0,
                'current_player_index': 0,
                'game_id': str(uuid.uuid4()), # Generate new ID
                'created_at': datetime.now(timezone.utc),
                'game_type': 'dice'
            }
            # Persist reset state if necessary
            # self._save_initial_states() 
        else:
             app.logger.warning(f"Attempted to reset unknown game type: {game_type}")

# Socket.IO setup
socketio = SocketIO(app, cors_allowed_origins="*", json=json)

@socketio.on('place_bet')
@rate_limit(limit=5, period=10)  # Limit to 5 bets per 10 seconds
def handle_bet(data):
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}
        
    # Process bet logic here
    emit('bet_placed', {'user': current_user.id, 'amount': data.get('amount')}, broadcast=True)

@socketio.on('spin_wheel')
@rate_limit(limit=1, period=5)  # Limit to 1 spin per 5 seconds
def handle_spin(data):
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}
        
    # Process spin logic here
    result = random.randint(0, 36)
    emit('wheel_result', {'result': result}, broadcast=True)

@socketio.on('timer')
def handle_timer(data):
    game_data = game_state.get_game_state()
    current_time = data.get('time', 0)
    
    # Don't allow joining in last 10 seconds
    if current_time <= 10:
        game_state.update_game_state({'status': 'running'})
    
    if current_time <= 0 and game_data['status'] == 'running':
        winner = select_winner()
        if winner:
            socketio.emit('winner_selected', {
                'winner': {
                    'username': winner['username'],
                    'emoji': winner['emoji'],
                    'prize': winner['prize'],  # Make sure prize is included
                    'wallet_balance': winner['wallet_balance']
                }
            })
            
            # Reset game state after winner selection
            game_state.update_game_state({
                'status': 'joining',
                'players': [],
                'timer': 300,
                'is_break': True
            })
            
            # Start break timer
            socketio.emit('break_timer', {'duration': 15})
    
    socketio.emit('timer', {'time': max(0, current_time)})

# Example of rate-limited API endpoint
@app.route('/api/place_bet', methods=['POST'])
@login_required
@rate_limit(limit=5, period=10)
def place_bet():
    # Bet processing logic here
    return jsonify({'success': True})

@app.route('/api/user/games', methods=['GET'])
@login_required
def get_user_games():
    try:
        # Get user's game history
        user = db.users.find_one({'_id': ObjectId(current_user.id)})
        if not user or 'game_history' not in user:
            return jsonify({
                'games': [],
                'total_games': 0,
                'total_wins': 0,
                'total_earnings': 0
            })

        # Get full game details for each game in user's history
        game_ids = [g['game_id'] for g in user.get('game_history', [])]
        games = list(db.games.find({'_id': {'$in': game_ids}}))
        
        # Format games for response
        formatted_games = []
        for game in games:
            formatted_game = {
                'id': str(game['_id']),
                'timestamp': game['timestamp'].isoformat(),
                'participant_count': game['participant_count'],
                'prize_pool': game['prize_pool'],
                'winner': {
                    'id': str(game['winner']['id']),
                    'username': game['winner']['username'],
                    'emoji': game['winner']['emoji']
                }
            }
            formatted_games.append(formatted_game)
        
        # Calculate statistics
        game_history = user.get('game_history', [])
        total_wins = sum(1 for g in game_history if g.get('won', False))
        total_earnings = sum(g['prize_pool'] for g in game_history if g.get('won', False))
        
        return jsonify({
            'games': formatted_games,
            'total_games': len(formatted_games),
            'total_wins': total_wins,
            'total_earnings': total_earnings
        })
    
    except Exception as e:
        print(f"Error in get_user_games: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/games/recent', methods=['GET'])
def get_recent_games():
    try:
        # Get 10 most recent games
        recent_games = list(db.games.find().sort('timestamp', -1).limit(10))
        
        # Format games for response
        formatted_games = []
        for game in recent_games:
            formatted_game = {
                'id': str(game['_id']),
                'timestamp': game['timestamp'].isoformat(),
                'participant_count': game['participant_count'],
                'prize_pool': game['prize_pool'],
                'winner': {
                    'id': str(game['winner']['id']),
                    'username': game['winner']['username'],
                    'emoji': game['winner']['emoji']
                }
            }
            formatted_games.append(formatted_game)
        
        return jsonify({'games': formatted_games})
    
    except Exception as e:
        print(f"Error in get_recent_games: {str(e)}")
        return jsonify({'error': str(e)}), 500

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id
        self._load_user_data()

    def _load_user_data(self):
        # Load user data directly from MongoDB
        user = db.users.find_one({'_id': ObjectId(self.id)})
        if user:
            self.user_data = user.get('user_data', {})
            self.is_admin = user.get('is_admin', False)
            self.is_blocked = user.get('is_blocked', False)
            self.game_history = user.get('game_history', [])
            self.created_at = user.get('created_at')
            self.last_active = user.get('last_active')
            self.phone = user.get('phone')  # Load phone number from user document
        else:
            self.user_data = {}
            self.is_admin = False
            self.is_blocked = False
            self.game_history = []
            self.created_at = None
            self.last_active = None
            self.phone = None

    @property
    def is_active(self):
        return not self.is_blocked

    @staticmethod
    def get(user_id):
        if not user_id:
            return None
        return User(user_id)

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

@app.route('/set_emoji_session', methods=['POST'])
def set_emoji_session():
    data = request.get_json()
    session['selected_emoji'] = data.get('emoji', '🎮')
    return jsonify({'success': True})

@app.route('/login/google')
def google_login():
    scheme = os.getenv('OAUTH_SCHEME', 'http')  # fallback to http
    redirect_uri = url_for('google_authorize', _external=True, _scheme=scheme)
    print("Using redirect URI:", redirect_uri)
    return google.authorize_redirect(redirect_uri)


@app.route('/auth/google/callback')
def google_authorize():
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()

        user = db.users.find_one({'email': user_info['email']})
        
        if not user:
            # Get selected emoji from session if available
            selected_emoji = session.pop('selected_emoji', '🎮')
            
            user_data = {
                'email': user_info['email'],
                'username': user_info.get('name', user_info['email'].split('@')[0]),
                'user_data': {
                    'username': user_info.get('name', user_info['email'].split('@')[0]),
                    'email': user_info['email'],
                    'profile_picture': user_info.get('picture'),
                    'wallet_balance': 0,
                    'emoji': selected_emoji
                },
                'is_admin': False,
                'is_blocked': False,
                'created_at': datetime.now(timezone.utc),
                'last_active': datetime.now(timezone.utc),
                'google_id': user_info['sub']
            }
            result = db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
        else:
            user_id = str(user['_id'])
            db.users.update_one(
                {'_id': ObjectId(user_id)},
                {'$set': {'last_active': datetime.now(timezone.utc)}}
            )
        
        user_obj = User(user_id)
        login_user(user_obj)
        flash('Successfully logged in with Google!', 'success')
        return redirect(url_for('index'))  # Redirect to homepage or dashboard
    except Exception as e:
        print(e)
        flash('Google login failed.', 'error')
        return redirect(url_for('login'))

def update_game_timer():
    while True:
        try:
            with app.app_context(): 
                # === Handle Wheel Game Timer ===
                wheel_game_data = game_state.get_game_state('wheel')
                
                if wheel_game_data.get('is_break'):
                    # Handle break timer
                    break_timer = wheel_game_data.get('break_timer', 15)
                    if break_timer > 0:
                        game_state.update_game_state({'break_timer': break_timer - 1}, 'wheel')
                        # Use the specific 'timer' event for wheel game?
                        socketio.emit('timer', {'time': break_timer - 1, 'isBreak': True})
                        app.logger.debug(f"[Wheel Timer] Break timer: {break_timer - 1}")
                    else:
                        # Break time over, start new game
                        app.logger.info("[Wheel Timer] Break ended. Resetting wheel game.")
                        game_state.reset_game('wheel')
                        new_state = game_state.get_game_state('wheel')
                        # Use specific 'game_status' event for wheel game? Make serializable.
                        serializable_state = make_serializable(new_state)
                        socketio.emit('game_status', serializable_state)
                elif wheel_game_data.get('status') == 'joining':
                    # Handle joining timer
                    join_timer = wheel_game_data.get('timer', 90)
                    if join_timer > 0:
                        # Decrement timer first
                        new_timer_value = join_timer - 1
                        game_state.update_game_state({'timer': new_timer_value}, 'wheel')

                        # Always emit the timer update
                        socketio.emit('timer', {'time': new_timer_value, 'isBreak': False})
                        app.logger.debug(f"[Wheel Timer] Joining timer: {new_timer_value}")

                        # Change status to running in last seconds (e.g., 10s) WITHOUT re-checking status
                        # Check based on the *new* timer value
                        if new_timer_value == 10 and wheel_game_data.get('status') == 'joining':
                            game_state.update_game_state({'status': 'running'}, 'wheel')
                            app.logger.info("[Wheel Timer] Wheel game status changed to running at 10 seconds.")
                            # Emit status update - Make serializable
                            # Fetch the updated state *after* status change
                            serializable_state = make_serializable(game_state.get_game_state('wheel'))
                            socketio.emit('game_status', serializable_state)
                    else: # Timer reached 0 while status was still 'joining' (should ideally not happen with the change above)
                        # Joining timer expired, select winner
                        app.logger.info("[Wheel Timer] Joining timer expired at 0. Selecting winner.")
                        game_state.update_game_state({'status': 'running'}, 'wheel') # Ensure status is running before selecting winner

                        winner = select_winner() # select_winner handles DB updates & prize
                        if winner:
                            app.logger.info(f"[Wheel Timer] Winner selected: {winner.get('username')}")
                            # select_winner should return serializable data including prize/balance
                            socketio.emit('winner_selected', make_serializable(winner))
                        else:
                            app.logger.info("[Wheel Timer] No winner selected (no players/bets?).")
                            # Make sure this payload is also serializable
                            socketio.emit('game_end', make_serializable({'winner': None}))

                        # Start break time after winner selection/no winner
                        game_state.update_game_state({
                            'status': 'break',
                            'is_break': True,
                            'break_timer': 15
                        }, 'wheel')
                        # Emit break status - Make serializable
                        serializable_state = make_serializable(game_state.get_game_state('wheel'))
                        socketio.emit('game_status', serializable_state)
                elif wheel_game_data.get('status') == 'running': # Add a new condition for 'running' status
                    # Handle running timer (after it was set to 'running' at 10s)
                    running_timer = wheel_game_data.get('timer', 0) # Get current timer value
                    if running_timer > 0:
                        # Decrement timer
                        new_timer_value = running_timer - 1
                        game_state.update_game_state({'timer': new_timer_value}, 'wheel')

                        # Emit timer update
                        socketio.emit('timer', {'time': new_timer_value, 'isBreak': False})
                        app.logger.debug(f"[Wheel Timer] Running timer: {new_timer_value}")
                    else:
                        # Running timer expired, select winner
                        app.logger.info("[Wheel Timer] Running timer expired. Selecting winner.")

                        winner = select_winner() # select_winner handles DB updates & prize
                        if winner:
                            app.logger.info(f"[Wheel Timer] Winner selected: {winner.get('username')}")
                            # select_winner should return serializable data including prize/balance
                            socketio.emit('winner_selected', make_serializable(winner))
                        else:
                            app.logger.info("[Wheel Timer] No winner selected (no players/bets?).")
                            # Make sure this payload is also serializable
                            socketio.emit('game_end', make_serializable({'winner': None}))

                        # Start break time after winner selection/no winner
                        game_state.update_game_state({
                            'status': 'break',
                            'is_break': True,
                            'break_timer': 15
                        }, 'wheel')
                        # Emit break status - Make serializable
                        serializable_state = make_serializable(game_state.get_game_state('wheel'))
                        socketio.emit('game_status', serializable_state)

                # === Handle Dice Game Timer ===
                dice_game_data = game_state.get_game_state('dice')
                if dice_game_data.get('status') == 'active':
                    current_player_timer = dice_game_data.get('player_timer', 10)
                    game_id = dice_game_data.get('game_id', 'N/A')
                    
                    if current_player_timer > 0:
                        game_state.update_game_state({'player_timer': current_player_timer - 1}, 'dice')
                        app.logger.info(f"[Dice Active Timer {game_id}] Timer decremented to {current_player_timer - 1}")
                        timer_update_data = {
                            'time': current_player_timer - 1,
                            'status': 'active'
                        }
                        socketio.emit('dice_timer_update', make_serializable(timer_update_data))
                    else:
                        # Player Timer expired - auto-advance turn
                        app.logger.info(f"[Dice Active Timer {game_id}] Player timer expired. Advancing turn.")
                        players = dice_game_data.get('players', [])
                        if not players:
                            app.logger.warning(f"[Dice Active Timer {game_id}] No players found, resetting.")
                            game_state.reset_game('dice')
                            continue # Skip rest of loop iteration
                            
                        current_idx = dice_game_data.get('current_player_index', 0)
                        next_player_index = (current_idx + 1) % len(players)
                        
                        # Update state: advance player index, reset timer
                        game_state.update_game_state({
                            'current_player_index': next_player_index,
                            'player_timer': 10 
                        }, 'dice')
                        
                        updated_game_data = game_state.get_game_state('dice') # Fetch updated state
                        
                        # Check if round ended
                        if next_player_index == 0:
                            current_round = updated_game_data.get('current_round', 1)
                            if current_round >= 3:
                                # --- Game End Logic (Copied from handle_dice_roll) ---
                                app.logger.info(f"[Dice Active Timer {game_id}] Game round limit reached. Ending game.")
                                winner = max(players, key=lambda p: p.get('score', 0))
                                prize = len(players) * 100 * 0.8
                                
                                try:
                                    db.users.update_one(
                                        {'_id': ObjectId(winner['user_id'])},
                                        {'$inc': {'user_data.wallet_balance': prize}}
                                    )
                                    # Ensure dice_games collection exists
                                    if 'dice_games' not in db.list_collection_names():
                                        db.create_collection('dice_games')
                                        
                                    db.dice_games.insert_one({
                                        'game_id': game_id,
                                        'players': players,
                                        'winner': winner['user_id'],
                                        'prize': prize,
                                        'created_at': updated_game_data.get('created_at'), # Use original creation time
                                        'completed_at': datetime.now(timezone.utc),
                                        'status': 'completed'
                                    })
                                    end_game_data = {
                                        'winner': winner['username'],
                                        'prize': prize,
                                        'final_scores': [{'username': p['username'], 'score': p.get('score', 0)} for p in players]
                                    }
                                    socketio.emit('dice_game_end', make_serializable(end_game_data))
                                except Exception as e:
                                    app.logger.error(f"[Dice Active Timer {game_id}] Error finalizing game: {e}", exc_info=True)
                                finally:
                                    game_state.reset_game('dice')
                                # --- End Game End Logic ---
                            else:
                                # Start next round
                                app.logger.info(f"[Dice Active Timer {game_id}] Starting round {current_round + 1}.")
                                game_state.update_game_state({'current_round': current_round + 1}, 'dice')
                                round_start_data = {
                                    'round': current_round + 1,
                                    'status': 'active'
                                }
                                socketio.emit('dice_round_start', make_serializable(round_start_data))
                                # Emit full state update too, so client knows timer reset etc.
                                socketio.emit('dice_game_update', make_serializable(game_state.get_game_state('dice')))
                        else:
                            # Emit game update to notify of turn change and timer reset
                            app.logger.info(f"[Dice Active Timer {game_id}] Advancing to player index {next_player_index}.")
                            socketio.emit('dice_game_update', make_serializable(updated_game_data))

            # Sleep at the end of the main loop
            socketio.sleep(1)
        except Exception as e:
            app.logger.error(f"Error in update_game_timer loop: {str(e)}", exc_info=True)
            socketio.sleep(5) # Sleep longer on error

# Start timer thread globally (ensure this is correctly starting the above function)
if 'timer_thread' not in locals(): # Basic check to prevent duplicate threads on reload
     timer_thread = None 
if timer_thread is None or not timer_thread.is_alive():
    timer_thread = socketio.start_background_task(update_game_timer)
    app.logger.info("Started background game timer thread.")

@socketio.on('connect')
def handle_connect():
    global timer_thread
    
    if timer_thread is None or not timer_thread.is_alive():
        timer_thread = socketio.start_background_task(update_game_timer)
    
    game_data = game_state.get_game_state()
    emit('game_status', {
        'status': game_data['status'],
        'players': game_data['players'],
        'timer': game_data['timer'],
        'isBreak': game_data.get('is_break', False)
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
    if current_user.user_data.get('wallet_balance', 0) < 100:
        emit('join_game_response', {'success': False, 'message': 'Insufficient balance'})
        return

    # Add player to game with emoji
    player_info = {
        'id': str(current_user.id),
        'username': current_user.user_data['username'],
        'emoji': current_user.user_data.get('emoji', '🎮')  # Default emoji if not found
    }
    
    game_state.update_game_state({'players': game_data.get('players', []) + [player_info]})

    # Deduct entry fee
    db.users.update_one(
        {'_id': ObjectId(current_user.id)},
        {'$inc': {'user_data.wallet_balance': -100}}
    )

    # Get updated game state
    updated_game_data = game_state.get_game_state()

    # Notify all clients
    socketio.emit('game_status', {
        'status': updated_game_data['status'],
        'players': updated_game_data['players'],
        'timer': updated_game_data['timer'],
        'isBreak': updated_game_data.get('is_break', False)
    })

    socketio.emit('player_joined', {
        'success': True,
        'message': f"{player_info['username']} joined the game!",
        'players': updated_game_data['players'],
        'player_count': len(updated_game_data['players']),
        'new_player': player_info
    })

    # Show wheel for first player
    if len(updated_game_data['players']) == 1:
        socketio.emit('show_wheel')

    emit('join_game_response', {'success': True, 'message': 'Successfully joined the game'})

def select_winner():
    game_data = game_state.get_game_state() # Wheel game default
    game_id_log = game_data.get('game_id', 'N/A')
    app.logger.info(f"[select_winner {game_id_log}] Attempting to select winner.")
    
    players = game_data.get('players', [])
    if not players:
        app.logger.warning(f"[select_winner {game_id_log}] No players in game state.")
        return None
    
    try:
        winner = random.choice(players)
        app.logger.info(f"[select_winner {game_id_log}] Randomly selected winner: {winner.get('username', 'N/A')}")
    except IndexError:
        app.logger.warning(f"[select_winner {game_id_log}] Player list was unexpectedly empty during random.choice.")
        return None
        
    total_players = len(players)
    total_pool = total_players * 100  
    prize_money = int(total_pool * 0.9)

    winner_user_id_str = winner.get('id')
    if not winner_user_id_str:
        app.logger.error(f"[select_winner {game_id_log}] Winner dictionary missing 'id': {winner}")
        return None # Cannot proceed without winner ID
        
    try:
        winner_user_id_obj = ObjectId(winner_user_id_str)
    except Exception as e:
        app.logger.error(f"[select_winner {game_id_log}] Invalid winner ID format '{winner_user_id_str}': {e}")
        return None # Cannot proceed with invalid ID format

    try:
        # Store game details in games collection
        game_record = {
            'timestamp': datetime.utcnow(), # Use UTC consistently
            'participants': players, # Store the list of player dicts
            'participant_count': total_players,
            'prize_pool': total_pool,  
            'winner': {
                'id': winner_user_id_str, # Store as string
                'username': winner.get('username'), # Use .get
                'emoji': winner.get('emoji')    # Use .get
            },
            'entry_fee': 100,
            'game_id': game_data.get('game_id'), # Get game_id from state
            'game_type': 'wheel',
            'status': 'completed' # Mark as completed
        }
        result = db.games.insert_one(game_record)
        db_game_id = result.inserted_id
        app.logger.info(f"[select_winner {game_id_log}] Game record created in DB with ID: {db_game_id}")

        # Add game reference to each participant's history
        participant_ids = []
        for p in players:
            p_id_str = p.get('id')
            if p_id_str:
                try:
                    participant_ids.append(ObjectId(p_id_str))
                except Exception:
                    app.logger.warning(f"[select_winner {game_id_log}] Skipping invalid participant ID format '{p_id_str}' for game history update.")
            else:
                 app.logger.warning(f"[select_winner {game_id_log}] Participant missing 'id' in player data: {p}")
        
        if participant_ids:
            db.users.update_many(
                {'_id': {'$in': participant_ids}},
                {'$push': {
                    'game_history': {
                        'game_id': db_game_id, # Use the DB game ID
                        'timestamp': game_record['timestamp'],
                        'won': False, # Default to false
                        'prize_pool': total_pool,
                        'prize_money': prize_money,
                        'game_type': 'wheel' # Add game type for clarity
                    }
                }}
            )
            app.logger.info(f"[select_winner {game_id_log}] Updated game history for {len(participant_ids)} participants.")
        
        # Update winner's game history and wallet
        winner_update_result = db.users.find_one_and_update(
            {'_id': winner_user_id_obj},
            [
                 {'$set': {
                     'user_data.wallet_balance': {'$add': ['$user_data.wallet_balance', prize_money]},
                     'game_history': {
                         '$map': {
                             'input': '$game_history',
                             'as': 'hist',
                             'in': {
                                 '$cond': {
                                      'if': {'$eq': ['$$hist.game_id', db_game_id]},
                                      'then': {'$mergeObjects': ['$$hist', {'won': True}]},
                                      'else': '$$hist'
                                 }
                             }
                         }
                     }
                 }}
            ],
            return_document=ReturnDocument.AFTER # Get the updated document
        )

        if not winner_update_result:
            app.logger.error(f"[select_winner {game_id_log}] Failed to find and update winner user {winner_user_id_str} after winning.")
            # Decide how to handle - maybe the prize wasn't awarded?
            # For now, return winner dict without updated balance
            winner['prize'] = prize_money
            winner['wallet_balance'] = 'Error updating'
        else:
            app.logger.info(f"[select_winner {game_id_log}] Winner {winner_user_id_str} updated successfully.")
            # Add wallet balance to winner data for frontend
            winner['wallet_balance'] = winner_update_result.get('user_data', {}).get('wallet_balance', 'N/A')
            winner['prize'] = prize_money

        app.logger.info(f"[select_winner {game_id_log}] Winner processing complete. Winner: {winner.get('username', 'N/A')}, Prize: {prize_money}")
        # Ensure final returned dict is serializable
        return make_serializable(winner) 

    except Exception as e:
        app.logger.error(f"[select_winner {game_id_log}] Unexpected error during winner processing: {str(e)}", exc_info=True)
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        phone = request.form.get('phone')
        password = request.form.get('password')
        selected_emoji = request.form.get('selected_emoji', '🎮')

        if db.users.find_one({'phone': phone}):
            flash('Phone number already registered')
            return redirect(url_for('register'))

        # Create user with initial fields
        user_data = {
            'username': username,
            'phone': phone,
            'password': bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'),
            'user_data': {
                'username': username,
                'wallet_balance': 0,
                'emoji': selected_emoji
            },
            'game_history': [],
            'is_admin': False,
            'is_blocked': False,
            'created_at': datetime.utcnow(),
            'last_active': datetime.utcnow()
        }
        
        # First user is automatically an admin
        if db.users.count_documents({}) == 0:
            user_data['is_admin'] = True
        
        db.users.insert_one(user_data)
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/leaderboard')
def leaderboard():
    # Fetch top players based on wins and earnings from games collection
    pipeline = [
        # Match only completed games
        {'$match': {'status': 'completed'}},
        # Group by winner to calculate statistics
        {'$group': {
            '_id': '$winner',
            'username': {'$first': '$winner'},
            'total_wins': {'$sum': 1},
            'total_earnings': {'$sum': '$winner_prize'},
            'games': {'$push': '$$ROOT'}
        }},
        # Add total games played (including non-wins)
        {'$lookup': {
            'from': 'games',
            'let': {'player_name': '$username'},
            'pipeline': [
                {'$match': {
                    '$expr': {'$in': ['$$player_name', {'$map': {
                        'input': '$players',
                        'as': 'player',
                        'in': '$$player.username'
                    }}]},
                    'status': 'completed'
                }}
            ],
            'as': 'all_games'
        }},
        {'$addFields': {
            'total_games': {'$size': '$all_games'}
        }},
        # Calculate win rate
        {'$addFields': {
            'win_rate': {
                '$multiply': [
                    {'$divide': ['$total_wins', {'$max': ['$total_games', 1]}]},
                    100
                ]
            }
        }},
        # Sort by total wins and earnings
        {'$sort': {'total_wins': -1, 'total_earnings': -1}},
        {'$limit': 10},
        # Project final fields
        {'$project': {
            '_id': 0,
            'username': 1,
            'total_wins': 1,
            'total_games': 1,
            'total_earnings': 1,
            'win_rate': {'$round': ['$win_rate', 2]}
        }}
    ]
    
    top_players = list(db.games.aggregate(pipeline))
    return render_template('leaderboard.html', players=top_players)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('select_game'))

    if request.method == 'POST':
        phone = request.form.get('phone')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
 
        user_data = db.users.find_one({'phone': phone})
        
        if user_data and user_data.get('is_blocked', False):
            flash('Your account has been blocked. Please contact admin.')
            return redirect(url_for('login'))
            
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password'].encode('utf-8')):
            user_obj = User(str(user_data['_id']))
            login_user(user_obj, remember=remember)
 
            # Update last active time
            now = datetime.now(timezone.utc)
            db.users.update_one(
                {'_id': ObjectId(user_data['_id'])},
                {'$set': {'last_active': now}}
            )

            # Set admin status in session
            session['is_admin'] = user_obj.is_admin
            
            flash('Login successful!', 'success')
            return redirect(url_for('select_game'))
 
        flash('Invalid phone number or password')
        return redirect(url_for('login'))
 
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    # Clear session
    session.clear()
    logout_user()
    return redirect(url_for('index'))

@app.route('/select-game')
@login_required
def select_game():
    return render_template('select_games.html')

@app.route('/game')
@login_required
def game():
    return render_template('game.html')

@app.route('/rs100-game')
@login_required
def rs100_game():
    return render_template('rs100_game.html')

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
    
    # Get user's game history from BOTH collections
    game_history = []
    user_id_str = str(current_user.id)

    # 1. Fetch Wheel Game history (existing logic)
    wheel_games = db.games.find({
        'players': {
            '$elemMatch': {
                'id': user_id_str
            }
        }
    }).sort('created_at', -1)

    for game in wheel_games:
        is_winner = game.get('winner') == current_user.user_data['username']
        winner_prize = game.get('winner_prize', 0) 
        game_history.append({
            'game_doc': game, # Keep original doc for potential future use
            'date': game.get('created_at'), 
            'game_type': 'Wheel', # Renamed for brevity
            'won': is_winner,
            'amount': winner_prize if is_winner else -100, 
            'details': f"Pool: ₹{game.get('total_pool', 0)}, Fee: ₹{game.get('platform_fee', 0)}"
        })

    # 2. Fetch Dice Game history
    dice_games = db.dice_games.find({
        # Query if the user_id exists within the players array
        'players.user_id': user_id_str 
    }).sort('completed_at', -1) # Sort by completion time for dice

    for game in dice_games:
        # Check if current user is the winner
        is_winner = game.get('winner') == user_id_str
        prize = game.get('prize', 0)
        entry_fee = 100 # Assuming fixed entry fee

        # Find the player's specific data in the players array
        player_data = next((p for p in game.get('players', []) if p.get('user_id') == user_id_str), None)
        player_score = player_data.get('score', 0) if player_data else 'N/A'
        player_rolls = player_data.get('rolls', []) if player_data else []
        rolls_str = ', '.join(map(str, player_rolls))

        game_history.append({
            'game_doc': game, # Keep original doc
            'date': game.get('completed_at') or game.get('created_at'), # Use completed_at if available
            'game_type': 'Dice', 
            'won': is_winner,
            'amount': prize if is_winner else -entry_fee,
            'details': f"Score: {player_score} (Rolls: {rolls_str})" # Show score/rolls as details
        })

    # 3. Sort combined history by date descending
    game_history.sort(key=lambda x: x.get('date') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    
    # Pass the original lists with datetime objects to the template
    # ... (rest of the function remains the same) ...
    return render_template('wallet.html', 
                           transactions=transactions, 
                           game_history=game_history)

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
        {'$inc': {'user_data.wallet_balance': -amount}}
    )
    
    db.transactions.insert_one(transaction)
    flash('Withdrawal request submitted successfully!')
    return redirect(url_for('wallet'))

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Admin routes
@app.route('/admin/')
@login_required
def admin():
    if not session.get('is_admin'):
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
    try:
        app.logger.info(f"Processing transaction {transaction_id} with action {action}")
        
        # Get transaction and ensure it exists
        transaction = db.transactions.find_one({'transaction_id': transaction_id})
        app.logger.info(f"Found transaction: {transaction}")
        
        if not transaction:
            app.logger.error(f"Transaction {transaction_id} not found")
            return jsonify({'success': False, 'message': 'Transaction not found'})
        
        if transaction['status'] != 'pending':
            app.logger.error(f"Transaction {transaction_id} is not pending (status: {transaction['status']})")
            return jsonify({'success': False, 'message': 'Transaction is not pending'})

        # Get user data to verify
        user = db.users.find_one({'_id': transaction['user_id']})
        app.logger.info(f"Found user: {user}")
        
        if not user:
            app.logger.error(f"User {transaction['user_id']} not found")
            return jsonify({'success': False, 'message': 'User not found'})
        
        if action == 'approve':
            app.logger.info(f"Approving {transaction['type']} transaction")
            
            # For withdrawals, money is already deducted during request
            if transaction['type'] == 'withdrawal':
                try:
                    result = db.transactions.update_one(
                        {'transaction_id': transaction_id},
                        {'$set': {
                            'status': 'completed',
                            'updated_at': datetime.now(timezone.utc),
                            'approved_by': str(current_user.id)
                        }}
                    )
                    app.logger.info(f"Withdrawal approval result: {result.modified_count} documents modified")
                except Exception as e:
                    app.logger.error(f"Error approving withdrawal: {str(e)}")
                    raise
                    
            # For deposits, add money to wallet
            elif transaction['type'] == 'deposit':
                try:
                    result = db.users.update_one(
                        {'_id': transaction['user_id']},
                        {'$inc': {'user_data.wallet_balance': transaction['amount']}}
                    )
                    app.logger.info(f"Deposit balance update result: {result.modified_count} documents modified")
                    
                    if result.modified_count == 0:
                        app.logger.error("Failed to update user balance")
                        return jsonify({'success': False, 'message': 'Failed to update user balance'})
                    
                    result = db.transactions.update_one(
                        {'transaction_id': transaction_id},
                        {'$set': {
                            'status': 'completed',
                            'updated_at': datetime.now(timezone.utc),
                            'approved_by': str(current_user.id)
                        }}
                    )
                    app.logger.info(f"Deposit approval result: {result.modified_count} documents modified")
                except Exception as e:
                    app.logger.error(f"Error approving deposit: {str(e)}")
                    raise
            
            return jsonify({'success': True, 'message': 'Transaction approved'})
        
        elif action == 'reject':
            app.logger.info(f"Rejecting {transaction['type']} transaction")
            
            # For withdrawals, refund the money since it was deducted during request
            if transaction['type'] == 'withdrawal':
                try:
                    result = db.users.update_one(
                        {'_id': transaction['user_id']},
                        {'$inc': {'user_data.wallet_balance': transaction['amount']}}
                    )
                    app.logger.info(f"Withdrawal refund result: {result.modified_count} documents modified")
                    
                    if result.modified_count == 0:
                        app.logger.error("Failed to refund user balance")
                        return jsonify({'success': False, 'message': 'Failed to refund user balance'})
                except Exception as e:
                    app.logger.error(f"Error refunding withdrawal: {str(e)}")
                    raise
            
            try:
                result = db.transactions.update_one(
                    {'transaction_id': transaction_id},
                    {'$set': {
                        'status': 'rejected',
                        'updated_at': datetime.now(timezone.utc),
                        'rejected_by': str(current_user.id)
                    }}
                )
                app.logger.info(f"Rejection update result: {result.modified_count} documents modified")
            except Exception as e:
                app.logger.error(f"Error updating transaction status: {str(e)}")
                raise
            
            return jsonify({'success': True, 'message': 'Transaction rejected'})
        
        app.logger.error(f"Invalid action: {action}")
        return jsonify({'success': False, 'message': 'Invalid action'})
        
    except Exception as e:
        app.logger.error(f"Transaction handling error: {str(e)}")
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'})

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

@app.route('/payment-options')
@login_required
def payment_options():
    return render_template('payment_options.html')

@app.route('/razorpay/deposit', methods=['GET', 'POST'])
@login_required
@rate_limit()
def razorpay_deposit():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
            if amount < 200 or amount > 100000:
                return jsonify({'error': 'Amount must be between ₹200 and ₹100,000'}), 400

            # Create Razorpay order with shorter receipt ID
            timestamp = int(time.time())
            receipt_id = f"dep_{current_user.id[:8]}_{timestamp}"
            
            order_data = {
                'amount': int(amount * 100),  # amount in paise
                'currency': 'INR',
                'receipt': receipt_id,
                'notes': {
                    'user_id': current_user.id,
                    'type': 'deposit'
                }
            }
            order = razorpay_client.order.create(data=order_data)
            
            # Create transaction record with completed status
            transaction = {
                'user_id': ObjectId(current_user.id),
                'type': 'deposit',
                'amount': amount,
                'status': 'completed',  # Set status as completed immediately
                'created_at': datetime.now(timezone.utc),
                'transaction_id': str(uuid.uuid4()),
                'username': current_user.user_data['username'],
                'razorpay_order_id': order['id']
            }
            db.transactions.insert_one(transaction)
            
            # Update user's wallet balance immediately
            db.users.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$inc': {'user_data.wallet_balance': amount}}
            )
            
            # Add notification for successful deposit
            if 'notifications' not in db.list_collection_names():
                db.create_collection('notifications')
            
            notification = {
                'user_id': ObjectId(current_user.id),
                'type': 'deposit',
                'message': f'Successfully deposited ₹{amount:.2f}',
                'created_at': datetime.now(timezone.utc),
                'read': False
            }
            db.notifications.insert_one(notification)
            
            return jsonify({
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency']
            })
        except Exception as e:
            app.logger.error(f"Razorpay deposit error: {str(e)}")
            return jsonify({'error': 'Payment processing failed'}), 500

    return render_template('razorpay_deposit.html')

@app.route('/razorpay/withdraw', methods=['GET', 'POST'])
@login_required
@rate_limit()
def razorpay_withdraw():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount'))
            if amount < 200 or amount > 100000:
                return jsonify({'error': 'Amount must be between ₹200 and ₹100,000'}), 400
            
            if current_user.user_data['wallet_balance'] < amount:
                return jsonify({'error': 'Insufficient balance'}), 400

            # Update user balance
            db.users.update_one(
                {'_id': ObjectId(current_user.id)},
                {'$inc': {'user_data.wallet_balance': -amount}}
            )
            
            # Log transaction
            transaction = {
                'user_id': ObjectId(current_user.id),
                'type': 'withdrawal',
                'amount': amount,
                'status': 'pending',
                'created_at': datetime.now(timezone.utc),
                'transaction_id': str(uuid.uuid4()),
                'username': current_user.user_data['username'],
                'bank_details': {
                    'account_number': request.form.get('account_number'),
                    'ifsc_code': request.form.get('ifsc_code'),
                    'account_holder': request.form.get('account_holder')
                }
            }
            db.transactions.insert_one(transaction)
            
            # Add notification
            notification = {
                'user_id': ObjectId(current_user.id),
                'type': 'withdrawal',
                'message': f'Withdrawal request of ₹{amount:.2f} submitted. Admin will process it soon.',
                'created_at': datetime.now(timezone.utc),
                'read': False
            }
            db.notifications.insert_one(notification)
            
            return jsonify({
                'status': 'success',
                'message': 'Withdrawal request submitted successfully. Admin will process it soon.'
            })
        except Exception as e:
            app.logger.error(f"Withdrawal error: {str(e)}")
            return jsonify({'error': 'Withdrawal processing failed'}), 500

    return render_template('razorpay_withdraw.html')

@app.route('/razorpay/withdraw/callback')
def razorpay_withdraw_callback():
    try:
        payout_id = request.args.get('payout_id')
        payout_status = request.args.get('payout_status')
        
        # Get transaction details
        transaction = db.transactions.find_one({
            'razorpay_payout_id': payout_id
        })
        
        if transaction:
            # Update transaction status based on payout status
            new_status = 'completed' if payout_status == 'processed' else 'failed'
            db.transactions.update_one(
                {'_id': transaction['_id']},
                {'$set': {'status': new_status}}
            )
            
            # Add notification based on status
            notification = {
                'user_id': transaction['user_id'],
                'type': 'withdrawal',
                'message': f'Withdrawal of ₹{transaction["amount"]:.2f} has been {new_status}',
                'created_at': datetime.now(timezone.utc),
                'read': False
            }
            db.notifications.insert_one(notification)
            
            return redirect(url_for('wallet', withdrawal=new_status))
        
        return redirect(url_for('wallet', withdrawal='error'))
    except Exception as e:
        app.logger.error(f"Withdrawal callback error: {str(e)}")
        return redirect(url_for('wallet', withdrawal='error'))

@app.route('/wheel/bet', methods=['POST'])
@login_required
@rate_limit(limit=5, period=10)  # Limit to 5 bets per 10 seconds
def wheel_bet():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        amount = float(data.get('amount', 0))
        if amount <= 0:
            return jsonify({'error': 'Invalid bet amount'}), 400

        if amount > current_user.user_data['wallet_balance']:
            return jsonify({'error': 'Insufficient balance'}), 400

        # Deduct amount from user's balance
        db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$inc': {'user_data.wallet_balance': -amount}}
        )

        # Add bet to game state
        game_state.add_bet(current_user.id, amount)

        return jsonify({
            'message': 'Bet placed successfully',
            'balance': current_user.user_data['wallet_balance'] - amount
        })
    except Exception as e:
        app.logger.error(f"Error placing bet: {str(e)}")
        return jsonify({'error': 'Failed to place bet'}), 500

@app.route('/manual_payment')
@login_required
def manual_payment():
    return render_template('manual_payment.html')

@app.route('/manual_deposit', methods=['GET', 'POST'])
@login_required
def manual_deposit():
    if request.method == 'GET':
        return render_template('manual_deposit.html')
    
    try:
        amount = float(request.form.get('amount'))
        if amount < 20 or amount > 1000:
            flash('Invalid deposit amount. Must be between ₹20 and ₹1000')
            return redirect(url_for('manual_payment'))
        
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
    except Exception as e:
        app.logger.error(f"Manual deposit error: {str(e)}")
        flash('An error occurred. Please try again.')
        return redirect(url_for('manual_payment'))

@app.route('/contact_us')
def contact_us():
    return render_template('contact_us.html')

@app.route('/help_center')
def help_center():
    return render_template('help_center.html')

@app.route('/game_rules')
def game_rules():
    return render_template('game_rules.html')

@app.route('/faq')
def faq():
    return render_template('faq.html')

@app.route('/report_issue')
def report_issue():
    return render_template('report_issue.html')

@app.route('/terms_of_service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')



@app.route('/manual_withdraw', methods=['GET', 'POST'])
@login_required
def manual_withdraw():
    if request.method == 'GET':
        return render_template('manual_withdraw.html')
    
    try:
        amount = float(request.form.get('amount'))
        if amount < 50 or amount > 500:
            flash('Invalid withdrawal amount. Must be between ₹50 and ₹500')
            return redirect(url_for('manual_payment'))
        
        if current_user.user_data['wallet_balance'] < amount:
            flash('Insufficient balance')
            return redirect(url_for('manual_payment'))
        
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
                'account_number': request.form.get('bank_account'),
                'ifsc_code': request.form.get('ifsc_code'),
                'account_holder': request.form.get('account_holder')
            }
        }
        
        # Deduct amount from wallet immediately for withdrawal
        db.users.update_one(
            {'_id': ObjectId(current_user.id)},
            {'$inc': {'user_data.wallet_balance': -amount}}
        )
        
        db.transactions.insert_one(transaction)
        flash('Withdrawal request submitted successfully! Admin will process your request.')
        return redirect(url_for('wallet'))
    except Exception as e:
        app.logger.error(f"Manual withdrawal error: {str(e)}")
        flash('An error occurred. Please try again.')
        return redirect(url_for('manual_payment'))


@app.route('/dice', methods=['POST', 'GET'])
def dice():
    # Fetch current dice game state
    current_game_state = game_state.get_game_state('dice')
    # Serialize using custom encoder
    serializable_state = json_dumps(current_game_state)
    return render_template('dice.html', initial_game_state=serializable_state)

@socketio.on('create_dice_game')
def handle_create_dice_game():
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}

    # Get current game state
    game_data = game_state.get_game_state('dice')

    # Verify fee
    if not game_state.verify_joining_fee(current_user.id):
        return {'error': 'Insufficient funds (₹100 required)'}

    # Only allow creation if no active game exists
    if game_data.get('status') == 'waiting' and not game_data.get('players'):
        # Deduct fee *before* creating game state
        if not game_state.deduct_joining_fee(current_user.id):
             return {'error': 'Failed to deduct fee'} # Handle deduction failure

        player_data = {
            'username': current_user.user_data['username'],
            'emoji': current_user.user_data.get('emoji', '🎲'),
            'user_id': current_user.id,
            'score': 0,
            'rolls': []
        }

        # Create new game with first player, set timer
        game_state.update_game_state({
            'players': [player_data],
            'timer': 120, # Set the 2-minute joining timer
            'created_at': datetime.now(timezone.utc),
            'status': 'waiting' # Ensure status is waiting
            # Keep existing game_id from reset_game
        }, 'dice')

        # Start countdown thread
        socketio.start_background_task(dice_game_countdown)
        app.logger.info(f"Dice game created by {current_user.user_data['username']}, starting countdown.")

        # Broadcast game created (send the whole state, making it serializable)
        game_data = game_state.get_game_state('dice')
        serializable_data = make_serializable(game_data)
        emit('dice_game_created', serializable_data, broadcast=True)

        return {'success': True, 'status': 'waiting'}
    elif game_data.get('status') != 'waiting':
         return {'error': 'Game is already active'}
    else: # status == 'waiting' but players exist
         return {'error': 'Game already created, please join instead'}


@socketio.on('join_dice_game')
def handle_join_dice_game():
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}

    # Get current game state
    game_data = game_state.get_game_state('dice')
    
    # Check if user is already in the game
    if any(p['user_id'] == current_user.id for p in game_data.get('players', [])):
        return {'error': 'You are already in the game'}

    # Verify fee *before* joining
    if not game_state.verify_joining_fee(current_user.id):
        return {'error': 'Insufficient funds (₹100 required)'}

    # Check if game is in waiting state and not full
    if game_data.get('status') == 'waiting' and len(game_data.get('players', [])) < 5:
        # Deduct fee *before* adding player
        if not game_state.deduct_joining_fee(current_user.id):
            return {'error': 'Failed to deduct fee'}

        player_data = {
            'username': current_user.user_data['username'],
            'emoji': current_user.user_data.get('emoji', '🎲'),
            'user_id': current_user.id,
            'score': 0,
            'rolls': []
        }

        # Check if this is the first player joining (should be handled by create, but double check)
        # if not game_data.get('players'):
        #     game_state.update_game_state({'players': [player_data], 'timer': 120}, 'dice')
        #     socketio.start_background_task(dice_game_countdown)
        # else:
        # Add player to existing game using $push simulation
        current_players = game_data.get('players', [])
        current_players.append(player_data)
        game_state.update_game_state({'players': current_players}, 'dice')

        # Broadcast updated player list
        # Emit the entire updated game state, making it serializable
        game_data = game_state.get_game_state('dice')
        serializable_data = make_serializable(game_data)
        emit('dice_player_joined', serializable_data, broadcast=True)

        return {'success': True, 'status': 'waiting'}
    elif game_data.get('status') == 'waiting' and len(game_data.get('players', [])) >= 5:
        return {'error': 'Game room is full'}
    else:
        return {'error': 'Game is not in waiting state or is full'}

def dice_game_countdown():
    app.logger.info(f"Starting dice game countdown thread for game {game_state.get_game_state('dice').get('game_id')}")
    while True:
        try:
            game_data = game_state.get_game_state('dice')
            game_id = game_data.get('game_id', 'N/A') # Get game_id for logging
            current_status = game_data.get('status')

            if current_status != 'waiting':
                app.logger.info(f"[Dice Countdown {game_id}] Status changed to {current_status}. Exiting loop.")
                break # Exit if game status is no longer 'waiting'

            current_timer = game_data.get('timer', 0)
            # app.logger.debug(f"[Dice Countdown {game_id}] Current timer: {current_timer}") # Optional debug log

            if current_timer > 0:
                # Decrement timer
                game_state.update_game_state({'timer': current_timer - 1}, 'dice')
                app.logger.info(f"[Dice Countdown {game_id}] Timer decremented to {current_timer - 1}")

                # Prepare data for emit
                timer_update_data = {
                    'time': current_timer - 1,
                    'status': 'waiting'
                }
                # Use socketio.emit in background thread, no broadcast=True needed
                socketio.emit('dice_timer_update', make_serializable(timer_update_data))
                # app.logger.debug(f"[Dice Countdown {game_id}] Emitted timer update: {timer_update_data}")
                
                # Sleep before next iteration
                socketio.sleep(1)
            else:
                # Timer expired
                app.logger.info(f"[Dice Countdown {game_id}] Joining timer expired.")
                players = game_data.get('players', [])
                if len(players) >= 2:
                    app.logger.info(f"[Dice Countdown {game_id}] Starting game with {len(players)} players.")
                    # ... (Start game logic) ...
                    game_state.update_game_state({
                        'status': 'active',
                        'current_round': 1,
                        'current_player_index': 0,
                        'player_timer': 10
                    }, 'dice')
                    updated_game_data = game_state.get_game_state('dice')
                    # Use socketio.emit in background thread, no broadcast=True needed
                    socketio.emit('dice_game_start', make_serializable(updated_game_data))
                    # ... (logging) ...
                else:
                    app.logger.info(f"[Dice Countdown {game_id}] Not enough players ({len(players)}). Cancelling game.")
                    # ... (Cancel game logic) ...
                    game_state.update_game_state({
                        'status': 'cancelled',
                        'players': []
                    }, 'dice')
                    cancel_data = {'reason': 'Not enough players'}
                    # Use socketio.emit in background thread, no broadcast=True needed
                    socketio.emit('dice_game_cancelled', make_serializable(cancel_data))
                    # Use socketio.emit in background thread
                    socketio.emit('dice_game_cancelled', make_serializable(cancel_data), broadcast=True)
                    # ... (refund/reset logic) ...
                
                app.logger.info(f"[Dice Countdown {game_id}] Timer logic complete. Exiting loop.")
                break # Exit loop after handling timer expiry
                
        except Exception as e:
            # Log any exception that occurs within the loop
            app.logger.error(f"[Dice Countdown {game_id}] Error in countdown loop: {e}", exc_info=True)
            # Optionally break the loop on error, or just log and continue (might spam logs)
            break # Exit loop on error to prevent potential spam

    app.logger.info(f"Exiting dice game countdown thread for game {game_state.get_game_state('dice').get('game_id')}")

@socketio.on('roll_dice')
@rate_limit(limit=1, period=5)  # Limit to 1 roll per 5 seconds
def handle_dice_roll(data=None): # Make data optional
    if not current_user.is_authenticated:
        return {'error': 'Authentication required'}
        
    game_data = game_state.get_game_state('dice')

    if game_data.get('status') != 'active':
        return {'error': 'Game is not active'}
        
    current_player_index = game_data.get('current_player_index', -1)
    if current_player_index == -1 or not game_data.get('players'):
        return {'error': 'Invalid game state - no players or index'}

    current_player = game_data['players'][current_player_index]
    if current_player['user_id'] != current_user.id:
        return {'error': 'Not your turn'}
    
    # Process dice roll logic - Roll only ONE die
    roll_value = random.randint(1, 6)
    
    # Update player's score and rolls using state update method
    # Need to adapt the GameState.update_game_state if it expects specific $inc/$push structure
    # For now, let's fetch, modify, and update the whole player object (less ideal but works with current update_game_state)
    updated_players = game_data['players']
    updated_players[current_player_index]['score'] = updated_players[current_player_index].get('score', 0) + roll_value
    # Append the single roll value
    if 'rolls' not in updated_players[current_player_index]:
         updated_players[current_player_index]['rolls'] = []
    updated_players[current_player_index]['rolls'].append(roll_value) 
    
    # Update game state with modified players list and reset timer
    game_state.update_game_state({
        'players': updated_players,
        'player_timer': 10  # Reset timer for next player
    }, 'dice')

    # Fetch updated player data for broadcast
    # updated_game_data = game_state.get_game_state('dice') # Already done implicitly by update
    updated_player_data = game_state.get_game_state('dice')['players'][current_player_index]
    
    # Broadcast result (reflecting single die roll)
    result_data = {
        'player': updated_player_data['username'],
        'roll': roll_value, # Send the single roll value
        'current_score': updated_player_data['score'],
        'round': game_data['current_round']
    }
    emit('dice_result', make_serializable(result_data), broadcast=True)
    
    # --- Advance Turn Logic --- (Remains the same) 
    players = updated_players # Use the modified list
    next_player_index = (current_player_index + 1) % len(players)
    
    game_state.update_game_state({
        'current_player_index': next_player_index
        # Timer reset was already included in the previous update
    }, 'dice')

    # ... (Rest of the turn/round/game end logic remains the same) ...
    # If back to first player, check if round is complete
    if next_player_index == 0:
        if game_data['current_round'] >= 3:
            # Game over - determine winner
            winner = max(game_data['players'], key=lambda p: p.get('score', 0)) # Use .get for safety
            prize = len(game_data['players']) * 100 * 0.8
            
            # ... (Update winner's wallet, store game results)
            db.users.update_one(
                {'_id': ObjectId(winner['user_id'])},
                {'$inc': {'user_data.wallet_balance': prize}}
            )
             # Ensure dice_games collection exists
            if 'dice_games' not in db.list_collection_names():
                db.create_collection('dice_games')
            db.dice_games.insert_one({
                'game_id': game_data['game_id'],
                'players': game_data['players'], # Store final player states
                'winner': winner['user_id'],
                'prize': prize,
                'created_at': game_data.get('created_at'),
                'completed_at': datetime.now(timezone.utc),
                'status': 'completed'
            })
            
            # Notify all players (make data serializable)
            end_game_data = {
                'winner': winner['username'],
                'prize': prize,
                'final_scores': [{'username': p['username'], 'score': p.get('score', 0)} for p in game_data['players']]
            }
            socketio.emit('dice_game_end', make_serializable(end_game_data))
            
            # Reset game state
            game_state.reset_game('dice')
        else:
            # Next round
            current_round = game_data.get('current_round', 0) # Fetch current round before incrementing
            game_state.update_game_state({
                'current_round': current_round + 1
            }, 'dice')
            
            round_start_data = {
                'round': current_round + 1,
                 'status': 'active'
            }
            socketio.emit('dice_round_start', make_serializable(round_start_data))
            
    # Notify about game update after turn advance (includes new player index and timer)
    final_state = game_state.get_game_state('dice')
    socketio.emit('dice_game_update', make_serializable(final_state))

    return {'success': True} # Return success to the roller


if __name__ == '__main__':
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
    except Exception as e:
        print(f"Server Error: {str(e)}")
