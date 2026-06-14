# Smart Home Energy Monitoring — Circuit Wiring Guide
## Phase 2: Sensing Fundamentals & Signal Conditioning

---

## Overview

We use a **non-invasive current clamp** (SCT-013-050) — it clamps around
an insulated live wire without cutting it. No mains contact.  
ESP32 ADC reads only 0–3.3 V, but the clamp outputs AC ±1 V around 0 V.  
We shift that signal to mid-rail (≈1.65 V) using a resistor-divider bias.

---

## Bill of Materials (Starter)

| Component              | Qty | Purpose                                   |
|------------------------|-----|-------------------------------------------|
| ESP32-DevKitC          | 1   | MCU — Wi-Fi, ADC, processing              |
| SCT-013-050 clamp      | 1–4 | Non-invasive current sensing (50A/1V)     |
| 10 kΩ resistor         | 2   | Bias divider to 1.65 V mid-rail           |
| 100 kΩ resistor        | 1   | Current limit / input protection          |
| 100 Ω resistor         | 1   | Safety bleed to GND                       |
| 10 µF electrolytic cap | 1   | Decouple bias node                        |
| 0.1 µF ceramic cap     | 1   | Anti-alias low-pass filter                |
| 3.5 mm audio jack      | 1   | Clamp connector                           |
| Breadboard / PCB       | 1   | Assembly                                  |
| USB-C 5V supply        | 1   | Power ESP32                               |
| Buzzer (optional)      | 1   | Local overload alert                      |
| LED + 220Ω (optional)  | 1   | Power / alert indicator                   |

---

## Wiring Diagram (ASCII)

```
                SCT-013-050 Clamp
                  ┌──────────┐
  Live Wire ──────┤  Clamp   ├────── 3.5mm Jack TIP  ──── [100kΩ] ──┬── GPIO34 (ADC1_CH6)
  (around only    └──────────┘                                        │
   live wire,                         3.5mm Jack SLEEVE (GND) ─┐     │  [0.1µF]
   not both)                                                    │     ├────────── GND
                                                                │     │
                                                     [100Ω] ───┘     │
                                                       │              │
                                                      GND             │
                                                                      │
       3.3V ─────┬─────[10kΩ]─────┬────[10kΩ]───── GND              │
                 │                 │                                   │
                 │              BIAS NODE (≈1.65V)────[10µF]──GND    │
                 │                 │                                   │
                 │                 └───────────────────────────────────┘
                 │                             (ties ADC to mid-rail)
                 │
                3.3V (ESP32 pin)


Optional Buzzer (Phase 4 — Alert):
    GPIO26 ──── [220Ω] ──── Buzzer (+) ──── GND

Optional LED Indicator:
    GPIO25 ──── [220Ω] ──── LED Anode ──── LED Cathode ──── GND
```

---

## Pin Assignment Summary

| ESP32 Pin  | Function          | Connected To                    |
|------------|-------------------|---------------------------------|
| GPIO34     | ADC1_CH6 (input)  | 100kΩ + clamp signal            |
| 3.3V       | Bias supply       | 10kΩ divider top                |
| GND        | Ground            | Bias bottom, caps, bleeder      |
| GPIO26     | Digital out       | Buzzer (alert)                  |
| GPIO25     | Digital out       | LED indicator                   |
| GPIO21/22  | I²C SDA/SCL       | ADS1115 (optional)              |

---

## Signal Conditioning Explanation

1. **Bias Divider** — Two 10 kΩ resistors from 3.3V to GND create 1.65 V
   mid-rail. This shifts the clamp's ±1 V AC signal so it sits at 0.65–2.65 V,
   within the ESP32 ADC range (0–3.3 V).

2. **Series 100 kΩ** — Limits current into the ADC pin and protects against
   over-voltage from transients.

3. **100 Ω bleed** — Provides a DC return path so the clamp isn't floating.

4. **0.1 µF cap** — With 100 kΩ forms a low-pass filter cutoff ≈ 15 kHz.
   Keeps mains 50 Hz signal, removes high-frequency noise.

5. **10 µF on bias** — Decouples the bias node so it stays stable under load.

---

## Clamp Placement (Safety)

```
  Main Panel  ──── [Live Wire inside plastic conduit] ────  Load
                            │
                     ┌──────┴──────┐
                     │  SCT-013    │  ← Clamp snaps shut around
                     │  Clamp      │    ONE insulated conductor
                     └─────────────┘    (live only, not both L+N)
                            │
                     3.5mm cable to circuit
```

> ⚠️  **NEVER** open the mains panel yourself.  
> Ask a licensed electrician to place the clamp.  
> The ESP32 circuit operates entirely at low voltage (3.3 V / 5 V).

---

## ADS1115 Wiring (Optional — Phase 7, Higher Accuracy)

```
  ESP32 GPIO21 (SDA) ──── ADS1115 SDA
  ESP32 GPIO22 (SCL) ──── ADS1115 SCL
  ESP32 3.3V         ──── ADS1115 VDD
  ESP32 GND          ──── ADS1115 GND
  ADS1115 ADDR       ──── GND  (I²C address 0x48)

  ADS1115 A0 ──── Clamp 1 signal (via bias + filter)
  ADS1115 A1 ──── Clamp 2 signal
  ADS1115 A2 ──── Clamp 3 signal
  ADS1115 A3 ──── Clamp 4 signal
```
