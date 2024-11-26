class WheelGame {
    constructor() {
        this.socket = io();
        this.wheel = document.querySelector('.wheel');
        this.playersList = document.querySelector('.players-list');
        this.gameStatus = document.querySelector('.game-status');
        this.joinButton = document.getElementById('joinGame');
        this.countdown = document.getElementById('countdown');
        this.setupSocketListeners();
    }

    setupSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('game_status', (data) => {
            this.updateGameStatus(data);
        });

        this.socket.on('players_update', (data) => {
            this.updatePlayers(data.players);
        });

        this.socket.on('spin_wheel', (data) => {
            this.spinWheel(data.degrees, data.winner);
        });

        this.socket.on('countdown', (data) => {
            this.updateCountdown(data.time);
        });

        this.socket.on('winner_announced', (data) => {
            this.announceWinner(data);
        });
    }

    updateGameStatus(data) {
        this.gameStatus.textContent = data.message;
        this.joinButton.disabled = !data.canJoin;
    }

    updatePlayers(players) {
        // Clear existing wheel segments
        while (this.wheel.firstChild) {
            this.wheel.removeChild(this.wheel.firstChild);
        }

        // Create new wheel segments
        const segmentAngle = 360 / players.length;
        players.forEach((player, index) => {
            const segment = document.createElement('div');
            segment.className = 'wheel-player';
            segment.textContent = player.username;
            segment.style.transform = `rotate(${index * segmentAngle}deg)`;
            segment.style.backgroundColor = this.getRandomColor();
            this.wheel.appendChild(segment);
        });

        // Update players list
        this.playersList.innerHTML = players.map(player => 
            `<div>${player.username}</div>`
        ).join('');
    }

    spinWheel(degrees, winner) {
        this.wheel.style.transform = `rotate(${degrees}deg)`;
        setTimeout(() => {
            this.announceWinner(winner);
        }, 5000); // Wait for spin animation to complete
    }

    updateCountdown(time) {
        const minutes = Math.floor(time / 60);
        const seconds = time % 60;
        this.countdown.textContent = `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
    }

    announceWinner(winner) {
        const winnerSegment = Array.from(this.wheel.children)
            .find(segment => segment.textContent === winner.username);
        
        if (winnerSegment) {
            winnerSegment.classList.add('winner-animation');
        }

        this.gameStatus.innerHTML = `
            <div class="alert alert-success">
                Winner: ${winner.username}!<br>
                Prize: ₹${winner.prize}
            </div>
        `;
    }

    joinGame() {
        this.socket.emit('join_game');
        this.joinButton.disabled = true;
    }

    getRandomColor() {
        const colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', 
            '#FFEEAD', '#D4A5A5', '#9B59B6', '#3498DB'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
}

// Initialize the game when the page loads
window.addEventListener('load', () => {
    const game = new WheelGame();
    window.wheelGame = game; // Make it globally accessible
});
