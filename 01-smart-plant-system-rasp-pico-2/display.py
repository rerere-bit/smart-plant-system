# ============================================================
# display.py — Modul I2C LCD (Raspberry Pi Pico 2 W)
# ============================================================
# Driver untuk LCD karakter I2C (HD44780 + PCF8574 backpack).
# Menampilkan status sensor ke layar LCD 16x2 via I2C.
#
# Wiring:
#   SDA = GP0 (Pin 1)
#   SCL = GP1 (Pin 2)
#   VCC = 5V
#   GND = GND
# ============================================================

import utime
from machine import Pin, I2C
import config

# ===== DRIVER LCD I2C (HD44780 + PCF8574) =====

class LcdApi:
    def __init__(self, num_lines, num_columns):
        self.num_lines = num_lines
        self.num_columns = num_columns
        self.cursor_x = 0
        self.cursor_y = 0
        self.backlight = True
        self.display_on = True

    def clear(self):
        self.hal_write_command(0x01)
        utime.sleep_ms(2)

    def putstr(self, string):
        for char in string:
            self.putchar(char)

    def putchar(self, char):
        if char == '\n':
            self.cursor_y += 1
            self.cursor_x = 0
        elif char == '\r':
            self.cursor_x = 0
        else:
            self.hal_write_data(ord(char))
            self.cursor_x += 1
        self.move_to(self.cursor_x, self.cursor_y)

    def move_to(self, cursor_x, cursor_y):
        self.cursor_x = cursor_x
        self.cursor_y = cursor_y
        addr = cursor_x & 0x3f
        if cursor_y & 1:
            addr += 0x40
        if cursor_y & 2:
            addr += self.num_columns
        self.hal_write_command(0x80 | addr)


class I2cLcd(LcdApi):
    def __init__(self, i2c, i2c_addr, num_lines, num_columns):
        self.i2c = i2c
        self.i2c_addr = i2c_addr
        self.backlight = True
        utime.sleep_ms(20)
        self.hal_write_init()
        super().__init__(num_lines, num_columns)

    def hal_write_init(self):
        self.hal_write_command(0x33)
        self.hal_write_command(0x32)
        self.hal_write_command(0x28)
        self.hal_write_command(0x0C)
        self.hal_write_command(0x06)
        self.clear()

    def hal_write_command(self, cmd):
        self.hal_write_8bits(cmd & 0xF0)
        self.hal_write_8bits((cmd << 4) & 0xF0)

    def hal_write_data(self, data):
        self.hal_write_8bits((data & 0xF0) | 0x01)
        self.hal_write_8bits(((data << 4) & 0xF0) | 0x01)

    def hal_write_8bits(self, value):
        bit_bl = 0x08 if self.backlight else 0x00
        self.i2c.writeto(self.i2c_addr, bytearray([value | bit_bl | 0x04]))
        self.i2c.writeto(self.i2c_addr, bytearray([value | bit_bl]))


# ===== INTERFACE MODULE =====

_lcd = None
_available = False


def init():
    """
    Inisialisasi I2C LCD display.
    Jika display tidak terdeteksi, sistem tetap jalan tanpa display.
    
    Return:
        bool: True jika berhasil, False jika gagal.
    """
    global _lcd, _available
    
    try:
        i2c = I2C(
            config.I2C_ID,
            sda=Pin(config.SDA_PIN),
            scl=Pin(config.SCL_PIN),
            freq=100000
        )
        
        # Scan I2C bus untuk mendeteksi LCD
        devices = i2c.scan()
        if not devices:
            print("║ LCD (I2C)  : Tidak terdeteksi  ⚠ Cek kabel SDA/SCL!")
            _available = False
            return False
        
        # Gunakan alamat pertama yang ditemukan (biasanya 0x27 atau 0x3F)
        addr = devices[0]
        
        _lcd = I2cLcd(i2c, addr, config.LCD_ROWS, config.LCD_COLS)
        _available = True
        
        # Tampilkan splash screen
        _lcd.clear()
        _lcd.move_to(1, 0)
        _lcd.putstr("Smart Plant Sys")
        _lcd.move_to(2, 1)
        _lcd.putstr("Starting...")
        
        print("║ LCD (I2C)  : 0x{:02X}   ✓ OK".format(addr))
        return True
        
    except Exception as e:
        print("║ LCD (I2C)  : Error — {}".format(e))
        _available = False
        return False


def is_available():
    """Cek apakah display tersedia dan siap."""
    return _available


def update(temperature, water_level, soil_moisture, pump_on, mode):
    """
    Update tampilan LCD dengan data sensor terbaru.
    
    Layout 16x2:
      Baris 1: "28.5C Air:15.2cm"
      Baris 2: "S:62%  Pump:OFF "
    
    Args:
        temperature (float): Suhu °C (atau None jika error)
        water_level (float): Tinggi air (cm)
        soil_moisture (int): Nilai ADC 16-bit 
        pump_on (bool): Apakah pompa menyala
        mode (str): Mode "auto" / "manual"
    """
    if not _available or _lcd is None:
        return
    
    try:
        # --- Baris 1: Suhu & Air ---
        if temperature is not None and temperature != -999.0:
            temp_str = "{:.1f}C".format(temperature)
        else:
            temp_str = "--.-C"
        
        water_str = "Air:{:.1f}cm".format(water_level)
        
        # Padding agar total 16 karakter
        line1 = temp_str + " " * (config.LCD_COLS - len(temp_str) - len(water_str)) + water_str
        
        # --- Baris 2: Kelembapan & Pompa ---
        moisture_pct = max(0, min(100, 100 - (soil_moisture / config.SOIL_SENSOR_MAX * 100)))
        soil_str = "S:{:.0f}%".format(moisture_pct)
        
        pump_str = "Pump:{}".format("ON" if pump_on else "OFF")
        
        line2 = soil_str + " " * (config.LCD_COLS - len(soil_str) - len(pump_str)) + pump_str
        
        # Tulis ke LCD
        _lcd.move_to(0, 0)
        _lcd.putstr(line1[:config.LCD_COLS])
        _lcd.move_to(0, 1)
        _lcd.putstr(line2[:config.LCD_COLS])
        
    except Exception as e:
        print("LCD update error: {}".format(e))


def show_message(line1="", line2=""):
    """
    Tampilkan pesan kustom di layar.
    
    Args:
        line1: Baris pertama (maks 16 karakter)
        line2: Baris kedua (maks 16 karakter)
    """
    if not _available or _lcd is None:
        return
    
    try:
        _lcd.clear()
        if line1:
            _lcd.move_to(0, 0)
            _lcd.putstr(line1[:config.LCD_COLS])
        if line2:
            _lcd.move_to(0, 1)
            _lcd.putstr(line2[:config.LCD_COLS])
    except Exception:
        pass
