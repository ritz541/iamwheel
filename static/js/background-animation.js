// Colorful particle animation using anime.js
const canvas = document.createElement('canvas');
document.body.insertBefore(canvas, document.body.firstChild);

canvas.style.position = 'fixed';
canvas.style.top = '0';
canvas.style.left = '0';
canvas.style.width = '100vw';
canvas.style.height = '100vh';
canvas.style.zIndex = '-1';
canvas.style.opacity = '0.5';

const ctx = canvas.getContext('2d');
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

const particles = [];
const colors = ['#FF5252', '#FF4081', '#E040FB', '#7C4DFF', '#536DFE', '#448AFF', '#40C4FF', '#18FFFF', '#64FFDA', '#69F0AE', '#B2FF59', '#EEFF41', '#FFFF00', '#FFD740', '#FFAB40', '#FF6E40'];

function Particle() {
  this.x = Math.random() * canvas.width;
  this.y = Math.random() * canvas.height;
  this.radius = Math.random() * 3 + 1;
  this.color = colors[Math.floor(Math.random() * colors.length)];
  this.speed = Math.random() * 2 + 0.5;
  this.angle = Math.random() * Math.PI * 2;
  this.direction = Math.random() > 0.5 ? 1 : -1;
  
  this.update = function() {
    this.x += Math.cos(this.angle) * this.speed;
    this.y += Math.sin(this.angle) * this.speed;
    this.angle += (Math.random() * 0.2 - 0.1) * this.direction;
    
    if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
    }
  };
  
  this.draw = function() {
    ctx.beginPath();
    ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    ctx.fillStyle = this.color;
    ctx.fill();
  };
}

function init() {
  for (let i = 0; i < 300; i++) {
    particles.push(new Particle());
  }
  
  anime({
    duration: Infinity,
    update: function() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.update();
        p.draw();
      });
    }
  });
}

window.addEventListener('resize', function() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
});

// Load anime.js from CDN and initialize animation
const script = document.createElement('script');
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/animejs/3.2.1/anime.min.js';
script.onload = init;
document.head.appendChild(script);