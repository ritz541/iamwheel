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
        this.currentRotation = 0;
        this.setupElements();
        this.setupSocketListeners();
        
        console.log('WheelGame initialized');
    }

    setupElements() {
        this.wheelContainer = document.querySelector('.wheel-container');
        this.wheel = document.querySelector('.wheel');
        this.joinButton = document.getElementById('joinGame');
        this.statusElement = document.querySelector('.game-status');
        this.timerElement = document.getElementById('countdown');
        this.playersListElement = document.querySelector('.players-list');
        
        if (this.joinButton) {
            this.joinButton.onclick = (e) => {
                e.preventDefault();
                this.joinGame();
            };
        }
    }

    updateWheel() {
        if (!this.wheel) return;
        
        // Clear existing segments
        this.wheel.innerHTML = '';
        
        const segmentCount = Math.max(8, this.players.length);
        const segmentAngle = 360 / segmentCount;
        
        // Create segments for each player
        this.players.forEach((player, index) => {
            const segment = document.createElement('div');
            segment.className = 'wheel-segment';
            segment.style.transform = `rotate(${index * segmentAngle}deg)`;
            
            // Add player name
            const nameLabel = document.createElement('div');
            nameLabel.className = 'segment-label';
            nameLabel.textContent = player.username;
            nameLabel.style.transform = `rotate(${segmentAngle / 2}deg)`;
            segment.appendChild(nameLabel);
            
            this.wheel.appendChild(segment);
        });

        // Fill remaining segments if needed
        for (let i = this.players.length; i < 8; i++) {
            const segment = document.createElement('div');
            segment.className = 'wheel-segment empty';
            segment.style.transform = `rotate(${i * segmentAngle}deg)`;
            this.wheel.appendChild(segment);
        }

        // Add center dot if it doesn't exist
        let center = this.wheelContainer.querySelector('.wheel-center');
        if (!center) {
            center = document.createElement('div');
            center.className = 'wheel-center';
            this.wheelContainer.appendChild(center);
        }

        // Add arrow if it doesn't exist
        let arrow = this.wheelContainer.querySelector('.wheel-arrow');
        if (!arrow) {
            arrow = document.createElement('div');
            arrow.className = 'wheel-arrow';
            this.wheelContainer.appendChild(arrow);
        }
    }

    spinWheel(winnerIndex) {
        if (!this.wheel) return;
        
        const segmentCount = Math.max(8, this.players.length);
        const segmentAngle = 360 / segmentCount;
        
        // Calculate the target rotation
        // Add 5 full rotations plus the angle to the winner
        const targetRotation = this.currentRotation + (360 * 5) + (segmentAngle * winnerIndex);
        
        // Apply the rotation with animation
        this.wheel.style.transform = `rotate(${targetRotation}deg)`;
        this.currentRotation = targetRotation;
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

        this.socket.on('connect_error', (error) => {
            console.error('Connection Error:', error);
            if (this.statusElement) {
                this.statusElement.textContent = 'Error connecting to server. Retrying...';
            }
            if (this.joinButton) {
                this.joinButton.disabled = true;
            }
        });

        this.socket.on('disconnect', (reason) => {
            console.log('Disconnected:', reason);
            if (this.statusElement) {
                this.statusElement.textContent = 'Disconnected from server. Reconnecting...';
            }
            if (this.joinButton) {
                this.joinButton.disabled = true;
            }
        });

        this.socket.on('timer', (data) => {
            if (this.timerElement && data.time !== undefined) {
                const minutes = Math.floor(data.time / 60);
                const seconds = data.time % 60;
                this.timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
                
                // When timer reaches 0, spin the wheel
                if (data.time === 0) {
                    const winnerIndex = Math.floor(Math.random() * this.players.length);
                    this.spinWheel(winnerIndex);
                }
            }
        });

        this.socket.on('game_status', (data) => {
            console.log('Game status update:', data);
            if (data.players && Array.isArray(data.players)) {
                this.players = data.players;
                this.updatePlayersList();
                this.updateWheel();
            }
            
            if (data.timer && this.timerElement) {
                const minutes = Math.floor(data.timer / 60);
                const seconds = data.timer % 60;
                this.timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
            
            if (this.joinButton) {
                this.joinButton.disabled = data.status !== 'joining';
            }
            
            if (this.statusElement) {
                this.statusElement.textContent = data.status === 'joining' ? 'Waiting for players...' : 'Game in progress';
            }
        });

        this.socket.on('player_joined', (data) => {
            console.log('Player joined:', data);
            if (data.players && Array.isArray(data.players)) {
                this.players = data.players;
                this.updatePlayersList();
                this.updateWheel();
                
                if (this.statusElement) {
                    this.statusElement.textContent = `Players in game: ${data.player_count}`;
                }
            }
        });

        this.socket.on('join_game_response', (response) => {
            console.log('Join game response:', response);
            if (this.joinButton) {
                this.joinButton.disabled = !response.success;
            }
            
            if (!response.success) {
                alert(response.message || 'Failed to join game');
            }
            
            if (this.statusElement) {
                this.statusElement.textContent = response.message;
            }
        });

        this.socket.on('game_end', (data) => {
            console.log('Game ended:', data);
            if (this.statusElement) {
                if (data.winner) {
                    this.statusElement.textContent = `Game Over! Winner: ${data.winner}`;
                } else {
                    this.statusElement.textContent = 'Game cancelled - No players joined';
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

    updatePlayersList() {
        console.log('Updating players list:', this.players);
        if (!this.playersListElement) {
            console.error('Players list element not found');
            return;
        }
        
        // Clear existing list
        this.playersListElement.innerHTML = '';
        
        // Add each player
        this.players.forEach((player, index) => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = player.username || 'Unknown Player';
            this.playersListElement.appendChild(li);
        });
    }
}

// Initialize game when document is ready
document.addEventListener('DOMContentLoaded', () => {
    window.wheelGame = new WheelGame();
});
