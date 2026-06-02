#include <Wire.h>
#include <rgb_lcd.h>
#include <DHT.h>

rgb_lcd lcd;

#define DHT_PIN 32
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

#define MQ135_PIN 34
#define MQ7_PIN 35

// Calibration constants
#define DHT_TEMP_OFFSET  2.0
#define RL               10.0
#define ADC_VREF         3.3
#define SENSOR_VCC       5.0
#define ADC_RESOLUTION   4095.0

// R0 values from calibration
#define R0_MQ135 233.35
#define R0_MQ7   2.59

// PPM safety clamps
#define MQ135_PPM_MAX 5000
#define MQ7_PPM_MAX   1000

// Update intervals
#define DISPLAY_INTERVAL 3000
#define SERIAL_INTERVAL  500

// ADC averaging samples
#define ADC_SAMPLES 10

int mq135_value = 0;
int mq7_value = 0;
float mq135_ppm = 0;
float mq7_ppm = 0;
float temperature = 25.0;
float humidity = 50.0;

int displayMode = 0;
unsigned long lastUpdate = 0;
unsigned long lastSerial = 0;

// ── ADC averaging (reduces noise and filters spikes) ──────────────
int readADCAverage(int pin, int samples) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    sum += analogRead(pin);
    delay(2);
  }
  return sum / samples;
}

// ── Calculate RS from raw ADC ──────────────────────────────────────
float calculateRS(int adcValue) {
  if (adcValue >= 4095) adcValue = 4094;
  if (adcValue <= 0) adcValue = 1;
  float voltage = adcValue * (ADC_VREF / ADC_RESOLUTION);
  return ((SENSOR_VCC - voltage) / voltage) * RL;
}

// ── MQ135 -> CO2 equivalent PPM ───────────────────────────────────
float getMQ135PPM(int adcValue) {
  float rs = calculateRS(adcValue);
  float ratio = rs / R0_MQ135;
  float ppm = 110.47 * pow(ratio, -2.862);
  if (ppm > MQ135_PPM_MAX) ppm = MQ135_PPM_MAX;
  if (ppm < 0) ppm = 0;
  return ppm;
}

// ── MQ7 -> CO PPM ─────────────────────────────────────────────────
float getMQ7PPM(int adcValue) {
  float rs = calculateRS(adcValue);
  float ratio = rs / R0_MQ7;
  float ppm = 99.042 * pow(ratio, -1.518);
  if (ppm > MQ7_PPM_MAX) ppm = MQ7_PPM_MAX;
  if (ppm < 0) ppm = 0;
  return ppm;
}

// ── Air quality classification ─────────────────────────────────────
String getAirQuality() {
  if (mq135_ppm < 1000 && mq7_ppm < 9) return "GOOD";
  if (mq135_ppm < 2000 && mq7_ppm < 25) return "MODERATE";
  return "POOR";
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  dht.begin();
  delay(2000);

  lcd.begin(16, 2);
  lcd.setRGB(255, 255, 255);
  lcd.clear();
  lcd.print("IAQ System");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
  delay(2000);

  // Test DHT11 and update globals immediately
  Serial.println("Testing DHT11...");
  for (int i = 0; i < 3; i++) {
    float t = dht.readTemperature() - DHT_TEMP_OFFSET;
    float h = dht.readHumidity();
    if (isnan(t) || isnan(h)) {
      Serial.println("DHT11 read failed!");
    } else {
      temperature = t;
      humidity = h;
      Serial.print("T: "); Serial.print(t);
      Serial.print("C, H: "); Serial.print(h);
      Serial.println("%");
    }
    delay(2000);
  }

  lcd.clear();
  lcd.print("Sensors Ready!");
  Serial.println("\n=== System Ready ===");
  Serial.println("--- Calibration Values ---");
  Serial.print("R0 MQ135  : "); Serial.println(R0_MQ135);
  Serial.print("R0 MQ7    : "); Serial.println(R0_MQ7);
  Serial.print("Sensor VCC: "); Serial.println(SENSOR_VCC);
  Serial.print("DHT offset: -"); Serial.println(DHT_TEMP_OFFSET);
  Serial.print("ADC samples: "); Serial.println(ADC_SAMPLES);
  Serial.println("--------------------------\n");

  delay(2000);
  lastUpdate = millis();
  lastSerial = millis();
}

void loop() {
  readSensors();

  if (millis() - lastSerial >= SERIAL_INTERVAL) {
    printToSerial();
    lastSerial = millis();
  }

  if (millis() - lastUpdate >= DISPLAY_INTERVAL) {
    updateDisplay();
    lastUpdate = millis();
  }

  delay(100);
}

void readSensors() {
  // Average 10 samples to reduce noise and filter spikes
  mq135_value = readADCAverage(MQ135_PIN, ADC_SAMPLES);
  mq7_value   = readADCAverage(MQ7_PIN,   ADC_SAMPLES);
  mq135_ppm   = getMQ135PPM(mq135_value);
  mq7_ppm     = getMQ7PPM(mq7_value);

  static unsigned long lastDHTRead = 0;
  if (millis() - lastDHTRead >= 2000) {
    float t = dht.readTemperature() - DHT_TEMP_OFFSET;
    float h = dht.readHumidity();
    if (!isnan(t) && !isnan(h)) {
      temperature = t;
      humidity = h;
    }
    lastDHTRead = millis();
  }
}

void printToSerial() {
  String aq = getAirQuality();
  Serial.println("========== Sensor Readings ==========");
  Serial.print("MQ-135 (ADC)      : "); Serial.println(mq135_value);
  Serial.print("MQ-135 (CO2 PPM)  : "); Serial.println(mq135_ppm, 1);
  Serial.print("MQ-7   (ADC)      : "); Serial.println(mq7_value);
  Serial.print("MQ-7   (CO PPM)   : "); Serial.println(mq7_ppm, 2);
  Serial.print("Temperature       : "); Serial.print(temperature, 1); Serial.println(" °C");
  Serial.print("Humidity          : "); Serial.print(humidity, 1); Serial.println(" %");
  Serial.print("Air Quality       : "); Serial.println(aq);
  Serial.println("=====================================\n");
}

void updateDisplay() {
  lcd.clear();
  String aq = getAirQuality();

  switch (displayMode) {
    case 0:
      lcd.setCursor(0, 0);
      lcd.print("CO2:");
      lcd.print(mq135_ppm, 0);
      lcd.print("ppm");
      lcd.setCursor(0, 1);
      lcd.print("CO:");
      lcd.print(mq7_ppm, 2);
      lcd.print("ppm");
      break;

    case 1:
      lcd.setCursor(0, 0);
      lcd.print("Temp: ");
      lcd.print(temperature, 1);
      lcd.print("C");
      lcd.setCursor(0, 1);
      lcd.print("Humid: ");
      lcd.print(humidity, 0);
      lcd.print("%");
      break;

    case 2:
      lcd.setCursor(0, 0);
      lcd.print("Air Quality:");
      lcd.setCursor(0, 1);
      lcd.print(aq);
      if (aq == "GOOD") {
        lcd.setRGB(0, 255, 0);
      } else if (aq == "MODERATE") {
        lcd.setRGB(255, 255, 0);
      } else {
        lcd.setRGB(255, 0, 0);
      }
      break;
  }

  displayMode++;
  if (displayMode > 2) {
    displayMode = 0;
    lcd.setRGB(255, 255, 255);
  }
}