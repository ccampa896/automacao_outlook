from dataclasses import dataclass, field
from typing import List, Optional
import datetime

@dataclass
class EmailAccount:
    """Representa uma conta de e-mail."""
    email_address: str
    password: str
    account_type: str  # Ex: "outlook", "gmail"
    is_active: bool = True

@dataclass
class EmailMessage:
    """Representa uma mensagem de e-mail."""
    sender: str
    recipient: str  # Pode ser uma lista de e-mails separados por vírgula
    subject: str
    body: str
    attachments: List['AttachmentData'] = field(default_factory=list) # Alterado para List[AttachmentData]
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    is_read: bool = False
    message_id: Optional[str] = None # ID único do e-mail no servidor
    folder: Optional[str] = "Inbox"  # Caixa de entrada, enviados, etc.

@dataclass
class Contact:
    """Representa um contato."""
    name: str
    email: str
    phone: Optional[str] = None
    organization: Optional[str] = None

@dataclass
class CalendarEvent:
    """Representa um evento de calendário."""
    subject: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    location: Optional[str] = None
    description: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    event_id: Optional[str] = None # ID único do evento no servidor

@dataclass
class Task:
    """Representa uma tarefa."""
    subject: str
    due_date: Optional[datetime.date] = None
    is_completed: bool = False
    reminder_time: Optional[datetime.datetime] = None
    task_id: Optional[str] = None # ID único da tarefa no servidor

# Mapeamento de tipos de conta para suas respectivas classes de serviço/adaptador
# Pode ser expandido conforme novos provedores são adicionados.
ACCOUNT_SERVICE_MAP = {
    "outlook": "OutlookService",
    "gmail": "GmailService", # Exemplo, não implementado ainda
}

# Poderia adicionar validações ou métodos auxiliares às classes dataclass se necessário.
# Exemplo:
# def __post_init__(self):
#     if not self.email_address or "@" not in self.email_address:
#         raise ValueError("Endereço de e-mail inválido.")

# Considerar adicionar um Enum para account_type ou outros campos com valores restritos.
# from enum import Enum
# class AccountType(Enum):
#     OUTLOOK = "outlook"
#     GMAIL = "gmail"
#
# class EmailAccount:
#   ...
#   account_type: AccountType
#   ...

@dataclass
class AttachmentData:
    """Representa os dados de um anexo de e-mail."""
    filename: str
    content_bytes: Optional[bytes] = None # Conteúdo do anexo em bytes
    filepath: Optional[str] = None # Caminho para um arquivo temporário, se aplicável
    content_type: Optional[str] = None # MIME type
    # Adicionar outros metadados se necessário, ex: content_id para anexos inline
    # attachment_id_on_server: Optional[str] = None # ID do anexo no servidor de e-mail
