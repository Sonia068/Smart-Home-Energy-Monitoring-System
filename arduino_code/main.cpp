/*
 * Smart Home Energy Monitoring System
 * ESP32 Firmware — Phase 4 (Sampling, RMS, MQTT)
 *
 * Hardware:
 *   - ESP32-DevKitC
 *   - SCT-013-050 non-invasive current clamp on GPIO34
 *   - Bias: two 10kΩ resistors to 3.3V (mid-rail ≈ 1.65V), 10µF cap to GND
 *   - Anti-alias: 100kΩ series, 0.1µF shunt to GND on ADC pin
 *
 * Libraries required (install via Arduino Library Manager):
 *   - PubSubClient  (knolleary)
 *   - Preferences   (built-in ESP32 core)
 *   - Adafruit ADS1X15  (optional — only if using external ADC)
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include <Arduino.h>

// ─────────────────────────────────────────────
// USER CONFIGURATION  ← edit these
// ─────────────────────────────────────────────
const char* WIFI_SSID  = "YOUR_SSID";
const char* WIFI_PASS  = "YOUR_PASSWORD";
const char* MQTT_HOST  = "192.168.1.10";   // IP of your Mosquitto broker
const int   MQTT_PORT  = 1883;
const char* NODE_ID    = "node1";

// Energy tariff (₹ per kWh)
const float TARIFF_RS_PER_KWH = 8.0f;

// Nominal mains voltage (India = 230 V, 50 Hz)
const float V_NOMINAL = 230.0f;

// ─────────────────────────────────────────────
// ADC / CALIBRATION
// ─────────────────────────────────────────────
const int   ADC_PIN        = 34;    // GPIO34 — ADC1_CH6 (input-only)
const float ADC_COUNTS     = 4095.0f;
const float VREF           = 3.3f;

// CAL_A_PER_COUNT:  multiply centered ADC value (in volts) by this to get Amps
// SCT-013-050 = 50A / 1V output → with VREF=3.3V and full-scale ≈ 1.65V peak
//   rough default: (50A / 1V) / (ADC_COUNTS/2 * VREF/ADC_COUNTS) ≈ 0.0606 A per count-volt
// Fine-tune during calibration (Step 3) and save to NVS.
float CAL_A_PER_COUNT = 0.0606f;

// Overload alert threshold (W)
const float OVERLOAD_THRESHOLD_W = 2000.0f;

// ─────────────────────────────────────────────
// GLOBAL STATE
// ─────────────────────────────────────────────
WiFiClient   espClient;
PubSubClient mqtt(espClient);
Preferences  prefs;

double   wh_total      = 0.0;   // cumulative energy (Wh)
uint64_t lastPublishMs = 0;
uint64_t startMs       = 0;

// ─────────────────────────────────────────────
// WIFI SETUP
// ─────────────────────────────────────────────
void setupWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
}

// ─────────────────────────────────────────────
// MQTT SETUP & RECONNECT
// ─────────────────────────────────────────────
void mqttReconnect() {
  while (!mqtt.connected()) {
    Serial.print("[MQTT] Connecting...");
    String clientId = String("energy-") + NODE_ID;
    if (mqtt.connect(clientId.c_str())) {
      Serial.println("connected");
    } else {
      Serial.printf("failed rc=%d, retry in 3s\n", mqtt.state());
      delay(3000);
    }
  }
}

void setupMQTT() {
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqttReconnect();
}

// ─────────────────────────────────────────────
// RMS SAMPLING  (Phase 4)
// Samples ADC at ~4 kHz for 500 ms (≈ 25 mains cycles at 50 Hz)
// Returns Irms in Amperes
// ─────────────────────────────────────────────
float measureIrms(int pin, int nSamples = 2000) {
  double sumSq = 0.0;
  for (int i = 0; i < nSamples; i++) {
    int raw = analogRead(pin);
    // Remove DC bias: mid-rail = ADC_COUNTS/2 counts
    float centered_counts = raw - (ADC_COUNTS / 2.0f);
    // Convert to volts
    float v = centered_counts * (VREF / ADC_COUNTS);
    // Convert to amps using calibration constant
    float iA = v * CAL_A_PER_COUNT;
    sumSq += iA * iA;
    delayMicroseconds(250); // ≈ 4 kHz sample rate
  }
  return sqrt(sumSq / nSamples);
}

// ─────────────────────────────────────────────
// ENERGY ACCUMULATION  (Phase 5)
// apparentW × sample_window_hours → Wh
// ─────────────────────────────────────────────
void accumulateEnergy(float apparentW, float sampleWindowSeconds) {
  wh_total += apparentW * (sampleWindowSeconds / 3600.0f);
}

// ─────────────────────────────────────────────
// COST ESTIMATION  (Phase 6)
// ─────────────────────────────────────────────
float estimateCost(double wh) {
  return (wh / 1000.0f) * TARIFF_RS_PER_KWH;
}

// ─────────────────────────────────────────────
// ALERT CHECK  (Phase 8)
// ─────────────────────────────────────────────
bool checkOverload(float apparentW) {
  return apparentW > OVERLOAD_THRESHOLD_W;
}

// ─────────────────────────────────────────────
// MQTT PUBLISH  (Phase 7)
// Topic: home/energy/{nodeId}/c1
// Payload: JSON with all metrics
// ─────────────────────────────────────────────
void publishMetrics(float Irms, float apparentW, double wh, float costRs, bool alert) {
  char topic[64];
  snprintf(topic, sizeof(topic), "home/energy/%s/c1", NODE_ID);

  char payload[300];
  snprintf(payload, sizeof(payload),
    "{"
      "\"Irms\":%.3f,"
      "\"voltage\":%.1f,"
      "\"apparent_w\":%.1f,"
      "\"wh_total\":%.3f,"
      "\"kwh_total\":%.5f,"
      "\"cost_rs\":%.2f,"
      "\"alert\":%s,"
      "\"uptime_s\":%llu"
    "}",
    Irms,
    V_NOMINAL,
    apparentW,
    wh,
    wh / 1000.0,
    costRs,
    alert ? "true" : "false",
    (uint64_t)((millis() - startMs) / 1000)
  );

  bool ok = mqtt.publish(topic, payload, /*retain=*/true);
  Serial.printf("[MQTT] %s → %s (%s)\n", topic, payload, ok ? "OK" : "FAIL");
}

