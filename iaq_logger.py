import serial
import csv
import os
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from datetime import datetime
from collections import deque

# ── Configuration ─────────────────────────────────────────────────
COM_PORT      = 'COM5'
BAUD_RATE     = 115200
CSV_FILE      = 'iaq_log.csv'
MAX_POINTS    = 100

# ── Data buffers ──────────────────────────────────────────────────
timestamps    = deque(maxlen=MAX_POINTS)
co2_data      = deque(maxlen=MAX_POINTS)
co_data       = deque(maxlen=MAX_POINTS)
temp_data     = deque(maxlen=MAX_POINTS)
humidity_data = deque(maxlen=MAX_POINTS)
time_labels   = deque(maxlen=MAX_POINTS)

# ── Create CSV file with headers if it doesn't exist ─────────────
def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp',
                'MQ135_ADC',
                'CO2_PPM',
                'MQ7_ADC',
                'CO_PPM',
                'Temperature_C',
                'Humidity_Pct',
                'Air_Quality'
            ])
        print(f"Created {CSV_FILE}")
    else:
        print(f"Appending to existing {CSV_FILE}")

# ── Parse one block of serial readings ───────────────────────────
def parse_reading(block):
    data = {}
    try:
        for line in block:
            line = line.strip()
            if 'MQ-135 (ADC)' in line:
                data['mq135_adc'] = int(line.split(':')[1].strip())
            elif 'MQ-135 (CO2 PPM)' in line:
                data['co2_ppm'] = float(line.split(':')[1].strip())
            elif 'MQ-7   (ADC)' in line:
                data['mq7_adc'] = int(line.split(':')[1].strip())
            elif 'MQ-7   (CO PPM)' in line:
                data['co_ppm'] = float(line.split(':')[1].strip())
            elif 'Temperature' in line:
                data['temperature'] = float(line.split(':')[1].strip().replace(' °C', ''))
            elif 'Humidity' in line:
                data['humidity'] = float(line.split(':')[1].strip().replace(' %', ''))
            elif 'Air Quality' in line:
                data['air_quality'] = line.split(':')[1].strip()
        if len(data) == 7:
            return data
    except Exception as e:
        print(f"Parse error: {e}")
    return None

# ── Save one reading to CSV ───────────────────────────────────────
def save_to_csv(data, timestamp):
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            data['mq135_adc'],
            data['co2_ppm'],
            data['mq7_adc'],
            data['co_ppm'],
            data['temperature'],
            data['humidity'],
            data['air_quality']
        ])

# ── Set up live plot ──────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 8))
fig.suptitle('IAQ Live Monitor — ESP32', fontsize=14, fontweight='bold')
plt.tight_layout(pad=3.0)

ax_co2  = axes[0, 0]
ax_co   = axes[0, 1]
ax_temp = axes[1, 0]
ax_hum  = axes[1, 1]

# ── Open serial port ──────────────────────────────────────────────
try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=2)
    print(f"Connected to {COM_PORT} at {BAUD_RATE} baud")
    time.sleep(2)
    ser.flushInput()
except Exception as e:
    print(f"Failed to connect to {COM_PORT}: {e}")
    print("Make sure Arduino IDE Serial Monitor is closed!")
    exit()

init_csv()
buffer = []
reading_count = 0

