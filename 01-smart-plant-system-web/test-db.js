import { initializeApp } from "firebase/app";
import { getDatabase, ref, set, onValue } from "firebase/database";

// 1. Konfigurasi Firebase
const firebaseConfig = {
  // Gunakan Realtime Database endpoint sesungguhnya
  databaseURL: "https://smart-plant-system-372b4-default-rtdb.asia-southeast1.firebasedatabase.app",
};

const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

// 2. Referensi ke node data sensor yang sesuai dengan ESP32
const sensorRef = ref(database, 'smart_plant/sensors/soil_moisture');

// 3. TEST READ: Listener untuk menangkap data secara real-time
console.log("Mendengarkan sinkronisasi data sensor dari Firebase...");
onValue(sensorRef, (snapshot) => {
  const data = snapshot.val();
  console.log(`[UPDATE DITERIMA] Kelembapan Tanah saat ini: ${data}`);
});

// 4. TEST WRITE: Mensimulasikan data ESP32 mengirim data tiap 3 detik
let dummyMoistureValue = 2600; 
setInterval(() => {
  // Membuat fluktuasi nilai acak kelembapan ADC (0-4095)
  dummyMoistureValue += Math.floor(Math.random() * 100) - 50; 
  console.log(`\n[MENGIRIM DATA] Update nilai Moisture ke Firebase: ${dummyMoistureValue}...`);

  set(sensorRef, dummyMoistureValue)
    .catch(err => console.error("Gagal mengirim data:", err));
}, 3000);