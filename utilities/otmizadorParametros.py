from itertools import product
import pandas as pd
import numpy as np
import sys
import os
from tqdm import tqdm  # Biblioteca para mostrar uma barra de progresso

# Adiciona o diretório superior ao caminho de busca
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.okxAPI import okxapi
from utilities.modeloPrevisao import realizar_previsao
from utilities.printLog import print_log


import pandas as pd

def simular_negociacao(df_resultado, params, taxa_compra, taxa_venda):
    try: 

        # Inicializar variáveis
        capital_inicial = 100
        posicao = 0
        capital_atual = capital_inicial
        lucro_alvo = params['lucro_alvo']
        stop_loss = params['stop_loss']
        margem_seguranca = float(params['margem_seguranca'])
        taxa_compra = taxa_compra #positivo
        taxa_venda = taxa_venda #positivo
        resultados = []

        for index, row in df_resultado.iloc[:-2].iterrows():
            ajuste_taxa_compra = (1 - taxa_compra)
            ajuste_taxa_venda = (1 - taxa_venda)
            preco_previsto = row['Previsto'] * (1 - margem_seguranca)
            preco_atual = df_resultado.loc[index + 1, 'Open']    
            preco_minimo = df_resultado.loc[index + 1, 'Low']
            preco_minimo_stop = df_resultado.loc[index + 2, 'Low']
            preco_alta_stop = df_resultado.loc[index + 2, 'High']
            preco_alta = df_resultado.loc[index + 1, 'High'] 

            preco_ajustado_compra = preco_atual / ajuste_taxa_compra
            variacao_futura = preco_previsto / preco_atual - 1
            variacao_minima = 1 / (ajuste_taxa_compra * ajuste_taxa_venda) # Sempre >1

            if posicao == 0 and (1 + lucro_alvo) >= variacao_minima:
                if variacao_futura > lucro_alvo and preco_atual >= preco_minimo:
                    posicao = capital_atual / preco_ajustado_compra
                    capital_pre_compra = capital_atual
                    capital_atual = 0
                    preco_compra = preco_ajustado_compra
                    resultados.append({
                        'Compra_preco': preco_compra,
                        'Venda_preco': None,
                        'Montante': capital_pre_compra,
                        'Variação (%)': None,
                        'Motivo': 'Compra'
                    })

            if posicao > 0:
                capital_pos_venda = posicao * preco_previsto * ajuste_taxa_venda

                if preco_previsto <= preco_alta and capital_pos_venda >= capital_pre_compra:
                    capital_atual = capital_pos_venda
                    posicao = 0
                    resultados.append({
                        'Compra_preco': preco_compra,
                        'Venda_preco': preco_previsto,
                        'Montante': capital_atual,
                        'Variação (%)': (capital_atual / capital_pre_compra - 1) * 100,
                        'Motivo': 'Venda por lucro'
                    })

                elif preco_compra / preco_minimo_stop - 1 > stop_loss and preco_compra * (1 - stop_loss) < preco_alta_stop:
                    preco_venda = preco_compra * (1 - stop_loss)
                    capital_atual = posicao * preco_venda * ajuste_taxa_venda
                    posicao = 0
                    resultados.append({
                        'Compra_preco': preco_compra,
                        'Venda_preco': preco_venda,
                        'Montante': capital_atual,
                        'Variação (%)': (capital_atual / capital_pre_compra - 1) * 100,
                        'Motivo': 'Venda por stop loss'
                    })

        if posicao > 0:
            capital_pos_venda = posicao * preco_previsto * ajuste_taxa_venda

            if preco_previsto <= preco_alta and capital_pos_venda >= capital_pre_compra:
                capital_atual = capital_pos_venda
                posicao = 0
                resultados.append({
                    'Compra_preco': preco_compra,
                    'Venda_preco': preco_previsto,
                    'Montante': capital_atual,
                    'Variação (%)': (capital_atual / capital_pre_compra - 1) * 100,
                    'Motivo': 'Venda por lucro'
                })

            elif preco_compra / preco_minimo - 1 >= stop_loss:
                preco_venda = preco_compra * (1 - stop_loss)
                capital_atual = posicao * preco_venda * ajuste_taxa_venda
                posicao = 0
                resultados.append({
                    'Compra_preco': preco_compra,
                    'Venda_preco': preco_venda,
                    'Montante': capital_atual,
                    'Variação (%)': (capital_atual / capital_pre_compra - 1) * 100,
                    'Motivo': 'Venda por stop loss'
                })

        # Cálculo das métricas de desempenho
        ganho_percentual_total = ((capital_atual) / capital_inicial - 1) * 100
        
        return ganho_percentual_total, resultados
        
    except KeyError:
        df_resultado
        return 0 

