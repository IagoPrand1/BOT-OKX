import sys
import os
import time
from datetime import datetime
import pandas as pd
import random

# Adiciona o diretório superior ao caminho de busca
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.okxAPI import okxapi
from utilities.modeloPrevisao import realizar_previsao
from utilities.okxWS import verificar_execucao
from utilities.avaliacaoResultados import avaliar_desempenho_modelo
from utilities.printLog import print_log

def atualizar_previsao(duracao_ciclo, par):
        
    df = okxapi.informacoes_mercado('demo', duracao_ciclo, par, 200)
    df_preve = realizar_previsao(df)
    preco_previsto = df_preve['Previsto'].iloc[-2]
    print(f'Preco previsto ajustado para: {preco_previsto}')
    avaliar_desempenho_modelo(df_preve, duracao_ciclo, par)

    return df_preve, preco_previsto

def comprar(carteira, df_preve, duracao_ciclo, par, ordem, parametros, taxa_compra, taxa_venda):
    while True:
        preco_mercado = okxapi.preco_mercado(par)
        time_preve = pd.to_datetime(df_preve['Open time'].iloc[-1], unit='ms')
        preco_previsto = df_preve['Previsto'].iloc[-1]
        time_atual = pd.Timestamp.now(tz='UTC').tz_localize(None)
        
        # Atualizar a previsão se o tempo atual ultrapassar duas vezes o intervalo de x minutos

        # print(time_atual, time_preve, 3 * parametros['intervalo'])
        if (time_atual - time_preve).total_seconds() > 2 * parametros['intervalo']:
            df_preve, preco_previsto = atualizar_previsao(duracao_ciclo, par)
            
                                            #termo de lucro na venda                                #termo de lucro na compra
        valorizacao = (preco_previsto*(1+parametros['margem_seguranca'])*(1+taxa_venda) - preco_mercado*(1-taxa_compra)) / (preco_mercado*(1-taxa_compra))

        # print(preco_previsto, (1+parametros['margem_seguranca']), (1+taxa_venda), (1-taxa_compra))

        # print_log(f'Preço previsto de fechamento: {preco_previsto*(1+parametros['margem_seguranca'])}')
        print_log(f'Preço atual de mercado: {preco_mercado} \n')
        print_log(f'Valorizacao potencial: {valorizacao}')              
              
        time.sleep(2)

        # Se o modelo prever valorização e o investidor não estiver posicionado
        if valorizacao >= parametros['lucro_alvo']:
            quantidade = (float(carteira['capital']) / preco_mercado)
            clOrdId = f"{random.randint(1, 99)}{ordem}{par.replace('-', '')}Q{str(round(quantidade,5)).replace('.','')}P{int(preco_mercado)}"

            envio_ordem = okxapi.abertura_ordem(par, preco_mercado, quantidade, ordem, clOrdId)

            if envio_ordem['code'] == '1':
                print_log(f"Erro ao enviar a ordem: {envio_ordem['data'][0]['sMsg']}")
                sys.exit(1)
            else:
                print_log(f'Ordem enviada com sucesso:\n {envio_ordem}')
                retorno = verificar_execucao(par, clOrdId, parametros['intervalo'])

                if retorno['state'] == 'canceled':
                    print_log('Ordem foi cancelada. Tentando novamente...')
                    continue
                elif retorno['state'] == 'filled':
                    print_log('Ordem executada com sucesso.')
                    return retorno, preco_previsto
                else:
                    print_log('Não sei o que rolou, mas vamos tentar de novo.')
                    continue
        
        time.sleep(5)

def venda(par, ordem, carteira, valorizacao, preco_compra, quantidade, time_abertura, parametros, taxa):
    while True:
        preco_mercado = okxapi.preco_mercado(par)
        preco_venda = preco_compra * (1 + valorizacao) #Valorizacao = Lucro + Taxa venda + Taxa compra
        quantidade = float(carteira[f'{par}'])
        clOrdId = f"{random.randint(1, 99)}{ordem}{par.replace('-', '')}Q{str(round(quantidade,5)).replace('.','')}P{int(preco_mercado)}T{str(time_abertura)[:4]}"

        time.sleep(2)

        def operacao_venda(par, ordem, preco_venda, quantidade, clOrdId):
            envio_ordem = okxapi.abertura_ordem(par, preco_venda, quantidade, ordem, clOrdId)

            if envio_ordem['code'] == '1':
                print_log(f"Erro ao enviar ordem: {envio_ordem['data'][0]['sMsg']}")
                return None  # Se ocorrer um erro, retorne None para tentar novamente
            else:
                print_log(f'Ordem enviada com sucesso:\n {envio_ordem}')
                retorno = verificar_execucao(par, clOrdId, parametros['intervalo'])
                return retorno

        print_log(f'Preco venda: {preco_venda} \n Preco mercado: {preco_mercado}')

        if preco_venda <= preco_mercado:
            print_log(preco_venda)
            print_log(preco_mercado)
            retorno = operacao_venda(par, ordem, preco_mercado, quantidade, clOrdId)

            if retorno is None:
                continue  # Se ocorreu um erro ao enviar a ordem, tente novamente
            if retorno['state'] == 'canceled':
                print_log("Ordem cancelada, tentando novamente.")
                continue  # Tenta novamente se a ordem for cancelada
            if retorno['state'] == 'filled':
                return retorno, 'Valorizacao'
            
        elif (preco_compra-preco_mercado)/preco_mercado >= parametros['stop_loss']:

            retorno = operacao_venda(par, ordem, preco_mercado, quantidade, clOrdId)

            if retorno is None:
                continue  # Se ocorreu um erro ao enviar a ordem, tente novamente
            if retorno['state'] == 'canceled':
                print_log("Ordem cancelada, tentando novamente.")
                continue  # Tenta novamente se a ordem for cancelada
            if retorno['state'] == 'filled':
                return retorno, 'Stop Loss'

        print_log('Condição não atendida, tentando novamente...')
        time.sleep(5)

