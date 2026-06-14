"""
Smart Home Energy Monitoring System
Phase 1-8 Python Simulation
-------------------------------
Simulates: normal, high-usage, overload, and multi-appliance scenarios.
Publishes to MQTT (if broker available), logs to CSV, prints to console.

Run:
    python simulator.py                  # default: normal mode, 30 readings
    python simulator.py --mode high      # high energy usage
    python simulator.py --mode overload  # overload condition
    python simulator.py --mode multi     # multiple appliances
    python simulator.py --readings 60    # custom count
"""

import argparse
import csv
import json
import math
import os
import random
import time
from datetime import datetime

# ── try MQTT (optional) ──────────────────────────────────────────────────────
try:
    import paho.mqtt.client as mqtt_client
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("[INFO] paho-mqtt not installed. Running without MQTT. "
          "Install: pip install paho-mqtt")

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
MQTT_HOST          = "localhost"
MQTT_PORT          = 1883
MQTT_TOPIC_BASE    = "home/energy/node1"
V_NOMINAL          = 230.0          # Volts (India mains)
TARIFF_RS_PER_KWH  = 8.0           # ₹ per kWh
OVERLOAD_THRESHOLD = 2000.0         # Watts
SAMPLE_INTERVAL_S  = 1.0           # seconds between readings
CSV_PATH           = os.path.join(os.path.dirname(__file__),
                                   "../data/energy_log.csv")
os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

# ─────────────────────────────────────────────
# APPLIANCE PROFILES  (Phase 11 – Virtual Simulation)
# ─────────────────────────────────────────────
APPLIANCE_PROFILES = {
    "normal": [
        {"name": "LED Lights",    "watts": 40,   "pf": 0.95},
        {"name": "Phone Charger", "watts": 10,   "pf": 0.85},
        {"name": "Laptop",        "watts": 65,   "pf": 0.90},
        {"name": "Ceiling Fan",   "watts": 75,   "pf": 0.85},
    ],
    "high": [
        {"name": "LED Lights",    "watts": 40,   "pf": 0.95},
        {"name": "Refrigerator",  "watts": 150,  "pf": 0.85},
        {"name": "Washing Machine","watts": 500, "pf": 0.80},
        {"name": "Water Heater",  "watts": 1500, "pf": 0.99},
        {"name": "AC (1.5 ton)",  "watts": 1200, "pf": 0.85},
    ],
    "overload": [
        {"name": "AC (1.5 ton)",  "watts": 1200, "pf": 0.85},
        {"name": "Water Heater",  "watts": 1500, "pf": 0.99},
        {"name": "Oven",          "watts": 1800, "pf": 0.99},
        {"name": "Washing Machine","watts": 500, "pf": 0.80},
    ],
    "multi": [
        {"name": "AC (1.5 ton)",  "watts": 1200, "pf": 0.85},
        {"name": "Refrigerator",  "watts": 150,  "pf": 0.85},
        {"name": "TV",            "watts": 100,  "pf": 0.90},
        {"name": "Laptop",        "watts": 65,   "pf": 0.90},
        {"name": "Ceiling Fan",   "watts": 75,   "pf": 0.85},
        {"name": "Microwave",     "watts": 900,  "pf": 0.95},
    ],
}

# ─────────────────────────────────────────────
# PHASE 3: SENSOR DATA SIMULATION
# Adds realistic noise (±5%) and occasional spikes
# ─────────────────────────────────────────────
def simulate_sensor_reading(total_watts: float) -> dict:
    """
    Simulate ADC + clamp reading for given total load.
    Returns dict with Irms, voltage, apparent_w, true_w, pf, noise info.
    """
    noise_factor = 1.0 + random.uniform(-0.05, 0.05)  # ±5% noise
    spike        = random.random() < 0.03              # 3% chance of spike

    true_watts   = total_watts * noise_factor
    if spike:
        true_watts *= 1.25                             # 25% transient spike

    voltage_v    = V_NOMINAL + random.uniform(-5, 5)  # ±5 V fluctuation
    irms_a       = true_watts / voltage_v if voltage_v > 0 else 0.0
    apparent_va  = irms_a * voltage_v

    return {
        "voltage":    round(voltage_v, 2),
        "Irms":       round(irms_a, 4),
        "apparent_w": round(apparent_va, 2),
        "true_w":     round(true_watts, 2),
        "spike":      spike,
    }

