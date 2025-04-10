console.log("JavaScript loaded with D3.js");

document.addEventListener('DOMContentLoaded', () => {
    const cardsContainer = d3.select('#cards');
    const timeDisplay = d3.select('#time');
    const scoreDisplay = d3.select('#score');
    
    let cards = [];
    let hasFlippedCard = false;
    let lockBoard = false;
    let firstCard, secondCard;
    let score = 0;
    let timeLeft = 60;
    let timer;
    
    // Card symbols
    const symbols = ['🍎', '🍌', '🍒', '🍓', '🍊', '🍋', '🍉', '🍇'];
    
    // Initialize game
    function initGame() {
        // Duplicate symbols to create pairs
        const gameCards = [...symbols, ...symbols];
        
        // Shuffle cards
        gameCards.sort(() => Math.random() - 0.5);
        
        // Clear container
        cardsContainer.html('');
        
        // Create card elements with D3
        const cardSelection = cardsContainer.selectAll('.card')
            .data(gameCards)
            .enter()
            .append('div')
            .attr('class', 'card')
            .attr('data-symbol', d => d)
            .style('display', 'flex')
            .style('visibility', 'visible')
            .on('click', flipCard);
            
        cards = cardSelection.nodes();
        score = 0;
        timeLeft = 60;
        updateScore();
        startTimer();
    }
    
    // Flip card with D3 animation
    function flipCard() {
        if (lockBoard) return;
        if (this === firstCard) return;
        
        d3.select(this)
            .classed('flipped', true)
            .text(this.dataset.symbol)
            .transition()
            .duration(300)
            .style('transform', 'rotateY(180deg)');
        
        if (!hasFlippedCard) {
            // First click
            hasFlippedCard = true;
            firstCard = this;
            return;
        }
        
        // Second click
        secondCard = this;
        checkForMatch();
    }
    
    // Check for match
    function checkForMatch() {
        const isMatch = firstCard.dataset.symbol === secondCard.dataset.symbol;
        
        if (isMatch) {
            disableCards();
            score += 10;
            updateScore();
            checkWin();
        } else {
            unflipCards();
        }
    }
    
    // Disable matched cards with D3
    function disableCards() {
        d3.select(firstCard).on('click', null);
        d3.select(secondCard).on('click', null);
        
        d3.select(firstCard)
            .classed('matched', true)
            .transition()
            .duration(500)
            .style('opacity', 0);
            
        d3.select(secondCard)
            .classed('matched', true)
            .transition()
            .duration(500)
            .style('opacity', 0);
        
        resetBoard();
    }
    
    // Unflip cards with D3 animation
    function unflipCards() {
        lockBoard = true;
        
        d3.select(firstCard)
            .transition()
            .duration(300)
            .style('transform', 'rotateY(0deg)')
            .on('end', function() {
                d3.select(firstCard).classed('flipped', false).text('');
                d3.select(secondCard).classed('flipped', false).text('');
                resetBoard();
            });
        
        d3.select(secondCard)
            .transition()
            .duration(300)
            .style('transform', 'rotateY(0deg)');
    }
    
    // Reset board state
    function resetBoard() {
        [hasFlippedCard, lockBoard] = [false, false];
        [firstCard, secondCard] = [null, null];
    }
    
    // Update score display
    function updateScore() {
        scoreDisplay.textContent = score;
    }
    
    // Start timer
    function startTimer() {
        clearInterval(timer);
        timeDisplay.textContent = timeLeft;
        
        timer = setInterval(() => {
            timeLeft--;
            timeDisplay.textContent = timeLeft;
            
            if (timeLeft <= 0) {
                clearInterval(timer);
                endGame();
            }
        }, 1000);
    }
    
    // Check if all cards are matched
    function checkWin() {
        const matchedCards = document.querySelectorAll('.card.matched');
        if (matchedCards.length === symbols.length * 2) {
            clearInterval(timer);
            setTimeout(() => {
                alert(`You won! Your score: ${score}`);
                initGame();
            }, 500);
        }
    }
    
    // End game when time runs out
    function endGame() {
        alert(`Time's up! Your score: ${score}`);
        initGame();
    }
    
    // Initialize game on load
    initGame();
});