def salvar_negociacao(df_resultados_novo, par, duracao_ciclo):

    caminho_csv = f'./static/tables/historico_negociacao.csv'

    df_resultados_novo = pd.DataFrame([df_resultados_novo])
    # Se o arquivo CSV já existe, leia os dados existentes e adicione os novos
    if os.path.exists(caminho_csv):
        df_resultados_existente = pd.read_csv(caminho_csv)
        df_resultados = pd.concat([df_resultados_existente, df_resultados_novo], ignore_index=True)
    else:
        df_resultados = df_resultados_novo

    # Salvar o DataFrame de desempenho atualizado em um arquivo CSV
    df_resultados.to_csv(caminho_csv, index=False)

def negociar(df_preve, carteira, duracao_ciclo, par, parametros):
    valorizacao_real = 0
    ordem = 'buy'

    taxa_venda = okxapi.taxas(par, 'sell')
    taxa_compra = okxapi.taxas(par, 'buy')

    try: 
        if ordem == 'buy':
            transacao, preco_previsto = comprar(carteira, df_preve, duracao_ciclo, par, ordem, parametros, taxa_compra=taxa_compra, taxa_venda=taxa_venda )
            print_log(transacao)
            preco_previsto = abs(preco_previsto)
            quantidade = float(transacao['fillSz'])
            taxa_recolhida = float(transacao['fee']) #É negativo
            quantidade_menos_taxa = quantidade + taxa_recolhida
            preco_compra = abs(float(transacao['fillPx'])*(-1))
            carteira['capital'] = str(float(carteira['capital'])-quantidade*preco_compra)
            carteira[f'{par}'] = str(quantidade_menos_taxa+float(carteira[f'{par}']))

            resultados = {
                'Data-hora Abertura': datetime.fromtimestamp(int(transacao['cTime']) / 1000).strftime('%H:%M:%S %d/%m/%Y'),
                'Data-hora Fechamento': datetime.fromtimestamp(int(transacao['uTime']) / 1000).strftime('%H:%M:%S %d/%m/%Y'),
                'Operacao': ordem,
                'Dolar Carteira': float(carteira['capital']),
                'Moeda Carteira': float(carteira[f'{par}']),
                'Moeda': par,
                'Preco Venda Previsto': preco_previsto,
                'Motivo': 'Compra',
                'Preco': preco_compra,
                'Quantidade': quantidade,
                'Variação (%)': 0,
            }

            salvar_negociacao(resultados, par, duracao_ciclo)

            ordem = 'sell'

        if ordem == 'sell':
            taxa_venda = okxapi.taxas(par, ordem)
            venda_preco_alvo = preco_previsto * (1 + parametros['margem_seguranca'])*(1-taxa_venda)
            valorizacao_mais_taxa = ((venda_preco_alvo - preco_compra) / preco_compra)
            time_abertura = str(int(time.time() * 1000))

            transacao, motivo = venda(par, ordem, carteira, valorizacao_mais_taxa, preco_compra, quantidade, time_abertura, parametros, taxa_venda)
            print_log(transacao)
            quantidade = float(transacao['fillSz'])
            taxa_recolhida = float(transacao['fee'])*(-1) 
            preco_venda = abs(float(transacao['fillPx']))
            carteira['capital'] = str((quantidade*preco_venda)+taxa_recolhida+float(carteira['capital']))
            carteira[f'{par}'] = str(float(carteira[f'{par}'])-quantidade)
            valorizacao_real = (preco_venda*(1-taxa_venda)) / (preco_compra*(1+taxa_compra)) - 1 #Há uma diferença de 0,1% entre a valorizacao na carteira e a valorizacao nos valores

            resultados = {
                'Data-hora Abertura': datetime.fromtimestamp(int(transacao['cTime']) / 1000).strftime('%H:%M:%S %d/%m/%Y'),
                'Data-hora Fechamento': datetime.fromtimestamp(int(transacao['uTime']) / 1000).strftime('%H:%M:%S %d/%m/%Y'),
                'Operacao': ordem,
                'Dolar Carteira': float(carteira['capital']),
                'Moeda Carteira': float(carteira[f'{par}']),
                'Moeda': par,
                'Preco Venda Previsto': preco_previsto,
                'Motivo': motivo,
                'Preco': preco_venda,
                'Quantidade': quantidade,
                'Variação (%)': valorizacao_real * 100,
            }

            ordem = 'buy'

            salvar_negociacao(resultados, par, duracao_ciclo)

        # Mostrar os resultados
        return carteira
    
    except TypeError as e:
        print_log(f"Ocorreu um erro durante a negociação: {e}")
        sys.exit(1)