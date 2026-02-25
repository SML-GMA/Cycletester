//#include <SoftwareSerial.h>

// --- Pins (Matching your hardware) ---
#define SENSLEFT A1
#define SENSRIGHT A2
#define SENSMID A0
#define ESTOP A3
#define MOTORCW 3
#define MOTORCCW 11
#define MAGNET 9
#define CONTACTOR 8
#define DISTANCESENSOR A6
#define DOORSENSOR A7

//SoftwareSerial myserial(12, 10);  // RX, TX

void setup() {
  Serial.begin(115200);
  //myserial.begin(9600);  // Connection to Raspberry Pi

  pinMode(MOTORCW, OUTPUT);
  pinMode(MOTORCCW, OUTPUT);
  pinMode(MAGNET, OUTPUT);
  pinMode(CONTACTOR, OUTPUT);

  pinMode(SENSLEFT, INPUT);
  pinMode(SENSRIGHT, INPUT);
  pinMode(SENSMID, INPUT);
  pinMode(ESTOP, INPUT);
  pinMode(DOORSENSOR, INPUT);

  // Set PWM Frequency High for motor smoothness
  TCCR2B = (TCCR2B & 0b11111000) | 0x01;
}

void loop() {
  if (digitalRead(ESTOP) == LOW) {
    analogWrite(MOTORCW, 0);
    analogWrite(MOTORCCW, 0);
  }


  // 1. Report Sensors to Pi (Format: "L:0,M:1,R:0,D:450,E:1")
  // Sent every loop for maximum resolution
  static unsigned long lastReport;
  if (millis() - lastReport > 20) {
    Serial.print("DATA:");
    Serial.print("L:");
    Serial.print(digitalRead(SENSLEFT));
    Serial.print(",M:");
    Serial.print(digitalRead(SENSMID));
    Serial.print(",R:");
    Serial.print(digitalRead(SENSRIGHT));
    Serial.print(",D:");
    Serial.print(analogRead(DISTANCESENSOR));
    Serial.print(",S:");
    Serial.print(analogRead(DOORSENSOR));
    Serial.print(",E:");
    Serial.println(digitalRead(ESTOP));
    lastReport = millis();
  }

  // 2. Listen for Commands from Pi
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd >= 'A' && cmd <= 'Z') {
      int val = Serial.parseInt();  // Reads the number following the char
                                      // OPTIONAL: Print a confirmation to the Monitor (Debug)
      //Serial.print("CMD_RCVD: ");
      //Serial.print(cmd);
      //Serial.println(val);
      switch (cmd) {
        case 'W':  // Clockwise PWM (W150)
          if (digitalRead(ESTOP) == HIGH) {
            analogWrite(MOTORCCW, 0);
            analogWrite(MOTORCW, constrain(val, 0, 255));
          }
          break;
        case 'C':  // Counter-Clockwise PWM (C150)
          if (digitalRead(ESTOP) == HIGH) {
            analogWrite(MOTORCW, 0);
            analogWrite(MOTORCCW, constrain(val, 0, 255));
          }
          break;
        case 'S':  // Stop (S0)
          analogWrite(MOTORCW, 0);
          analogWrite(MOTORCCW, 0);
          break;
        case 'M':  // Magnet (M1 or M0)
          digitalWrite(MAGNET, val);
          break;
        case 'K':  // Contactor (K1 or K0)
          digitalWrite(CONTACTOR, val);
          break;
      }
    }
  }
}