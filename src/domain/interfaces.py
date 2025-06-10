from abc import ABC, abstractmethod
from typing import List, Optional, Any, Dict # Dict was missing
from src.domain.models import EmailMessage, EmailAccount, CalendarEvent, Task, Contact, AttachmentData

class EmailService(ABC):
    """Interface para serviços de e-mail (Outlook, Gmail, etc.)."""

    @abstractmethod
    def login(self, account: EmailAccount) -> Any: # Retorna o objeto de sessão/conexão
        """Realiza login na conta de e-mail."""
        pass

    @abstractmethod
    def logout(self, session: Any) -> None:
        """Realiza logout da conta de e-mail."""
        pass

    @abstractmethod
    def send_email(self, session: Any, message: EmailMessage) -> bool:
        """Envia um e-mail."""
        pass

    @abstractmethod
    def list_emails(self, session: Any, folder: str = "Inbox", limit: int = 20, search_criteria: Optional[dict] = None) -> List[EmailMessage]:
        """Lista e-mails de uma pasta específica."""
        pass

    @abstractmethod
    def get_email(self, session: Any, message_id: str, folder: str = "Inbox") -> Optional[EmailMessage]:
        """Busca um e-mail específico pelo seu ID."""
        pass

    @abstractmethod
    def mark_as_read(self, session: Any, message_id: str, folder: str = "Inbox") -> bool:
        """Marca um e-mail como lido."""
        pass

    @abstractmethod
    def move_email(self, session: Any, message_id: str, source_folder: str, destination_folder: str) -> bool:
        """Move um e-mail entre pastas."""
        pass

    @abstractmethod
    def delete_email(self, session: Any, message_id: str, folder: str = "Inbox") -> bool:
        """Deleta um e-mail."""
        pass

    @abstractmethod
    def create_folder(self, session: Any, folder_name: str) -> bool:
        """Cria uma nova pasta de e-mails."""
        pass

    @abstractmethod
    def download_attachments(self, session: Any, message_id: str, mail_folder: Optional[str] = None) -> List[AttachmentData]:
        """
        Baixa todos os anexos de um e-mail específico.
        Opcionalmente, pode-se especificar a pasta do e-mail se a API exigir.
        Retorna uma lista de objetos AttachmentData, cada um contendo o nome do arquivo e seu conteúdo em bytes.
        Pode salvar em arquivo temporário e popular o campo 'filepath' em AttachmentData,
        ou popular diretamente 'content_bytes'.
        """
        pass

    # Métodos relacionados a calendário (podem ser movidos para uma CalendarService interface)
    @abstractmethod
    def create_event(self, session: Any, event: CalendarEvent) -> Optional[CalendarEvent]:
        """Cria um novo evento no calendário."""
        pass

    @abstractmethod
    def list_events(self, session: Any, start_date: Any, end_date: Any) -> List[CalendarEvent]:
        """Lista eventos do calendário em um período."""
        pass

    # Métodos relacionados a tarefas (podem ser movidos para uma TaskService interface)
    @abstractmethod
    def create_task(self, session: Any, task: Task) -> Optional[Task]:
        """Cria uma nova tarefa."""
        pass

    @abstractmethod
    def list_tasks(self, session: Any, only_pending: bool = True) -> List[Task]:
        """Lista tarefas."""
        pass

    # Métodos relacionados a contatos (podem ser movidos para uma ContactService interface)
    @abstractmethod
    def list_contacts(self, session: Any, search_query: Optional[str] = None) -> List[Contact]:
        """Lista contatos."""
        pass


class NotificationService(ABC):
    """Interface para serviços de notificação (Telegram, Slack, SMS, etc.)."""

    @abstractmethod
    def send_notification(self, message: str, recipient_id: str) -> bool:
        """Envia uma notificação."""
        pass

    @abstractmethod
    def send_file(self, file_path_or_bytes: Any, recipient_id: str, caption: Optional[str] = None, filename: Optional[str] = None) -> bool:
        """Envia um arquivo para o serviço de notificação."""
        pass


class DatabaseRepository(ABC):
    """Interface para repositórios de banco de dados."""

    @abstractmethod
    def add_account(self, account: EmailAccount) -> EmailAccount:
        """Adiciona uma nova conta de e-mail ao banco de dados."""
        pass

    @abstractmethod
    def get_account(self, email_address: str) -> Optional[EmailAccount]:
        """Recupera uma conta de e-mail pelo endereço."""
        pass

    @abstractmethod
    def list_accounts(self, is_active: Optional[bool] = None) -> List[EmailAccount]:
        """Lista todas as contas de e-mail, opcionalmente filtrando por ativas/inativas."""
        pass

    @abstractmethod
    def update_account(self, account: EmailAccount) -> EmailAccount:
        """Atualiza os dados de uma conta de e-mail."""
        pass

    @abstractmethod
    def delete_account(self, email_address: str) -> bool:
        """Remove uma conta de e-mail."""
        pass

    # Métodos para persistir outras entidades, se necessário
    # @abstractmethod
    # def save_email_log(self, email_log: Any) -> None:
    #     """Salva um log de e-mail enviado/recebido."""
    #     pass
    #
    # @abstractmethod
    # def get_configuration(self, key: str) -> Optional[str]:
    #     """Obtém uma configuração do banco de dados."""
    #     pass
    #
    # @abstractmethod
    # def set_configuration(self, key: str, value: str) -> None:
    #     """Define uma configuração no banco de dados."""
    #     pass


class ConfigRepository(ABC):
    """Interface para gerenciamento de configurações da aplicação."""

    @abstractmethod
    def load_config(self) -> dict:
        """Carrega as configurações da aplicação (ex: de um arquivo .env ou config.json)."""
        pass

    @abstractmethod
    def get_config_value(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Obtém um valor de configuração específico."""
        pass

    @abstractmethod
    def set_config_value(self, key: str, value: Any) -> None:
        """Define um valor de configuração (pode não ser aplicável para todos os tipos de config)."""
        pass


class ProcessedEmailRepository(ABC):
    """Interface para o repositório de e-mails processados (checkpoint)."""

    @abstractmethod
    def add_processed_email(self, message_id: str, account_email: str, processed_at: 'datetime.datetime') -> None:
        """
        Marca um e-mail como processado para uma determinada conta.
        'processed_at' é incluído para manter a ordenação e o timestamp original do processamento.
        """
        pass

    @abstractmethod
    def is_email_processed(self, message_id: str, account_email: str) -> bool:
        """Verifica se um e-mail já foi processado para uma determinada conta."""
        pass

    @abstractmethod
    def get_last_processed_email_id(self, account_email: str) -> Optional[str]:
        """Obtém o ID do último e-mail processado para uma determinada conta (checkpoint)."""
        pass

    @abstractmethod
    def set_initial_checkpoint(self, message_id: str, account_email: str, processed_at: 'datetime.datetime') -> None:
        """
        Define o checkpoint inicial para uma conta, marcando um e-mail como já processado.
        'processed_at' é o timestamp do e-mail que está sendo marcado como checkpoint.
        """
        pass
import datetime # Add this import for the type hint
