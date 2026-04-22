#include <Arduino.h>
#include <WiFi.h>
#include <DHT.h>
#include <Firebase_ESP_Client.h>

#include "addons/TokenHelper.h"
#include "addons/RTDBHelper.h"

// KONFIGURASI WIFI & FIREBASE
#define WIFI_SSID "TP-Link_42CE"
#define WIFI_PASSWORD "21011980"
#define API_KEY "AIzaSyCFYf6a4gZsw27YDEl9OfdgM0R8sJz8YXk"
#define DATABASE_URL "https://smart-plant-system-372b4-default-rtdb.asia-southeast1.firebasedatabase.app" 


// DEFINISI PIN
#define PUMP_PIN 4        // Pin untuk Relay/Transistor Dinamo Pompa
#define SOIL_PIN 34       // Pin Analog untuk Sensor Kelembapan Tanah (ADC1)
#define TRIG_PIN 5        // Pin Trigger Sensor Ultrasonik HC-SR04
#define ECHO_PIN 18       // Pin Echo Sensor Ultrasonik HC-SR04
#define DHT_PIN 12        // Pin Data Sensor DHT11

// KONFIGURASI SENSOR SUHU
#define DHT_TYPE DHT11
DHT dht(DHT_PIN, DHT_TYPE);

// DIMENSI WADAH AIR (Dalam cm)
const float TINGGI_WADAH_CM = 23.0; 

// OBJEK FIREBASE
FirebaseData fbdo;
FirebaseData streamData;
FirebaseAuth auth;
FirebaseConfig config;

// VARIABEL GLOBAL
String currentMode = "auto";
bool manualPumpTrigger = false;
unsigned long sendDataPrevMillis = 0;
unsigned long logPrevMillis = 0;
int timerDelay = 5000;  // Kirim data telemetri tiap 5 detik
int logDelay = 2000;    // Log diagnostik tiap 2 detik

// THRESHOLD PENYIRAMAN
const int SOIL_DRY_THRESHOLD = 2500;  // Di atas ini = tanah kering, pompa nyala
const int SOIL_SENSOR_MAX = 4095;     // Nilai ADC maksimum (12-bit)
const int SOIL_SENSOR_SUSPECT = 4080; // Di atas ini = kemungkinan sensor rusak/terputus

// FUNGSI BACA SENSOR

// 1. Fungsi Baca Sensor Kelembapan Tanah
// ESP32 ADC membaca 0 (basah maksimal) hingga 4095 (kering maksimal)
int readSoilMoisture() { 
  int rawValue = analogRead(SOIL_PIN);
  return rawValue; 
} 

// 2. Fungsi Baca Sensor Ultrasonik (Mengembalikan Sisa Ketinggian Air dalam cm)
float readWaterLevel() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);   
  
  if (duration == 0) {
    return 0; // Sensor error atau tidak terbaca
  }

  // Hitung jarak dari sensor ke permukaan air (Kecepatan suara = 0.034 cm/us)
  float distanceToWater = duration * 0.034 / 2;
  
  // Hitung sisa air: Tinggi total wadah dikurangi jarak sensor ke air
  float sisaAirCm = TINGGI_WADAH_CM - distanceToWater;
  
  // Cegah nilai negatif jika air benar-benar kosong
  if (sisaAirCm < 0) sisaAirCm = 0;
  
  return sisaAirCm;
}

