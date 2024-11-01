from flask import Flask, render_template, request, redirect, url_for, jsonify
import threading
import os
import time
import json
from dotenv import load_dotenv
import pandas as pd
from utilities.okxAPI import okxapi
from utilities.modeloPrevisao import realizar_previsao
from utilities.avaliacaoResultados import avaliar_desempenho_modelo
from utilities.estrategiaNegociacao import negociar
from utilities.otmizadorParametros import otimizar_parametros

app = Flask(__name__)
log_file_path = './static/tables/output.log'

stop_event = threading.Event()
pause_event = threading.Event()
exit_requested = False

conversao = {
    's': 1,
    'm': 60,
    'H': 60*60,
    'D': 60*60*60
}

lista_duracao_ciclo = ['4H']

carteira_virtual = {}

# Carregar variáveis do arquivo .env
load_dotenv()

# Caminho do arquivo .env na pasta V2_WebApp
env_file_path = os.path.join(os.path.dirname(__file__), '.env')

def set_env_vars(api_key, secret_key, passphrase):
    # Salvar as variáveis no arquivo .env
    with open(env_file_path, 'w') as env_file:
        env_file.write(f"API_KEY='{api_key}'\n")
        env_file.write(f"SECRET_KEY='{secret_key}'\n")
        env_file.write(f"PASSPHRASE='{passphrase}'\n")

def salvar_atualizacao_parametros_otimizados(par, duracao_ciclo, parametros_otimizados, resultado_otimizacao):
    arquivo_json = 'resultados_otimizacao.json'
    if not os.path.exists(arquivo_json):
        with open(arquivo_json, 'w') as f:
            json.dump([], f)

    with open(arquivo_json, 'r') as f:
        resultados = json.load(f)

    novo_resultado = {
        'time': str(pd.Timestamp.now(tz='UTC').tz_localize(None)),
        'par': par,
        'ciclo': duracao_ciclo,
        "lucro_alvo": parametros_otimizados['lucro_alvo'],
        "stop_loss": parametros_otimizados['stop_loss'],
        "margem_seguranca": parametros_otimizados['margem_seguranca'],
        "resultado": resultado_otimizacao
    }
    resultados.append(novo_resultado)

    with open(arquivo_json, 'w') as f:
        json.dump(resultados, f, indent=4)

def executar_otimizacao_parametros(duracao_ciclo, par):
    parametros_otimizados, resultado_otimizacao = otimizar_parametros(duracao_ciclo, par)
    salvar_atualizacao_parametros_otimizados(par, parametros_otimizados['ciclo'], parametros_otimizados, f'{resultado_otimizacao:.2f}%')
    if resultado_otimizacao == 0:
        time.sleep(60*60*24)
        return executar_otimizacao_parametros(duracao_ciclo, par)
    else:
        return parametros_otimizados 

def inicializar_carteira_virtual(capital_inicial: float, par: str):
    return {
        'capital': str(capital_inicial),
        f'{par}': '0'
    }
    
def executar_loop(par, capital_inicial):
    global stop_event, pause_event, carteira_virtual, conversao, lista_duracao_ciclo

    carteira_virtual = inicializar_carteira_virtual(capital_inicial, par)

    while not stop_event.is_set():
        try:
            parametros_gerais = executar_otimizacao_parametros(lista_duracao_ciclo, par)
            duracao_ciclo = parametros_gerais['ciclo']
            unidade_tempo = duracao_ciclo[-1]

            parametros = {
                'lucro_alvo': parametros_gerais['lucro_alvo'],
                'stop_loss': parametros_gerais['stop_loss'],
                'margem_seguranca': parametros_gerais['margem_seguranca'],
                'intervalo': int(duracao_ciclo[:-1]) * conversao[unidade_tempo]
            }

            if pause_event.is_set():
                stop_event.wait()

            usdt_carteira = float(okxapi.carteira('USDT')['data'][0]['details'][0]['eq'])

            if usdt_carteira < float(carteira_virtual['capital']):
                capital_inicial = usdt_carteira / 2
                carteira_virtual['capital'] = str(capital_inicial)
                print(f'Capital inicial ajustado para {usdt_carteira / 2} USDT')

            dados_mercado = okxapi.informacoes_mercado('demo', duracao_ciclo, par, 300)

            previsao = realizar_previsao(dados_mercado)
            avaliar_desempenho_modelo(previsao, duracao_ciclo, par)

            if pause_event.is_set():
                stop_event.wait()

            carteira_virtual = negociar(previsao, carteira_virtual, duracao_ciclo, par, parametros)

            minha_carteira = pd.DataFrame([carteira_virtual])
            minha_carteira.to_csv(f'./static/tables/carteira.csv', index=False)

            if stop_event.is_set():
                print("Encerrando a execução...")
                break
        except Exception as e:
            print(f"Erro durante a negociação: {e}")
            break

@app.route('/historico')
def historico():
    try:
        historico_negociacao = pd.read_csv('./static/tables/historico_negociacao.csv')
        historico_json = historico_negociacao.to_dict(orient='records')
        return jsonify({'historico': historico_json})
    except FileNotFoundError:
        return jsonify({'historico': []})

@app.route('/')
def index():
    try:
        historico_negociacao = pd.read_csv('./static/tables/historico_negociacao.csv')
    except FileNotFoundError:
        historico_negociacao = pd.DataFrame()
    
    try:
        carteira_atual = pd.read_csv('./static/tables/carteira.csv')
    except FileNotFoundError:
        carteira_atual = pd.DataFrame()
    
    # Inicializa carteira_virtual como um dicionário vazio se não houver dados carregados
    carteira_virtual = carteira_atual.iloc[0].to_dict() if not carteira_atual.empty else {}

    return render_template('index.html', historico_negociacao=historico_negociacao, carteira_virtual=carteira_virtual)

@app.route('/start', methods=['POST'])
def start():
    par = request.form['par']
    capital_inicial = float(request.form['capital_inicial'])
    stop_event.clear()
    loop_thread = threading.Thread(target=executar_loop, args=(par, capital_inicial))
    loop_thread.start()
    return redirect(url_for('index'))

@app.route('/pause', methods=['POST'])
def pause():
    pause_event.set()
    return redirect(url_for('index'))

@app.route('/resume', methods=['POST'])
def resume():
    pause_event.clear()
    stop_event.set()
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop():
    stop_event.set()
    return redirect(url_for('index'))

@app.route('/logs')
def logs():
    try:
        with open(log_file_path, 'r') as f:
            logs = f.readlines()
        return jsonify({'logs': logs[-50:]})  # Retorna apenas as últimas 50 linhas
    except FileNotFoundError:
        return jsonify({'logs': ['Nenhum log disponível']})

@app.route('/set_env', methods=['POST'])
def set_env():
    api_key = request.form['api_key']
    secret_key = request.form['secret_key']
    passphrase = request.form['passphrase']

    # Armazenar as variáveis de ambiente no arquivo .env
    set_env_vars(api_key, secret_key, passphrase)

    # Carregar novamente o .env para garantir que as variáveis sejam atualizadas
    load_dotenv(env_file_path)

    # Redireciona para a página inicial após salvar as credenciais
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run(debug=True)
