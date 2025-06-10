from typing import List, Optional, Any
from src.domain.models import EmailMessage, EmailAccount, CalendarEvent, Task
from src.domain.interfaces import EmailService, DatabaseRepository, NotificationService, ConfigRepository
import importlib # Para carregar dinamicamente classes de serviço de e-mail

class EmailAppService:
    """
    Serviço de aplicação para gerenciar operações de e-mail e contas.
    Orquestra a interação entre adaptadores de e-mail, repositório de banco de dados
    e serviços de notificação.
    """
    def __init__(self,
                 db_repository: DatabaseRepository,
                 config_repository: ConfigRepository,
                 notification_service: Optional[NotificationService] = None):
        self.db_repository = db_repository
        self.config_repository = config_repository
        self.notification_service = notification_service
        self._email_service_instances = {} # Cache para instâncias de EmailService
        self.app_config = self.config_repository.load_config()

    def _get_email_service(self, account_type: str) -> EmailService:
        """
        Carrega e instancia dinamicamente o serviço de e-mail apropriado
        baseado no tipo de conta (ex: "outlook", "gmail").
        As implementações concretas (adaptadores) devem estar em src.infrastructure.
        """
        if account_type in self._email_service_instances:
            return self._email_service_instances[account_type]

        service_class_name = self.app_config.get("ACCOUNT_SERVICE_MAP", {}).get(account_type)
        if not service_class_name:
            raise ValueError(f"Tipo de conta de e-mail não suportado ou não mapeado: {account_type}")

        try:
            # Assumindo que os adaptadores estão em src.infrastructure
            # e seguem o padrão de nomenclatura <NomeDoServico>Adapter
            # Ex: OutlookAdapter, GmailAdapter
            module_path = f"src.infrastructure.{service_class_name.lower()}_adapter" # outlook_adapter
            module = importlib.import_module(module_path)

            # O nome da classe no arquivo do adaptador pode ser diferente,
            # mas idealmente deveria ser o mesmo que `service_class_name`
            # Ex: No arquivo outlook_adapter.py, a classe é OutlookAdapter
            # Se for diferente, precisará de um mapeamento mais explícito.
            # Para este exemplo, vamos assumir que o nome da classe é o service_class_name
            # Ex: OutlookAdapter (definido no config) -> infrastructure.outlook_adapter.OutlookAdapter

            # Tentativa de encontrar a classe no módulo.
            # Pode ser necessário ajustar se a convenção de nomenclatura for diferente.
            # Ex: Se o mapeamento for "OutlookService" e a classe for "OutlookEmailAdapter"
            service_class = getattr(module, service_class_name)

            # Passar configurações específicas do serviço, se houver
            service_config = self.app_config.get(account_type.upper(), {}) # ex: OUTLOOK_CONFIG
            instance = service_class(config=service_config, db_repository=self.db_repository) # Adaptadores podem precisar de config e/ou db_repo

            self._email_service_instances[account_type] = instance
            return instance
        except ImportError:
            raise ImportError(f"Não foi possível encontrar o módulo do adaptador: {module_path}")
        except AttributeError:
            raise AttributeError(f"Não foi possível encontrar a classe {service_class_name} no módulo {module_path}")
        except Exception as e:
            # Logar o erro e relançar ou tratar de forma mais específica
            print(f"Erro ao instanciar {service_class_name}: {e}")
            raise

    def add_email_account(self, email_address: str, password: str, account_type: str) -> EmailAccount:
        """Adiciona uma nova conta de e-mail."""
        # TODO: Criptografar senha antes de salvar
        account = EmailAccount(email_address=email_address, password=password, account_type=account_type)
        created_account = self.db_repository.add_account(account)
        if self.notification_service:
            self.notification_service.send_notification(
                f"Nova conta de e-mail adicionada: {email_address}",
                self.app_config.get("ADMIN_NOTIFICATION_RECIPIENT")
            )
        return created_account

    def get_account_details(self, email_address: str) -> Optional[EmailAccount]:
        """Obtém detalhes de uma conta de e-mail."""
        return self.db_repository.get_account(email_address)

    def list_all_accounts(self) -> List[EmailAccount]:
        """Lista todas as contas de e-mail configuradas."""
        return self.db_repository.list_accounts()

    def send_email(self, account_email: str, recipient: str, subject: str, body: str, attachments: List[str] = None) -> bool:
        """Envia um e-mail usando a conta especificada."""
        account = self.db_repository.get_account(account_email)
        if not account or not account.is_active:
            raise ValueError(f"Conta {account_email} não encontrada ou inativa.")

        email_service = self._get_email_service(account.account_type)

        # O login pode retornar uma sessão ou um objeto de cliente que precisa ser usado
        # para chamadas subsequentes.
        session_or_client = email_service.login(account)
        if not session_or_client:
             # Logar o erro e talvez notificar
            print(f"Falha no login da conta {account_email}")
            if self.notification_service:
                self.notification_service.send_notification(
                    f"Falha no login da conta {account_email} ao tentar enviar e-mail.",
                    self.app_config.get("ADMIN_NOTIFICATION_RECIPIENT")
                )
            return False

        email_message = EmailMessage(
            sender=account.email_address,
            recipient=recipient,
            subject=subject,
            body=body,
            attachments=attachments or []
        )

        try:
            success = email_service.send_email(session_or_client, email_message)
            if success and self.notification_service:
                self.notification_service.send_notification(
                    f"E-mail enviado de {account_email} para {recipient} com assunto: {subject}",
                    self.app_config.get("USER_NOTIFICATION_RECIPIENT", account_email) # Notificar o remetente ou admin
                )
            # TODO: Logar o e-mail enviado no banco de dados (se necessário)
            return success
        finally:
            email_service.logout(session_or_client)


    def check_new_emails(self, account_email: str, folder: str = "Inbox", limit: int = 5) -> List[EmailMessage]:
        """Verifica novos e-mails para uma conta."""
        account = self.db_repository.get_account(account_email)
        if not account or not account.is_active:
            raise ValueError(f"Conta {account_email} não encontrada ou inativa.")

        email_service = self._get_email_service(account.account_type)
        session_or_client = email_service.login(account)
        if not session_or_client:
            print(f"Falha no login da conta {account_email} ao verificar e-mails.")
            return []

        try:
            emails = email_service.list_emails(session_or_client, folder=folder, limit=limit)
            # TODO: Filtrar e-mails que já foram processados/notificados
            # TODO: Salvar estado do último e-mail verificado para evitar reprocessamento

            # Exemplo de notificação para cada novo e-mail (pode ser customizado)
            if emails and self.notification_service:
                for email in emails: # Assumindo que list_emails retorna apenas os não lidos ou novos
                    if not email.is_read: # Adicionar um filtro extra se necessário
                        self.notification_service.send_notification(
                            f"Novo e-mail para {account_email} de {email.sender}: {email.subject}",
                            self.app_config.get("USER_NOTIFICATION_RECIPIENT", account_email)
                        )
                        # Opcional: marcar como lido após notificar
                        # email_service.mark_as_read(session_or_client, email.message_id, folder)
            return emails
        finally:
            email_service.logout(session_or_client)

    # --- Métodos de Calendário (usando o EmailService por enquanto) ---
    def create_calendar_event(self, account_email: str, event_data: dict) -> Optional[CalendarEvent]:
        account = self.db_repository.get_account(account_email)
        if not account or not account.is_active:
            raise ValueError(f"Conta {account_email} não encontrada ou inativa.")

        email_service = self._get_email_service(account.account_type)
        session = email_service.login(account)
        if not session: return None

        try:
            event = CalendarEvent(**event_data) # Assume que event_data corresponde aos campos de CalendarEvent
            return email_service.create_event(session, event)
        finally:
            email_service.logout(session)

    # --- Métodos de Tarefas (usando o EmailService por enquanto) ---
    def create_task(self, account_email: str, task_data: dict) -> Optional[Task]:
        account = self.db_repository.get_account(account_email)
        if not account or not account.is_active:
            raise ValueError(f"Conta {account_email} não encontrada ou inativa.")

        email_service = self._get_email_service(account.account_type)
        session = email_service.login(account)
        if not session: return None

        try:
            task = Task(**task_data) # Assume que task_data corresponde aos campos de Task
            return email_service.create_task(session, task)
        finally:
            email_service.logout(session)

    def get_app_config_value(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """Obtém um valor da configuração da aplicação."""
        return self.app_config.get(key, default)

    def set_app_config_value(self, key: str, value: Any) -> None:
        """Define um valor na configuração da aplicação (e persiste se o repo de config suportar)."""
        self.app_config[key] = value
        self.config_repository.set_config_value(key, value) # Persiste a mudança
        # Recarregar config localmente ou invalidar cache se necessário
        self.app_config = self.config_repository.load_config()


class NotificationAppService:
    """
    Serviço de aplicação para gerenciar notificações.
    """
    def __init__(self,
                 notification_service: NotificationService,
                 config_repository: ConfigRepository):
        self.notification_service = notification_service
        self.config_repository = config_repository
        self.app_config = self.config_repository.load_config()

    def send_direct_notification(self, message: str, recipient_id: Optional[str] = None) -> bool:
        """
        Envia uma notificação direta.
        Se recipient_id não for fornecido, tenta usar um destinatário padrão da configuração.
        """
        if not recipient_id:
            recipient_id = self.app_config.get("DEFAULT_NOTIFICATION_RECIPIENT")

        if not recipient_id:
            raise ValueError("Destinatário da notificação não especificado e nenhum padrão configurado.")

        return self.notification_service.send_notification(message, recipient_id)

# Poderiam existir outros serviços de aplicação aqui, como:
# - UserManagementService
# - AutomationRuleService
# - ReportingService
# - CalendarAppService (se a lógica de calendário se tornar complexa)
# - TaskAppService (se a lógica de tarefas se tornar complexa)
