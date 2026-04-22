# ============================================================
# main.py — Smart Plant System (Raspberry Pi Pico 2 W)
# ============================================================
# Entry point utama. Migrasi dari ESP32 (Arduino/C++).
#
# Alur:
#   1. Koneksi WiFi
#   2. Firebase Anonymous Auth
#   3. Diagnostik sensor & display
#   4. Main loop:
#      - Baca sensor (soil, water level)
#      - Poll kontrol dari Firebase (mode, manual_pump)
#      - Logika keputusan pompa (auto/manual + fail-safe)
#      - Aktuasi H-Bridge
#      - Log diagnostik ke REPL
#      - Push telemetri ke Firebase
#      - Update LCD
#
# Logika Auto-Pump:
#   - Jika tanah kering → pompa nyala 3 detik (burst)
#   - Setelah burst → cooldown 4 jam
#   - Setelah cooldown → cek lagi, jika masih kering → burst lagi
#   - Pompa MATI jika air < 15 cm (semua mode)
# ============================================================

import network
import time
import gc

import config
import sensors
import actuators
import firebase_client
import display


# ----- KONEKSI WIFI -----

def connect_wifi():
    """
    Hubungkan Pico 2 W ke jaringan WiFi.
    Blocking sampai terhubung.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        print("WiFi sudah terhubung! IP: " + wlan.ifconfig()[0])
        return wlan
    
    print("Menghubungkan ke WiFi", end="")
    wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
    
    # Tunggu koneksi (timeout 20 detik)
    max_wait = 40  # 40 * 0.5s = 20 detik
    while max_wait > 0:
        status = wlan.status()
        if status < 0 or status >= 3:
            break
        max_wait -= 1
        print(".", end="")
        time.sleep(0.5)
    
    if wlan.isconnected():
        print("\nWiFi Terhubung! IP: " + wlan.ifconfig()[0])
    else:
        print("\nWiFi GAGAL terhubung! Status: " + str(wlan.status()))
        print("  → Cek SSID dan password di config.py")
        print("  → Reboot Pico untuk mencoba ulang")
    
    return wlan


def _format_cooldown(seconds_left):
    """Format sisa cooldown ke string jam:menit:detik."""
    if seconds_left <= 0:
        return "0:00:00"
    h = seconds_left // 3600
    m = (seconds_left % 3600) // 60
    s = seconds_left % 60
    return "{}:{:02d}:{:02d}".format(h, m, s)


# ----- MAIN -----

def main():
    # Garbage collect sebelum mulai
    gc.collect()
    
    print()
    print("╔══════════════════════════════════════╗")
    print("║   SMART PLANT SYSTEM — Pico 2 W     ║")
    print("║   Migrasi dari ESP32                 ║")
    print("╚══════════════════════════════════════╝")
    print()
    
    # 1. Koneksi WiFi
    wlan = connect_wifi()
    if not wlan.isconnected():
        print("Sistem berhenti: Tidak ada koneksi WiFi.")
        return
    
    # 2. Firebase Anonymous Auth
    print()
    if not firebase_client.firebase_auth():
        print("⚠ Firebase Auth gagal, tetapi sistem tetap berjalan (sensor + pompa lokal).")
        print("  Telemetri tidak akan dikirim sampai auth berhasil.")
    
    # 3. Diagnostik Sensor & Display
    sensors.run_diagnostic()
    display.init()
    
    # 4. State variabel
    current_mode = "auto"
    manual_pump_trigger = False
    last_temperature = None  # Cache suhu terakhir untuk display
    
    # State auto-pump (burst + cooldown)
    auto_pumping = False        # Apakah sedang dalam burst 3 detik
    auto_pump_start = 0         # Waktu mulai burst (ticks_ms)
    auto_cooldown_end = 0       # Waktu selesai cooldown (time.time() epoch)
    
    # Timer
    send_data_prev = time.ticks_ms()
    poll_control_prev = time.ticks_ms()
    log_prev = 0
    display_prev = 0
    
    print("Memulai main loop...")
    print()
    
    # ===== MAIN LOOP =====
    while True:
        now = time.ticks_ms()
        now_epoch = time.time()
        
        # =============================================
        # BAGIAN 1: BACA SENSOR (Selalu jalan)
        # =============================================
        soil_moisture = sensors.read_soil_moisture()
        water_level = sensors.read_water_level()
        
        # =============================================
        # BAGIAN 2: POLLING KONTROL DARI FIREBASE (Setiap 2 Detik)
        # =============================================
        if time.ticks_diff(now, poll_control_prev) > config.CONTROL_POLL_INTERVAL_MS:
            poll_control_prev = now
            
            if firebase_client.is_ready():
                controls = firebase_client.firebase_get("/smart_plant/controls")
                if controls is not None:
                    new_mode = controls.get("mode", current_mode)
                    new_pump = controls.get("manual_pump", manual_pump_trigger)
                    
                    if new_mode != current_mode:
                        current_mode = new_mode
                        print("Dashboard CMD: Mode penyiraman -> " + current_mode)
                        # Reset state auto-pump saat ganti mode
                        auto_pumping = False
                    
                    if new_pump != manual_pump_trigger:
                        manual_pump_trigger = new_pump
                        print("Dashboard CMD: Pompa Manual -> " + ("ON" if manual_pump_trigger else "OFF"))
        
        # =============================================
        # BAGIAN 3: LOGIKA KEPUTUSAN POMPA
        # =============================================
        should_pump_run = False
        pump_reason = ""
        sensor_suspect = False
        
        # Deteksi sensor tanah yang kemungkinan rusak/terputus
        if soil_moisture >= config.SOIL_SENSOR_SUSPECT:
            sensor_suspect = True
        
        # ---------------------------------------------------
        # FAIL-SAFE: Air terlalu rendah (berlaku SEMUA mode)
        # ---------------------------------------------------
        if water_level < config.WATER_MIN_LEVEL_CM:
            should_pump_run = False
            auto_pumping = False  # Hentikan burst jika sedang jalan
            pump_reason = "BLOCKED: Air rendah ({:.1f} cm < {:.1f} cm)".format(
                water_level, config.WATER_MIN_LEVEL_CM)
        
        # ---------------------------------------------------
        # MODE MANUAL: Pompa dikontrol sepenuhnya dari dashboard
        # ---------------------------------------------------
        elif current_mode == "manual":
            if manual_pump_trigger:
                should_pump_run = True
                pump_reason = "MANUAL ON: Tombol ditekan dari dashboard"
            else:
                should_pump_run = False
                pump_reason = "MANUAL OFF: Menunggu perintah dashboard"
        
        # ---------------------------------------------------
        # MODE AUTO: Burst 3 detik + Cooldown 4 jam
        # ---------------------------------------------------
        elif current_mode == "auto":
            # Sensor suspect mem-block auto mode
            if sensor_suspect:
                should_pump_run = False
                auto_pumping = False
                pump_reason = "BLOCKED: Sensor suspect (ADC={})".format(soil_moisture)
            
            # Sedang dalam burst 3 detik?
            elif auto_pumping:
                elapsed = time.ticks_diff(now, auto_pump_start)
                if elapsed < config.AUTO_PUMP_DURATION_MS:
                    # Masih dalam durasi burst
                    should_pump_run = True
                    remaining = (config.AUTO_PUMP_DURATION_MS - elapsed) // 1000 + 1
                    pump_reason = "AUTO BURST: Menyiram... ({}s tersisa)".format(remaining)
                else:
                    # Burst selesai → mulai cooldown
                    auto_pumping = False
                    auto_cooldown_end = now_epoch + config.AUTO_PUMP_COOLDOWN_S
                    should_pump_run = False
                    pump_reason = "AUTO COOLDOWN: Siram selesai, cooldown {}".format(
                        _format_cooldown(config.AUTO_PUMP_COOLDOWN_S))
                    print("  ✓ Burst siram selesai. Cooldown 4 jam dimulai.")
            
            # Dalam masa cooldown?
            elif now_epoch < auto_cooldown_end:
                should_pump_run = False
                sisa = int(auto_cooldown_end - now_epoch)
                pump_reason = "AUTO COOLDOWN: {} tersisa".format(_format_cooldown(sisa))
            
            # Tanah kering & tidak sedang cooldown → mulai burst baru
            elif soil_moisture > config.SOIL_DRY_THRESHOLD:
                auto_pumping = True
                auto_pump_start = now
                should_pump_run = True
                pump_reason = "AUTO BURST: Tanah kering ({} > {}), mulai siram 3s".format(
                    soil_moisture, config.SOIL_DRY_THRESHOLD)
                print("  → Memulai burst penyiraman 3 detik...")
            
            # Tanah cukup lembab
            else:
                should_pump_run = False
                pump_reason = "AUTO OFF: Tanah lembab ({} <= {})".format(
                    soil_moisture, config.SOIL_DRY_THRESHOLD)
        
        # Aktuasi Pompa via H-Bridge
        if should_pump_run:
            actuators.pump_on()
        else:
            actuators.pump_off()
        
        # =============================================
        # BAGIAN 4: LOG DIAGNOSTIK (Setiap 2 Detik)
        # =============================================
        if time.ticks_diff(now, log_prev) > config.LOG_INTERVAL_MS or log_prev == 0:
            log_prev = now
            
            firebase_status = "Ready" if firebase_client.is_ready() else "NOT READY"
            
            print("────────────────────────────────────────")
            print("[{}ms] MODE: {} | Firebase: {}".format(
                now, current_mode, firebase_status))
            
            suspect_tag = "  ⚠ SUSPECT!" if sensor_suspect else ""
            print("  Tanah (ADC) : {} / {}{}".format(
                soil_moisture, config.SOIL_SENSOR_MAX, suspect_tag))
            print("  Air (cm)    : {:.1f} / {:.1f} (min: {:.1f})".format(
                water_level, config.TINGGI_WADAH_CM, config.WATER_MIN_LEVEL_CM))
            print("  Pompa       : {}".format("ON" if should_pump_run else "OFF"))
            print("  Alasan      : {}".format(pump_reason))
        
        # =============================================
        # BAGIAN 5: TELEMETRI FIREBASE (Setiap 5 Detik)
        # =============================================
        if time.ticks_diff(now, send_data_prev) > config.TELEMETRY_INTERVAL_MS or send_data_prev == 0:
            send_data_prev = now
            
            # Baca DHT11 (lambat, cukup tiap 5 detik)
            temperature = sensors.read_temperature()
            if temperature is None:
                temperature = -999.0
                print("  ⚠ DHT11: Gagal membaca suhu!")
            
            # Simpan suhu terakhir untuk display
            last_temperature = temperature if temperature != -999.0 else last_temperature
            
            if firebase_client.is_ready():
                # Push data ke Firebase (satu request PATCH efisien)
                telemetry = {
                    "soil_moisture": soil_moisture,
                    "water_level": round(water_level, 1),
                    "temperature": round(temperature, 1) if temperature != -999.0 else -999.0
                }
                
                ok = firebase_client.firebase_put_multi("/smart_plant/sensors", telemetry)
                
                print("────────────────────────────────────────")
                print("📡 TELEMETRI FIREBASE:")
                
                temp_status = "[ERR]" if temperature == -999.0 else "[OK]"
                print("  Suhu     : {:.1f} °C  {}".format(temperature, temp_status))
                print("  Air      : {:.1f} cm      {}".format(water_level, "[OK]" if ok else "[FAIL]"))
                print("  Tanah    : {} ADC      {}".format(soil_moisture, "[OK]" if ok else "[FAIL]"))
                
                if not ok:
                    print("  ⚠ Error: Gagal mengirim telemetri ke Firebase")
        
        # =============================================
        # BAGIAN 6: UPDATE LCD (Setiap 1 Detik)
        # =============================================
        if time.ticks_diff(now, display_prev) > config.DISPLAY_INTERVAL_MS or display_prev == 0:
            display_prev = now
            display.update(
                temperature=last_temperature,
                water_level=water_level,
                soil_moisture=soil_moisture,
                pump_on=should_pump_run,
                mode=current_mode
            )
        
        # Yield CPU sebentar agar tidak 100% busy loop
        time.sleep_ms(100)
        
        # Garbage collect periodik agar RAM tidak bocor
        gc.collect()


# ----- ENTRY POINT -----
if __name__ == "__main__":
    main()
