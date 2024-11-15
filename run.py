# Skrip untuk 1 user_id dan banyak proxies dengan multiplier x2
import asyncio
import random
import ssl
import json
import time
import uuid
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent, FakeUserAgentError

# Konstanta
URIS = [
    "wss://proxy.wynd.network:4444/",
    "wss://proxy.wynd.network:4650/"
]

STATIC_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/112.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/115.0.0.0"
]

# Tambahkan sink untuk mencatat kesalahan ke error_logs.txt
logger.add("error_logs.txt", level="ERROR", rotation="1 MB",
           retention="10 days", compression="zip")

# Inisialisasi UserAgent dengan penanganan error
try:
    user_agent = UserAgent(
        os=['windows', 'macos', 'linux'],
        browsers=['chrome', 'firefox', 'edge', 'safari'],
        platforms=['pc', 'mac']
    )
except FakeUserAgentError as e:
    logger.error(f"Gagal memuat UserAgent: {e}")
    user_agent = None

def get_random_user_agent():
    if user_agent:
        try:
            return user_agent.random
        except FakeUserAgentError as e:
            logger.error(f"Error saat mendapatkan user agent: {e}")
    return random.choice(STATIC_USER_AGENTS)

def determine_os_browser(user_agent_str):
    os_mapping = {
        "Windows": "Windows",
        "Macintosh": "MacOS"
    }
    browser_mapping = {
        "Edge": "Edge",
        "Chrome": "Chrome",
        "Firefox": "Firefox",
        "Safari": "Safari"
    }

    os_type = next((os for keyword, os in os_mapping.items() if keyword in user_agent_str), "Linux")
    browser_type = next((browser for keyword, browser in browser_mapping.items() if keyword in user_agent_str), "Safari")

    return os_type, browser_type

def create_custom_headers(os_type, browser_type, user_agent_str):
    return {
        "User-Agent": user_agent_str,
        "Origin": "http://tauri.localhost",
        "Referer": "http://tauri.localhost/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua-platform": f"\"{os_type}\"",
        "sec-ch-ua": f"\"{browser_type}\";v=\"130\", \"Not?A_Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty"
    }

async def send_ping(websocket):
    while True:
        send_message = json.dumps({"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}}).replace(" ", "")
        logger.debug(f"Mengirim PING: {send_message}")
        await websocket.send(send_message)
        await asyncio.sleep(5)

async def handle_message(message, websocket, device_id, user_id, custom_headers):
    action = message.get("action")
    if action == "AUTH":
        # Pisahkan operasi untuk meningkatkan keterbacaan
        sec_ch_ua_split = custom_headers['sec-ch-ua'].split(';')[0].strip('"')
        sec_ch_ua_platform = custom_headers['sec-ch-ua-platform']
        
        auth_response = {
            "id": message["id"],
            "origin_action": "AUTH",
            "result": {
                "browser_id": device_id,
                "user_id": user_id,
                "user_agent": custom_headers['User-Agent'],
                "timestamp": int(time.time()),
                "device_type": "desktop",
                "version": "4.28.2",
                "multiplier": 2,
                "type": f"desktop, {sec_ch_ua_platform}, 10, {sec_ch_ua_split}, 130.0.0.0"
            }
        }
        logger.debug(f"Mengirim respons AUTH: {auth_response}")
        await websocket.send(json.dumps(auth_response))
    elif action == "PONG":
        pong_response = {
            "id": message["id"],
            "origin_action": "PONG"
        }
        logger.debug(f"Mengirim respons PONG: {pong_response}")
        await websocket.send(json.dumps(pong_response))
    else:
        logger.info(f"Aksi tidak ditangani: {action}")

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid4())
    logger.info(f"Connecting dengan Device ID: {device_id}")
    while True:
        try:
            await asyncio.sleep(random.uniform(0.1, 1.0))
            user_agent_str = get_random_user_agent()
            os_type, browser_type = determine_os_browser(user_agent_str)
            
            if os_type not in ["Windows", "MacOS", "Linux"]:
                logger.warning(f"OS tidak dikenal: {os_type}")
                os_type = "Unknown"

            if browser_type not in ["Edge", "Chrome", "Firefox", "Safari"]:
                logger.warning(f"Browser tidak dikenal: {browser_type}")
                browser_type = "Unknown"

            custom_headers = create_custom_headers(os_type, browser_type, user_agent_str)

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            uri = random.choice(URIS)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)

            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                asyncio.create_task(send_ping(websocket))
                await asyncio.sleep(1)

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(f"Menerima pesan: {message}")
                    await handle_message(message, websocket, device_id, user_id, custom_headers)
        except Exception as e:
            logger.error(f"Error dengan proxy {socks5_proxy}: {e}")
            await asyncio.sleep(5)  # Tambahkan delay sebelum mencoba koneksi ulang

async def main():
    _user_id = input('Silakan Masukkan user ID Anda: ')
    try:
        with open('proxy_list.txt', 'r') as file:
            local_proxies = file.read().splitlines()
    except FileNotFoundError:
        logger.error("File proxy_list.txt tidak ditemukan.")
        return
    except Exception as e:
        logger.error(f"Error saat membaca proxy_list.txt: {e}")
        return

    tasks = [asyncio.create_task(connect_to_wss(proxy, _user_id)) for proxy in local_proxies]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Aplikasi dihentikan oleh pengguna.")
    except Exception as e:
        logger.error(f"Error tak terduga: {e}")
