import os
from dotenv import load_dotenv
from typing import Optional, Any, Dict
from src.domain.interfaces import ConfigRepository

class DotEnvConfigRepository(ConfigRepository):
    """
    Implementação de ConfigRepository que carrega configurações de um arquivo .env
    e variáveis de ambiente.
    """
    def __init__(self, env_file_path: Optional[str] = None):
        """
        :param env_file_path: Caminho para o arquivo .env. Se None, procura por ".env" no diretório atual
                              ou em diretórios pais.
        """
        self.env_file_path = env_file_path if env_file_path else self._find_env_file()
        self._config = self._load_config_from_env()

    def _find_env_file(self) -> str:
        """
        Procura pelo arquivo .env começando do diretório atual e subindo na árvore de diretórios.
        Isso é útil para quando o script é executado de subdiretórios.
        """
        current_dir = os.getcwd()
        while current_dir != os.path.dirname(current_dir): # Raiz do sistema
            potential_path = os.path.join(current_dir, ".env")
            if os.path.exists(potential_path):
                return potential_path
            current_dir = os.path.dirname(current_dir)
        # Se não encontrar, retorna o padrão (pode não existir, load_dotenv lidará com isso)
        return ".env"


    def _load_config_from_env(self) -> Dict[str, Any]:
        """
        Carrega as configurações do arquivo .env e das variáveis de ambiente.
        Variáveis de ambiente têm precedência sobre as do arquivo .env.
        """
        # Carrega do arquivo .env especificado (ou encontrado)
        # override=True significa que vars de ambiente do sistema não sobrescrevem .env ao carregar
        # mas nós faremos uma segunda passada para garantir que vars de ambiente do sistema tenham precedência.
        load_dotenv(dotenv_path=self.env_file_path, override=False)

        config_data = {}
        # Adiciona variáveis do arquivo .env
        config_data.update(os.environ)

        # Opcional: Mapeamento e conversão de tipos
        # Exemplo: converter 'True'/'False' para booleano, strings numéricas para int/float
        typed_config = {}
        for key, value in config_data.items():
            if value.lower() == 'true':
                typed_config[key] = True
            elif value.lower() == 'false':
                typed_config[key] = False
            elif value.isdigit():
                typed_config[key] = int(value)
            # Adicionar mais conversões conforme necessário (ex: listas separadas por vírgula)
            # elif ',' in value:
            # typed_config[key] = [item.strip() for item in value.split(',')]
            else:
                typed_config[key] = value

        # Adicionar configurações padrão ou fixas aqui, se necessário
        # Ex: typed_config.setdefault("DEFAULT_TIMEOUT", 30)

        # Mapeamento de serviços de e-mail (exemplo, poderia vir do .env também)
        # Este é um local onde o ACCOUNT_SERVICE_MAP de domain.models pode ser populado
        # ou verificado contra o que está no .env
        typed_config.setdefault("ACCOUNT_SERVICE_MAP", {
            "outlook": "OutlookAdapter", # Nome da CLASSE do adaptador
            "gmail": "GmailAdapter", # Exemplo
            # Adicionar outros provedores aqui
        })

        # Configurações específicas para o Outlook (exemplos)
        # Estes seriam idealmente carregados de variáveis de ambiente ou do arquivo .env
        typed_config.setdefault("OUTLOOK_CLIENT_ID", os.getenv("OUTLOOK_CLIENT_ID"))
        typed_config.setdefault("OUTLOOK_CLIENT_SECRET", os.getenv("OUTLOOK_CLIENT_SECRET"))
        typed_config.setdefault("OUTLOOK_TENANT_ID", os.getenv("OUTLOOK_TENANT_ID"))

        # Configurações para o Telegram (exemplos)
        typed_config.setdefault("TELEGRAM_BOT_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN"))
        typed_config.setdefault("TELEGRAM_DEFAULT_CHAT_ID", os.getenv("TELEGRAM_DEFAULT_CHAT_ID"))

        # Configurações do banco de dados (exemplo para SQLite)
        typed_config.setdefault("DATABASE_TYPE", os.getenv("DATABASE_TYPE", "sqlite"))
        typed_config.setdefault("DATABASE_NAME", os.getenv("DATABASE_NAME", "automail.db"))

        # Destinatário padrão para notificações (pode ser um ID de chat do Telegram, e-mail, etc.)
        typed_config.setdefault("DEFAULT_NOTIFICATION_RECIPIENT", os.getenv("DEFAULT_NOTIFICATION_RECIPIENT"))
        typed_config.setdefault("ADMIN_NOTIFICATION_RECIPIENT", os.getenv("ADMIN_NOTIFICATION_RECIPIENT", typed_config.get("DEFAULT_NOTIFICATION_RECIPIENT")))


        return typed_config

    def load_config(self) -> Dict[str, Any]:
        """Retorna o dicionário de configuração carregado."""
        return self._config.copy() # Retorna uma cópia para evitar modificação externa

    def get_config_value(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Obtém um valor de configuração específico."""
        return self._config.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """
        Define um valor de configuração.
        Nota: Isso altera a configuração em memória. Para persistir,
        o arquivo .env precisaria ser reescrito, o que geralmente não é
        feito por esta classe para evitar complexidade e riscos.
        A persistência de configuração geralmente é gerenciada externamente.
        """
        self._config[key] = value
        # Recomenda-se não escrever de volta no .env automaticamente por questões de segurança
        # e para evitar alterações acidentais. Se for necessário, implementar com cuidado.
        # print(f"Config '{key}' set to '{value}'. Para persistir, atualize o arquivo .env manualmente.")

# Exemplo de como criar um arquivo .env se ele não existir, para fins de teste/setup inicial.
def create_example_env_file(env_file_path=".env"):
    if not os.path.exists(env_file_path):
        default_env_content = {
            "LOG_LEVEL": "INFO",
            "DEFAULT_EMAIL_ACCOUNT": "", # Ex: "user@example.com"
            # "OUTLOOK_CLIENT_ID": "your_outlook_client_id_here",
            # "OUTLOOK_CLIENT_SECRET": "your_outlook_client_secret_here",
            # "OUTLOOK_TENANT_ID": "your_outlook_tenant_id_here",
            "TELEGRAM_BOT_TOKEN": "",
            "TELEGRAM_DEFAULT_CHAT_ID": "", # Seu ID de chat do Telegram
            "DATABASE_TYPE": "sqlite",
            "DATABASE_NAME": "automail.db",
            # Adicione outras configurações padrão que seu aplicativo espera
            "ACCOUNT_SERVICE_MAP_OUTLOOK_CLASS": "OutlookAdapter", # Exemplo de como poderia ser armazenado no .env
        }
        with open(env_file_path, "w") as f:
            for key, value in default_env_content.items():
                f.write(f"{key}='{value}'\n")
        print(f"Arquivo .env de exemplo criado em: {os.path.abspath(env_file_path)}")
        print("Por favor, edite-o com suas configurações reais.")

# Para ser chamado na inicialização da aplicação, por exemplo, no main.py ou __init__.py do src
def initialize_config() -> ConfigRepository:
    # create_example_env_file() # Descomente para criar .env na primeira execução se não existir
    config_repo = DotEnvConfigRepository()
    # Você pode querer logar algumas configurações carregadas aqui (cuidado com dados sensíveis)
    # print(f"Config loaded. DB type: {config_repo.get_config_value('DATABASE_TYPE')}")
    return config_repo

if __name__ == "__main__":
    # Exemplo de uso e teste
    print(f"Procurando por .env a partir de: {os.getcwd()}")
    # Cria um .env de exemplo no diretório atual se não existir
    create_example_env_file(".env_example_test") # Cria um arquivo de teste

    # Testando com o arquivo de exemplo
    test_repo = DotEnvConfigRepository(env_file_path=".env_example_test")
    config = test_repo.load_config()

    print("\nConfigurações carregadas (.env_example_test):")
    for key, value in config.items():
        if "SECRET" not in key.upper() and "TOKEN" not in key.upper(): # Não imprimir segredos
            print(f"  {key}: {value} (Tipo: {type(value).__name__})")

    print(f"\nValor de LOG_LEVEL: {test_repo.get_config_value('LOG_LEVEL')}")
    print(f"Valor de NON_EXISTENT_KEY: {test_repo.get_config_value('NON_EXISTENT_KEY', 'default_value')}")

    test_repo.set_config_value("NEW_SETTING", "test_value")
    print(f"Valor de NEW_SETTING: {test_repo.get_config_value('NEW_SETTING')}")

    # Limpar o arquivo de teste
    if os.path.exists(".env_example_test"):
        os.remove(".env_example_test")
        print("\nArquivo .env_example_test removido.")

    # Testando com o .env padrão (se existir)
    print("\n--- Testando com .env padrão (se existir) ---")
    default_repo = DotEnvConfigRepository() # Tenta carregar .env do projeto
    if os.path.exists(default_repo.env_file_path):
        print(f"Arquivo .env encontrado em: {default_repo.env_file_path}")
        default_config_loaded = default_repo.load_config()
        print("LOG_LEVEL do .env padrão:", default_repo.get_config_value("LOG_LEVEL", "Não definido"))
        print("TELEGRAM_BOT_TOKEN do .env padrão:", "Presente" if default_repo.get_config_value("TELEGRAM_BOT_TOKEN") else "Ausente")
    else:
        print(f"Arquivo .env padrão não encontrado em {default_repo.env_file_path} ou diretórios pais.")
        print("Crie um arquivo .env na raiz do projeto com suas configurações.")
