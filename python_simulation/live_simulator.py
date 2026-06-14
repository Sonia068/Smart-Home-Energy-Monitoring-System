# live_simulator.py
import json
import random
import time
from datetime import datetime

energy = 0

while True:
    voltage = random.randint(225, 235)
    current = round(random.uniform(1.0, 3.5), 2)

    power = round(voltage * current, 2)
    energy += power / 3600000
    cost = round(energy * 8, 2)

    alert = "Normal"
    if power > 1000:
        alert = "High Consumption"

    data = {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "voltage": voltage,
        "current": current,
        "power": power,
        "energy": round(energy, 4),
        "cost": cost,
        "alert": alert
    }

    with open("energy_data.json", "w") as f:
        json.dump(data, f)

    time.sleep(1)