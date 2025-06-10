import sys
import os

# Adicionar o diretório 'src' ao sys.path para permitir importações relativas
# como 'from application.services import ...' quando o script é executado
# de outros diretórios, ou quando o entrypoint está fora de 'src'.
# Isso é mais relevante se você estiver executando `python src/main.py`
# de um diretório pai, ou usando ferramentas que não ajustam o PYTHONPATH automaticamente.
# Se `main.py` é sempre executado da raiz do projeto (`python -m src.main`),
# o Python geralmente lida bem com os imports do pacote `src`.

# current_dir = os.path.dirname(os.path.abspath(__file__))
# if current_dir not in sys.path:
#    sys.path.insert(0, current_dir)
# project_root = os.path.dirname(current_dir) # Se src está um nível abaixo da raiz
# if project_root not in sys.path:
#    sys.path.insert(0, project_root)


def run_application():
    """
    Ponto de entrada principal para a aplicação AutoMail.
    Por enquanto, delega para a interface de linha de comando (CLI).
    """
    print("Iniciando AutoMail...")

    # Tenta importar e executar a CLI.
    # O try-except é uma boa prática para capturar erros de importação
    # que podem ocorrer se a estrutura do projeto não estiver correta
    # ou se houver dependências faltando (embora as dependências devam ser
    # verificadas dentro dos módulos específicos quando possível).
    try:
        from src.interfaces.cli import main_cli
        # Nota: Se você executar `python src/main.py` de dentro do diretório `src`,
        # a importação acima pode precisar ser `from interfaces.cli import main_cli`.
        # Se executar como `python -m src.main` da raiz do projeto,
        # `from src.interfaces.cli import main_cli` é o correto.
        # A configuração do PYTHONPATH ou a forma como o módulo é invocado afeta isso.
        # Para consistência, assumimos que o projeto será executado como um módulo
        # a partir da raiz, ou que o PYTHONPATH está configurado.
    except ModuleNotFoundError as e:
        print(f"Erro crítico: Não foi possível importar 'src.interfaces.cli.main_cli'.")
        print(f"Detalhe do erro: {e}")
        print(f"Verifique se a estrutura do projeto está correta e se o PYTHONPATH inclui a raiz do projeto.")
        print(f"sys.path atual: {sys.path}")
        sys.exit(1) # Sai com código de erro
    except Exception as e:
        print(f"Um erro inesperado ocorreu durante a importação da CLI: {e}")
        sys.exit(1)

    # Executa a lógica principal da CLI
    try:
        main_cli()
    except Exception as e:
        # Captura exceções não tratadas que podem subir da CLI
        print(f"\nErro inesperado durante a execução da aplicação: {e}")
        # Em um ambiente de produção, você logaria este erro de forma mais robusta.
        # ex: import logging; logging.exception("Erro fatal na aplicação")
        sys.exit(1)

    print("\nAutoMail finalizado.")


if __name__ == "__main__":
    # Este bloco é executado quando o script `main.py` é chamado diretamente.
    # Ex: `python src/main.py` ou `python -m src.main`
    run_application()
