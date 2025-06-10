import requests
from typing import Optional, Dict, Any, IO
from src.domain.interfaces import NotificationService
import os # For filename from path

class TelegramAdapter(NotificationService):
    """
    Adaptador para enviar notificações via Telegram Bot API.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Inicializa o adaptador do Telegram.
        :param config: Dicionário de configuração contendo:
                       'TELEGRAM_BOT_TOKEN': Token do seu bot do Telegram.
                       'TELEGRAM_DEFAULT_CHAT_ID': Chat ID padrão para enviar mensagens (opcional).
        """
        self.config = config or {}
        self.bot_token = self.config.get("TELEGRAM_BOT_TOKEN")
        self.default_chat_id = self.config.get("TELEGRAM_DEFAULT_CHAT_ID")

        if not self.bot_token:
            print("TelegramAdapter: TELEGRAM_BOT_TOKEN não configurado. As notificações do Telegram não funcionarão.")
            # raise ValueError("TELEGRAM_BOT_TOKEN é obrigatório para TelegramAdapter.")

    def send_notification(self, message: str, recipient_id: Optional[str] = None) -> bool:
        """
        Envia uma mensagem de notificação de texto para um chat do Telegram.
        :param message: A mensagem a ser enviada.
        :param recipient_id: O chat_id do destinatário. Se None, usa o default_chat_id.
        :return: True se a mensagem foi enviada com sucesso, False caso contrário.
        """
        if not self.bot_token:
            print("TelegramAdapter: Impossível enviar notificação de texto, token do bot não fornecido.")
            return False

        chat_id_to_use = recipient_id if recipient_id else self.default_chat_id

        if not chat_id_to_use:
            print("TelegramAdapter: Impossível enviar notificação de texto, recipient_id (ou default_chat_id) não fornecido.")
            return False

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id_to_use,
            "text": message,
            "parse_mode": "HTML" # Changed from Markdown to HTML to match old script's <b> tags
        }

        try:
            response = requests.post(api_url, json=payload, timeout=10)
            response.raise_for_status()

            response_data = response.json()
            if response_data.get("ok"):
                print(f"TelegramAdapter: Notificação de texto enviada com sucesso para chat_id {chat_id_to_use}.")
                return True
            else:
                print(f"TelegramAdapter: Falha ao enviar notificação de texto. API do Telegram retornou erro: {response_data.get('description')}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"TelegramAdapter: Erro de requisição ao enviar notificação de texto: {e}")
            return False
        except Exception as e:
            print(f"TelegramAdapter: Erro inesperado ao enviar notificação de texto: {e}")
            return False

    def send_file(self, file_path_or_bytes: Any, recipient_id: Optional[str] = None, caption: Optional[str] = None, filename: Optional[str] = None) -> bool:
        """
        Envia um arquivo (documento) para um chat do Telegram.
        :param file_path_or_bytes: Caminho para o arquivo local (str) ou bytes do arquivo (bytes ou BytesIO).
        :param recipient_id: O chat_id do destinatário. Se None, usa o default_chat_id.
        :param caption: Legenda para o arquivo (opcional).
        :param filename: Nome do arquivo a ser usado pelo Telegram (opcional, inferido se path é dado).
        :return: True se o arquivo foi enviado com sucesso, False caso contrário.
        """
        if not self.bot_token:
            print("TelegramAdapter: Impossível enviar arquivo, token do bot não fornecido.")
            return False

        chat_id_to_use = recipient_id if recipient_id else self.default_chat_id
        if not chat_id_to_use:
            print("TelegramAdapter: Impossível enviar arquivo, recipient_id (ou default_chat_id) não fornecido.")
            return False

        api_url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        data = {"chat_id": chat_id_to_use}
        if caption:
            data["caption"] = caption
            data["parse_mode"] = "HTML"


        files_payload = None
        actual_filename = filename

        try:
            if isinstance(file_path_or_bytes, str): # É um caminho de arquivo
                if not actual_filename:
                    actual_filename = os.path.basename(file_path_or_bytes)
                with open(file_path_or_bytes, "rb") as f_bytes:
                    files_payload = {"document": (actual_filename, f_bytes)}
                    response = requests.post(api_url, data=data, files=files_payload, timeout=30) # Timeout maior para arquivos
            elif isinstance(file_path_or_bytes, bytes): # São bytes diretos
                if not actual_filename:
                    actual_filename = "file.dat" # Nome padrão se não fornecido
                files_payload = {"document": (actual_filename, file_path_or_bytes)}
                response = requests.post(api_url, data=data, files=files_payload, timeout=30)
            elif hasattr(file_path_or_bytes, "read"): # É um objeto file-like (BytesIO, etc)
                if not actual_filename:
                    actual_filename = "file.dat"
                files_payload = {"document": (actual_filename, file_path_or_bytes)}
                response = requests.post(api_url, data=data, files=files_payload, timeout=30)
            else:
                print("TelegramAdapter: Tipo de arquivo inválido. Use path (str), bytes ou file-like object.")
                return False

            response.raise_for_status()
            response_data = response.json()

            if response_data.get("ok"):
                print(f"TelegramAdapter: Arquivo '{actual_filename}' enviado com sucesso para chat_id {chat_id_to_use}.")
                return True
            else:
                print(f"TelegramAdapter: Falha ao enviar arquivo '{actual_filename}'. API do Telegram retornou erro: {response_data.get('description')}")
                return False
        except FileNotFoundError:
            print(f"TelegramAdapter: Arquivo não encontrado em '{file_path_or_bytes}'.")
            return False
        except requests.exceptions.RequestException as e:
            print(f"TelegramAdapter: Erro de requisição ao enviar arquivo '{actual_filename}': {e}")
            if hasattr(e, 'response') and e.response is not None:
                 print(f"TelegramAdapter: Detalhe do erro: {e.response.text}")
            return False
        except Exception as e:
            print(f"TelegramAdapter: Erro inesperado ao enviar arquivo '{actual_filename}': {e}")
            return False


# Exemplo de uso (para teste rápido)
if __name__ == '__main__':
    print("--- Testando TelegramAdapter ---")

    try:
        from src.infrastructure.config import DotEnvConfigRepository
        config_repo = DotEnvConfigRepository()
        app_config = config_repo.load_config()
    except ImportError:
        print("DotEnvConfigRepository não encontrado, usando config dummy.")
        app_config = {}

    test_bot_token = app_config.get("TELEGRAM_BOT_TOKEN")
    test_chat_id = app_config.get("TELEGRAM_DEFAULT_CHAT_ID")

    if not test_bot_token or not test_chat_id:
        print("\nAVISO: TELEGRAM_BOT_TOKEN ou TELEGRAM_DEFAULT_CHAT_ID não estão definidos.")
        if not test_bot_token:
            test_bot_token = input("Digite o TELEGRAM_BOT_TOKEN (ou pressione Enter para pular): ").strip()
        if not test_chat_id and test_bot_token :
             test_chat_id = input("Digite o TELEGRAM_DEFAULT_CHAT_ID (ou pressione Enter para pular): ").strip()

    if test_bot_token and test_chat_id:
        telegram_config = {
            "TELEGRAM_BOT_TOKEN": test_bot_token,
            "TELEGRAM_DEFAULT_CHAT_ID": test_chat_id
        }
        adapter = TelegramAdapter(config=telegram_config)

        print(f"\nEnviando notificação de TEXTO de teste para chat_id: {test_chat_id}...")
        message_content = "Olá! Esta é uma mensagem de <b>TEXTO</b> de teste do <i>TelegramAdapter</i> em Python. 🎉"
        success_text = adapter.send_notification(message_content)
        if success_text:
            print("Notificação de texto enviada com sucesso!")
        else:
            print("Falha ao enviar notificação de texto.")

        print(f"\nEnviando notificação de ARQUIVO de teste para chat_id: {test_chat_id}...")
        # Criar um arquivo de teste dummy
        dummy_file_name = "test_document.txt"
        with open(dummy_file_name, "w") as f:
            f.write("Este é um arquivo de teste para o TelegramAdapter.\n")
            f.write("Contém algumas linhas de exemplo.\n")

        success_file = adapter.send_file(dummy_file_name, caption="Documento de teste com <b>legenda</b> HTML.")
        if success_file:
            print(f"Arquivo '{dummy_file_name}' enviado com sucesso!")
        else:
            print(f"Falha ao enviar arquivo '{dummy_file_name}'.")

        # Testar envio de bytes
        print(f"\nEnviando ARQUIVO (bytes) de teste para chat_id: {test_chat_id}...")
        byte_content = b"Estes sao bytes de um arquivo de teste."
        success_bytes_file = adapter.send_file(byte_content, filename="bytes_test.txt", caption="Teste de envio de bytes.")
        if success_bytes_file:
            print("Arquivo de bytes enviado com sucesso!")
        else:
            print("Falha ao enviar arquivo de bytes.")


        if os.path.exists(dummy_file_name):
            os.remove(dummy_file_name)

        print("\nVerifique seu Telegram.")
    else:
        print("\nTeste do TelegramAdapter pulado devido à falta de token ou chat_id.")

    print("\n--- Fim dos testes do TelegramAdapter ---")
