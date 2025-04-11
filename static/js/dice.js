// Helper function to show NES.css dialogs
function showNesDialog(message, type = 'default', options = {}) { 
    // options can include { winnerName: string, prize: number, players: array }
    const { winnerName, prize, players } = options;
    console.log("[showNesDialog] Received options:", { winnerName, prize, players }); // Log received options

    // Check if a dialog already exists, remove it first
    const existingDialog = document.getElementById('nes-game-dialog');
    if (existingDialog) {
        existingDialog.remove();
    }

    // Create dialog element
    const dialog = document.createElement('dialog');
    let dialogClass = 'nes-dialog';
    let iconClass = 'nes-icon star is-small'; // Default icon
    let titleText = 'Notification';
    let isWinnerDialog = false;

    switch (type) {
        case 'success':
            if (winnerName !== undefined && prize !== undefined) { // Check if winner details provided
                 console.log("[showNesDialog] Conditions met for winner dialog."); // Log condition check
                 dialogClass += ' is-success is-winner-dialog'; // Add specific class for winner
                 iconClass = 'nes-icon trophy is-large'; // Larger trophy icon
                 titleText = 'Game Over!';
                 isWinnerDialog = true;
            } else {
                console.log("[showNesDialog] Conditions NOT met for winner dialog (winnerName or prize missing)."); // Log condition check failure
                dialogClass += ' is-success';
                iconClass = 'nes-icon like is-small'; // Regular success icon
                titleText = 'Success!';
            }
            break;
        case 'warning':
            dialogClass += ' is-warning';
            iconClass = 'nes-icon exclamation is-small';
            titleText = 'Warning';
            break;
        case 'error':
            dialogClass += ' is-error';
            iconClass = 'nes-icon close is-small';
            titleText = 'Error';
            break;
        default:
             dialogClass += ' is-light'; 
    }

    console.log("[showNesDialog] isWinnerDialog flag:", isWinnerDialog); // Log the flag value

    dialog.className = dialogClass;
    dialog.id = 'nes-game-dialog';
    dialog.style.position = 'fixed'; 
    dialog.style.top = '50%'; // Center vertically
    dialog.style.left = '50%';
    dialog.style.transform = 'translate(-50%, -50%)'; // Centering transform
    dialog.style.zIndex = '1000';
    dialog.style.minWidth = '350px'; // Slightly wider for winner info
    dialog.style.maxWidth = '90%'; 

    // Create form (required by nes.css dialog)
    const form = document.createElement('form');
    form.method = 'dialog';

    // Add title with icon
    const titleContainer = document.createElement('p');
    titleContainer.className = 'title';
    titleContainer.style.display = 'flex';
    titleContainer.style.alignItems = 'center';
    titleContainer.style.gap = '0.5rem'; // Space between icon and text
    titleContainer.innerHTML = `<i class="${iconClass}"></i> ${titleText}`;
    form.appendChild(titleContainer);

    const messageBody = document.createElement('div'); // Use a div for more control
    messageBody.style.marginTop = '1rem';
    messageBody.style.marginBottom = '1.5rem';
    messageBody.style.textAlign = 'center';

    if (isWinnerDialog) {
        // Construct winner message with highlighting
        const congratsText = document.createElement('p');
        congratsText.innerHTML = 
            `Congratulations <strong class="winner-name nes-text is-warning">${winnerName}</strong>!`; // Use nes-text is-warning for name
        messageBody.appendChild(congratsText);

        const prizeText = document.createElement('p');
        prizeText.style.marginTop = '0.5rem';
        prizeText.innerHTML = `You won the prize of <strong class="nes-text is-success">₹${prize}</strong>!`; // Highlight prize
        messageBody.appendChild(prizeText);

        messageBody.appendChild(document.createElement('hr')); // Separator

        if (players && players.length > 0) {
            const scoreTitle = document.createElement('p');
            scoreTitle.style.marginBottom = '0.5rem';
            scoreTitle.style.textAlign = 'left';
            scoreTitle.innerHTML = '<strong>Final Scores:</strong>';
            messageBody.appendChild(scoreTitle);

            // Sort players by score descending
            const sortedPlayers = [...players].sort((a, b) => (b.score || 0) - (a.score || 0));
            const scoreList = document.createElement('ul');
            scoreList.className = 'nes-list is-disc'; 
            scoreList.style.textAlign = 'left';
            scoreList.style.marginBottom = '0'; 

            sortedPlayers.forEach(p => {
                const listItem = document.createElement('li');
                // Format the rolls array, handle if it's missing
                const rollsText = p.rolls && Array.isArray(p.rolls) ? `(Rolls: ${p.rolls.join(', ')})` : '(No rolls data)';
                listItem.textContent = `${p.username || 'Player'}: ${p.score || 0} ${rollsText}`;
                
                 if (p.username === winnerName) {
                     listItem.style.fontWeight = 'bold'; 
                 }
                 // Add small spacing below each item for readability
                 listItem.style.marginBottom = '0.3rem'; 
                scoreList.appendChild(listItem);
            });
            messageBody.appendChild(scoreList);
        }
    } else {
        messageBody.textContent = message; // Use the standard message
    }
    form.appendChild(messageBody);

    // Add close button menu
    const menu = document.createElement('menu');
    menu.className = 'dialog-menu';
    menu.style.textAlign = 'center'; 

    const closeButton = document.createElement('button');
    let btnClass = 'nes-btn';
     switch (type) {
        case 'success': btnClass += isWinnerDialog ? ' is-success' : ' is-success'; break; // Keep success style
        case 'warning': btnClass += ' is-warning'; break;
        case 'error': btnClass += ' is-error'; break;
        default: btnClass += ' is-primary';
    }
    closeButton.className = btnClass;
    closeButton.textContent = 'Ok';
    closeButton.onclick = (e) => {
        e.preventDefault(); 
        dialog.close();
        dialog.remove(); 
    };
    menu.appendChild(closeButton);
    form.appendChild(menu);

    dialog.appendChild(form);
    document.body.appendChild(dialog);

    // Show the dialog
    dialog.showModal();
}

