import threading
from pynput import keyboard
import requests
import ctypes
import os

# --- Konfigurace ---
QR_SUFFIX_KEY = keyboard.Key.enter  # Klávesa, kterou pošle skener jako konec (Enter)
SERVER_URL = "https://vpass.cloud/api.php?action=result&type=text&data={\"Návštěva\":true}&exhibit_id=609&code="

# Globální stav
qr_buffer = ""

# --- Windows-specific: mapování kláves na EN-US ---
if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ENGLISH_HKL = user32.LoadKeyboardLayoutA(b"00000409", 0)

    def _is_key_down(vk):
        return bool(user32.GetAsyncKeyState(vk) & 0x8000)

    def translate_to_en_char(vk, scan):
        if ENGLISH_HKL is None:
            return None
        state = (ctypes.c_ubyte * 256)()
        if _is_key_down(0x10):  # VK_SHIFT
            state[0x10] = 0x80
        if user32.GetKeyState(0x14) & 0x0001:  # CapsLock
            state[0x14] = 0x01
        buf = ctypes.create_unicode_buffer(8)
        res = user32.ToUnicodeEx(ctypes.c_uint(vk), ctypes.c_uint(scan), state, buf, ctypes.c_int(len(buf)), 0, ENGLISH_HKL)
        if res > 0:
            return buf.value[:res]
        return None

    def key_to_en_char(key):
        vk = None
        scan = 0
        try:
            if hasattr(key, "vk") and key.vk is not None:
                vk = int(key.vk)
            elif hasattr(key, "value"):
                val = getattr(key, "value", None)
                if isinstance(val, int):
                    vk = int(val)
                elif isinstance(val, tuple) and len(val) >= 2 and val[0] is not None:
                    vk = int(val[0])
        except Exception:
            vk = None
        if hasattr(key, "scan_code") and key.scan_code is not None:
            try:
                scan = int(key.scan_code)
            except Exception:
                scan = 0
        ch = translate_to_en_char(vk, scan) if vk is not None else None
        if ch:
            return ch
        return None

def send_code(code):
    url = SERVER_URL + code
    try:
        response = requests.get(url)
        print(f"Odesláno: {code} | Stav: {response.status_code} | Odpověď: {response.text}")
    except Exception as e:
        print(f"Chyba při odesílání: {e}")

def on_press(key):
    global qr_buffer
    try:
        # 1. Kontrola ukončovací klávesy (Enter)
        if key == QR_SUFFIX_KEY:
            filtered = qr_buffer  # neposíláme filtr, vezmeme vše krom speciálních
            if filtered:
                send_code(filtered)
            else:
                print("Nebyl odeslán žádný platný text.")
            qr_buffer = ""  # reset bufferu
            return

        # 2. Ignorujeme speciální klávesy
        if isinstance(key, keyboard.Key):
            # seznam ignorovaných speciálních kláves
            ignore = {
                keyboard.Key.shift, keyboard.Key.shift_r,
                keyboard.Key.ctrl, keyboard.Key.ctrl_r,
                keyboard.Key.alt, keyboard.Key.alt_r,
                keyboard.Key.tab, keyboard.Key.backspace,
                keyboard.Key.esc, keyboard.Key.caps_lock,
                keyboard.Key.cmd, keyboard.Key.cmd_r,
                keyboard.Key.up, keyboard.Key.down,
                keyboard.Key.left, keyboard.Key.right,
                keyboard.Key.page_up, keyboard.Key.page_down,
                keyboard.Key.home, keyboard.Key.end,
                keyboard.Key.insert, keyboard.Key.delete,
                keyboard.Key.f1, keyboard.Key.f2, keyboard.Key.f3, keyboard.Key.f4,
                keyboard.Key.f5, keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8,
                keyboard.Key.f9, keyboard.Key.f10, keyboard.Key.f11, keyboard.Key.f12,
            }
            if key in ignore:
                return

        # 3. Mapování na EN-US znak
        if os.name == "nt":
            ch = key_to_en_char(key)
            if ch:
                qr_buffer += ch
                return
        else:
            # 4. Sběr znaků (včetně NumPad, symbolů, diakritiky)
            if hasattr(key, 'char') and key.char is not None:
                qr_buffer += key.char
                return

        # 5. Podpora NumPad kláves
        if hasattr(key, 'name') and key.name.startswith('num_'):
            num_value = key.name.replace('num_', '')
            qr_buffer += num_value
            return

    except Exception as e:
        print(f"Chyba v hooku: {e}")
        return

def start_keyboard_listener():
    print("Čtečka spuštěna. Zadejte kód a potvrďte Enterem.")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def main():
    # Spustíme hook v samostatném vlákně (volitelné, zde běží v hlavním)
    start_keyboard_listener()

if __name__ == "__main__":
    main()