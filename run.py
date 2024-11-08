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
import websockets

# Tambahkan sink untuk mencatat kesalahan ke error_logs.txt dan aktivitas ke activity_logs.txt
logger.add("error_logs.txt", level="ERROR", rotation="1 MB", retention="10 days", compression="zip")
logger.add("activity_logs.txt", level="INFO", rotation="1 MB", retention="10 days", compression="zip")

# Inisialisasi User-Agent dengan berbagai OS dan browser
user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers=['chrome', 'firefox', 'edge'])

# Tambahkan set untuk menyimpan proxies aktif dan lock untuk sinkronisasi
active_proxies = set()
proxies_lock = asyncio.Lock()

async def connect_to_wss(socks5_proxy, user_id):
    device_id = str(uuid.uuid4())  # Menggunakan UUID4 untuk device_id yang unik setiap koneksi
    logger.info(f"Connecting with Device ID: {device_id} menggunakan proxy {socks5_proxy}")
    retry_delay = 6  # Delay awal sebelum mencoba kembali
    max_retries = 30   # Batas maksimal percobaan kembali
    retries = 0

    while retries < max_retries:
        try:
            await asyncio.sleep(random.uniform(0.1, 1))  # Penundaan acak antara 0.1 hingga 1 detik
            random_user_agent = user_agent.random
            custom_headers = {
                "User-Agent": random_user_agent,
                "Origin": "http://tauri.localhost",
                "Referer": "http://tauri.localhost/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-US,en;q=0.9",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-ch-ua": "\"Chromium\";v=\"130\", \"Microsoft Edge\";v=\"130\", \"Not?A_Brand\";v=\"99\", \"Microsoft Edge WebView2\";v=\"130\"",
                "sec-ch-ua-mobile": "?0",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty"
            }
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            urilist = ["wss://proxy.wynd.network:4444/", "wss://proxy.wynd.network:4650/"]
            uri = random.choice(urilist)
            server_hostname = "proxy.wynd.network"
            proxy = Proxy.from_url(socks5_proxy)

            async with proxy_connect(uri, proxy=proxy, ssl=ssl_context, server_hostname=server_hostname,
                                     extra_headers=custom_headers) as websocket:
                async def send_ping():
                    while True:
                        try:
                            send_message = json.dumps(
                                {"id": str(uuid.uuid4()), "version": "1.0.0", "action": "PING", "data": {}})
                            logger.debug(f"Sending PING: {send_message}")
                            await websocket.send(send_message)
                            await asyncio.sleep(5)
                        except websockets.exceptions.ConnectionClosedError as e:
                            logger.error(f"WebSocket connection closed during PING: {e}")
                            break  # Keluar dari loop jika koneksi ditutup
                        except Exception as e:
                            logger.error(f"Unexpected error in send_ping: {e}")
                            break  # Keluar dari loop untuk mencegah loop tanpa akhir

                await asyncio.sleep(1)
                ping_task = asyncio.create_task(send_ping())

                while True:
                    try:
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
                                    "type": "desktop, Windows, 10, Edge, 130.0.0.0"
                                }
                            }
                            logger.debug(f"Sending AUTH response: {auth_response}")
                            await websocket.send(json.dumps(auth_response))

                        elif message.get("action") == "PONG":
                            pong_response = {"id": message["id"], "origin_action": "PONG"}
                            logger.debug(f"Sending PONG response: {pong_response}")
                            await websocket.send(json.dumps(pong_response))
                    except websockets.exceptions.ConnectionClosedError as e:
                        logger.error(f"WebSocket connection closed: {e}")
                        break  # Keluar dari loop untuk mencoba reconnect
                    except Exception as e:
                        logger.error(f"Unexpected error in message handling: {e}")
                        break  # Keluar dari loop untuk mencoba reconnect

                # Tentukan apakah ping_task perlu dibatalkan
                if not ping_task.done():
                    ping_task.cancel()
                    try:
                        await ping_task
                    except asyncio.CancelledError:
                        logger.info("send_ping task dibatalkan.")

        except websockets.exceptions.ConnectionClosedError as e:
            logger.error(f"WebSocket connection closed dengan proxy {socks5_proxy}: {e}")
            retries += 1
            if retries < max_retries:
                logger.info(f"Mencoba kembali koneksi {socks5_proxy} (Percobaan {retries}/{max_retries}) setelah {retry_delay} detik.")
                await asyncio.sleep(retry_delay)
                continue  # Coba kembali koneksi
            else:
                logger.info(f"Max retries reached for proxy {socks5_proxy}. Proxy akan dihapus.")
        except Exception as e:
            logger.error(f"Error dengan proxy {socks5_proxy}: {e}")
            # Hapus proxy dari file proxy_list.txt
            proxy_to_remove = socks5_proxy
            try:
                async with proxies_lock:
                    if proxy_to_remove in active_proxies:
                        active_proxies.remove(proxy_to_remove)
                        logger.info(f"Proxy {proxy_to_remove} dihapus dari daftar aktif.")
                    # Baca semua proxy dari file
                    with open('proxy_list.txt', 'r') as file:
                        lines = file.readlines()
                    # Filter proxy yang akan dihapus
                    updated_lines = [line for line in lines if line.strip() != proxy_to_remove]
                    # Tulis kembali proxy yang tersisa ke file
                    with open('proxy_list.txt', 'w') as file:
                        file.writelines(updated_lines)
                logger.info(f"Proxy '{proxy_to_remove}' telah dihapus dari file.")
            except Exception as file_error:
                logger.error(f"Gagal menghapus proxy {proxy_to_remove} dari file: {file_error}")
            break  # Keluar dari loop untuk menghentikan penggunaan proxy ini

        else:
            # Jika koneksi berhasil dan loop tidak pecah, reset retry count
            retries = 0

    logger.info(f"Max retries reached for proxy {socks5_proxy}. Proxy akan dihapus.")
    # Jika loop berakhir karena mencapai max_retries, hapus proxy
    proxy_to_remove = socks5_proxy
    try:
        async with proxies_lock:
            if proxy_to_remove in active_proxies:
                active_proxies.remove(proxy_to_remove)
                logger.info(f"Proxy {proxy_to_remove} dihapus dari daftar aktif.")
            # Baca semua proxy dari file
            with open('proxy_list.txt', 'r') as file:
                lines = file.readlines()
            # Filter proxy yang akan dihapus
            updated_lines = [line for line in lines if line.strip() != proxy_to_remove]
            # Tulis kembali proxy yang tersisa ke file
            with open('proxy_list.txt', 'w') as file:
                file.writelines(updated_lines)
        logger.info(f"Proxy '{proxy_to_remove}' telah dihapus dari file setelah gagal reconnect.")
    except Exception as file_error:
        logger.error(f"Gagal menghapus proxy {proxy_to_remove} dari file: {file_error}")

async def main():
    # Minta user_id dari pengguna
    _user_id = input('Silakan Masukkan user ID Anda: ')
    # Baca proxy dari file proxy_list.txt
    try:
        with open('proxy_list.txt', 'r') as file:
            local_proxies = file.read().splitlines()
    except FileNotFoundError:
        logger.error("File 'proxy_list.txt' tidak ditemukan.")
        return

    # Inisialisasi active_proxies dengan proxies dari file
    async with proxies_lock:
        active_proxies.update(local_proxies)

    tasks = []
    async with proxies_lock:
        for proxy in list(active_proxies):
            task = asyncio.create_task(connect_to_wss(proxy, _user_id))
            tasks.append(task)

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Semua task telah dibatalkan.")
    except Exception as e:
        logger.error(f"Terjadi kesalahan saat menjalankan tasks: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program dihentikan oleh pengguna.")
