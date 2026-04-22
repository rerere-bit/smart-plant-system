import { getDatabase, ref, onValue, set, onDisconnect } from "firebase/database";
import { app, authReady } from "./src/firebase.js";

// Initialize Realtime Database
const db = getDatabase(app);

// Nodes References
const sensorsRef = ref(db, 'smart_plant/sensors');
const controlsRef = ref(db, 'smart_plant/controls');
const modeRef = ref(db, 'smart_plant/controls/mode');
const pumpRef = ref(db, 'smart_plant/controls/manual_pump');

// DOM Elements - Telemetry
const valMoisture = document.getElementById('val-moisture');
const barMoisture = document.getElementById('bar-moisture');
const valWater = document.getElementById('val-water');
const barWater = document.getElementById('bar-water');
const valTemp = document.getElementById('val-temp');
const barTemp = document.getElementById('bar-temp');


const connStatus = document.getElementById('conn-status');
const connText = document.getElementById('conn-text');

// DOM Elements - Controls
const modeToggle = document.getElementById('mode-toggle');
const btnPump = document.getElementById('btn-pump');

// Constants for display
const MAX_WATER_CM = 23.0; // Kapasitas maks tinggi wadah
const MAX_ADC_MOISTURE = 65535.0; // Dry (kering) max — Pico 2 W ADC 16-bit

// --- TUNGGU AUTH SELESAI SEBELUM AKSES DATABASE ---
authReady.then(() => {

// --- SYSTEM CONNECTION STATUS ---
const connectedRef = ref(db, ".info/connected");
onValue(connectedRef, (snap) => {
  if (snap.val() === true) {
    connStatus.className = "status-badge connected";
    connStatus.innerHTML = "<i class='bx bx-wifi'></i> <span id='conn-text'>Connected to Firebase</span>";
    
    // Fail-safe manual pump off on disconnect to prevent pump running forever
    onDisconnect(pumpRef).set(false);
  } else {
    connStatus.className = "status-badge error";
    connStatus.innerHTML = "<i class='bx bx-wifi-off'></i> <span id='conn-text'>Disconnected</span>";
  }
});


// --- READ SENSOR TELEMETRY ---
onValue(sensorsRef, (snapshot) => {
    const data = snapshot.val();
    if(data) {
        // 1. Soil Moisture Processing
        // Biasanya ADC rentang 0 (basah) - 4095 (kering ekstrem)
        let moisture = data.soil_moisture !== undefined ? data.soil_moisture : '--';
        valMoisture.innerText = moisture;
        
        let moisturePercent = 0;
        if(moisture !== '--') {
            moisturePercent = (moisture / MAX_ADC_MOISTURE) * 100;
            if(moisturePercent > 100) moisturePercent = 100;
            barMoisture.style.width = moisturePercent + '%';
            
            // Warna indikator: Hijau (sehat), Kuning (mulai kering), Merah (kering parah)
            if(moisture > 2500) barMoisture.style.background = "var(--danger)";
            else if(moisture > 1500) barMoisture.style.background = "var(--warning)";
            else barMoisture.style.background = "var(--primary)";
        }

        // 2. Water Level Processing
        let water = data.water_level !== undefined ? data.water_level : '--';
        if(water !== '--') {
            valWater.innerText = water.toFixed(1);
            let waterPercent = (water / MAX_WATER_CM) * 100;
            if (waterPercent > 100) waterPercent = 100;
            barWater.style.width = waterPercent + '%';

            // Peringatan Merah jika air hampir habis
            if(water <= 2.0) {
                barWater.style.background = "var(--danger)";
                document.getElementById('val-water').style.color = "var(--danger)";
            } else {
                barWater.style.background = "var(--info)";
                document.getElementById('val-water').style.color = "var(--text-main)";
            }
        }
        // 3. Temperature Processing
        let temperature = data.temperature !== undefined ? data.temperature : '--';
        if(temperature !== '--' && temperature !== -999) {
            valTemp.innerText = temperature.toFixed(1);
            
            // Anggap 50 derajat celcius sebagai 100% suhu max ekstrem untuk UI balok visual
            const MAX_TEMP_DISPLAY = 50.0;
            let tempPercent = (temperature / MAX_TEMP_DISPLAY) * 100;
            if(tempPercent > 100) tempPercent = 100;
            if(tempPercent < 0) tempPercent = 0;
            
            barTemp.style.width = tempPercent + '%';

            // Indikator Suhu: Panas (>35°C), Hangat (>28°C), Normal/Dingin (<28°C)
            if(temperature > 35.0) {
                barTemp.style.background = "var(--danger)";
            } else if(temperature > 28.0) {
                barTemp.style.background = "var(--warning)";
            } else {
                barTemp.style.background = "var(--primary)";
            }
        } else if (temperature === -999) {
            valTemp.innerText = "ERR"; // Fallback DHT11 misread
            barTemp.style.width = "0%";
        }

    }
});


// --- READ & SYNC CONTROLS STATE FROM CLOUD ---
onValue(controlsRef, (snapshot) => {
    const data = snapshot.val();
    if(data) {
        // Sync Mode Switch
        if(data.mode === "auto") {
            modeToggle.checked = true;
            btnPump.disabled = true; // Kunci tombol manual saat mode auto
            btnPump.classList.remove('active');
        } else {
            modeToggle.checked = false;
            btnPump.disabled = false; // Buka kunci tombol manual
        }

        // Sync Pump State
        if(!btnPump.disabled) {
            if(data.manual_pump === true) {
                btnPump.classList.add('active');
                btnPump.innerHTML = "<i class='bx bx-water'></i> Pompa Menyala";
            } else {
                btnPump.classList.remove('active');
                btnPump.innerHTML = "<i class='bx bx-power-off'></i> Siram Sekarang";
            }
        }
    }
});


// --- WRITE / SEND CONTROLS STATE TO CLOUD ---

// Mode Toggle Event
modeToggle.addEventListener('change', (e) => {
    const isAuto = e.target.checked;
    const newMode = isAuto ? "auto" : "manual";
    
    // Set to Firebase
    set(modeRef, newMode)
        .catch(err => console.error("Filter Mode gagal: ", err));

    // Jika masuk mode auto, pastikan pompa manual dimatikan dari database
    if(isAuto) {
        set(pumpRef, false);
    }
});

// Manual Pump Interaction
// Toggle: Klik sekali = pompa ON (tetap nyala), klik lagi = pompa OFF.
// Pola toggle diperlukan karena Pico 2 W menggunakan polling (bukan realtime stream),
// sehingga pola tahan-tombol (mousedown/mouseup) tidak akan terdeteksi tepat waktu.
btnPump.addEventListener('click', () => {
    if(!btnPump.disabled) {
        const isCurrentlyOn = btnPump.classList.contains('active');
        set(pumpRef, !isCurrentlyOn);
    }
});

}); // akhir authReady.then()
