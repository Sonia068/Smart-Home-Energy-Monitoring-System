#define SENSOR_PIN 34
#define LED_PIN 25
#define BUZZER_PIN 26

void setup() {
  Serial.begin(115200);

  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
}

void loop() {
  int sensorValue = analogRead(SENSOR_PIN);

  Serial.print("Sensor Value: ");
  Serial.println(sensorValue);

  if (sensorValue > 3000) {
    digitalWrite(LED_PIN, HIGH);
    tone(BUZZER_PIN, 1000);
  } else {
    digitalWrite(LED_PIN, LOW);
    noTone(BUZZER_PIN);
  }

  delay(500);
}