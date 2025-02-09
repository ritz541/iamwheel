# 🎯 Casino-Style Spinning Wheel Game

Welcome to the **Casino-Style Spinning Wheel Game**, a real-time multiplayer web application where players participate in a thrilling game of chance with the opportunity to win cash rewards.

## 📝 Features

- **🎡 Dynamic Spinning Wheel:** Displays up to 20 players' random IDs per round.
- **💰 Prize Pool:** Players pay ₹10 to join, with 80% of the pool awarded to the winner and 20% kept as a platform fee.
- **⏱️ 5-Minute Countdown:** Each game round has a 5-minute joining phase.
- **🔄 Random Winner Selection:** Ensures fairness with automated randomization.
- **👛 In-Game Wallet System:** Securely manage deposits and withdrawals.
- **📊 Admin Panel:** Two-password secured dashboard with transaction logs, revenue tracking, and round history.
- **🔔 Notifications:** Real-time updates for both players and admins.

## 🚀 How It Works

1. **Join the Game:** Pay ₹10 to enter a round.
2. **Wait for the Countdown:** A 5-minute timer allows more players to join.
3. **Spin the Wheel:** After the timer ends, the wheel spins and selects a random winner.
4. **Claim Your Prize:** 80% of the prize pool is added to the winner's in-game wallet.

If only one player joins, the entry fee is fully refunded.

## 💼 Admin Features

- View and manage user wallets.
- Approve deposits and withdrawals manually.
- Monitor platform revenue and game statistics.
- Access transaction logs and detailed round histories.

## ⚙️ Tech Stack

- **Backend:** Python (Flask)
- **Frontend:** HTML, CSS, JavaScript
- **Database:** MongoDB

## 📋 Database Collections

- `users` - Stores user information and wallet details.
- `games` - Logs details of each game round.
- `transactions` - Records deposits, withdrawals, and winnings.
- `notifications` - Manages system notifications for users and admins.

## 💳 Wallet & Payment Info

- **Deposit:** Minimum ₹20, Maximum ₹1000
- **Withdrawal:** Minimum ₹50, Maximum ₹500
- **Payment Verification:** Handled manually by the admin.

## 🔒 Security

- Two-password authentication for admin panel access.
- Secure session management (auto-logout after 24 hours).

## 📈 Future Enhancements

- Real-time payment gateway integration
- Enhanced UI/UX for the spinning wheel
- Automated withdrawal and deposit verification

## 🗂️ License

This project is for educational purposes only. Use responsibly.

---

**Developed by [Your Name]** 🚀