// ─────────────────────────────────────────────
// SETUP
// ─────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n=== Smart Home Energy Monitor ===");

  // Load calibration from Non-Volatile Storage
  prefs.begin("cal", /*readOnly=*/false);
  CAL_A_PER_COUNT = prefs.getFloat("calI", CAL_A_PER_COUNT);
  wh_total        = prefs.getDouble("wh", 0.0);
  Serial.printf("[CAL] calI=%.6f, wh_restore=%.3f\n", CAL_A_PER_COUNT, wh_total);

  analogReadResolution(12); // 0 – 4095
  analogSetAttenuation(ADC_11db); // 0–3.3V range
  pinMode(ADC_PIN, INPUT);

  setupWiFi();
  setupMQTT();

  startMs = millis();
  Serial.println("[INIT] Ready — sampling started");
}

// ─────────────────────────────────────────────
// MAIN LOOP
// ─────────────────────────────────────────────
void loop() {
  // Keep MQTT alive
  if (!mqtt.connected()) mqttReconnect();
  mqtt.loop();

  // --- Phase 4: Sample & compute RMS ---
  const int N_SAMPLES       = 2000;
  const float SAMPLE_WIN_S  = N_SAMPLES * 0.00025f; // 250 µs × 2000 = 0.5 s
  float Irms = measureIrms(ADC_PIN, N_SAMPLES);

  // --- Phase 5: Apparent power ---
  float apparentW = Irms * V_NOMINAL;

  // --- Phase 5: Accumulate energy ---
  accumulateEnergy(apparentW, SAMPLE_WIN_S);

  // --- Phase 6: Cost ---
  float costRs = estimateCost(wh_total);

  // --- Phase 8: Alert ---
  bool alert = checkOverload(apparentW);

  // --- Phase 7: Publish every 1 s ---
  if (millis() - lastPublishMs >= 1000) {
    publishMetrics(Irms, apparentW, wh_total, costRs, alert);
    lastPublishMs = millis();

    // Persist energy & calibration periodically
    prefs.putDouble("wh", wh_total);
  }

  // Serial monitor for debugging
  Serial.printf("Irms=%.3fA | Power=%.1fW | Energy=%.3fWh | Cost=₹%.2f | Alert=%d\n",
    Irms, apparentW, wh_total, costRs, alert);
}

// ─────────────────────────────────────────────
// CALIBRATION HELPER  (call once from Serial Monitor)
// Send "CAL:xxx.xxx" over serial to set new calI and store to NVS
// Example: CAL:0.06250
// ─────────────────────────────────────────────
void serialCalibration() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.startsWith("CAL:")) {
      float newCal = cmd.substring(4).toFloat();
      if (newCal > 0) {
        CAL_A_PER_COUNT = newCal;
        prefs.putFloat("calI", newCal);
        Serial.printf("[CAL] Updated calI=%.6f saved to NVS\n", newCal);
      }
    }
    if (cmd == "RESET_WH") {
      wh_total = 0;
      prefs.putDouble("wh", 0.0);
      Serial.println("[CAL] Energy reset to 0 Wh");
    }
  }
}
