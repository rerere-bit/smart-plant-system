# ============================================================
# firebase_client.py — Firebase REST API Client (MicroPython)
# ============================================================
# Menggantikan Firebase_ESP_Client library yang hanya tersedia di ESP32.
# Menggunakan REST API untuk:
#   1. Anonymous Authentication (identitytoolkit.googleapis.com)
#   2. PUT data ke Realtime Database
#   3. GET data dari Realtime Database (polling kontrol)
# ============================================================

import urequests
import ujson
import time

import config

# ----- STATE INTERNAL -----
_id_token = None
_token_expiry = 0  # epoch time saat token expired


# ----- AUTHENTICATION -----

def firebase_auth():
    """
    Lakukan Anonymous Sign-In ke Firebase.
    Mendapatkan ID token untuk autentikasi request selanjutnya.
    
    Return:
        bool: True jika berhasil, False jika gagal.
    """
    global _id_token, _token_expiry
    
    url = "https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=" + config.API_KEY
    
    headers = {"Content-Type": "application/json"}
    payload = ujson.dumps({"returnSecureToken": True})
    
    try:
        response = urequests.post(url, data=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            _id_token = data.get("idToken")
            expires_in = int(data.get("expiresIn", 3600))
            _token_expiry = time.time() + expires_in - 60  # Refresh 60 detik sebelum expired
            response.close()
            print("Firebase Anonymous Auth ✓ Berhasil!")
            return True
        else:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            response.close()
            print("Firebase Anonymous Auth ✗ GAGAL!")
            print("  Error: " + error_msg)
            print("  → Pastikan Anonymous Auth di-enable di Firebase Console.")
            print("  → Authentication > Sign-in method > Anonymous > Enable")
            return False
            
    except Exception as e:
        print("Firebase Auth Exception: " + str(e))
        return False


def _ensure_token():
    """
    Pastikan token masih valid. Jika hampir expired, refresh otomatis.
    
    Return:
        bool: True jika token valid/berhasil di-refresh, False jika gagal.
    """
    global _id_token, _token_expiry
    
    if _id_token is None or time.time() >= _token_expiry:
        print("Token expired/belum ada, melakukan re-auth...")
        return firebase_auth()
    
    return True


def is_ready():
    """
    Cek apakah Firebase client siap (token valid).
    
    Return:
        bool: True jika siap.
    """
    return _id_token is not None and time.time() < _token_expiry


# ----- DATABASE OPERATIONS -----

def firebase_put(path, data):
    """
    PUT (set) data ke Firebase Realtime Database.
    
    Args:
        path (str): Path node di RTDB (contoh: "/smart_plant/sensors/soil_moisture")
        data: Data yang akan dikirim (int, float, str, dict, dll.)
    
    Return:
        bool: True jika berhasil, False jika gagal.
    """
    if not _ensure_token():
        return False
    
    url = config.DATABASE_URL + path + ".json?auth=" + _id_token
    headers = {"Content-Type": "application/json"}
    payload = ujson.dumps(data)
    
    try:
        response = urequests.put(url, data=payload, headers=headers)
        success = response.status_code == 200
        response.close()
        return success
    except Exception as e:
        print("Firebase PUT error ({}): {}".format(path, e))
        return False


def firebase_get(path):
    """
    GET data dari Firebase Realtime Database.
    
    Args:
        path (str): Path node di RTDB (contoh: "/smart_plant/controls")
    
    Return:
        dict/value: Data dari Firebase, atau None jika gagal.
    """
    if not _ensure_token():
        return None
    
    url = config.DATABASE_URL + path + ".json?auth=" + _id_token
    
    try:
        response = urequests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            response.close()
            return data
        else:
            response.close()
            return None
            
    except Exception as e:
        print("Firebase GET error ({}): {}".format(path, e))
        return None


def firebase_put_multi(base_path, data_dict):
    """
    PUT beberapa nilai sekaligus dalam satu request (PATCH-like via PUT ke parent).
    Lebih efisien daripada memanggil firebase_put() berkali-kali.
    
    Args:
        base_path (str): Path parent node (contoh: "/smart_plant/sensors")
        data_dict (dict): Dictionary data (contoh: {"soil_moisture": 30000, "water_level": 15.2})
    
    Return:
        bool: True jika berhasil, False jika gagal.
    """
    if not _ensure_token():
        return False
    
    url = config.DATABASE_URL + base_path + ".json?auth=" + _id_token
    headers = {"Content-Type": "application/json"}
    payload = ujson.dumps(data_dict)
    
    try:
        response = urequests.patch(url, data=payload, headers=headers)
        success = response.status_code == 200
        response.close()
        return success
    except Exception as e:
        print("Firebase PATCH error ({}): {}".format(base_path, e))
        return False
