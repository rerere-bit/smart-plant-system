# ============================================================
# config.py — Konfigurasi Smart Plant System (Raspberry Pi Pico 2 W)
# ============================================================

# ----- KONFIGURASI WIFI -----
WIFI_SSID = "TP-Link_42CE"
WIFI_PASSWORD = "21011980"

# ----- KONFIGURASI FIREBASE -----
API_KEY = "AIzaSyCFYf6a4gZsw27YDEl9OfdgM0R8sJz8YXk"
DATABASE_URL = "https://smart-plant-system-372b4-default-rtdb.asia-southeast1.firebasedatabase.app"

# ----- DEFINISI PIN -----
# I2C LCD (HD44780 + PCF8574)
I2C_ID = 0       # I2C bus 0
SDA_PIN = 0      # GP0 — SDA
SCL_PIN = 1      # GP1 — SCL
LCD_COLS = 16    # Jumlah kolom LCD
LCD_ROWS = 2     # Jumlah baris LCD

# Sensor Ultrasonik HC-SR04
TRIG_PIN = 2   # GP2 — Trigger (Output)
ECHO_PIN = 3   # GP3 — Echo (Input)

# Sensor Kelembapan Tanah (ADC)
SOIL_PIN = 26   # GP26 — ADC Channel 0

# Sensor Suhu & Kelembapan DHT11
DHT_PIN = 4    # GP4 — Data (Input, Pull-Up)

# H-Bridge Motor Driver (Pompa)
IN1_PIN = 15   # GP15 — Motor Forward
IN2_PIN = 14   # GP14 — Motor Reverse / Brake

# ----- DIMENSI WADAH AIR -----
TINGGI_WADAH_CM = 23.0   # Tinggi total wadah air (cm)

# ----- THRESHOLD PENYIRAMAN -----
# Pico ADC read_u16() mengembalikan 0–65535 (16-bit)
SOIL_DRY_THRESHOLD = 40000    # Di atas ini = tanah kering, pompa nyala
SOIL_SENSOR_MAX = 65535       # Nilai ADC maksimum (16-bit)
SOIL_SENSOR_SUSPECT = 65200   # Di atas ini = kemungkinan sensor rusak/terputus

# ----- KEAMANAN POMPA -----
# Pompa dimatikan jika air di bawah level ini (semua mode)
WATER_MIN_LEVEL_CM = 15.0

# ----- LOGIKA AUTO-PUMP -----
# Mode auto: pompa nyala selama 3 detik (burst), lalu cooldown 4 jam.
# Mencegah pompa jalan terus-menerus yang bisa merusak tanaman (overwatering).
AUTO_PUMP_DURATION_MS = 3000              # Durasi siram: 3 detik
AUTO_PUMP_COOLDOWN_S = 4 * 60 * 60       # Cooldown: 4 jam (14400 detik)

# ----- TIMING (milidetik) -----
TELEMETRY_INTERVAL_MS = 5000   # Kirim telemetri ke Firebase tiap 5 detik
CONTROL_POLL_INTERVAL_MS = 2000  # Polling kontrol dari Firebase tiap 2 detik
LOG_INTERVAL_MS = 2000          # Log diagnostik ke REPL tiap 2 detik
DISPLAY_INTERVAL_MS = 1000      # Refresh LCD tiap 1 detik
