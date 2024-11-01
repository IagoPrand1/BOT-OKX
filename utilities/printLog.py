import sys

# Redirecionar stdout para um arquivo de log
log_file_path = './static/tables/output.log'
sys.stdout = open(log_file_path, 'w')

# Função para garantir que as mensagens também sejam exibidas no terminal do servidor
def print_log(message):
    original_stdout = sys.__stdout__  # Preserve o stdout original
    print(message)  # Exibe a mensagem no terminal
    sys.stdout.flush()  # Garante que a mensagem é escrita no arquivo imediatamente
    with open(log_file_path, 'a') as f:  # Anexa a mensagem ao arquivo de log
        sys.stdout = f
        print(message)
        sys.stdout = original_stdout  # Retorna o stdout para o original
