import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

def plotar_subplots(df, duracao_ciclo, par):

    caminho = f'./static/imagens/indicadores_desempenho_modelo.png'

    _, axs = plt.subplots(5, 1, figsize=(12, 20), sharex=True)
    
    # Converter a coluna 'Data' para datetime e depois para um array NumPy
    df['Data'] = pd.to_datetime(df['Data'])
    datas = df['Data'].dt.strftime('%H:%M %d-%m-%Y').values

    # Garantir que todas as colunas estejam em formato NumPy
    mae = df['MAE'].values
    r2 = df['R²'].values
    mse = df['MSE'].values
    mape = df['MAPE (%)'].values
    acuracia = df['Acurácia (%)'].values
    recall = df['Recall (%)'].values
    especificidade = df['Especificidade (%)'].values
    auc = df['AUC'].values

    # Subplot 1: MAE
    axs[0].plot(datas, mae, label='MAE', color='blue')
    axs[0].set_ylabel('MAE')
    axs[0].legend()
    axs[0].grid(True)
    axs[0].xaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))  # Limitar o número de rótulos no eixo X

    # Subplot 2: R²
    axs[1].plot(datas, r2, label='R²', color='green')
    axs[1].set_ylabel('R²')
    axs[1].legend()
    axs[1].grid(True)
    axs[1].xaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))

    # Subplot 3: MSE
    axs[2].plot(datas, mse, label='MSE', color='red')
    axs[2].set_ylabel('MSE')
    axs[2].legend()
    axs[2].grid(True)
    axs[2].xaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))

    # Subplot 4: MAPE (%)
    axs[3].plot(datas, mape, label='MAPE (%)', color='purple')
    axs[3].set_ylabel('MAPE (%)')
    axs[3].legend()
    axs[3].grid(True)
    axs[3].xaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))

    # Subplot 5: Acurácia, Recall, Especificidade, AUC
    axs[4].plot(datas, acuracia, label='Acurácia (%)', color='orange')
    axs[4].plot(datas, recall, label='Recall (%)', color='pink')
    axs[4].plot(datas, especificidade, label='Especificidade (%)', color='brown')
    axs[4].plot(datas, auc*100, label='AUC', color='grey')
    axs[4].set_xlabel('Data')
    axs[4].set_ylabel('Desempenho (%)')
    axs[4].legend()
    axs[4].grid(True)
    axs[4].xaxis.set_major_locator(MaxNLocator(integer=True, prune='both'))

    # Rotacionar os rótulos do eixo X e aumentar a rotação para 90 graus
    plt.setp(axs[4].xaxis.get_majorticklabels(), rotation=45)

    # Ajustar o layout para melhor visualização
    plt.tight_layout()

    # Salvar o gráfico
    plt.savefig(caminho)
    plt.close()
    print(f"Gráfico salvo como {caminho}")