// DIAGNOSTIK SENSOR SAAT STARTUP
void runSensorDiagnostic() {
  Serial.println();
  Serial.println("╔══════════════════════════════════════╗");
  Serial.println("║     DIAGNOSTIK SENSOR STARTUP        ║");
  Serial.println("╠══════════════════════════════════════╣");
  
  // Test Sensor Tanah
  int soilRaw = analogRead(SOIL_PIN);
  Serial.printf("║ Tanah (ADC)  : %-4d", soilRaw);
  if (soilRaw >= SOIL_SENSOR_SUSPECT) {
    Serial.println("  ⚠ SUSPECT: Pin floating / sensor terputus!");
  } else if (soilRaw == 0) {
    Serial.println("  ⚠ SUSPECT: Selalu 0, cek kabel data!");
  } else {
    Serial.printf("  ✓ OK (threshold=%d)\n", SOIL_DRY_THRESHOLD);
  }

  // Test Sensor Ultrasonik
  float water = readWaterLevel();
  Serial.printf("║ Air (cm)     : %-5.1f", water);
  if (water <= 0) {
    Serial.println(" ⚠ SUSPECT: Tidak terbaca, cek TRIG/ECHO!");
  } else {
    Serial.println(" ✓ OK");
  }

  // Test DHT11
  float temp = dht.readTemperature();
  Serial.print("║ Suhu (°C)    : ");
  if (isnan(temp)) {
    Serial.println("NaN    ⚠ SUSPECT: DHT11 tidak terbaca!");
  } else {
    Serial.printf("%-5.1f  ✓ OK\n", temp);
  }

  // Test Relay (pastikan mati)
  Serial.printf("║ Pompa (Pin %d): LOW   ✓ Aman\n", PUMP_PIN);
  
  Serial.println("╚══════════════════════════════════════╝");
  Serial.println();
}

// CALLBACK STREAM FIREBASE
void streamCallback(FirebaseStream data) {
  String path = data.dataPath();
  
  if (path == "/mode") {
    currentMode = data.stringData();
    Serial.println("Dashboard CMD: Mode penyiraman -> " + currentMode);
  } else if (path == "/manual_pump") {
    manualPumpTrigger = data.boolData();
    Serial.println("Dashboard CMD: Pompa Manual -> " + String(manualPumpTrigger ? "ON" : "OFF"));
  }
}

void streamTimeoutCallback(bool timeout) {
  if (timeout) {
    Serial.println("Stream timeout... Sinkronisasi ulang koneksi realtime.");
  }
}

// SETUP
void setup() {
  Serial.begin(115200);
  
  // Inisialisasi Pin
  pinMode(PUMP_PIN, OUTPUT);
  pinMode(SOIL_PIN, INPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  
  digitalWrite(PUMP_PIN, LOW); // Pompa mati di awal

  // Inisialisasi Sensor DHT
  dht.begin();

  // Koneksi WiFi
  Serial.print("Menghubungkan ke WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Terhubung! IP: " + WiFi.localIP().toString());

  // Inisialisasi Firebase
  config.api_key = API_KEY;
  config.database_url = DATABASE_URL;
  config.token_status_callback = tokenStatusCallback;

  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);

  // Anonymous Authentication — tidak butuh email/password
  // Pastikan Anonymous Auth sudah di-enable di Firebase Console!
  Serial.print("Firebase Anonymous Auth");
  if (Firebase.signUp(&config, &auth, "", "")) {
    Serial.println(" ✓ Berhasil!");
  } else {
    Serial.println(" ✗ GAGAL!");
    Serial.println("  Error: " + String(config.signer.signupError.message.c_str()));
    Serial.println("  → Pastikan Anonymous Auth di-enable di Firebase Console.");
    Serial.println("  → Authentication > Sign-in method > Anonymous > Enable");
  }

  // Inisiasi Streaming secara realtime ke node kontrol
  if (!Firebase.RTDB.beginStream(&streamData, "/smart_plant/controls")) {
    Serial.printf("Gagal memulai stream: %s\n", streamData.errorReason().c_str());
  } else {
    Serial.println("Berhasil mengaitkan jalur stream realtime!");
  }
  Firebase.RTDB.setStreamCallback(&streamData, streamCallback, streamTimeoutCallback);

  // Jalankan diagnostik sensor sebelum mulai loop
  runSensorDiagnostic();
}

