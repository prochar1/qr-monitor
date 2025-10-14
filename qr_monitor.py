import asyncio
import websockets
import threading
from pynput import keyboard
import json

# --- Konfigurace ---
QR_SUFFIX_KEY = keyboard.Key.enter  # Klávesa, kterou pošle skener jako konec (Enter)
WEBSOCKET_PORT = 8081
WEBSOCKET_HOST = "127.0.0.1"

# Globální stav
clients = set()
qr_buffer = ""
main_loop = None  # reference na asyncio loop hlavního vlákna

# --- 2. Funkce pro WebSocket (opravená signatura) ---

async def register(websocket, path=None):
    clients.add(websocket)
    print(f"WebSocket: Nový klient připojen. Celkem klientů: {len(clients)}")
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)
        print(f"WebSocket: Klient odpojen. Zbývá: {len(clients)}")

async def broadcast_qr_code(code):
    if clients:
        message = json.dumps({"qr_data": code})
        await asyncio.gather(*[client.send(message) for client in clients], return_exceptions=True)
        print(f"WebSocket: Odeslán kód: {code}")

async def start_websocket_server():
    try:
        async with websockets.serve(register, WEBSOCKET_HOST, WEBSOCKET_PORT):
            print(f"WebSocket Server běží na ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}")
            await asyncio.Future()
    except Exception as e:
        print(f"WebSocket Server CHYBA při startu: {e}")

# --- 3. Klávesnicový Hook (nevrací False) ---

def on_press(key):
    """Zpracování stisku klávesy z celého systému."""
    global qr_buffer, main_loop

    try:
        # 1. Kontrola ukončovací klávesy (Enter)
        if key == QR_SUFFIX_KEY:
            if qr_buffer:
                if main_loop is None:
                    print("Hook: CHYBA - hlavní event loop není nastaven.")
                else:
                    asyncio.run_coroutine_threadsafe(broadcast_qr_code(qr_buffer), main_loop)
                    print(f"Hook: Enter detekován. Kód odeslán: {qr_buffer}")
                qr_buffer = ""  # reset bufferu
            else:
                # prázdný buffer — nic posílat
                qr_buffer = ""
            # DŮLEŽITÉ: NEVRACET False (to by zastavilo listener)
            return  # vrátí None

        # 2. Sběr znaků
        elif hasattr(key, 'char') and key.char is not None:
            qr_buffer += key.char
            # nevracíme False — necháme listener běžet
            return

        # ostatní klávesy ignorujeme
        return

    except Exception as e:
        print(f"Chyba v hooku: {e}")
        return

def start_keyboard_listener():
    """Spustí listener klávesnice."""
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# --- 4. Hlavní spuštění (nastaví hlavní loop a spustí hook v vlákně) ---

def main():
    global main_loop
    # vytvoříme nový loop a nastavíme ho jako hlavní pro tento proces
    main_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(main_loop)

    print("Spouštím keyboard listener (vlákno) a websocket server...")
    # Spustíme hook v samostatném vlákně
    hook_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
    hook_thread.start()

    # Spustíme WebSocket server v hlavním vlákně
    try:
        main_loop.run_until_complete(start_websocket_server())
    except KeyboardInterrupt:
        print("Ukončuji server...")
    except Exception as e:
        print("Hlavní chyba:", e)

if __name__ == "__main__":
    main()