# ─────────────────────────────────────────────
# PHASE 4: POWER CALCULATION
# ─────────────────────────────────────────────
def calculate_power(voltage: float, current: float) -> float:
    return round(voltage * current, 2)

# ─────────────────────────────────────────────
# PHASE 5: ENERGY CONSUMPTION
# ─────────────────────────────────────────────
def calculate_energy(power_w: float, elapsed_s: float) -> float:
    """Returns energy in Wh for this interval."""
    return round(power_w * (elapsed_s / 3600.0), 6)

# ─────────────────────────────────────────────
# PHASE 6: COST ESTIMATION
# ─────────────────────────────────────────────
def estimate_cost(wh_total: float) -> float:
    return round((wh_total / 1000.0) * TARIFF_RS_PER_KWH, 4)

# ─────────────────────────────────────────────
# PHASE 8: ALERT GENERATION
# ─────────────────────────────────────────────
def check_alerts(apparent_w: float, spike: bool) -> dict:
    alerts = []
    if apparent_w > OVERLOAD_THRESHOLD:
        alerts.append(f"OVERLOAD: {apparent_w:.0f}W > {OVERLOAD_THRESHOLD:.0f}W limit")
    if apparent_w > OVERLOAD_THRESHOLD * 0.8:
        alerts.append(f"WARNING: Approaching limit ({apparent_w:.0f}W)")
    if spike:
        alerts.append("SPIKE: Transient load spike detected")
    return {
        "alert_active": len(alerts) > 0,
        "alert_messages": alerts,
    }

# ─────────────────────────────────────────────
# PHASE 7: MQTT PUBLISH
# ─────────────────────────────────────────────
def publish_mqtt(client, topic: str, payload: dict):
    if client is None:
        return
    try:
        msg = json.dumps(payload)
        client.publish(topic, msg, retain=True)
    except Exception as e:
        print(f"[MQTT] Publish error: {e}")

# ─────────────────────────────────────────────
# PHASE 9: CSV DATA LOGGING
# ─────────────────────────────────────────────
CSV_HEADERS = [
    "timestamp", "mode", "voltage_v", "current_a",
    "apparent_w", "true_w", "wh_interval", "wh_cumulative",
    "kwh_cumulative", "cost_rs", "alert_active", "alert_messages"
]

def init_csv(path: str):
    write_header = not os.path.exists(path) or os.path.getsize(path) == 0
    fh = open(path, "a", newline="")
    writer = csv.DictWriter(fh, fieldnames=CSV_HEADERS)
    if write_header:
        writer.writeheader()
    return fh, writer

def log_csv(writer, row: dict):
    writer.writerow(row)

# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────
def print_reading(i: int, total: int, mode: str, data: dict, alerts: dict,
                  wh_cum: float):
    bar = "█" * int(data["apparent_w"] / 100)
    alert_str = " ⚠ ALERT" if alerts["alert_active"] else ""
    print(
        f"[{i:>3}/{total}] {data['timestamp']}  MODE={mode.upper():<8}"
        f"  V={data['voltage_v']:>6.1f}V"
        f"  I={data['current_a']:>6.3f}A"
        f"  P={data['apparent_w']:>7.1f}W  {bar:<25}"
        f"  ΣkWh={wh_cum/1000:.4f}"
        f"  ₹{data['cost_rs']:.4f}"
        f"{alert_str}"
    )
    for msg in alerts["alert_messages"]:
        print(f"         ↳ {msg}")

