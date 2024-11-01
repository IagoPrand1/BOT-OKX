import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error, r2_score, mean_absolute_percentage_error, mean_squared_error, accuracy_score, recall_score, roc_auc_score, confusion_matrix
import os
import sys

# Adiciona o diretório superior ao caminho de busca
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.graficoDesempenho import plotar_subplots
from utilities.printLog import print_log

def avaliar_desempenho_modelo(df_previsao, duracao_ciclo, par):

    caminho_csv = f'./static/imagens/desempenho_modelo.csv'
    
    # Valores reais e previstos
    y_true = df_previsao['Real']
    y_pred = df_previsao['Previsto']

    # Cálculo do MAE (Mean Absolute Error)
    mae = mean_absolute_error(y_true, y_pred)
    # Cálculo do R² (Coeficiente de Determinação)
    r2 = r2_score(y_true, y_pred)
    # Cálculo do MSE (Mean Squared Error)
    mse = mean_squared_error(y_true, y_pred)
    # Cálculo do MAPE (Mean Absolute Percentage Error)
    mape = mean_absolute_percentage_error(y_true, y_pred)
    # Ordenar pelo tempo de abertura
    df_previsao = df_previsao.sort_values(by='Open time').reset_index(drop=True)
    
    plotar_grafico_previsao(df_previsao, par, duracao_ciclo)

    # Criar colunas para valorização
    df_previsao['Valorizacao_real'] = 0
    df_previsao['Valorizacao_prev'] = 0
    # Calcule a valorização com base na condição Pt+h > Pt
    for i in range(len(df_previsao)):
        if df_previsao.iloc[i]['Real'] > df_previsao.iloc[i]['Open']:
            df_previsao.at[i, 'Valorizacao_real'] = 1
        if df_previsao.iloc[i]['Previsto'] > df_previsao.iloc[i]['Open']:
            df_previsao.at[i, 'Valorizacao_prev'] = 1
    # Calcular métricas de classificação
    accuracy = accuracy_score(df_previsao['Valorizacao_real'], df_previsao['Valorizacao_prev'])
    recall = recall_score(df_previsao['Valorizacao_real'], df_previsao['Valorizacao_prev'])
    roc_auc = roc_auc_score(df_previsao['Valorizacao_real'], df_previsao['Valorizacao_prev'])
    # Calcular a matriz de confusão
    cm = confusion_matrix(df_previsao['Valorizacao_real'], df_previsao['Valorizacao_prev'])
    # Extraia os valores da matriz de confusão
    TN = cm[0][0]
    FP = cm[0][1]
    # Calcule a especificidade
    especificidade = TN / (TN + FP)
    # Criar um DataFrame com os resultados de desempenho
    desempenho_novo = {
        'Data':pd.Timestamp.now(tz='UTC').tz_localize(None),
        'MAE': [mae],
        'R²': [r2],
        'MSE': [mse],
        'MAPE (%)': [mape * 100],
        'Acurácia (%)': [accuracy * 100],
        'Recall (%)': [recall * 100],
        'Especificidade (%)': [especificidade * 100],
        'AUC': [roc_auc]
    }
    df_desempenho_novo = pd.DataFrame(desempenho_novo)
    # Se o arquivo CSV já existe, leia os dados existentes e adicione os novos
    if os.path.exists(caminho_csv):
        df_desempenho_existente = pd.read_csv(caminho_csv)
        df_desempenho = pd.concat([df_desempenho_existente, df_desempenho_novo], ignore_index=True)
    else:
        df_desempenho = df_desempenho_novo

    # Salvar o DataFrame de desempenho atualizado em um arquivo CSV
    df_desempenho.to_csv(caminho_csv, index=False)
    
    plotar_subplots(df_desempenho, duracao_ciclo, par)

    print_log("Resultados de desempenho atualizados e salvos.")
    return df_desempenho, df_previsao

def plotar_grafico_previsao(df_previsao, par, duracao_ciclo):
    caminho = f'./static/imagens/grafico_previsao.png'
    
    # Plotar os preços reais e previstos
    plt.figure(figsize=(20, 6))
    plt.plot(df_previsao['Real'], label='Real Price')
    plt.plot(df_previsao['Previsto'], label='Predicted Price')
    plt.legend()
    plt.grid()
    # Salvar o gráfico em vez de exibí-lo
    plt.savefig(caminho)
    plt.close()  

# Função para calcular as métricas e gerar um novo DataFrame
def calcular_desempenho(df_resultados, capital_inicial):
    # Filtrar apenas as operações do tipo 'sell'
    df_vendas = df_resultados[df_resultados['Operacao'] == 'sell']

    if df_vendas.empty:
        print_log("Nenhuma operação do tipo 'sell' encontrada.")
        return pd.DataFrame()  # Retorna um DataFrame vazio se não houver vendas

    # Cálculo das métricas
    variacao_media = df_vendas['Variação (%)'].mean()
    
    # Nível de acurácia: baseado no acerto da previsão de venda em relação ao preço real
    acuracia = (df_vendas['Preco'] <= df_vendas['Preco Venda Previsto']).mean() * 100

    # Montante final após todas as operações de venda
    montante_final = df_vendas['Montante'].iloc[-1]

    # Lucro total: diferença entre capital inicial e montante final
    lucro_total = montante_final - capital_inicial

    # Diferença média entre a data-hora de abertura e fechamento
    df_vendas['Data-hora Abertura'] = pd.to_datetime(df_vendas['Data-hora Abertura'], format='%H:%M:%S %d/%m/%Y')
    df_vendas['Data-hora Fechamento'] = pd.to_datetime(df_vendas['Data-hora Fechamento'], format='%H:%M:%S %d/%m/%Y')
    diferenca_media_tempo = (df_vendas['Data-hora Fechamento'] - df_vendas['Data-hora Abertura']).mean()

    # Converter a diferença média de tempo para minutos
    diferenca_media_minutos = diferenca_media_tempo.total_seconds() / 60

    # Quantidade de operações 'sell'
    quantidade_sell = len(df_vendas)

    # Criar um novo DataFrame com os cálculos
    df_metricas = pd.DataFrame([{
        'Variação (%) Média': variacao_media,
        'Nível de Acurácia (%)': acuracia,
        'Montante Final ($)': montante_final,
        'Lucro Total ($)': lucro_total,
        'Diferença Média de Tempo (min)': diferenca_media_minutos,
        'Quantidade de Operações Sell': quantidade_sell
    }])

    return df_metricas

