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
        const gridSize = this.getGridSize(this.players.length);
        const currentClass = this.gridContainer.className.match(/grid-\d/)?.[0] || 'grid-2';
        const newClass = `grid-${gridSize}`;
        
        if (currentClass !== newClass) {
            this.gridContainer.classList.remove(currentClass);
            this.gridContainer.classList.add(newClass);
        }
        
        // Clear existing cells
        this.gridContainer.innerHTML = '';
        
        // Create grid cells
        const totalCells = gridSize * gridSize;
        const playerPositions = this.getRandomPositions(totalCells, this.players.length);
        
        for (let i = 0; i < totalCells; i++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            
            const playerIndex = playerPositions.indexOf(i);
            if (playerIndex !== -1) {
                const player = this.players[playerIndex];
                cell.innerHTML = `
                    <div class="player-emoji">${player.emoji}</div>
                    <div class="player-name">${player.username}</div>
                `;
                cell.classList.add('occupied');
            }
            
            this.gridContainer.appendChild(cell);
        }
    }

    updatePlayersList() {
        if (!this.playersListElement) return;
        
        this.playersListElement.innerHTML = this.players.map(player => `
            <div class="player-item">
                <span class="player-emoji">${player.emoji}</span>
                <span class="player-name">${player.username}</span>
            </div>
        `).join('');
    }

    getRandomPositions(totalCells, playerCount) {
        const positions = [];
        for (let i = 0; i < playerCount; i++) {
            let position;
            do {
                position = Math.floor(Math.random() * totalCells);
            } while (positions.includes(position));
            positions.push(position);
        }
        return positions;
    }

    showNotification(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `game-notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // Trigger animation
        setTimeout(() => notification.classList.add('show'), 10);
        
        // Remove after duration
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    setupSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('game_status', (data) => {
            this.players = data.players;
            this.isBreakTime = data.isBreak;
            this.updateTimer(data.timer, data.isBreak);
            this.updateGrid();
            this.updatePlayersList();
        });

        this.socket.on('player_joined', (data) => {
            if (data.success) {
                // Show notification
                this.showNotification(`${data.new_player.emoji} ${data.message}`, 'success');
                
                // Update grid if needed
                const oldPlayerCount = this.players.length;
                this.players = data.players;
                
                if (this.getGridSize(oldPlayerCount) !== this.getGridSize(this.players.length)) {
                    this.showExpansionNotice();
                }
                
                this.updateGrid();
                this.updatePlayersList();
            }
        });

        this.socket.on('winner_selected', (data) => {
            this.showWinnerPopup(data.winner);
            this.isBreakTime = true;
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
