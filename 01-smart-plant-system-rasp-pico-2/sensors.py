# ============================================================
# sensors.py — Modul Pembacaan Sensor (Raspberry Pi Pico 2 W)
# ============================================================

from machine import Pin, ADC, time_pulse_us
import dht
import time

import config

# ----- INISIALISASI SENSOR -----

# Sensor Ultrasonik HC-SR04
_trig = Pin(config.TRIG_PIN, Pin.OUT)
_echo = Pin(config.ECHO_PIN, Pin.IN)

# Sensor Kelembapan Tanah (ADC)
_soil_adc = ADC(Pin(config.SOIL_PIN))

# Sensor Suhu DHT11
_dht_sensor = dht.DHT11(Pin(config.DHT_PIN, Pin.IN, Pin.PULL_UP))


# ----- FUNGSI BACA SENSOR -----

def read_soil_moisture():
    """
    Baca nilai kelembapan tanah dari ADC.
    
    Return:
        int: Nilai ADC 16-bit (0–65535).
             0 = basah maksimal, 65535 = kering maksimal.
    """
    return _soil_adc.read_u16()


def read_water_level():
    """
    Baca sisa ketinggian air menggunakan sensor ultrasonik HC-SR04.
    
    Return:
        float: Sisa ketinggian air dalam cm.
               0 jika sensor error atau tidak terbaca.
    """
    # Kirim pulse trigger 10μs
    _trig.low()
    time.sleep_us(2)
    _trig.high()
    time.sleep_us(10)
    _trig.low()
    
    # Baca durasi echo (timeout 30ms = 30000μs)
    try:
        duration = time_pulse_us(_echo, 1, 30000)
    except OSError:
        return 0.0
    
    if duration < 0:
        return 0.0  # Timeout, sensor error
    
    # Hitung jarak dari sensor ke permukaan air (kecepatan suara = 0.034 cm/μs)
    distance_to_water = duration * 0.034 / 2
    
    # Hitung sisa air: tinggi total wadah dikurangi jarak sensor ke air
    sisa_air_cm = config.TINGGI_WADAH_CM - distance_to_water
    
    # Cegah nilai negatif
    if sisa_air_cm < 0:
        sisa_air_cm = 0.0
    
    return sisa_air_cm


def read_temperature():
    """
    Baca suhu dari sensor DHT11.
    
    Return:
        float: Suhu dalam °C.
        None: Jika gagal membaca sensor.
    """
    try:
        _dht_sensor.measure()
        return _dht_sensor.temperature()
    except OSError:
        return None


# ----- DIAGNOSTIK SENSOR -----

def run_diagnostic():
    """
    Jalankan diagnostik semua sensor saat startup.
    Mencetak status setiap sensor ke REPL (serial).
    """
    print()
    print("╔══════════════════════════════════════╗")
    print("║     DIAGNOSTIK SENSOR STARTUP        ║")
    print("╠══════════════════════════════════════╣")
    
    # Test Sensor Tanah
    soil_raw = read_soil_moisture()
    status = ""
    if soil_raw >= config.SOIL_SENSOR_SUSPECT:
        status = "  ⚠ SUSPECT: Pin floating / sensor terputus!"
    elif soil_raw == 0:
        status = "  ⚠ SUSPECT: Selalu 0, cek kabel data!"
    else:
        status = "  ✓ OK (threshold={})".format(config.SOIL_DRY_THRESHOLD)
    print("║ Tanah (ADC)  : {:<5d}{}".format(soil_raw, status))
    
    # Test Sensor Ultrasonik
    water = read_water_level()
    if water <= 0:
        status = " ⚠ SUSPECT: Tidak terbaca, cek TRIG/ECHO!"
    else:
        status = " ✓ OK"
    print("║ Air (cm)     : {:<5.1f}{}".format(water, status))
    
    # Test DHT11
    temp = read_temperature()
    if temp is None:
        print("║ Suhu (°C)    : NaN    ⚠ SUSPECT: DHT11 tidak terbaca!")
    else:
        print("║ Suhu (°C)    : {:<5.1f}  ✓ OK".format(temp))
    
    # Test Motor (pastikan mati)
    print("║ Pompa (IN1={}, IN2={}): LOW   ✓ Aman".format(
        config.IN1_PIN, config.IN2_PIN))
    
    print("╚══════════════════════════════════════╝")
    print()
