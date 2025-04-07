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
        this.isMobile = window.innerWidth < 768;
        
        // Listen for window resize to update mobile status
        window.addEventListener('resize', () => {
            this.isMobile = window.innerWidth < 768;
            this.updateGrid(); // Re-render grid with new size
        });
        
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
        if (this.wheelContainer && !this.wheelContainer.querySelector('.grid-container')) {
            this.wheelContainer.innerHTML = '<div class="grid-container"></div>';
        }
        this.gridContainer = this.wheelContainer.querySelector('.grid-container');
        
        if (this.joinButton) {
            this.joinButton.onclick = (e) => {
                e.preventDefault();
                this.joinGame();
            };
        }
    }

    initializeGrid() {
        // Create empty grid cells initially
        if (this.gridContainer) {
            // Determine grid size based on screen
            const gridSize = this.isMobile ? 9 : 12;
            this.gridContainer.innerHTML = '';
            
            for (let i = 0; i < gridSize; i++) {
                const cell = document.createElement('div');
                cell.className = 'grid-cell';
                this.gridContainer.appendChild(cell);
            }
        }
    }

    showWinnerPopup(winner) {
        if (!winner || !winner.winner) return;

        const result = winner.winner;
        const prizeAmount = result.prize_pool;

        // Format the prize amount as currency
        const formattedPrize = new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR'
        }).format(prizeAmount);

        // Create dialog if it doesn't exist
        let dialog = document.getElementById('winner-dialog');
        if (!dialog) {
            dialog = document.createElement('dialog');
            dialog.className = 'nes-dialog is-rounded';
            dialog.id = 'winner-dialog';
            document.body.appendChild(dialog);
        }

        // Set dialog content
        dialog.innerHTML = `
            <form method="dialog">
                <p class="title">Winner!</p>
                <div class="winner-content">
                    <div class="winner-emoji">${result.emoji || '🎮'}</div>
                    <p class="winner-name">${result.username || 'Unknown'}</p>
                    <p class="prize-amount">Won ${formattedPrize}!</p>
                </div>
                <menu class="dialog-menu">
                    <button class="nes-btn is-primary">Close</button>
                </menu>
            </form>
        `;

        // Show the dialog
        dialog.showModal();

        // Auto-close after 6 seconds
        setTimeout(() => {
            if (dialog.open) {
                dialog.close();
            }
        }, 6000);
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
        if (!this.gridContainer) return;
        
        // Clear existing cells
        this.gridContainer.innerHTML = '';
        
        // Determine grid size based on screen size
        const isMobile = window.innerWidth < 768;
        const isSmallMobile = window.innerWidth < 480;
        
        // Adjust grid size based on device
        let totalCells = 12; // Default for desktop (4x3)
        
        if (isSmallMobile) {
            totalCells = 9; // 3x3 for very small screens
            this.gridContainer.style.gridTemplateColumns = 'repeat(3, 1fr)';
        } else if (isMobile) {
            totalCells = 12; // 4x3 for mobile
            this.gridContainer.style.gridTemplateColumns = 'repeat(4, 1fr)';
        } else {
            // For desktop
            totalCells = 12; // 4x3
            this.gridContainer.style.gridTemplateColumns = 'repeat(4, 1fr)';
        }
        
        // If we have many players, expand grid
        if (this.players.length > totalCells) {
            totalCells = Math.min(20, Math.ceil(this.players.length * 1.2)); // Allow space for more players
            const columns = isSmallMobile ? 3 : 4;
            this.gridContainer.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;
        }
        
        const playerPositions = this.getRandomPositions(totalCells, this.players.length);
        
        for (let i = 0; i < totalCells; i++) {
            const cell = document.createElement('div');
            cell.className = 'grid-cell';
            
            const playerIndex = playerPositions.indexOf(i);
            if (playerIndex !== -1 && this.players[playerIndex]) {
                const player = this.players[playerIndex];
                const colorIndex = playerIndex % 12; // We have 12 colors defined in CSS
                
                cell.classList.add('occupied');
                cell.style.setProperty('--player-color', `var(--color-${colorIndex + 1})`);
                
                // Simplified inner HTML for mobile
                if (isMobile) {
                    cell.innerHTML = `
                        <div class="player-emoji">${player.emoji || '🎮'}</div>
                        <div class="player-name">${player.username || 'Player'}</div>
                    `;
                } else {
                    cell.innerHTML = `
                        <div class="player-emoji">${player.emoji || '🎮'}</div>
                        <div class="player-name">${player.username || 'Player'}</div>
                    `;
                }
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

    showNotification(message, type = 'info') {
        // Create dialog if it doesn't exist
        let dialog = document.getElementById('notification-dialog');
        if (!dialog) {
            dialog = document.createElement('dialog');
            dialog.className = 'nes-dialog is-rounded';
            dialog.id = 'notification-dialog';
            document.body.appendChild(dialog);
        }

        // Set dialog content
        dialog.innerHTML = `
            <form method="dialog">
                <p class="title">${type.charAt(0).toUpperCase() + type.slice(1)}</p>
                <p>${message}</p>
                <menu class="dialog-menu">
                    <button class="nes-btn is-primary">OK</button>
                </menu>
            </form>
        `;

        // Show the dialog
        dialog.showModal();

        // Add event listener to close on backdrop click
        dialog.addEventListener('click', (e) => {
            const rect = dialog.getBoundingClientRect();
            const isInDialog = (rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
                rect.left <= e.clientX && e.clientX <= rect.left + rect.width);
            if (!isInDialog) {
                dialog.close();
            }
        });
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

// Add styles to the document
const style = document.createElement('style');
style.textContent = `
    .nes-dialog {
        border-image-repeat: stretch;
        padding: 1rem;
        max-width: 90%;
    }

    .nes-dialog .title {
        font-size: 1.5rem;
        margin-bottom: 1rem;
        color: #212529;
    }

    .nes-dialog .dialog-menu {
        margin-top: 2rem;
        text-align: right;
        padding: 0;
    }

    .winner-content {
        text-align: center;
        padding: 1rem 0;
    }

    .winner-content .winner-emoji {
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }

    .winner-content .winner-name {
        font-size: 1.2rem;
        margin-bottom: 0.5rem;
    }

    .winner-content .prize-amount {
        font-size: 1.5rem;
        color: #28a745;
    }

    @media (max-width: 480px) {
        .nes-dialog {
            padding: 0.5rem;
            margin: 1rem;
        }

        .nes-dialog .title {
            font-size: 1.2rem;
        }

        .winner-content .winner-emoji {
            font-size: 2.5rem;
        }

        .winner-content .winner-name {
            font-size: 1rem;
        }

        .winner-content .prize-amount {
            font-size: 1.2rem;
        }
    }
`;
document.head.appendChild(style);
