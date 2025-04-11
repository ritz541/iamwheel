// Multiplayer Dice Game Logic
class DiceGame {
  constructor(initialState, socketInstance) {
    console.log("Initializing DiceGame with state:", initialState);
    this.socket = socketInstance;
    this.players = initialState?.players || [];
    this.currentPlayerIndex = initialState?.current_player_index ?? 0;
    this.currentRound = initialState?.current_round || 0; // Start at round 0 if no state
    this.gameStatus = initialState?.status || 'waiting';
    this.gameId = initialState?.game_id || null;
    this.maxRounds = 3;
    this.entryFee = 100;
    this.diceValue = initialState?.last_roll || 0;

    // Determine initial button states
    this.gameStarted = this.gameStatus === 'active';
    this.gameEnded = this.gameStatus === 'completed' || this.gameStatus === 'cancelled';
    
    this.initElements();
    this.setupEventListeners();

    // Initial UI setup based on loaded state
    this.updateUIFromState(initialState);
    if (initialState?.last_roll) {
        this.updateDiceDisplay(initialState.last_roll);
    }
  }

  initElements() {
    this.diceElement = document.getElementById('dice');
    this.rollBtn = document.getElementById('roll-btn');
    this.joinBtn = document.getElementById('join-game-btn');
    this.createBtn = document.getElementById('create-game-btn');
    this.timerElement = document.getElementById('timer');
    this.timerLabelElement = document.getElementById('timer-label');
    this.playersContainer = document.getElementById('players-container');
    this.gameStatusElement = document.getElementById('game-status');
    this.roundElement = document.getElementById('current-round');
    
    // Initialize the dice SVG
    this.initDiceSVG();
  }
  
  initDiceSVG() {
    // Replace the text with SVG
    const diceSVG = `
      <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
        <!-- Dice face background -->
        <rect x="5" y="5" width="90" height="90" rx="15" ry="15" fill="white" stroke="black" stroke-width="2" />
        
        <!-- Dice dots for all faces -->
        <g id="face1">
          <!-- Center dot -->
          <circle id="center-dot" cx="50" cy="50" r="8" fill="black" />
        </g>
        
        <g id="face2" style="display:none">
          <!-- Top-left dot -->
          <circle cx="25" cy="25" r="8" fill="black" />
          <!-- Bottom-right dot -->
          <circle cx="75" cy="75" r="8" fill="black" />
        </g>
        
        <g id="face3" style="display:none">
          <!-- Top-left dot -->
          <circle cx="25" cy="25" r="8" fill="black" />
          <!-- Center dot -->
          <circle cx="50" cy="50" r="8" fill="black" />
          <!-- Bottom-right dot -->
          <circle cx="75" cy="75" r="8" fill="black" />
        </g>
        
        <g id="face4" style="display:none">
          <!-- Top-left dot -->
          <circle cx="25" cy="25" r="8" fill="black" />
          <!-- Top-right dot -->
          <circle cx="75" cy="25" r="8" fill="black" />
          <!-- Bottom-left dot -->
          <circle cx="25" cy="75" r="8" fill="black" />
          <!-- Bottom-right dot -->
          <circle cx="75" cy="75" r="8" fill="black" />
        </g>
        
        <g id="face5" style="display:none">
          <!-- Top-left dot -->
          <circle cx="25" cy="25" r="8" fill="black" />
          <!-- Top-right dot -->
          <circle cx="75" cy="25" r="8" fill="black" />
          <!-- Center dot -->
          <circle cx="50" cy="50" r="8" fill="black" />
          <!-- Bottom-left dot -->
          <circle cx="25" cy="75" r="8" fill="black" />
          <!-- Bottom-right dot -->
          <circle cx="75" cy="75" r="8" fill="black" />
        </g>
        
        <g id="face6" style="display:none">
          <!-- Top-left dot -->
          <circle cx="25" cy="25" r="8" fill="black" />
          <!-- Top-right dot -->
          <circle cx="75" cy="25" r="8" fill="black" />
          <!-- Middle-left dot -->
          <circle cx="25" cy="50" r="8" fill="black" />
          <!-- Middle-right dot -->
          <circle cx="75" cy="50" r="8" fill="black" />
          <!-- Bottom-left dot -->
          <circle cx="25" cy="75" r="8" fill="black" />
          <!-- Bottom-right dot -->
          <circle cx="75" cy="75" r="8" fill="black" />
        </g>
      </svg>
    `;
    
    // Replace the content of the dice element
    this.diceElement.innerHTML = diceSVG;
    
    // Set initial display to question mark (no face shown)
    this.hideAllDiceFaces();
  }
  
