# Skrip untuk 1 user_id dan banyak proxies dengan multiplier x2
import asyncio
import random
import ssl
import json
import time
import uuid
import requests
import shutil
from loguru import logger
from websockets_proxy import Proxy, proxy_connect
from fake_useragent import UserAgent

# Tambahkan sink untuk mencatat kesalahan ke error_logs.txt
logger.add("error_logs.txt", level="ERROR", rotation="1 MB",
           retention="10 days", compression="zip")

# Modifikasi bagian user agent untuk mendukung berbagai OS dan browser
user_agent = UserAgent(
    os=['windows', 'macos', 'linux'],
    browsers=['chrome', 'firefox', 'edge', 'safari'],
    platforms=['pc', 'mac']
)


async def connect_to_wss(socks5_proxy, user_id):
    # Menggunakan UUID4 untuk device_id yang unik setiap koneksi
    device_id = str(uuid.uuid4())
    logger.info(f"Connecting with Device ID: {device_id}")
    while True:
        try:
            await asyncio.sleep(random.randint(1, 10) / 10)
            # Generate user agent baru untuk setiap koneksi
            random_user_agent = user_agent.random

            # Menentukan OS dan browser dari user agent
            os_type = "Windows" if "Windows" in random_user_agent else "MacOS" if "Mac" in random_user_agent else "Linux"
            browser_type = "Edge" if "Edge" in random_user_agent else "Chrome" if "Chrome" in random_user_agent else "Firefox" if "Firefox" in random_user_agent else "Safari"

            custom_headers = {
                "User-Agent": random_user_agent,
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
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            urilist = ["wss://proxy.wynd.network:4444/",
                       "wss://proxy.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)
            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        send_message = json.dumps(
                            {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                        logger.debug(f"Sending PING: {send_message}")
                        await websocket.send(send_message)
                        await asyncio.sleep(5)

                await asyncio.sleep(1)
                asyncio.create_task(send_ping())

                while True:
                    response = await websocket.recv()
                    message = json.loads(response)
                    logger.info(f"Received message: {message}")
                    if message.get("action") == "AUTH":
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
                                "type": f"desktop, {os_type}, 10, {browser_type}, 130.0.0.0"
                            }
                        }
                        logger.debug(f"Sending AUTH response: {auth_response}")
                        await websocket.send(json.dumps(auth_response))

                    elif message.get("action") == "PONG":
                        pong_response = {
                            "id": message["id"], "origin_action": "PONG"}
                        logger.debug(f"Sending PONG response: {pong_response}")
                        await websocket.send(json.dumps(pong_response))
        except Exception as e:
            logger.error(f"Error dengan proxy {socks5_proxy}: {e}")


async def main():
    _user_id = input('Silakan Masukkan user ID Anda: ')
    with open('proxy_list.txt', 'r') as file:
        local_proxies = file.read().splitlines()
    tasks = [asyncio.ensure_future(connect_to_wss(i, _user_id))
             for i in local_proxies]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    asyncio.run(main())
