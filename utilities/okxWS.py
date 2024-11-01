import asyncio
import websockets
import json
import hmac
import base64
import time
import os
import sys
from dotenv import load_dotenv 

# Adiciona o diretório superior ao caminho de busca
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.okxAPI import okxapi

# Carregar variáveis do arquivo .env
load_dotenv()

# Recuperar as variáveis de ambiente
api_key = os.getenv("API_KEY")
secret_key = os.getenv("SECRET_KEY")
passphrase = os.getenv("PASSPHRASE")

# Função para gerar os parâmetros de login
def login_params(timestamp, api_key, passphrase, secret_key):
    message = timestamp + 'GET' + '/users/self/verify'
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)

    login_param = {"op": "login", "args": [{"apiKey": api_key,
                                            "passphrase": passphrase,
                                            "timestamp": timestamp,
                                            "sign": sign.decode("utf-8")}]}
    login_str = json.dumps(login_param)
    return login_str

def get_local_timestamp():
    return int(time.time())

# Função para monitorar a ordem e verificar seu status
async def subscribe(url, channels, par, clOrdId, intervalo):
    # Armazena o timestamp do momento de abertura da posição
    time_open_position = time.time()

    while True:
        try:
            async with websockets.connect(url) as ws:
                # Login
                timestamp = str(get_local_timestamp())
                login_str = login_params(timestamp, api_key, passphrase, secret_key)
                await ws.send(login_str)
                res = await ws.recv()
                print(f"Login Response: {res}")

                # Subscribe to the orders channel
                sub_param = {"op": "subscribe", "args": channels}
                sub_str = json.dumps(sub_param)
                await ws.send(sub_str)
                print(f"Subscribed: {sub_str}")
                
                while True:
                    try:
                        # Verificar o status da ordem a cada ciclo
                        detalhes_ordem = okxapi.detalhes_ordem(par, clOrdId)

                        if detalhes_ordem['state'] == 'filled':
                            return detalhes_ordem
                        if detalhes_ordem['state'] == 'cancelled':
                            return detalhes_ordem
                        
                        # Verificar se já se passaram 12 horas desde a abertura da posição
                        elapsed_time = time.time() - time_open_position
                        if elapsed_time*60 >= 2 * intervalo:
                            print(f'Ordem cancelada:{okxapi.cancelar_ordem(par, clOrdId)}')
                            return {'state':'canceled','clOrdId': clOrdId }
                                           
                        # Wait for a response with a timeout
                        res = await asyncio.wait_for(ws.recv(), timeout=300)
                        res_data = json.loads(res)
                        print(f"Received: {res_data}")

                        # Check if the order status is filled
                        if "data" in res_data:
                            order_data = res_data["data"][0]
                            if order_data["clOrdId"] == clOrdId and order_data["state"] == "filled":
                                print(f"Order {clOrdId} is filled.")
                                return order_data
                            
                            if order_data["clOrdId"] == clOrdId and order_data["state"] == "canceled":
                                print(f"Order {clOrdId} is canceled.")
                                return order_data                           
                            
                    except asyncio.TimeoutError:
                        # Send a ping to keep the connection alive
                        await ws.send('ping')
                        res = await ws.recv()
                        print(f"Ping Response: {res}")

        except Exception as e:
            print(e)
            print("Disconnected, reconnecting...")
            time.sleep(30)
            continue

# Função principal para verificar a execução da ordem
def verificar_execucao(par, clOrdId, intervalo):

    url = "wss://ws.okx.com:8443/ws/v5/private?brokerId=9999"
    channels = [{"channel": "orders", "instType": "SPOT"}]

    while True:
        loop = asyncio.get_event_loop()
        try:
            response = loop.run_until_complete(subscribe(url, channels, par, clOrdId, intervalo))

            if response and response['state'] == 'filled' and response['clOrdId'] == clOrdId:
                print("Order execution confirmed.")
                return response
            elif response and response['state'] == 'canceled' and response['clOrdId'] == clOrdId:
                print(f"Order {clOrdId} has been canceled.")
                return response
        except TypeError:
            print("Backup verification for execution.")
            continue
