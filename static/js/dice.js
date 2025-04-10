// Multiplayer Dice Game Logic
class DiceGame {
  constructor() {
    this.players = [];
    this.currentPlayerIndex = 0;
    this.currentRound = 1;
    this.maxRounds = 3;
    this.turnTimer = null;
    this.turnTimeLimit = 10; // seconds
    this.entryFee = 100;
    this.gameStarted = false;
    this.gameEnded = false;
    this.diceValue = 0;
    
    this.initElements();
    this.setupEventListeners();
  }
  
  initElements() {
    this.diceElement = document.getElementById('dice');
    this.rollBtn = document.getElementById('roll-btn');
    this.timerElement = document.getElementById('timer');
    this.playersContainer = document.getElementById('players-container');
  }
  
  setupEventListeners() {
    this.rollBtn.addEventListener('click', () => this.rollDice());
  }
  
  addPlayer(player) {
    this.players.push({
      id: player.id,
      name: player.name,
      rolls: [],
      total: 0
    });
    this.updateLeaderboard();
  }
  
  startGame() {
    this.gameStarted = true;
    this.startTurn();
  }
  
  startTurn() {
    if (this.gameEnded) return;
    
    // Enable roll button only for current player
    this.rollBtn.disabled = false;
    
    // Start turn timer
    let timeLeft = this.turnTimeLimit;
    this.timerElement.textContent = timeLeft;
    
    this.turnTimer = setInterval(() => {
      timeLeft--;
      this.timerElement.textContent = timeLeft;
      
      if (timeLeft <= 0) {
        this.handleTurnTimeout();
      }
    }, 1000);
    
    this.updateLeaderboard();
  }
  
  handleTurnTimeout() {
    clearInterval(this.turnTimer);
    this.players[this.currentPlayerIndex].rolls.push(-1);
    this.players[this.currentPlayerIndex].total += -1;
    this.nextTurn();
  }
  
  rollDice() {
    // Disable button during roll
    this.rollBtn.disabled = true;
    
    // Show rolling animation
    this.diceElement.textContent = '...';
    
    // Simulate dice roll with delay
    setTimeout(() => {
      const value = Math.floor(Math.random() * 6) + 1;
      this.diceValue = value;
      this.diceElement.textContent = value;
      
      // Record roll and update score
      this.players[this.currentPlayerIndex].rolls.push(value);
      this.players[this.currentPlayerIndex].total += value;
      
      // Update leaderboard
      this.updateLeaderboard();
      
      // Move to next turn after short delay
      setTimeout(() => this.nextTurn(), 1000);
    }, 1000);
  }
  
  nextTurn() {
    clearInterval(this.turnTimer);
    
    // Check if round is complete
    if (this.currentPlayerIndex >= this.players.length - 1) {
      this.currentRound++;
      this.currentPlayerIndex = 0;
      
      // Check if game is over
      if (this.currentRound > this.maxRounds) {
        this.endGame();
        return;
      }
    } else {
      this.currentPlayerIndex++;
    }
    
    // Start next turn
    this.startTurn();
  }
  
  updateLeaderboard() {
    this.playersContainer.innerHTML = '';
    
    // Sort players by total score (descending)
    const sortedPlayers = [...this.players].sort((a, b) => b.total - a.total);
    
    sortedPlayers.forEach((player, index) => {
      const playerRow = document.createElement('div');
      playerRow.className = 'player-row';
      
      // Highlight current player
      if (player.id === this.players[this.currentPlayerIndex].id) {
        playerRow.classList.add('current-player');
      }
      
      // Create player info
      const playerInfo = document.createElement('div');
      playerInfo.textContent = `${index + 1}. ${player.name}`;
      
      // Create roll display
      const rollDisplay = document.createElement('div');
      rollDisplay.textContent = `Rolls: ${player.rolls.join(', ')} | Total: ${player.total}`;
      
      playerRow.appendChild(playerInfo);
      playerRow.appendChild(rollDisplay);
      this.playersContainer.appendChild(playerRow);
    });
  }
  
  endGame() {
    this.gameEnded = true;
    this.rollBtn.disabled = true;
    
    // Calculate winners and distribute prizes
    const maxScore = Math.max(...this.players.map(p => p.total));
    const winners = this.players.filter(p => p.total === maxScore);
    const prizePool = this.players.length * this.entryFee;
    const winnerShare = prizePool * 0.8 / winners.length;
    
    // Show game over message with winners
    alert(`Game Over! Winners: ${winners.map(w => w.name).join(', ')}. Each wins ₹${winnerShare}`);
  }
}

// Initialize game when page loads
window.addEventListener('DOMContentLoaded', () => {
  // For testing - in real app these would come from server
  const game = new DiceGame();
  
  // Add test players
  game.addPlayer({ id: 1, name: 'Player 1' });
  game.addPlayer({ id: 2, name: 'Player 2' });
  game.addPlayer({ id: 3, name: 'Player 3' });
  
  // Start game after 3 seconds (in real app this would wait for server)
  setTimeout(() => game.startGame(), 3000);
});