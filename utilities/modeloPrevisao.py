from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
import pandas as pd
import os

# Caminho relativo para o arquivo do modelo (assumindo que está no mesmo diretório do código)
modelo_filename = 'Mod_1h_R2-99_MAPE1-9_AC55_SE57_ES53_AUC55.keras'

# Construir o caminho completo usando o diretório atual do script
script_dir = os.path.dirname(os.path.abspath(__file__))  # Diretório onde o script está localizado
modelo_filepath = os.path.join(script_dir, modelo_filename)

# Carregar o modelo
model = load_model(modelo_filepath)

def realizar_previsao(df): 

    def calcular_indicadores_estatisticos(df):

        # Cálculo dos indicadores estatísticos
        ema = df['Close'].ewm(span=20, adjust=False).mean()  # Média Móvel Exponencial (EMA)
        delta = df['Close'].diff()  # Variação do preço
        gain = delta.where(delta > 0, 0)  # Ganho em cada período
        loss = -delta.where(delta < 0, 0)  # Perda em cada período
        avg_gain = gain.rolling(window=14).mean()  # Média móvel dos ganhos
        avg_loss = loss.rolling(window=14).mean()  # Média móvel das perdas
        rs = avg_gain / avg_loss  # Índice de Força Relativa (RSI)
        macd = df['Close'].ewm(span=12, adjust=False).mean() - df['Close'].ewm(span=26, adjust=False).mean()  # Moving Average Convergence Divergence (MACD)

        # Incluir os indicadores estatísticos em uma cópia do dataframe original
        df_with_stats = df.copy()
        df_with_stats['EMA'] = ema
        df_with_stats['RSI'] = rs
        df_with_stats['MACD'] = macd

        # Tratamento dos dados
        df_with_stats.dropna(inplace=True)  # Remover valores ausentes
        df_with_stats = df_with_stats[~(df_with_stats == 0).any(axis=1)]  # Remover linhas com valores igual a zero
        df_with_stats = df_with_stats.loc[:, (df_with_stats != df_with_stats.iloc[0]).any()]  # Remover colunas com valores constantes    

        return df_with_stats

    # Gerar dados estatísticos
    df = calcular_indicadores_estatisticos(df)
    
    # Deslocar a coluna 'Prevista' para cima uma linha. Essa coluna preve o Close da próxima linha
    df['Real'] = df['Close'].shift(-1)

    print(df)

    df.dropna(inplace=True)
    df = df.reset_index(drop=True)

    # Separe os recursos (features) e o alvo (target)
    X = df[['Open time','Open', 'High', 'Low', 'Close', 'Volume', 'EMA', 'MACD']].values
    y = df['Real'].values

    # Reformatar X para [amostras, timesteps, características]
    X = X.reshape((X.shape[0], 1, X.shape[1]))

    # Normalizar os dados
    scaler_input = MinMaxScaler()
    X = scaler_input.fit_transform(X.reshape(-1, X.shape[2])).reshape(X.shape)
    scaler_output = MinMaxScaler()
    y = scaler_output.fit_transform(y.reshape(-1, 1)).reshape(-1)

    y_prev = model.predict(X) #PODE DAR ERRO

    # Inverter a normalização dos dados para obter os preços reais
    y_prev_desno = scaler_output.inverse_transform(y_prev.reshape(-1, 1))

    df_y_prev = pd.DataFrame(data=y_prev_desno, columns=['Previsto'])

    # Para reverter X ao formato original
    X_original = scaler_input.inverse_transform(X.reshape(-1, X.shape[2])).reshape(X.shape)

    X_reshaped = X_original.reshape(X_original.shape[0], -1)

    # Definindo os nomes das colunas
    column_names = ['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'EMA', 'MACD']

    # Criar um DataFrame a partir de X_reshaped
    df_X_test_original = pd.DataFrame(X_reshaped, columns=column_names)

    # Exibindo o DataFrame resultante
    df_X_test_original

    # Exemplo de concatenação horizontal
    df_resultado = pd.concat([df_X_test_original[['Open time', 'Open', 'Low' ,'High', 'Close']], df['Real'], df_y_prev], axis=1)

    # Supondo que 'Open time' esteja em formato UNIX (em milissegundos), caso contrário ajuste.
    df_resultado['Data-Hora'] = pd.to_datetime(df_resultado['Open time'], unit='ms')

    # Adicionando uma nova coluna com data-hora formatada
    df_resultado['Data-Hora'] = df_resultado['Data-Hora'].dt.strftime('%H:%M %d/%m/%Y')

    return df_resultado