def lista_candidatos():
    lucro_alvo_range = np.arange(0.0025, 0.01, 0.00125)
    stop_loss_range = np.arange(0.0001, 0.001, 0.0001)
    margem_seguranca_range = np.arange(-0.03, 0.03, 0.005)
    return lucro_alvo_range, stop_loss_range, margem_seguranca_range

def otimizar_parametros(duracoes_ciclo, par):
    melhores_parametros_geral = None
    maior_retorno_geral = float('-inf')
    df_negociacao_geral = None

    print_log('Otimizando parâmetros')

    for duracao_ciclo in duracoes_ciclo:
        taxa_venda = float(okxapi.taxas(par, 'sell')) * (-1)  # negative to positive
        taxa_compra = float(okxapi.taxas(par, 'buy')) * (-1)  # negative to positive

        df_mercado = okxapi.informacoes_mercado('demo', duracao_ciclo, par, 300)
        df_resultado = realizar_previsao(df_mercado)

        params = {
            'lucro_alvo': 0,
            'stop_loss': 0,
            'margem_seguranca': 0
        }

        lucro_alvo_range, stop_loss_range, margem_seguranca_range = lista_candidatos()

        melhores_parametros = None
        maior_retorno = float('-inf')
        df_negociacao = None

        # Criar uma barra de progresso para o loop
        total_combinations = len(lucro_alvo_range) * len(stop_loss_range) * len(margem_seguranca_range)

        with tqdm(total=total_combinations, desc=f"Otimizando parâmetros para duração {duracao_ciclo}") as pbar:
            for lucro_alvo, stop_loss, margem_seguranca in product(lucro_alvo_range, stop_loss_range, margem_seguranca_range):
                params['lucro_alvo'] = lucro_alvo
                params['stop_loss'] = stop_loss
                params['margem_seguranca'] = margem_seguranca

                ganho_percentual_total, resultados = simular_negociacao(
                    df_resultado,
                    params,
                    taxa_compra,
                    taxa_venda
                )

                # Ajustar o ganho percentual total para ser proporcional à duração do ciclo
                horas_ciclo = converter_duracao_para_horas(duracao_ciclo)
                ganho_percentual_por_hora = ganho_percentual_total / horas_ciclo

                if ganho_percentual_por_hora > maior_retorno:
                    maior_retorno = ganho_percentual_por_hora
                    maior_retorno_total = ganho_percentual_total
                    melhores_parametros = {
                        'par': par,
                        'ciclo': duracao_ciclo,
                        'lucro_alvo': lucro_alvo,
                        'stop_loss': stop_loss,
                        'margem_seguranca': margem_seguranca
                    }
                
                    df_negociacao = pd.DataFrame(resultados)

                pbar.update(1)  # Atualiza a barra de progresso

        if maior_retorno > maior_retorno_geral:
            maior_retorno_geral = maior_retorno
            maior_retorno_total_geral = maior_retorno_total
            melhores_parametros_geral = melhores_parametros
            df_negociacao_geral = df_negociacao

    # Mostrar os melhores parâmetros gerais e o maior retorno
    print_log(df_negociacao_geral)
    print_log(f'Melhores parêmtros: {melhores_parametros_geral} \n Retorno de {maior_retorno_total_geral:.2f}%')

    return melhores_parametros_geral, maior_retorno_total_geral

def converter_duracao_para_horas(duracao):
    if duracao.endswith('H'):
        return int(duracao[:-1])
    elif duracao.endswith('D'):
        return int(duracao[:-1]) * 24
    else:
        raise ValueError("Formato de duração não suportado. Use 'H' para horas ou 'D' para dias.")