class WheelGame {
    constructor() {
        this.socket = io();
        this.players = [];
        this.isBreakTime = false;
        this.gameStatus = 'joining';
        this.setupElements();
        this.setupSocketListeners();
        this.initializeGrid();
        this.createPopupElements();
        
        console.log('WheelGame initialized');
    }

    createPopupElements() {
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
        this.wheelContainer.innerHTML = '<div class="grid-container"></div>';
        this.gridContainer = this.wheelContainer.querySelector('.grid-container');
        
        if (this.joinButton) {
            this.joinButton.onclick = (e) => {
                e.preventDefault();
                this.joinGame();
            };
        }
    }

    showWinnerPopup(winner) {
        // Remove existing popup if any
        const existingPopup = document.querySelector('.winner-popup');
        if (existingPopup) {
            existingPopup.remove();
        }

        // Create new popup
        const popup = document.createElement('div');
        popup.className = 'winner-popup';
        
        // Format prize money with commas
        const formattedPrize = new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR'
        }).format(winner.prize);

        popup.innerHTML = `
            <div class="title">🎉 Winner! 🎉</div>
            <div class="emoji">${winner.emoji}</div>
            <div class="player-name">${winner.username}</div>
            <div class="prize">Prize: ${formattedPrize}</div>
        `;
        
        document.body.appendChild(popup);
        
        // Force reflow
        popup.offsetHeight;
        
        // Show popup
        popup.classList.add('show');
        
        // Remove popup after 5 seconds
        setTimeout(() => {
            popup.classList.remove('show');
            setTimeout(() => popup.remove(), 300);
        }, 5000);
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

    updateGrid() {
        // Clear existing cells
        this.gridContainer.innerHTML = '';
        
        // Determine if we need expanded grid (more than 12 players)
        const needsExpanded = this.players.length > 12;
        this.gridContainer.classList.toggle('expanded', needsExpanded);
        
        // Calculate total cells based on grid type
        const totalCells = needsExpanded ? 20 : 12; // 5x4 or 4x3
        const playerPositions = this.getRandomPositions(totalCells, this.players.length);
        
        for (let i = 0; i < totalCells; i++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            
            const playerIndex = playerPositions.indexOf(i);
            if (playerIndex !== -1) {
                const player = this.players[playerIndex];
                const colorIndex = playerIndex % 12; // We have 12 colors defined in CSS
                
                cell.classList.add('occupied');
                cell.style.setProperty('--player-color', `var(--color-${colorIndex + 1})`);
                
                cell.innerHTML = `
                    <div class="player-emoji">${player.emoji}</div>
                    <div class="player-name">${player.username}</div>
                `;
            }
            
            this.gridContainer.appendChild(cell);
        }
    }

    updatePlayersList() {
        if (!this.playersListElement) return;
        
        this.playersListElement.innerHTML = this.players.map((player, index) => {
            const colorIndex = index % 12;
            return `
                <div class="player-item" style="--player-color: var(--color-${colorIndex + 1})">
                    <span class="player-emoji">${player.emoji}</span>
                    <span class="player-name">${player.username}</span>
                </div>
            `;
        }).join('');
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
            this.gameStatus = data.status;
            this.players = data.players;
            this.isBreakTime = data.isBreak;
            this.updateTimer(data.timer, data.isBreak);
            this.updateGrid();
            this.updatePlayersList();
            this.updateJoinButton();
        });

        this.socket.on('player_joined', (data) => {
            if (data.success) {
                this.showNotification(`${data.new_player.emoji} ${data.message}`, 'success');
                const oldPlayerCount = this.players.length;
                this.players = data.players;
                
                if (oldPlayerCount !== this.players.length) {
                    this.showExpansionNotice();
                }
                
                this.updateGrid();
                this.updatePlayersList();
            }
        });

        this.socket.on('winner_selected', (data) => {
            if (data.winner) {
                this.showWinnerPopup(data.winner);
                // Update wallet balance if current user is winner
                const balanceElement = document.querySelector('.text-center.mb-3 p');
                if (balanceElement && data.winner.wallet_balance !== undefined) {
                    balanceElement.textContent = `Your Balance: ₹${data.winner.wallet_balance}`;
                }
                // Schedule page refresh after winner display
                setTimeout(() => {
                    window.location.reload();
                }, 6000); // Refresh 1 second after winner popup disappears
            }
        });

        this.socket.on('timer', (data) => {
            const timeLeft = data.time;
            this.updateTimer(timeLeft);
            
            // Disable join button in last 10 seconds
            if (timeLeft <= 10 && this.joinButton) {
                this.joinButton.disabled = true;
                this.joinButton.title = 'Cannot join in last 10 seconds';
            }
        });

        this.socket.on('break_timer', (data) => {
            this.isBreakTime = true;
            this.updateJoinButton();
            setTimeout(() => {
                this.isBreakTime = false;
                this.updateJoinButton();
            }, data.duration * 1000);
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

    updateJoinButton() {
        if (!this.joinButton) return;
        
        const canJoin = this.gameStatus === 'joining' && !this.isBreakTime;
        this.joinButton.disabled = !canJoin;
        
        if (this.isBreakTime) {
            this.joinButton.title = 'Game is in break';
        } else if (this.gameStatus !== 'joining') {
            this.joinButton.title = 'Game is in progress';
        } else {
            this.joinButton.title = 'Click to join the game';
        }
    }

    announceWinner(winner) {
        // Show winner popup
        this.showWinnerPopup(winner);

        // Remove non-winner cells with animation
        const playerCells = this.gridContainer.querySelectorAll('.player-cell');
        playerCells.forEach(cell => {
            const playerEmoji = cell.querySelector('.player-emoji').textContent;
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