  hideAllDiceFaces() {
    // Hide all dice faces
    if (this.diceElement) {
      const svg = this.diceElement.querySelector('svg');
      if (svg) {
        for (let i = 1; i <= 6; i++) {
          const face = svg.querySelector(`#face${i}`);
          if (face) {
            face.style.display = 'none';
          }
        }
      }
    }
  }
  
  updateDiceDisplay(value) {
    if (!this.diceElement) return;
    
    // Record the dice value
    this.diceValue = value;
    
    // Hide all faces
    this.hideAllDiceFaces();
    
    // Get the SVG element
    const svg = this.diceElement.querySelector('svg');
    if (!svg) return;
    
    // Show the appropriate face based on the roll
    if (value >= 1 && value <= 6) {
      const face = svg.querySelector(`#face${value}`);
      if (face) {
        face.style.display = 'block';
      }
    } else {
      // Show question mark if value is invalid
      // For now, we'll just leave all faces hidden
    }
    
    // Add a rolling animation
    this.diceElement.classList.add('rolling');
    setTimeout(() => {
      this.diceElement.classList.remove('rolling');
    }, 500);
  }
  
  setupEventListeners() {
    // Use this.socket to emit events
    this.createBtn?.addEventListener('click', () => this.socket.emit('create_dice_game'));
    this.joinBtn?.addEventListener('click', () => this.socket.emit('join_dice_game'));
    this.rollBtn?.addEventListener('click', () => this.socket.emit('roll_dice'));
    
    // Socket listeners remain the same, using the global 'socket' or the instance passed implicitly
    // It's slightly cleaner if the listeners are also set up using this.socket
    this.socket.on('dice_player_joined', (data) => {
      console.log('Event: dice_player_joined', data);
      this.updateUIFromState(data);
    });

    this.socket.on('dice_game_created', (data) => {
       console.log('Event: dice_game_created', data);
       this.updateUIFromState(data);
    });
    
    this.socket.on('dice_game_update', (data) => {
      console.log('Event: dice_game_update', data);
      this.updateUIFromState(data);
    });
    
    this.socket.on('dice_timer_update', (data) => {
      console.log('Event: dice_timer_update', data);
      this.updateTimerDisplay(data.time, data.status);
    });

    this.socket.on('dice_game_start', (data) => {
      console.log("Event: dice_game_start", data);
      this.updateUIFromState(data);
    });

    this.socket.on('dice_game_end', (data) => {
      console.log("Event: dice_game_end", data);
      this.gameStatus = 'completed';
      this.updateUIFromState(data); // Update with final scores
      alert(`Game Over! Winner: ${data.winner}. Prize: ₹${data.prize}`);
    });

    this.socket.on('dice_game_cancelled', (data) => {
      console.log("Event: dice_game_cancelled", data);
       this.gameStatus = 'cancelled';
       this.updateUIFromState({ status: 'cancelled', players: [] }); // Reset state
       alert(`Game Cancelled: ${data.reason}`);
    });
    
    // Listen for single roll result
    this.socket.on('dice_result', (data) => {
      console.log('Event: dice_result', data);
      // Update the dice display immediately with the roll value
      this.updateDiceDisplay(data.roll);
    });

    this.socket.on('dice_game_update', (data) => {
      console.log('Event: dice_game_update', data);
      // Update dice display if a recent roll value is included
      if (data.last_roll) {
          this.updateDiceDisplay(data.last_roll);
      }
      this.updateUIFromState(data);
    });
    
    this.socket.on('connect_error', (err) => {
        console.error('Connection Error:', err);
        alert('Failed to connect to the server.');
    });

    this.socket.on('disconnect', (reason) => {
        console.log('Disconnected:', reason);
        // Optionally grey out UI or show disconnected message
    });

    this.socket.on('dice_error', (data) => {
        console.error('Dice Game Error:', data.error);
        alert(`Error: ${data.error}`); // Show error to user
    });
  }

  updateUIFromState(state) {
    if (!state) return;

    // Update internal state representation
    this.players = state.players || this.players;
    this.currentPlayerIndex = state.current_player_index ?? this.currentPlayerIndex;
    this.currentRound = state.current_round || this.currentRound;
    this.gameStatus = state.status || this.gameStatus;
    this.gameId = state.game_id || this.gameId;
    this.gameStarted = this.gameStatus === 'active';
    this.gameEnded = this.gameStatus === 'completed' || this.gameStatus === 'cancelled';

    // Update UI Elements
    if (this.gameStatusElement) this.gameStatusElement.textContent = this.gameStatus;
    if (this.roundElement) this.roundElement.textContent = this.gameStarted ? this.currentRound : '-';
    
    this.updateLeaderboard();
    this.updateTimerDisplay(state.timer ?? state.player_timer ?? 0, this.gameStatus);
    this.updateButtonStates();
  }

