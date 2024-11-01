import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv
from httpx import ReadTimeout

import okx.MarketData as MarketData  # Consultar o valor atual
import okx.Account as Account
import okx.Trade as Trade  # Para negociar
import okx.Funding as Funding

# Adiciona o diretório superior ao caminho de busca
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.modeloPrevisao import realizar_previsao

# Função para reconectar a API
def conectar_api():
    global accountAPI, tradeAPI, fundingAPI, marketDataAPI, flag
    accountAPI = Account.AccountAPI(api_key, secret_key, passphrase, False, flag)
    tradeAPI = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
    fundingAPI = Funding.FundingAPI(api_key, secret_key, passphrase, False, flag)
    marketDataAPI = MarketData.MarketAPI(flag=flag)
    print("API conectada com sucesso.")

# Carregar variáveis do arquivo .env
load_dotenv()

# Recuperar as variáveis de ambiente
api_key = os.getenv("API_KEY")
secret_key = os.getenv("SECRET_KEY")
passphrase = os.getenv("PASSPHRASE")

flag = {
    'demo': '1',
    'live': '0'
}

flag = flag['demo']

# Inicializar a API
conectar_api()

# Contador de requisições e controle de tempo
request_counter = 0
start_time = time.time()

def controlar_requisicoes():
    global request_counter, start_time

    # Incrementar o contador de requisições
    request_counter += 1

    # Calcular o tempo decorrido desde o início da contagem
    elapsed_time = time.time() - start_time

    # Se exceder 8 requisições por 60 segundos, aguardar até o próximo minuto
    if request_counter > 7:
        if elapsed_time < 60:
            time.sleep(60 - elapsed_time)  # Aguarde até completar 60 segundos
        # Reiniciar o contador e o tempo
        request_counter = 1
        start_time = time.time()

# Classe com funções para a API da OKX
class okxapi:

    @staticmethod
    def tentar_reconectar(tentativa, max_tentativas):
        if tentativa >= max_tentativas:
            print(f"Número máximo de tentativas atingido. Reconectando a API...")
            conectar_api()
            tentativa = 0
        return tentativa

    @staticmethod
    def informacoes_mercado(mode: str, short_step: str, par: str, tamanho_coleta):
        controlar_requisicoes()  # Controlar o número de requisições

        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                # Coletar dados históricos
                marketDataAPI = MarketData.MarketAPI(flag=flag)

                # Retrieve the candlestick charts
                dados_atuais = marketDataAPI.get_candlesticks(
                    instId=par,
                    bar=short_step,
                    limit= str(tamanho_coleta)
                )

                dados_atuais = dados_atuais['data']

                # Transforma a lista de dados em um dataframe
                df = pd.DataFrame(dados_atuais, columns=["Open time", "Open", "High", "Low", "Close", "Volume", "VolCcy", "VolCcyQuote", "confirm"])
                
                # Selecionando apenas as colunas necessárias
                dados_iniciais = df[['Open time', 'Open', 'High', 'Low', 'Close', 'Volume']]

                # Convertendo as colunas numéricas em float
                dados_iniciais.iloc[:, 1:] = dados_iniciais.iloc[:, 1:].astype(float)

                # Revertendo a ordem das linhas (da última para a primeira)
                dados_mercado = dados_iniciais.iloc[::-1].reset_index(drop=True)

                # Retornando o DataFrame atualizado
                return dados_mercado

            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                time.sleep(2)  # Aguardar antes de tentar novamente
                okxapi.tentar_reconectar(tentativa, max_tentativas)

            except Exception as e:
                tentativa += 1
                print(f"Erro ao buscar informações do mercado: {e}")
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível obter os dados de mercado.")

    @staticmethod
    def carteira(moeda):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                return accountAPI.get_account_balance(moeda)
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                tentativa += 1
                print(f"Erro ao buscar informações da carteira: {e}")
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível obter os dados da carteira.")

    @staticmethod
    def taxas(par, ordem):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                taxa = accountAPI.get_fee_rates(
                    instType="SPOT",
                    instId=par
                )
                return float(taxa['data'][0]['maker']) if ordem == 'buy' else float(taxa['data'][0]['taker'])
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                print(f"Erro ao buscar taxas: {e}")
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível obter as taxas.")

    @staticmethod
    def abertura_ordem(par, preco, quantidade, ordem, clOrdId):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                result = tradeAPI.place_order(
                    instId=par,
                    tdMode="cash",
                    side=ordem,
                    ordType="limit",
                    px=str(preco),
                    sz=str(quantidade),
                    clOrdId=clOrdId  # você pode definir seu próprio ID de ordem definido pelo cliente
                )
                return result
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                print(f"Erro ao abrir ordem: {e}")
                tentativa += 1
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível abrir a ordem.")

    @staticmethod
    def preco_mercado(par):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                response = marketDataAPI.get_ticker(
                    instId=par
                )
                return float(response['data'][0]['last'])
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                print(f"Erro ao buscar preço de mercado: {e}")
                tentativa += 1
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível obter o preço de mercado.")
        
    @staticmethod
    def cancelar_ordem(par, clOrdId):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                response = tradeAPI.cancel_order(
                    instId=par, 
                    clOrdId=clOrdId
                )
                return response['data'][0]
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                print(f"Erro ao cancelar a ordem: {e}")
                tentativa += 1
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                

        # raise Exception("Número máximo de tentativas atingido. Não foi possível cancelar a ordem.")

    @staticmethod
    def detalhes_ordem(par, clOrdId):
        controlar_requisicoes()  # Controlar o número de requisições
        tentativa = 0
        max_tentativas = 5

        while tentativa < max_tentativas:
            try:
                response = tradeAPI.get_order(
                    instId=par, 
                    clOrdId=clOrdId
                )
                return response['data'][0]
            except ReadTimeout:
                tentativa += 1
                print(f"Tentativa {tentativa} de {max_tentativas} falhou devido ao timeout. Tentando novamente...")
                okxapi.tentar_reconectar(tentativa, max_tentativas)
                time.sleep(2)

            except Exception as e:
                print(f"Erro ao buscar detalhes da ordem: {e}")
                print(response)
                tentativa += 1
                time.sleep(60)
                okxapi.tentar_reconectar(tentativa, max_tentativas)

        # raise Exception("Número máximo de tentativas atingido. Não foi possível obter os detalhes da ordem.")
