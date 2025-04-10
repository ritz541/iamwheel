// p5.js sketch to display two cards
let cardFlipped = false;
let flipTime = 0;
let lastFlipTime = 0;
let flipDuration = 30000; // 30 seconds
let stayFlippedDuration = 10000; // 10 seconds

function setup() {
  let canvasWidth = min(window.innerWidth, 800);
  let canvasHeight = canvasWidth * 0.6; // More vertical space for mobile
  createCanvas(canvasWidth, canvasHeight);
  background(220);
  
  // Calculate responsive card dimensions
  let cardWidth = canvasWidth * 0.2;
  let cardHeight = canvasHeight * 0.866;
  let cardX = canvasWidth * 0.5 - cardWidth/2;
  let cardY = canvasHeight * 0.5 - cardHeight/2;
  
  // Draw first card (centered with spacing)
  fill(255);
  rect(cardX, cardY, cardWidth, cardHeight, 10);
  textSize(cardWidth * 0.375); // Responsive text size
  textAlign(CENTER, CENTER);
  text('🍎', cardX + cardWidth/2, cardY + cardHeight/2);
}

function draw() {
  // Clear and center the background
  background(220);
  translate(width * 0.5, height * 0.5);
  
  // Update timer display
  let elapsed = millis() - lastFlipTime;
  let remaining = flipDuration - (elapsed % flipDuration);
  document.getElementById('time').textContent = Math.floor(remaining / 1000);
  
  // Auto-flip logic
  if (elapsed % flipDuration < 500 && !cardFlipped) {
    cardFlipped = true;
    flipTime = millis();
  } else if (elapsed % flipDuration > flipDuration - stayFlippedDuration && cardFlipped) {
    cardFlipped = false;
  }
  
  // Calculate responsive dimensions
  let cardWidth = width * (window.innerWidth < 600 ? 0.4 : 0.2);
  let cardHeight = cardWidth * 1.5; // Better proportions for mobile
  let cardCenterX = 0;
  let cardCenterY = 0;
  
  // Draw first card
  push();
  translate(cardCenterX, cardCenterY);
  
  if (cardFlipped) {
    let flipProgress = min((millis() - flipTime) / 500, 1);
    
    if (flipProgress < 0.5) {
      // First half of flip - show front shrinking
      scale(1 - flipProgress * 2, 1);
      fill(255);
      rect(-cardWidth/2, -cardHeight/2, cardWidth, cardHeight, 10);
      textSize(cardWidth * 0.375);
      textAlign(CENTER, CENTER);
      text('🍎', 0, 0);
    } else {
      // Second half of flip - show back expanding
      scale((flipProgress - 0.5) * 2, 1);
      fill(200);
      rect(-cardWidth/2, -cardHeight/2, cardWidth, cardHeight, 10);
      textSize(cardWidth * 0.375);
      textAlign(CENTER, CENTER);
      text('🃏', 0, 0);
    }
  } else {
    // Not flipped - show normal front
    fill(255);
    rect(-cardWidth/2, -cardHeight/2, cardWidth, cardHeight, 10);
    textSize(cardWidth * 0.375);
    textAlign(CENTER, CENTER);
    text('🍎', 0, 0);
  }
  pop();
  

  
  if (cardFlipped && millis() - flipTime > 10000) {
    cardFlipped = false;
    redraw();
  }
}

function touchStarted() {
  return false; // Prevent default touch behavior
}

function mouseClicked() {
  let cardWidth = width * (window.innerWidth < 600 ? 0.4 : 0.2);
  let cardHeight = cardWidth * 1.5; // Better proportions for mobile
  let cardX = width * 0.5 - cardWidth/2;
  let cardY = height * 0.5 - cardHeight/2;
  
  if (mouseX > cardX && mouseX < cardX + cardWidth && 
      mouseY > cardY && mouseY < cardY + cardHeight && !cardFlipped) {
    cardFlipped = true;
    flipTime = millis();
    redraw();
  }
}