# ── Helper: format x axis with time labels ────────────────────────
def set_time_xticks(ax, labels):
    n = len(labels)
    if n == 0:
        return
    # Show ~5 evenly spaced time labels
    step = max(1, n // 5)
    tick_positions = list(range(0, n, step))
    tick_labels = [labels[i].strftime('%H:%M:%S') for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, fontsize=7, rotation=15)

# ── Animation update function ─────────────────────────────────────
def update(frame):
    global buffer, reading_count

    while ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if '=====================================' in line and buffer:
                data = parse_reading(buffer)
                if data:
                    now = datetime.now()
                    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S')
                    save_to_csv(data, timestamp_str)
                    reading_count += 1

                    timestamps.append(now)
                    time_labels.append(now)
                    co2_data.append(data['co2_ppm'])
                    co_data.append(data['co_ppm'])
                    temp_data.append(data['temperature'])
                    humidity_data.append(data['humidity'])

                    print(f"[{timestamp_str}] CO2={data['co2_ppm']:.1f}ppm | "
                          f"CO={data['co_ppm']:.2f}ppm | "
                          f"T={data['temperature']:.1f}C | "
                          f"H={data['humidity']:.0f}% | "
                          f"{data['air_quality']} | #{reading_count}")

                buffer = []
            else:
                buffer.append(line)

        except Exception as e:
            print(f"Read error: {e}")
            buffer = []

    if len(co2_data) < 2:
        return

    x = list(range(len(co2_data)))
    labels = list(time_labels)

    # ── CO2 Plot ──────────────────────────────────────────────────
    ax_co2.clear()
    ax_co2.set_title('CO2 Equivalent (PPM)', fontweight='bold')
    ax_co2.set_ylabel('PPM')
    ax_co2.plot(x, list(co2_data), color='steelblue', linewidth=1.5)
    ax_co2.fill_between(x, list(co2_data), alpha=0.2, color='steelblue')
    ax_co2.axhline(y=1000, color='orange', linestyle='--', linewidth=1, label='MODERATE (1000)')
    ax_co2.axhline(y=2000, color='red', linestyle='--', linewidth=1, label='POOR (2000)')
    ax_co2.legend(fontsize=7, loc='upper right')
    ax_co2.set_ylim(bottom=0, top=max(1200, max(co2_data) * 1.2))
    set_time_xticks(ax_co2, labels)

    # ── CO Plot — AUTO SCALED to actual data range ────────────────
    ax_co.clear()
    ax_co.set_title('CO Concentration (PPM)', fontweight='bold')
    ax_co.set_ylabel('PPM')
    ax_co.plot(x, list(co_data), color='tomato', linewidth=1.5)
    ax_co.fill_between(x, list(co_data), alpha=0.2, color='tomato')

    # Dynamic y-axis — shows actual variation clearly
    co_min = max(0, min(co_data) - 0.2)
    co_max = max(co_data) + 0.5
    ax_co.set_ylim(bottom=co_min, top=co_max)

    # Only show WHO lines if they're in range
    if 9 <= co_max * 1.5:
        ax_co.axhline(y=9, color='orange', linestyle='--', linewidth=1, label='WHO 8hr (9 PPM)')
    if 25 <= co_max * 2:
        ax_co.axhline(y=25, color='red', linestyle='--', linewidth=1, label='WHO 1hr (25 PPM)')

    # Add annotation showing current CO level vs WHO limit
    current_co = list(co_data)[-1]
    pct_of_limit = (current_co / 9) * 100
    ax_co.annotate(f'Current: {current_co:.2f} PPM\n({pct_of_limit:.1f}% of WHO limit)',
                   xy=(0.02, 0.95), xycoords='axes fraction',
                   fontsize=8, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    ax_co.legend(fontsize=7, loc='upper right')
    set_time_xticks(ax_co, labels)

    # ── Temperature Plot ──────────────────────────────────────────
    ax_temp.clear()
    ax_temp.set_title('Temperature (°C)', fontweight='bold')
    ax_temp.set_ylabel('°C')
    ax_temp.plot(x, list(temp_data), color='darkorange', linewidth=1.5)
    ax_temp.fill_between(x, list(temp_data), alpha=0.2, color='darkorange')
    temp_min = max(0, min(temp_data) - 2)
    temp_max = max(temp_data) + 2
    ax_temp.set_ylim(bottom=temp_min, top=temp_max)
    set_time_xticks(ax_temp, labels)

    # ── Humidity Plot ─────────────────────────────────────────────
    ax_hum.clear()
    ax_hum.set_title('Humidity (%)', fontweight='bold')
    ax_hum.set_ylabel('%')
    ax_hum.plot(x, list(humidity_data), color='mediumseagreen', linewidth=1.5)
    ax_hum.fill_between(x, list(humidity_data), alpha=0.2, color='mediumseagreen')
    hum_min = max(0, min(humidity_data) - 5)
    hum_max = min(100, max(humidity_data) + 5)
    ax_hum.set_ylim(bottom=hum_min, top=hum_max)
    ax_hum.axhline(y=30, color='orange', linestyle='--', linewidth=1, label='Low (30%)')
    ax_hum.axhline(y=60, color='orange', linestyle='--', linewidth=1, label='High (60%)')
    ax_hum.legend(fontsize=7, loc='upper right')
    set_time_xticks(ax_hum, labels)

    plt.tight_layout(pad=3.0)

# ── Run ───────────────────────────────────────────────────────────
print("\n=== IAQ Logger v2 Started ===")
print(f"Logging to: {CSV_FILE}")
print(f"Press Ctrl+C or close the graph window to stop\n")

ani = animation.FuncAnimation(fig, update, interval=500, cache_frame_data=False)

try:
    plt.show()
except KeyboardInterrupt:
    pass
finally:
    ser.close()
    print(f"\n=== Logging stopped ===")
    print(f"Total readings logged: {reading_count}")
    print(f"Data saved to: {CSV_FILE}")