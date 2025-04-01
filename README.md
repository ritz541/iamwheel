

# I Am Wheel Game

This project consists of a Flask backend API and a Spring Boot frontend application.

## Prerequisites

- Python 3.x
- Java 17
- Maven

## Running the Application

### 1. Start the Flask Backend

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Flask application:
   ```bash
   python api/app.py
   ```

### 2. Start the Spring Boot Frontend

1. Build and run the Spring Boot application:
   ```bash
   ./mvnw spring-boot:run
   ```
   Or on Windows:
   ```bash
   mvnw.cmd spring-boot:run
   ```

The application should now be running with:
- Flask backend API
- Spring Boot frontend application

Access the application through your web browser at `http://localhost:8080`