# ============================================================
# actuators.py — Modul Kontrol Aktuator (Raspberry Pi Pico 2 W)
# ============================================================
# Mengontrol pompa air via H-Bridge motor driver.
# IN1 = GP15, IN2 = GP14
#
# Tabel Kebenaran H-Bridge:
#   IN1=HIGH, IN2=LOW  → Motor berputar maju (pompa nyala)
#   IN1=LOW,  IN2=LOW  → Motor berhenti (pompa mati)
# ============================================================

from machine import Pin
import config

# ----- INISIALISASI PIN H-BRIDGE -----
_in1 = Pin(config.IN1_PIN, Pin.OUT)
_in2 = Pin(config.IN2_PIN, Pin.OUT)

# Pastikan pompa mati saat inisialisasi
_in1.low()
_in2.low()


# ----- FUNGSI KONTROL POMPA -----

def pump_on():
    """
    Nyalakan pompa (motor berputar maju).
    IN1=HIGH, IN2=LOW
    """
    _in1.high()
    _in2.low()


def pump_off():
    """
    Matikan pompa (motor berhenti).
    IN1=LOW, IN2=LOW
    """
    _in1.low()
    _in2.low()


def is_pump_on():
    """
    Cek apakah pompa sedang menyala.
    
    Return:
        bool: True jika pompa nyala, False jika mati.
    """
    return _in1.value() == 1 and _in2.value() == 0