# ─────────────────────────────────────────────
# MAIN SIMULATION LOOP
# ─────────────────────────────────────────────
def run_simulation(mode: str = "normal", n_readings: int = 30,
                   mqtt_host: str = MQTT_HOST, use_mqtt: bool = True):

    print(f"\n{'='*70}")
    print(f"  Smart Home Energy Monitoring System — Python Simulation")
    print(f"  Mode: {mode.upper()}   Readings: {n_readings}")
    print(f"{'='*70}\n")

    # Validate mode
    if mode not in APPLIANCE_PROFILES:
        print(f"[ERROR] Unknown mode '{mode}'. Choose: {list(APPLIANCE_PROFILES)}")
        return

    appliances  = APPLIANCE_PROFILES[mode]
    total_watts = sum(a["watts"] for a in appliances)

    print("Active Appliances:")
    for a in appliances:
        print(f"  • {a['name']:<20} {a['watts']:>5}W  PF={a['pf']}")
    print(f"  {'TOTAL':<20} {total_watts:>5}W\n")

    # MQTT setup
    mqtt_client_obj = None
    if use_mqtt and MQTT_AVAILABLE:
        try:
            mqtt_client_obj = mqtt_client.Client(client_id="py-energy-sim")
            mqtt_client_obj.connect(mqtt_host, MQTT_PORT, keepalive=60)
            mqtt_client_obj.loop_start()
            print(f"[MQTT] Connected to {mqtt_host}:{MQTT_PORT}\n")
        except Exception as e:
            print(f"[MQTT] Could not connect ({e}). Running offline.\n")
            mqtt_client_obj = None

    # CSV setup
    csv_fh, csv_writer = init_csv(CSV_PATH)

    wh_cumulative = 0.0
    readings      = []

    try:
        for i in range(1, n_readings + 1):
            ts = datetime.now().isoformat(timespec="seconds")

            # Phase 3: Simulate sensor
            sensor = simulate_sensor_reading(total_watts)

            # Phase 4: Power
            power_w = calculate_power(sensor["voltage"], sensor["Irms"])

            # Phase 5: Energy
            wh_interval   = calculate_energy(power_w, SAMPLE_INTERVAL_S)
            wh_cumulative += wh_interval

            # Phase 6: Cost
            cost_rs = estimate_cost(wh_cumulative)

            # Phase 8: Alerts
            alerts = check_alerts(sensor["apparent_w"], sensor["spike"])

            row = {
                "timestamp":       ts,
                "mode":            mode,
                "voltage_v":       sensor["voltage"],
                "current_a":       sensor["Irms"],
                "apparent_w":      sensor["apparent_w"],
                "true_w":          sensor["true_w"],
                "wh_interval":     round(wh_interval, 6),
                "wh_cumulative":   round(wh_cumulative, 4),
                "kwh_cumulative":  round(wh_cumulative / 1000, 6),
                "cost_rs":         cost_rs,
                "alert_active":    alerts["alert_active"],
                "alert_messages":  "; ".join(alerts["alert_messages"]),
            }
            readings.append(row)

            # Phase 9: Log CSV
            log_csv(csv_writer, row)
            csv_fh.flush()

            # Phase 7: MQTT
            mqtt_payload = {**row, "alert_messages": alerts["alert_messages"]}
            publish_mqtt(mqtt_client_obj, f"{MQTT_TOPIC_BASE}/c1", mqtt_payload)

            # Console output
            print_reading(i, n_readings, mode, row, alerts, wh_cumulative)

            time.sleep(SAMPLE_INTERVAL_S)

    except KeyboardInterrupt:
        print("\n[INFO] Simulation interrupted by user.")

    finally:
        csv_fh.close()
        if mqtt_client_obj:
            mqtt_client_obj.loop_stop()
            mqtt_client_obj.disconnect()

    # Summary
    print(f"\n{'─'*70}")
    print(f"  SIMULATION SUMMARY  ({mode.upper()} mode, {len(readings)} readings)")
    print(f"{'─'*70}")
    if readings:
        avg_power = sum(r["apparent_w"] for r in readings) / len(readings)
        max_power = max(r["apparent_w"] for r in readings)
        alerts_n  = sum(1 for r in readings if r["alert_active"])
        print(f"  Avg Power   : {avg_power:.1f} W")
        print(f"  Peak Power  : {max_power:.1f} W")
        print(f"  Total Energy: {wh_cumulative:.4f} Wh  ({wh_cumulative/1000:.6f} kWh)")
        print(f"  Total Cost  : ₹{estimate_cost(wh_cumulative):.4f}")
        print(f"  Alerts fired: {alerts_n}")
    print(f"  CSV saved   : {os.path.abspath(CSV_PATH)}")
    print(f"{'─'*70}\n")
    return readings


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy Monitoring Simulator")
    parser.add_argument("--mode", choices=list(APPLIANCE_PROFILES.keys()),
                        default="normal", help="Simulation scenario")
    parser.add_argument("--readings", type=int, default=30,
                        help="Number of 1-second readings")
    parser.add_argument("--mqtt-host", default=MQTT_HOST,
                        help="MQTT broker hostname/IP")
    parser.add_argument("--no-mqtt", action="store_true",
                        help="Disable MQTT (log to CSV only)")
    args = parser.parse_args()

    run_simulation(
        mode=args.mode,
        n_readings=args.readings,
        mqtt_host=args.mqtt_host,
        use_mqtt=not args.no_mqtt,
    )