  updateTimerDisplay(time, status) {
    if (!this.timerElement || !this.timerLabelElement) return;

    let label = "Time left";
    time = time ?? 0;
    status = status || this.gameStatus;

    if (status === 'waiting') {
      label = "Joining Ends In";
    } else if (status === 'active') {
      label = "Roll Ends In";
    } else if (status === 'completed' || status === 'cancelled') {
      label = "Game Over";
      time = "-";
    } else {
        label = "Loading Timer"; // Default/Unknown state
        time = "--";
    }

    this.timerLabelElement.textContent = label;
    this.timerElement.textContent = time;
  }

  updateButtonStates() {
    if (!this.createBtn || !this.joinBtn || !this.rollBtn) return;

    const canCreate = this.gameStatus === 'waiting' && this.players.length === 0;
    const canJoin = this.gameStatus === 'waiting' && this.players.length > 0 && this.players.length < 5;
    const isMyTurn = this.gameStatus === 'active' && 
                     this.players.length > 0 &&
                     this.players[this.currentPlayerIndex]?.user_id === currentUserId;

    this.createBtn.style.display = canCreate ? 'inline-block' : 'none';
    this.joinBtn.style.display = canJoin ? 'inline-block' : 'none';
    this.rollBtn.style.display = (this.gameStatus === 'active') ? 'inline-block' : 'none';

    // Enable/disable Roll button
    if (this.gameStatus === 'active') {
        this.rollBtn.disabled = !isMyTurn;
        if (!isMyTurn) {
             this.rollBtn.classList.add('is-disabled');
        } else {
             this.rollBtn.classList.remove('is-disabled');
        }
    } else {
         this.rollBtn.disabled = true;
         this.rollBtn.classList.add('is-disabled');
    }
    
    // Hide Create/Join if game is active or ended
    if (this.gameStatus !== 'waiting') {
         this.createBtn.style.display = 'none';
         this.joinBtn.style.display = 'none';
    }
  }

  updateLeaderboard() {
    if (!this.playersContainer) return;
    this.playersContainer.innerHTML = ''; // Clear previous entries

    if (this.players.length === 0) {
        this.playersContainer.innerHTML = '<p>Waiting for players...</p>';
        return;
    }

    // Sort players by score if game is active/ended, otherwise by join order (implicit)
    const sortedPlayers = [...this.players];
    if (this.gameStarted || this.gameEnded) {
        sortedPlayers.sort((a, b) => (b.score || 0) - (a.score || 0));
    }
    
    sortedPlayers.forEach((player, index) => {
      const playerRow = document.createElement('div');
      playerRow.className = 'player-row nes-container is-rounded is-dark'; 
      
      // Highlight current player in active game
      if (this.gameStatus === 'active' && player.user_id === this.players[this.currentPlayerIndex]?.user_id) {
        playerRow.classList.add('is-primary');
        playerRow.classList.remove('is-dark'); 
      }
      
      const playerInfo = document.createElement('div');
      playerInfo.innerHTML = 
        `<span class="player-rank">#${index + 1}</span> 
         <span class="player-emoji">${player.emoji || '👤'}</span> 
         <span class="player-name">${player.username}</span>`;
      
      const scoreDisplay = document.createElement('div');
      scoreDisplay.className = 'player-score';
      if (this.gameStarted || this.gameEnded) {
          scoreDisplay.textContent = `Score: ${player.score || 0}`;
          // Add roll history display (list of single numbers)
          if (player.rolls && player.rolls.length > 0) {
              const rollsText = player.rolls.join(', ');
              const rollsDiv = document.createElement('div');
              rollsDiv.className = 'player-rolls nes-text is-small';
              rollsDiv.textContent = `Rolls: [${rollsText}]`;
              scoreDisplay.appendChild(rollsDiv); // Append rolls below score
          }
      } else {
          scoreDisplay.textContent = `Joined`;
      }
      
      playerRow.appendChild(playerInfo);
      playerRow.appendChild(scoreDisplay);
      this.playersContainer.appendChild(playerRow);
    });
  }
}

// Initialize game when page loads
window.addEventListener('DOMContentLoaded', () => {
  if (typeof io === 'undefined') {
    console.error("Socket.IO client library not found.");
    alert("Error connecting to game server. Please refresh.");
    return;
  }
  
  // Define socket connection FIRST
  const socket = io(); 
  
  // Create the DiceGame instance, passing the socket and initial state
  const game = new DiceGame(initialGameState, socket);
  
  console.log("Dice game client initialized with state:", initialGameState);
});