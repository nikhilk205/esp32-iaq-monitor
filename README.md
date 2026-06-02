# Indoor Air Quality Monitor — ESP32

Real-time indoor air quality monitoring system built on an ESP32. Measures CO2, CO, temperature, and humidity, displays readings on an RGB LCD, logs data locally to CSV, and uploads to ThingSpeak for cloud monitoring. Includes a live Python dashboard with animated plots.

## Hardware

| Component | Pin |
|-----------|-----|
| MQ-135 (CO2) | GPIO 34 |
| MQ-7 (CO) | GPIO 35 |
| DHT11 (Temp/Humidity) | GPIO 32 |
| RGB LCD (16x2) | SDA → GPIO 21, SCL → GPIO 22 |

## Repository Structure

```plaintext
indoor-air-quality-esp32/
├── iaq_esp32.ino
├── iaq_logger.py
├── iaq_logger_thingspeak.py
└── README.md
```

## How It Works

**Firmware (ESP32)**
- Averages 10 ADC samples per reading to reduce noise
- Converts raw ADC values to PPM using sensor-specific power-law curves
- Classifies air quality as GOOD / MODERATE / POOR based on WHO thresholds
- Cycles RGB LCD through three display modes: gas readings → temp/humidity → air quality
- Streams structured serial output at 115200 baud every 500ms

**Python Logger**
- Reads serial stream from ESP32 over USB
- Parses sensor blocks and logs to `iaq_log.csv`
- Animates live 2x2 dashboard: CO2, CO, Temperature, Humidity
- ThingSpeak variant uploads 6 fields to cloud every 15 seconds (free tier rate limit)

## Setup

**Firmware**
1. Install libraries: `DHT sensor library`, `Grove LCD RGB Backlight`
2. Flash `iaq_esp32.ino` to ESP32 via Arduino IDE
3. Close Serial Monitor before running Python logger

**Python Logger**
```bash
pip install pyserial matplotlib requests
```

Update `COM_PORT` in the script to match your ESP32's port (`COM5` on Windows, `/dev/ttyUSB0` on Linux).

For ThingSpeak, replace `YOUR_THINGSPEAK_API_KEY` in `iaq_logger_thingspeak.py` with your channel write API key.

```bash
python iaq_logger.py              # local only
python iaq_logger_thingspeak.py   # with cloud upload
```

## Sample Output

```plaintext
[2026-06-02 10:15:32] CO2=423.5ppm | CO=0.84ppm | T=27.3C | H=62% | GOOD | #1
[2026-06-02 10:15:33] CO2=425.1ppm | CO=0.85ppm | T=27.3C | H=62% | GOOD | #2
```

## Tech Stack

- **Microcontroller:** ESP32
- **Firmware:** Arduino (C++)
- **Sensors:** MQ-135, MQ-7, DHT11
- **Display:** Grove RGB LCD 16x2 (I2C)
- **Logger:** Python 3 (pyserial, matplotlib, requests)
- **Cloud:** ThingSpeak IoT
- **Protocol:** UART Serial, I2C
