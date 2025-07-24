#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// Game constants
#define JUMP_DURATION 300
#define INITIAL_SPEED 400

// Pins
#define BUTTON_PIN 8
#define BUZZER_PIN 10

// Game variables
int gameSpeed = INITIAL_SPEED;
int level = 1;
bool gameOver = false;
bool isPaused = false;
unsigned long lastUpdate = 0;
bool jumpState = false;
unsigned long jumpStart = 0;


int dinoPos = 1;
int obstaclePos = 15;
int obstacleType = random(1, 3);
int obstacleLine = (obstacleType == 2) ? 0 : 1;


// Game characters
byte dino[8] = {0b01110, 0b11011, 0b11111, 0b11100, 0b11111, 0b01100, 0b10010, 0b11011};
byte cactus[8] = {0b00100, 0b00101, 0b10101, 0b10101, 0b10111, 0b11100, 0b00100, 0b00100};
byte bird[8] = {0b00000, 0b01000, 0b01110, 0b10111, 0b11111, 0b01110, 0b00100, 0b00000};

void setup() {
  Serial.begin(9600);
  while (!Serial) {}
  
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  
  lcd.init();
  lcd.backlight();
  
  // Create custom characters
  lcd.createChar(0, dino);
  lcd.createChar(1, cactus);
  lcd.createChar(2, bird);
  
  showStartScreen();
  Serial.println("READY");  // Сигнал о готовности
}

void loop() {
  handleSerialCommands();
  
  if (!gameOver && !isPaused) {
    gameUpdate();
  }
  
  // Регулярная отправка состояния
  static unsigned long lastStatusSend = 0;
  if (millis() - lastStatusSend > 500) {
    sendGameStatus();
    lastStatusSend = millis();
  }
}

void handleSerialCommands() {
  if (Serial.available()) {
    char cmd = Serial.read();
    
    switch (cmd) {
      case 'j': // Jump
        if (!isPaused && !gameOver) {
          jumpState = true;
          jumpStart = millis();
          tone(BUZZER_PIN, 500, 100);
        }
        break;
        
      case 'p': // Pause
        isPaused = !isPaused;
        if (isPaused) {
          Serial.println("STATUS:PAUSED");
          lcd.clear();
          lcd.print("GAME PAUSED");
        } else {
          Serial.println("STATUS:ACTIVE");
          lastUpdate = millis(); // Reset timer
        }
        break;
        
      case 's': // Set speed
        gameSpeed = Serial.parseInt();
        gameSpeed = constrain(gameSpeed, 100, 1000);
        break;
        
      case 'r': // Reset game
        resetGame();
        // Полный сброс игрового состояния
        lastUpdate = millis();
        obstaclePos = 15;
        obstacleType = random(1, 3);
        obstacleLine = (obstacleType == 2) ? 0 : 1;
        dinoPos = 1;
        jumpState = false;
        Serial.println("STATUS:GAME_RESET");
        break;
        
      case '?': // Status request
        sendGameStatus();
        break;
    }
  }
}

void gameUpdate() {
  if (millis() - lastUpdate > gameSpeed) {

    // Handle jumping
    if (jumpState && (millis() - jumpStart > JUMP_DURATION)) {
      jumpState = false;
      dinoPos = 1;
    } else if (jumpState) {
      dinoPos = 0;
    }

    lcd.clear();
    
    // Display level
    lcd.setCursor(0, 0);
    lcd.print("Lvl:");
    lcd.print(level);
    
    // Draw dino
    lcd.setCursor(2, dinoPos);
    lcd.write(0);
    
    // Draw obstacle
    lcd.setCursor(obstaclePos, obstacleLine);
    lcd.write(obstacleType);
    
    // Collision detection
    if (obstaclePos == 2 && obstacleLine == dinoPos) {
      endGame();
      return;
    }
    
    obstaclePos--;
    
    if (obstaclePos < 0) {
      obstaclePos = 15;
      obstacleType = random(1, 3);
      obstacleLine = (obstacleType == 2) ? 0 : 1;
      level++;
      gameSpeed = max(100, gameSpeed - 20);
      tone(BUZZER_PIN, 800, 50);
    }
    
    lastUpdate = millis();
  }
}

void sendGameStatus() {
  Serial.print("STATUS:");
  Serial.print(gameOver ? "GAME_OVER" : "RUNNING");
  Serial.print(":");
  Serial.print(isPaused ? "PAUSED" : "ACTIVE");
  Serial.print(":");
  Serial.println(level);
}

void endGame() {
  gameOver = true;
  lcd.clear();
  lcd.print("GAME OVER!");
  lcd.setCursor(0, 1);
  lcd.print("Level: ");
  lcd.print(level);
  
  tone(BUZZER_PIN, 200, 500);
  sendGameStatus();
}

void resetGame() {
  gameOver = false;
  isPaused = false;
  level = 1;
  gameSpeed = INITIAL_SPEED;
  showStartScreen();
  sendGameStatus();
}

void showStartScreen() {
  lcd.clear();
  lcd.print("Dino Game");
  lcd.setCursor(0, 1);
  lcd.print("Press to start");
  
  tone(BUZZER_PIN, 600, 100);
  delay(200);
  tone(BUZZER_PIN, 800, 100);
}