// MAIN LOOP
void loop() {
  // =============================================
  // BAGIAN 1: BACA SENSOR (Selalu jalan, independen dari Firebase)
  // =============================================
  int soilMoisture = readSoilMoisture();
  float waterLevel = readWaterLevel();

  // =============================================
  // BAGIAN 2: LOGIKA KEPUTUSAN POMPA
  // =============================================
  bool shouldPumpRun = false;
  String pumpReason = "";
  bool sensorSuspect = false;

  // Deteksi sensor tanah yang kemungkinan rusak/terputus
  if (soilMoisture >= SOIL_SENSOR_SUSPECT) {
    sensorSuspect = true;
    pumpReason = "BLOCKED: Sensor tanah suspect (ADC=" + String(soilMoisture) + ", kemungkinan terputus!)";
    shouldPumpRun = false; // JANGAN nyalakan pompa jika sensor tidak reliable
  }
  // Proteksi Dinamo Terbakar (Fail-Safe): Air terlalu rendah
  else if (waterLevel <= 2.0) {
    shouldPumpRun = false;
    pumpReason = "BLOCKED: Air terlalu rendah (" + String(waterLevel, 1) + " cm <= 2.0 cm)";
  } 
  else {
    if (currentMode == "auto") {
      if (soilMoisture > SOIL_DRY_THRESHOLD) {
        shouldPumpRun = true;
        pumpReason = "AUTO ON: Tanah kering (" + String(soilMoisture) + " > " + String(SOIL_DRY_THRESHOLD) + ")";
      } else {
        shouldPumpRun = false;
        pumpReason = "AUTO OFF: Tanah cukup lembab (" + String(soilMoisture) + " <= " + String(SOIL_DRY_THRESHOLD) + ")";
      }
    } 
    else if (currentMode == "manual") {
      if (manualPumpTrigger) {
        shouldPumpRun = true;
        pumpReason = "MANUAL ON: Tombol ditekan dari dashboard";
      } else {
        shouldPumpRun = false;
        pumpReason = "MANUAL OFF: Menunggu perintah dashboard";
      }
    }
  }

  // Aktuasi Pompa
  digitalWrite(PUMP_PIN, shouldPumpRun ? HIGH : LOW);

  // =============================================
  // BAGIAN 3: LOG DIAGNOSTIK (Setiap 2 Detik)
  // =============================================
  if (millis() - logPrevMillis > logDelay || logPrevMillis == 0) {
    logPrevMillis = millis();

    Serial.println("────────────────────────────────────────");
    Serial.printf("[%lums] MODE: %s | Firebase: %s\n", 
                  millis(), currentMode.c_str(), Firebase.ready() ? "Ready" : "NOT READY");
    Serial.printf("  Tanah (ADC) : %d / %d", soilMoisture, SOIL_SENSOR_MAX);
    if (sensorSuspect) Serial.print("  ⚠ SENSOR SUSPECT!");
    Serial.println();
    Serial.printf("  Air (cm)    : %.1f / %.1f\n", waterLevel, TINGGI_WADAH_CM);
    Serial.printf("  Pompa       : %s\n", shouldPumpRun ? "🟢 ON" : "⚫ OFF");
    Serial.printf("  Alasan      : %s\n", pumpReason.c_str());
  }

  // =============================================
  // BAGIAN 4: TELEMETRI FIREBASE (Setiap 5 Detik)
  // =============================================
  if (Firebase.ready() && (millis() - sendDataPrevMillis > timerDelay || sendDataPrevMillis == 0)) {
    sendDataPrevMillis = millis();
    
    // Baca DHT11 (lambat, cukup tiap 5 detik)
    float temperature = dht.readTemperature();
    if (isnan(temperature)) {
      temperature = -999.0;
      Serial.println("  ⚠ DHT11: Gagal membaca suhu!");
    }

    // Push data ke Firebase Realtime Database
    bool ok1 = Firebase.RTDB.setInt(&fbdo, "/smart_plant/sensors/soil_moisture", soilMoisture);
    bool ok2 = Firebase.RTDB.setFloat(&fbdo, "/smart_plant/sensors/water_level", waterLevel);
    bool ok3 = Firebase.RTDB.setFloat(&fbdo, "/smart_plant/sensors/temperature", temperature);
    
    Serial.println("────────────────────────────────────────");
    Serial.println("📡 TELEMETRI FIREBASE:");
    Serial.printf("  Suhu     : %.1f °C  %s\n", temperature, temperature == -999.0 ? "[ERR]" : "[OK]");
    Serial.printf("  Air      : %.1f cm      %s\n", waterLevel, ok2 ? "[OK]" : "[FAIL]");
    Serial.printf("  Tanah    : %d ADC      %s\n", soilMoisture, ok1 ? "[OK]" : "[FAIL]");
    Serial.printf("  Suhu FB  :              %s\n", ok3 ? "[OK]" : "[FAIL]");
    
    if (!ok1 || !ok2 || !ok3) {
      Serial.printf("  ⚠ Error: %s\n", fbdo.errorReason().c_str());
    }
  }
}