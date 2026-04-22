# Smart Plant System — Raspberry Pi Pico 2 W

Sistem irigasi otomatis dan monitoring tanaman berbasis **Raspberry Pi Pico 2 W** menggunakan **MicroPython**. Migrasi dari versi ESP32.

## Arsitektur Sistem

```
┌──────────────────────────────┐
│   Raspberry Pi Pico 2 W     │
│   (MicroPython)              │
│                              │
│  GP0  ──→ OLED SDA (I2C)    │
│  GP1  ──→ OLED SCL (I2C)    │
│  GP2  ──→ HC-SR04 TRIG      │
│  GP3  ←── HC-SR04 ECHO      │
│  GP4  ←── DHT11 Data        │
│  GP14 ──→ H-Bridge IN2      │
│  GP15 ──→ H-Bridge IN1      │
│  GP26 ←── Soil Moisture ADC  │
│                              │
│  WiFi ←──→ Firebase RTDB    │
│           (REST API)         │
└──────────────────────────────┘
```

## Struktur File

| File | Deskripsi |
|---|---|
| `config.py` | Konfigurasi WiFi, Firebase, pin, threshold, timing |
| `sensors.py` | Modul pembacaan sensor (soil, ultrasonik, DHT11) |
| `actuators.py` | Modul kontrol H-Bridge motor (pompa) |
| `firebase_client.py` | REST API client untuk Firebase RTDB |
| `display.py` | Modul LCD OLED SSD1306 (I2C) — tampilan status sensor |
| `main.py` | Entry point & main loop |

## Wiring / Pin Mapping

| Komponen | Pin Pico 2 W | Tipe |
|---|---|---|
| OLED SDA | GP0 | I2C Data |
| OLED SCL | GP1 | I2C Clock |
| HC-SR04 Trigger | GP2 | Digital Output |
| HC-SR04 Echo | GP3 | Digital Input |
| DHT11 Data | GP4 | Digital Input (Pull-Up) |
| H-Bridge IN2 (Motor Stop) | GP14 | Digital Output |
| H-Bridge IN1 (Motor Forward) | GP15 | Digital Output |
| Soil Moisture Sensor | GP26 (ADC0) | Analog Input |

## Perbedaan dari Versi ESP32

| Aspek | ESP32 | Pico 2 W |
|---|---|---|
| Framework | Arduino (C++) | MicroPython |
| WiFi | `WiFi.h` | `network.WLAN` |
| ADC | 12-bit (0–4095) | 16-bit (0–65535) |
| Firebase | Native library (SSE stream) | REST API + polling |
| Motor | Relay single pin | H-Bridge (IN1/IN2) |
| DHT11 | Adafruit library | Built-in `dht` module |
| Display | — | SSD1306 OLED 128x64 (I2C) |
| Upload | PlatformIO | Thonny / mpremote |

## Cara Penggunaan

### 1. Flash MicroPython ke Pico 2 W

1. Tahan tombol **BOOTSEL** pada Pico 2 W
2. Sambungkan ke komputer via USB (tetap tahan BOOTSEL)
3. Lepas tombol setelah drive **RPI-RP2** muncul
4. Download firmware MicroPython dari: https://micropython.org/download/RPI_PICO2_W/
5. Salin file `.uf2` ke drive RPI-RP2
6. Pico akan reboot otomatis dengan MicroPython

### 2. Install Library SSD1306

Sebelum upload kode, install driver OLED di Pico:

**Via Thonny:**
Tools > Manage Packages > Cari `ssd1306` > Install

**Via REPL:**
```python
import mip
mip.install("ssd1306")
```

### 3. Upload Kode

**Via Thonny:**
1. Buka Thonny IDE
2. Pilih interpreter: MicroPython (Raspberry Pi Pico)
3. Upload semua file (`.py`) ke Pico:
   - `config.py`
   - `sensors.py`
   - `actuators.py`
   - `firebase_client.py`
   - `display.py`
   - `main.py`

**Via mpremote:**
```bash
pip install mpremote
mpremote cp config.py sensors.py actuators.py firebase_client.py display.py main.py :
```

### 4. Konfigurasi

Edit `config.py` untuk menyesuaikan:
- `WIFI_SSID` dan `WIFI_PASSWORD` — Kredensial WiFi
- `API_KEY` dan `DATABASE_URL` — Firebase project
- `SOIL_DRY_THRESHOLD` — Sesuaikan setelah kalibrasi sensor

### 5. Jalankan

Setelah upload, Pico akan otomatis menjalankan `main.py` saat boot.
Untuk melihat log diagnostik, buka serial monitor di Thonny atau:

```bash
mpremote connect auto repl
```

## Catatan Teknis

- **ADC 16-bit**: `read_u16()` mengembalikan 0–65535. Threshold kering diskalakan dari ESP32 (2500/4095 → 40000/65535).
- **Firebase Polling**: Kontrol dari dashboard di-poll setiap 2 detik (bukan realtime stream seperti ESP32). Delay respons 1-2 detik.
- **Sensor Suspect**: Threshold dinaikkan ke 65200 (99.5%) agar tanah kering di udara (~58000-63000) tidak salah dideteksi. Sensor suspect hanya mem-block mode **auto**, mode **manual** tetap bisa digunakan.
- **Fail-Safe**: Pompa otomatis mati jika air di wadah ≤ 2.0 cm (berlaku di semua mode).
- **Token Refresh**: Token Firebase otomatis di-refresh sebelum expired.
- **OLED Display**: Menampilkan suhu, tinggi air, kelembapan tanah (%), dan status pompa. Refresh setiap 1 detik. Jika display tidak terhubung, sistem tetap berjalan normal.
