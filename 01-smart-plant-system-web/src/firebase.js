// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously } from "firebase/auth";

// Your web app's Firebase configuration
const firebaseConfig = {

  apiKey: "AIzaSyCFYf6a4gZsw27YDEl9OfdgM0R8sJz8YXk",

  authDomain: "smart-plant-system-372b4.firebaseapp.com",

  databaseURL: "https://smart-plant-system-372b4-default-rtdb.asia-southeast1.firebasedatabase.app",

  projectId: "smart-plant-system-372b4",

  storageBucket: "smart-plant-system-372b4.firebasestorage.app",

  messagingSenderId: "274811201747",

  appId: "1:274811201747:web:55d34d4ab07084b3bf4c26"

};

// Initialize Firebase
export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);

// Anonymous Auth — sama seperti ESP32, web juga perlu login
export const authReady = signInAnonymously(auth)
  .then(() => {
    console.log("✓ Firebase Anonymous Auth berhasil (Web)");
  })
  .catch((error) => {
    console.error("✗ Firebase Auth gagal:", error.code, error.message);
  });