// Multiplayer Dice Game Logic
// Constants for dice management
const MIN_DICE = 1;
const MAX_DICE = 5;

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
    this.diceCount = 1; // Only one die as per requirement
    this.diceValues = []; // Store individual dice values

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
    
    // Initialize dice
    this.loadDice();
  }

  initElements() {
    this.diceContainer = document.getElementById('dice');
    this.singleDiceElement = document.getElementById('single-dice');
    this.addDiceBtn = document.getElementById('add-dice');
    this.rollBtn = document.getElementById('roll-btn');
    this.joinBtn = document.getElementById('join-game-btn');
    this.createBtn = document.getElementById('create-game-btn');
    this.timerElement = document.getElementById('timer');
    this.timerLabelElement = document.getElementById('timer-label');
    this.playersContainer = document.getElementById('players-container');
    this.gameStatusElement = document.getElementById('game-status');
    this.roundElement = document.getElementById('current-round');
    
    // Initialize the dot map for single dice
    this.initDotMap();
    
    // Hide the add dice button since we only want one dice
    if (this.addDiceBtn) {
      this.addDiceBtn.style.display = 'none';
    }
  }
  
  initDotMap() {
    // Define the dot positions for each dice face (1-6)
    this.dotMap = {
      1: [5],
      2: [1, 9],
      3: [1, 5, 9],
      4: [1, 3, 7, 9],
      5: [1, 3, 5, 7, 9],
      6: [1, 3, 4, 6, 7, 9],
    };
    
    // Hide all dots initially
    this.hideAllDots();
  }
  
  hideAllDots() {
    // Hide all dots
    if (this.diceElement) {
      const dots = this.diceElement.querySelectorAll('.dot');
      console.log("Found dots to hide:", dots.length);
      dots.forEach(dot => {
        dot.classList.remove('show');
      });
    } else {
      console.warn("Cannot hide dots: dice element not found");
    }
  }
  
  loadDice() {
    // Show the single dice element and set it as the active dice element
    if (this.singleDiceElement) {
      // First, ensure the dice container is ready
      if (this.diceContainer) {
        this.diceContainer.innerHTML = '';
      }
      
      // Set up the single dice element
      this.singleDiceElement.style.display = 'grid';
      this.diceElement = this.singleDiceElement;
      
      // Apply the dice styling to match the design
      this.diceElement.style.width = '60px';
      this.diceElement.style.height = '60px';
      this.diceElement.style.backgroundColor = 'white';
      this.diceElement.style.border = '3px solid #333';
      this.diceElement.style.borderRadius = '10px';
      this.diceElement.style.display = 'grid';
      this.diceElement.style.gridTemplateColumns = 'repeat(3, 1fr)';
      this.diceElement.style.gridTemplateRows = 'repeat(3, 1fr)';
      this.diceElement.style.gap = '2px';
      this.diceElement.style.padding = '4px';
      this.diceElement.style.boxShadow = '3px 3px 8px rgba(0, 0, 0, 0.2)';
      this.diceElement.style.transition = 'transform 0.3s ease';
      
      // Clear existing dots and recreate them
      this.diceElement.innerHTML = '';
      console.log("Creating dot elements for dice");
      for (let i = 1; i <= 9; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        dot.id = 'd' + i;
        this.diceElement.appendChild(dot);
      }
      
      // Hide the add dice button
      if (this.addDiceBtn) {
        this.addDiceBtn.style.display = 'none';
      }
      
      // Add the dice to the container
      if (this.diceContainer) {
        this.diceContainer.appendChild(this.diceElement);
      }
      
      // Add the CSS file for dice animation
      if (!document.querySelector('link[href*="dice-fix.css"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/dice-fix.css';
        document.head.appendChild(link);
      }
      
      console.log("Dice initialized with", this.diceElement.querySelectorAll('.dot').length, "dots");
    } else {
      console.error("Single dice element not found");
    }
  }
  
  updateDiceDisplay(value) {
    if (!this.diceElement) {
      console.error("Cannot update dice: dice element not found");
      return;
    }
    
    console.log("Updating dice display with value:", value);
    
    // Record the dice value
    this.diceValue = value;
    
    // Reset - hide all dots
    this.hideAllDots();
    
    // Make sure we have dots in the dice
    if (this.diceElement.querySelectorAll('.dot').length === 0) {
      console.log("Recreating dots for dice display");
      for (let i = 1; i <= 9; i++) {
        const dot = document.createElement('div');
        dot.className = 'dot';
        dot.id = 'd' + i;
        this.diceElement.appendChild(dot);
      }
    }
    
    // First remove any existing rolling class to reset animation
    this.diceElement.classList.remove('rolling');
    
    // Force a reflow to ensure the animation restarts
    void this.diceElement.offsetWidth;
    
    // Add the rolling class for 3D animation
    this.diceElement.classList.add('rolling');
    
    // After animation completes, show the correct dots
    setTimeout(() => {
      // Show the appropriate dots based on the roll
      if (value >= 1 && value <= 6) {
        const showDots = this.dotMap[value];
        console.log("Showing dots for value", value, "positions:", showDots);
        
        // First ensure all dots are hidden
        this.diceElement.querySelectorAll('.dot').forEach(dot => {
          dot.classList.remove('show');
        });
        
        // Then show only the dots for this value
        showDots.forEach(pos => {
          // Find the dot within the dice element
          const dot = this.diceElement.querySelector("#d" + pos);
          if (dot) {
            dot.classList.add("show");
            console.log("Showing dot:", pos);
          } else {
            console.warn("Dot element not found for position:", pos);
          }
        });
      }
      
      // Keep the dice in its final position
      this.diceElement.classList.remove('rolling');
    }, 1000);
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
      console.log("[dice_game_end] Received data:", JSON.stringify(data)); 
      this.gameStatus = 'completed';
      this.updateUIFromState(data); 
      console.log("[dice_game_end] this.players state (may not have final scores):", JSON.stringify(this.players)); 
      
      // Delay the winner dialog by 1 second 
      setTimeout(() => {
          const dialogOptions = { 
              winnerName: data.winner, 
              prize: data.prize, 
              players: data.final_scores 
          }; 
          console.log("[dice_game_end setTimeout] Options being passed to showNesDialog:", JSON.stringify(dialogOptions)); 
          showNesDialog('Game Over!', 'success', dialogOptions); 
      }, 1000); // Reduced delay to 1000ms
    });

    this.socket.on('dice_game_cancelled', (data) => {
      console.log("Event: dice_game_cancelled", data);
       this.gameStatus = 'cancelled';
       this.updateUIFromState({ status: 'cancelled', players: [] }); // Reset state
       showNesDialog(`Game Cancelled: ${data.reason}`, 'warning'); // No winner info here
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
        showNesDialog('Failed to connect to the game server. Please try refreshing.', 'error');
    });

    this.socket.on('disconnect', (reason) => {
        console.log('Disconnected:', reason);
        // Optionally grey out UI or show disconnected message
    });

    this.socket.on('dice_error', (data) => {
        console.error('Dice Game Error:', data.error);
        showNesDialog(`Error: ${data.error}`, 'error');
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
      // Simpler row structure
      playerRow.className = 'player-row nes-text'; 
      playerRow.style.padding = '8px';
      playerRow.style.marginBottom = '5px'; 
      playerRow.style.border = '2px solid #dedede'; // Simple border
      playerRow.style.borderRadius = '4px';
      playerRow.style.display = 'flex';
      playerRow.style.justifyContent = 'space-between';
      playerRow.style.alignItems = 'center';
      
      let turnIndicatorText = '';
      // Highlight current player in active game
      if (this.gameStatus === 'active' && player.user_id === this.players[this.currentPlayerIndex]?.user_id) {
        playerRow.classList.add('is-primary'); // Keep NES primary highlight
        turnIndicatorText = ' (Your Turn)'; // Add text indicator
      }
      
      // Consistent highlight for the viewing user
      if (player.user_id === currentUserId) {
           playerRow.classList.add('current-user-highlight'); 
      }

      // Left side: Rank, Name, Turn Indicator
      const playerInfo = document.createElement('span');
      playerInfo.style.fontWeight = 'bold';
      playerInfo.textContent = `#${index + 1} ${player.username || 'Player'}${turnIndicatorText}`;

      // Right side: Score and Rolls
      const scoreDisplay = document.createElement('div'); // Container for score/rolls
      scoreDisplay.className = 'player-score';
      scoreDisplay.style.textAlign = 'right';

      const scoreText = document.createElement('span');
      if (this.gameStarted || this.gameEnded) {
          scoreText.textContent = `Score: ${player.score || 0}`;
          scoreDisplay.appendChild(scoreText);

          // Add roll history display (list of single numbers)
          if (player.rolls && player.rolls.length > 0) {
              const rollsText = player.rolls.join(', ');
              const rollsDiv = document.createElement('div');
              rollsDiv.className = 'player-rolls nes-text is-small';
              rollsDiv.style.marginTop = '3px';
              rollsDiv.textContent = `Rolls: [${rollsText}]`;
              scoreDisplay.appendChild(rollsDiv); // Append rolls below score
          }
      } else {
          scoreText.textContent = `Joined`;
          scoreDisplay.appendChild(scoreText);
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
    showNesDialog("Error connecting to game server. Please refresh.", 'error');
    return;
  }
  
  // Define socket connection FIRST
  const socket = io(); 
  
  // Create the DiceGame instance, passing the socket and initial state
  const game = new DiceGame(initialGameState, socket);
  
  console.log("Dice game client initialized with state:", initialGameState);
});