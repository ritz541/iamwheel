class WheelGame {
    constructor() {
        this.socket = io({
            transports: ['websocket', 'polling'],
            reconnection: true,
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 5000
        });
        
        this.players = [];
        this.usedEmojis = new Set();
        this.isBreakTime = false;
        this.setupElements();
        this.setupSocketListeners();
        this.initializeGrid();
        this.createPopupElements();
        
        console.log('WheelGame initialized');
    }

    createPopupElements() {
        // Create winner popup
        const popup = document.createElement('div');
        popup.className = 'winner-popup';
        popup.innerHTML = `
            <div class="title">Winner!</div>
            <div class="emoji"></div>
            <div class="player-name"></div>
        `;
        document.body.appendChild(popup);
        this.winnerPopup = popup;

        // Create grid expansion notice
        const notice = document.createElement('div');
        notice.className = 'grid-expansion-notice';
        this.wheelContainer.appendChild(notice);
        this.expansionNotice = notice;
    }

    setupElements() {
        this.wheelContainer = document.querySelector('.wheel-container');
        this.joinButton = document.getElementById('joinGame');
        this.statusElement = document.querySelector('.game-status');
        this.timerElement = document.getElementById('countdown');
        this.playersListElement = document.querySelector('.players-list');
        
        // Initialize grid container
        this.wheelContainer.innerHTML = '<div class="grid-container grid-2"></div>';
        this.gridContainer = this.wheelContainer.querySelector('.grid-container');
        
        if (this.joinButton) {
            this.joinButton.onclick = (e) => {
                e.preventDefault();
                this.joinGame();
            };
        }
    }

    showWinnerPopup(winner, duration = 5000) {
        const popup = this.winnerPopup;
        popup.querySelector('.emoji').textContent = winner.emoji;
        popup.querySelector('.player-name').textContent = winner.username;
        popup.classList.add('show');
        
        setTimeout(() => {
            popup.classList.remove('show');
        }, duration);
    }

    showExpansionNotice() {
        this.expansionNotice.textContent = 'Grid expanding...';
        this.expansionNotice.classList.add('show');
        
        setTimeout(() => {
            this.expansionNotice.classList.remove('show');
        }, 2000);
    }

    updateTimer(time, isBreak = false) {
        if (!this.timerElement) return;
        
        if (isBreak) {
            this.timerElement.className = 'break-timer';
            this.timerElement.textContent = `Next game starts in: ${time}s`;
        } else {
            this.timerElement.className = '';
            const minutes = Math.floor(time / 60);
            const seconds = time % 60;
            this.timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }
    }

    getGridSize(playerCount) {
        if (playerCount <= 3) return 2;  // 2x2 grid for 1-3 players
        if (playerCount <= 8) return 3;  // 3x3 grid for 4-8 players
        return 4;  // 4x4 grid for 9+ players
    }

    updateGrid() {
        const currentSize = this.getGridSize(this.players.length);
        const gridContainer = this.gridContainer;
        
        // Clear existing grid
        while (gridContainer.firstChild) {
            gridContainer.removeChild(gridContainer.firstChild);
        }
        
        // Update grid size class
        gridContainer.className = `grid-container grid-${currentSize}`;
        
        // Create empty cells
        const totalCells = currentSize * currentSize;
        for (let i = 0; i < totalCells; i++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            cell.dataset.index = i;
            gridContainer.appendChild(cell);
        }
        
        // Place players in random cells
        const emptyCells = Array.from(gridContainer.querySelectorAll('.grid-cell'));
        this.players.forEach((player, index) => {
            if (emptyCells.length > 0) {
                const randomIndex = Math.floor(Math.random() * emptyCells.length);
                const cell = emptyCells.splice(randomIndex, 1)[0];
                cell.textContent = player.emoji;
                cell.className = 'grid-cell player-cell';
                cell.style.backgroundColor = `var(--color-${(index % 8) + 1})`;
            }
        });
    }

    getRandomEmoji() {
        const availableEmojis = this.emojiPool.filter(emoji => !this.usedEmojis.has(emoji));
        if (availableEmojis.length === 0) return '🎲'; // Fallback emoji
        const randomIndex = Math.floor(Math.random() * availableEmojis.length);
        const selectedEmoji = availableEmojis[randomIndex];
        this.usedEmojis.add(selectedEmoji);
        return selectedEmoji;
    }

    getRandomEmptyCell() {
        const emptyCells = Array.from(this.gridContainer.querySelectorAll('.grid-cell:not(.player-cell)'));
        if (emptyCells.length === 0) return null;
        const randomIndex = Math.floor(Math.random() * emptyCells.length);
        return emptyCells[randomIndex];
    }

    updatePlayersList() {
        if (!this.playersListElement) return;
        
        this.playersListElement.innerHTML = '';
        
        this.players.forEach((player) => {
            const li = document.createElement('div');
            li.className = 'player-item';
            li.innerHTML = `
                <span class="player-name">${player.username}</span>
                <span class="emoji">${player.emoji || '🎲'}</span>
            `;
            this.playersListElement.appendChild(li);
        });
    }

    announceWinner(winner) {
        // Show winner popup
        this.showWinnerPopup(winner);

        // Remove non-winner cells with animation
        const playerCells = this.gridContainer.querySelectorAll('.player-cell');
        playerCells.forEach(cell => {
            const playerEmoji = cell.textContent;
            const isWinner = winner.emoji === playerEmoji;
            if (!isWinner) {
                cell.classList.add('fade-out');
            } else {
                cell.classList.add('winner');
            }
        });

        if (this.statusElement) {
            this.statusElement.innerHTML = `
                <div class="alert alert-success">
                    Winner: ${winner.username} ${winner.emoji}<br>
                    Prize: ₹${winner.prize}
                </div>
            `;
        }
    }

    setupSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            if (this.statusElement) {
                this.statusElement.textContent = 'Connected to server';
            }
            if (this.joinButton) {
                this.joinButton.disabled = false;
            }
        });

        this.socket.on('timer', (data) => {
            if (!this.timerElement) return;
            
            const isBreak = data.isBreak || false;
            if (isBreak) {
                this.timerElement.className = 'break-timer';
                this.timerElement.textContent = `Next game starts in: ${data.time}s`;
            } else {
                this.timerElement.className = '';
                const minutes = Math.floor(data.time / 60);
                const seconds = data.time % 60;
                this.timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        });

        this.socket.on('game_status', (data) => {
            console.log('Game status update:', data);
            
            // Update break time status
            this.isBreakTime = data.isBreak || false;
            
            if (data.players && Array.isArray(data.players)) {
                const oldSize = this.getGridSize(this.players.length);
                const newSize = this.getGridSize(data.players.length);
                
                if (newSize > oldSize) {
                    this.showExpansionNotice();
                }
                
                this.players = data.players;
                this.updateGrid();
                this.updatePlayersList();
            }
            
            // Update join button state
            if (this.joinButton) {
                this.joinButton.disabled = data.status !== 'joining' || this.isBreakTime;
            }
            
            // Update status message
            if (this.statusElement) {
                if (this.isBreakTime) {
                    this.statusElement.textContent = 'Break time - Next game starting soon';
                } else {
                    this.statusElement.textContent = data.status === 'joining' ? 'Waiting for players...' : 'Game in progress';
                }
            }
        });

        this.socket.on('player_joined', (data) => {
            console.log('Player joined:', data);
            if (data.players && Array.isArray(data.players)) {
                // Clear existing cells before updating
                const existingCells = this.gridContainer.querySelectorAll('.player-cell');
                existingCells.forEach(cell => {
                    cell.className = 'grid-cell';
                    cell.textContent = '';
                    cell.style.backgroundColor = '';
                });
                
                this.players = data.players;
                this.updateGrid();
                this.updatePlayersList();
                
                if (this.statusElement) {
                    this.statusElement.textContent = `Players in game: ${data.player_count}`;
                }
            }
        });

        this.socket.on('game_end', (data) => {
            console.log('Game ended:', data);
            if (data.winner) {
                const winner = this.players.find(p => p.username === data.winner);
                if (winner) {
                    this.announceWinner(winner);
                }
            }
            
            if (this.joinButton) {
                this.joinButton.disabled = true;
            }
        });
    }

    joinGame() {
        if (this.joinButton) {
            this.joinButton.disabled = true;
        }
        
        if (this.statusElement) {
            this.statusElement.textContent = 'Joining game...';
        }
        
        console.log('Attempting to join game...');
        this.socket.emit('join_game');
    }
}

// Initialize game when document is ready
document.addEventListener('DOMContentLoaded', () => {
    window.wheelGame = new WheelGame();
});
