from src.application.services import EmailAppService
from src.domain.models import EmailMessage # , अन्य मॉडल्स જો જરૂરી હોય તો
from typing import List, Optional

class SendEmailUseCase:
    """Caso de uso para enviar um e-mail."""
    def __init__(self, email_app_service: EmailAppService):
        self.email_app_service = email_app_service

    def execute(self, account_email: str, recipient: str, subject: str, body: str, attachments: Optional[List[str]] = None) -> bool:
        """
        Executa o caso de uso.
        :param account_email: E-mail da conta remetente.
        :param recipient: E-mail do destinatário.
        :param subject: Assunto do e-mail.
        :param body: Corpo do e-mail.
        :param attachments: Lista de caminhos para anexos (opcional).
        :return: True se o e-mail foi enviado com sucesso, False caso contrário.
        """
        try:
            return self.email_app_service.send_email(
                account_email=account_email,
                recipient=recipient,
                subject=subject,
                body=body,
                attachments=attachments or []
            )
        except ValueError as e:
            # Logar o erro (ex: conta não encontrada, inativa)
            print(f"Erro ao enviar e-mail (ValueError): {e}")
            return False
        except Exception as e:
            # Logar outros erros inesperados
            print(f"Erro inesperado ao enviar e-mail: {e}")
            return False

class CheckNewEmailsUseCase:
    """Caso de uso para verificar novos e-mails."""
    def __init__(self, email_app_service: EmailAppService):
        self.email_app_service = email_app_service

    def execute(self, account_email: str, folder: str = "Inbox", limit: int = 10) -> List[EmailMessage]:
        """
        Executa o caso de uso.
        :param account_email: E-mail da conta a ser verificada.
        :param folder: Pasta a ser verificada (padrão: "Inbox").
        :param limit: Número máximo de e-mails a serem retornados.
        :return: Lista de objetos EmailMessage.
        """
        try:
            return self.email_app_service.check_new_emails(
                account_email=account_email,
                folder=folder,
                limit=limit
            )
        except ValueError as e:
            print(f"Erro ao verificar e-mails (ValueError): {e}")
            return []
        except Exception as e:
            print(f"Erro inesperado ao verificar e-mails: {e}")
            return []

class AddEmailAccountUseCase:
    """Caso de uso para adicionar uma nova conta de e-mail."""
    def __init__(self, email_app_service: EmailAppService):
        self.email_app_service = email_app_service

    def execute(self, email_address: str, password: str, account_type: str) -> bool:
        """
        Executa o caso de uso.
        :param email_address: Endereço de e-mail da nova conta.
        :param password: Senha da nova conta.
        :param account_type: Tipo da conta (ex: "outlook", "gmail").
        :return: True se a conta foi adicionada com sucesso, False caso contrário.
        """
        try:
            self.email_app_service.add_email_account(
                email_address=email_address,
                password=password,
                account_type=account_type
            )
            return True
        except ValueError as e: # Pode ser lançado se o tipo de conta não for suportado, etc.
            print(f"Erro ao adicionar conta de e-mail (ValueError): {e}")
            return False
        except Exception as e: # Outras exceções do repositório ou serviço
            print(f"Erro inesperado ao adicionar conta de e-mail: {e}")
            return False

class NotifyAboutNewEmailsUseCase:
    """
    Caso de uso para verificar novos e-mails e notificar através de um serviço.
    Este é um exemplo de um caso de uso mais complexo que pode orquestrar outros.
    """
    def __init__(self, email_app_service: EmailAppService, notification_recipient: Optional[str] = None):
        self.email_app_service = email_app_service
        self.notification_recipient = notification_recipient or \
                                      self.email_app_service.get_app_config_value("DEFAULT_NOTIFICATION_RECIPIENT")

    def execute(self, account_email: str, folder: str = "Inbox") -> int:
        """
        Verifica novos e-mails e envia notificações.
        :param account_email: Conta de e-mail para verificar.
        :param folder: Pasta a ser verificada.
        :return: Número de novas mensagens notificadas.
        """
        if not self.email_app_service.notification_service:
            print("Serviço de notificação não configurado. Pulando notificações.")
            return 0

        if not self.notification_recipient:
            print("Destinatário de notificação não configurado. Pulando notificações.")
            return 0

        new_emails = self.email_app_service.check_new_emails(account_email, folder)

        count_notified = 0
        for email in new_emails:
            # A lógica de `check_new_emails` já pode ter notificado,
            # mas este use case pode ter uma lógica de notificação diferente
            # ou adicional, ou garantir que a notificação ocorra aqui.
            # Para este exemplo, vamos assumir que `check_new_emails` não notifica
            # ou que queremos uma notificação adicional/diferente.

            # Simplificando: se o EmailAppService já notifica em check_new_emails,
            # este use case pode ser mais sobre agendar a verificação,
            # ou agregar resultados de múltiplas contas.
            # Vamos ajustar para que a notificação seja feita aqui explicitamente.

            # Reconstruindo a lógica de notificação que estava comentada em EmailAppService:
            if not email.is_read: # Ou alguma outra lógica para determinar se deve notificar
                message = f"Novo e-mail em {account_email} de {email.sender}: {email.subject}"
                try:
                    # Usando o notification_service diretamente do EmailAppService
                    self.email_app_service.notification_service.send_notification(
                        message,
                        self.notification_recipient # Pode ser o e-mail do usuário ou um admin
                    )
                    # Opcional: Marcar como lido/processado após notificar
                    # account = self.email_app_service.get_account_details(account_email)
                    # if account:
                    #     email_service_adapter = self.email_app_service._get_email_service(account.account_type)
                    #     session = email_service_adapter.login(account)
                    #     if session:
                    #         try:
                    #             email_service_adapter.mark_as_read(session, email.message_id, folder)
                    #         finally:
                    #             email_service_adapter.logout(session)
                    count_notified += 1
                except Exception as e:
                    print(f"Falha ao enviar notificação para o e-mail {email.message_id}: {e}")

        if count_notified > 0:
            print(f"{count_notified} novas notificações de e-mail enviadas para {self.notification_recipient}.")
        else:
            print(f"Nenhum e-mail novo encontrado para {account_email} que precise de notificação.")

        return count_notified

# Outros exemplos de casos de uso:
# - ArchiveOldEmailsUseCase
# - OrganizeInboxUseCase (ex: mover e-mails para pastas baseadas em regras)
# - CreateCalendarEventFromEmailUseCase
# - GenerateEmailReportUseCase
# - AutoReplyUseCase
# - ManageContactUseCase (CRUD para contatos)
# - ScheduleRecurringEmailUseCase
# - BackupEmailsUseCase

import datetime
import os
import time # For potential delays between notifications/downloads
# from src.infrastructure.sqlite_repository import SQLiteRepository # No longer specific, use interface
from src.domain.interfaces import ProcessedEmailRepository # Import the interface
from src.application.utils import sanitize_html, normalize_filename, SKIP_IMAGE_EXTENSIONS
from src.domain.models import EmailAccount # For type hinting

class MonitorNewEmailsAndNotifyUseCase:
    """
    Caso de uso para monitorar continuamente novos e-mails de uma conta,
    enviar notificações detalhadas (incluindo anexos) via Telegram,
    e rastrear e-mails processados para evitar duplicidade.
    Este caso de uso é mais próximo da funcionalidade do script original `automail_old.py`.
    """
    def __init__(self,
                 email_app_service: EmailAppService,
                 db_repository: ProcessedEmailRepository, # Use ProcessedEmailRepository interface
                 default_notification_recipient: Optional[str] = None):
        self.email_app_service = email_app_service
        self.db_repository = db_repository
        self.default_notification_recipient = default_notification_recipient or \
            self.email_app_service.get_app_config_value("DEFAULT_NOTIFICATION_RECIPIENT")

        # Ensure notification service is available, otherwise this use case is largely pointless
        if not self.email_app_service.notification_service:
            # This could raise an error or simply log a warning and allow execution (but do nothing)
            print("MonitorNewEmailsAndNotifyUseCase: Serviço de notificação não configurado no EmailAppService. As notificações não funcionarão.")
            # raise ValueError("Notification service is required for MonitorNewEmailsAndNotifyUseCase")


    def _build_telegram_message_content(self, sender: str, subject: str, body_preview: str, max_length: int = 4000) -> str:
        """
        Constrói a mensagem de texto formatada para o Telegram.
        Similar à função build_telegram_message do script original.
        """
        # Sanitização já deve ter sido feita antes de chamar esta função
        message = f"<b>Novo e-mail!</b>\n<b>De:</b> {sender}\n<b>Assunto:</b> {subject}\n\n{body_preview}"
        if len(message) > max_length:
            # Trunca preservando o final da mensagem de truncamento
            trunc_msg = "\n\n(Mensagem truncada pelo limite do Telegram)"
            message = message[:max_length - len(trunc_msg)] + trunc_msg
        return message

    def execute(self, account_email_address: str, folder_to_monitor: str = "Inbox", processing_delay_seconds: int = 2, initial_outlook_session: Optional[dict] = None) -> int:
        """
        Executa o monitoramento e notificação.
        :param account_email_address: O endereço de e-mail da conta a ser monitorada.
        :param folder_to_monitor: A pasta de e-mail a ser monitorada (ex: "Inbox").
        :param processing_delay_seconds: Pequeno delay para evitar sobrecarga (API, disco).
        :param initial_outlook_session: (Opcional) Uma sessão do Outlook pré-existente para reutilizar, útil para local_win32 com seleção de store.
        :return: Número de novos e-mails processados e notificados.
        """
        if not self.email_app_service.notification_service:
            print(f"MonitorNewEmailsAndNotifyUseCase: Sem serviço de notificação, não é possível processar {account_email_address}.")
            return 0

        account: Optional[EmailAccount] = self.email_app_service.get_account_details(account_email_address)
        if not account or not account.is_active:
            print(f"MonitorNewEmailsAndNotifyUseCase: Conta {account_email_address} não encontrada ou inativa.")
            return 0

        print(f"MonitorNewEmailsAndNotifyUseCase: Iniciando verificação para {account_email_address} na pasta {folder_to_monitor}.")

        # 1. Obter o EmailService específico para a conta
        # Este é um método interno do EmailAppService, talvez precise expor de forma controlada
        # ou passar o EmailService diretamente para o construtor do UseCase se for mais limpo.
        # Por enquanto, vamos assumir que o EmailAppService pode fornecer acesso à instância de serviço.
        try:
            email_service_adapter = self.email_app_service._get_email_service(account.account_type)
        except (ValueError, ImportError, AttributeError) as e:
            print(f"MonitorNewEmailsAndNotifyUseCase: Erro ao obter adaptador de e-mail para {account.account_type}: {e}")
            return 0

        # 2. Login na conta de e-mail
        # Passar initial_outlook_session se for uma conta outlook e a sessão existir
        login_session_to_reuse = None
        if account.account_type == 'outlook' and initial_outlook_session:
            login_session_to_reuse = initial_outlook_session
            print(f"MonitorNewEmailsAndNotifyUseCase: Tentando reutilizar sessão Outlook para {account_email_address}.")

        session_or_client = email_service_adapter.login(account, session_to_reuse=login_session_to_reuse)
        if not session_or_client:
            print(f"MonitorNewEmailsAndNotifyUseCase: Falha no login da conta {account_email_address}.")
            return 0

        processed_count = 0
        try:
            # 3. Obter o último EntryID processado para esta conta.
            # Renomeado para get_last_processed_email_id e account_email é obrigatório.
            last_checkpoint_entry_id = self.db_repository.get_last_processed_email_id(account_email=account.email_address)
            print(f"MonitorNewEmailsAndNotifyUseCase: Último checkpoint para {account_email_address}: {last_checkpoint_entry_id or 'Nenhum'}")

            # 4. Listar e-mails da pasta.
            # Precisamos de uma forma de listar e-mails mais recentes que o checkpoint.
            # A interface EmailService.list_emails pode precisar de um parâmetro `after_entry_id` ou `min_received_date`.
            # O script original lia todos, ordenava e parava no checkpoint.
            # Para simplificar, vamos pegar os últimos N e filtrar aqui.
            # O limite deve ser configurável ou suficientemente grande para não perder e-mails entre verificações.
            # A ordenação deve ser por data de recebimento, decrescente (mais novo primeiro).
            # O OutlookAdapter já faz isso.
            # O EmailMessage.timestamp deve ser um objeto datetime.

            # O `limit` aqui é quantos e-mails recentes buscar para verificação.
            # Não é o limite final de processamento, apenas o tamanho da janela de busca.
            # O ideal é que o `list_emails` possa filtrar por data ou ID no servidor.
            # Como fallback, pegamos os últimos (ex: 50) e filtramos.
            config_limit_check = self.email_app_service.get_app_config_value("MONITOR_FETCH_LIMIT", 50)
            all_recent_emails = email_service_adapter.list_emails(
                session_or_client,
                folder=folder_to_monitor,
                limit=config_limit_check, # Pega os X mais recentes
                # search_criteria={"sort": "receivedDateTime DESC"} # Opcional, se o adapter suportar
            )

            if not all_recent_emails and not last_checkpoint_entry_id:
                 print(f"MonitorNewEmailsAndNotifyUseCase: Nenhuma mensagem na caixa de entrada de {account_email_address} e nenhum checkpoint. Nada a fazer.")
                 # Se não há checkpoint e não há e-mails, podemos definir o checkpoint para o próximo e-mail que chegar.
                 # Mas, por enquanto, vamos apenas sair. O script original definiria o checkpoint para o mais recente se existisse.
                 return 0

            if not all_recent_emails and last_checkpoint_entry_id:
                print(f"MonitorNewEmailsAndNotifyUseCase: Nenhuma mensagem recente encontrada para {account_email_address}, checkpoint {last_checkpoint_entry_id} mantido.")
                return 0


            # 5. Lógica de primeira execução: definir checkpoint se não existir
            if not last_checkpoint_entry_id and all_recent_emails:
                # O e-mail mais recente (primeiro da lista, pois está ordenado) será o checkpoint.
                # Nenhum e-mail será processado nesta primeira execução.
                latest_email_for_checkpoint = all_recent_emails[0]
                if latest_email_for_checkpoint.message_id and latest_email_for_checkpoint.timestamp:
                    self.db_repository.set_initial_checkpoint(
                        message_id=latest_email_for_checkpoint.message_id, # Corrigido para message_id
                        processed_at=latest_email_for_checkpoint.timestamp, # Corrigido para processed_at
                        account_email=account.email_address
                    )
                    print(f"MonitorNewEmailsAndNotifyUseCase: Primeira execução para {account_email_address}. Marco inicial definido para MessageID: {latest_email_for_checkpoint.message_id}. E-mails anteriores não serão processados.")
                else:
                     print(f"MonitorNewEmailsAndNotifyUseCase: Não foi possível definir checkpoint inicial, ID da mensagem ou timestamp ausente no e-mail mais recente.")
                return 0


            # 6. Filtrar e-mails que são realmente novos (após o checkpoint) e ainda não processados
            new_emails_to_process = []
            if last_checkpoint_entry_id:
                for email in all_recent_emails: # Iterando do mais novo para o mais antigo
                    if email.message_id == last_checkpoint_entry_id:
                        break # Encontramos o último processado, parar
                    # is_email_processed agora requer account_email
                    if not self.db_repository.is_email_processed(email.message_id, account.email_address):
                        new_emails_to_process.append(email)
            else: # Se não havia checkpoint, mas por alguma razão a lógica de "primeira execução" não pegou.
                  # Processar todos os e-mails não processados.
                for email in all_recent_emails:
                    # is_email_processed agora requer account_email
                    if not self.db_repository.is_email_processed(email.message_id, account.email_address):
                        new_emails_to_process.append(email)

            # A lista `new_emails_to_process` está do mais novo para o mais antigo (se `all_recent_emails` estava).
            # O script original processava do mais antigo para o mais novo dos novos.
            new_emails_to_process.reverse()


            if not new_emails_to_process:
                print(f"MonitorNewEmailsAndNotifyUseCase: Nenhum e-mail novo para {account_email_address} desde o último checkpoint.")
                return 0

            print(f"MonitorNewEmailsAndNotifyUseCase: {len(new_emails_to_process)} novo(s) e-mail(s) para processar para {account_email_address}.")

            # 7. Processar cada novo e-mail
            for email_message in new_emails_to_process:
                if not email_message.message_id or not email_message.timestamp:
                    print(f"MonitorNewEmailsAndNotifyUseCase: E-mail ignorado por falta de message_id ou timestamp. Assunto: {email_message.subject}")
                    continue

                try:
                    print(f"MonitorNewEmailsAndNotifyUseCase: Processando e-mail de '{email_message.sender}', Assunto: '{email_message.subject}'")

                    # Sanitizar conteúdo
                    clean_sender = sanitize_html(email_message.sender or "(Remetente desconhecido)")
                    clean_subject = sanitize_html(email_message.subject or "(Sem assunto)")
                    # O corpo pode ser HTML, o adapter deve fornecer o melhor texto possível.
                    # Para o preview do Telegram, podemos querer uma versão mais curta ou em texto plano.
                    # Assumindo que email_message.body já é um texto razoável (ex: HTMLBody ou Body).
                    # O build_telegram_message_content fará o truncamento se necessário.
                    # Idealmente, o adapter deveria fornecer uma prévia em texto plano do corpo se for HTML.
                    body_preview = sanitize_html(email_message.body or "(Sem corpo)")

                    # Construir mensagem para Telegram
                    telegram_text_content = self._build_telegram_message_content(clean_sender, clean_subject, body_preview)

                    # Enviar notificação de texto
                    if self.email_app_service.notification_service:
                        self.email_app_service.notification_service.send_notification(
                            telegram_text_content,
                            recipient_id=self.default_notification_recipient # Ou um recipient_id específico
                        )

                    # Processar e enviar anexos
                    # Esta parte depende de como EmailMessage.attachments é populado pelo adapter.
                    # Assumindo que attachments é uma lista de objetos/dicionários com 'filename' e 'content' (bytes)
                    # ou 'filepath' (caminho para arquivo temporário).
                    if email_message.attachments:
                        # O adapter precisa de um método para buscar o conteúdo dos anexos se não for embutido.
                        # Ex: email_service_adapter.get_attachment_content(session_or_client, email_message.message_id, attachment_id)
                        # Por agora, vamos simular o que o script antigo fazia: attachments são caminhos de arquivos.
                        # Esta é uma área que PRECISA de refatoração no OutlookAdapter.

                        # Placeholder para a lógica de download de anexos:
                        # Suponha que o adapter populou `email_message.attachments` com uma lista de dicts:
                        # [{'filename': 'doc.pdf', 'content_bytes': b'...'}, {'filename': 'image.jpg', 'content_bytes': b'...'}]
                        # OU [{'filename': 'doc.pdf', 'temp_filepath': '/tmp/xyz.pdf'}]

                        # Temporariamente, vamos assumir que o EmailAdapter lida com o download
                        # e `email_message.attachments` é uma lista de caminhos para arquivos temporários.
                        # Esta lógica precisará ser ajustada com base na implementação real do adapter.

                        # O adapter deve fornecer os anexos de uma forma que possam ser lidos aqui.
                        # Ex: uma lista de tuplas (filename, filebytes) ou (filename, temp_filepath)

                        downloaded_attachments = email_service_adapter.download_attachments(
                            session_or_client,
                            email_message.message_id,
                            folder_to_monitor # Alguns APIs podem precisar da pasta
                        ) # Este método precisa ser adicionado à interface EmailService e implementado

                        if downloaded_attachments:
                            for att_info in downloaded_attachments: # att_info = {'filename': str, 'content': bytes, 'filepath': Optional[str]}
                                original_fname = att_info['filename']
                                normalized_fname = normalize_filename(original_fname)
                                file_extension = os.path.splitext(normalized_fname)[1].lower()

                                if file_extension in SKIP_IMAGE_EXTENSIONS:
                                    print(f"MonitorNewEmailsAndNotifyUseCase: Anexo '{normalized_fname}' ignorado (imagem).")
                                    continue

                                print(f"MonitorNewEmailsAndNotifyUseCase: Enviando anexo '{normalized_fname}'...")
                                file_content_to_send = None
                                if att_info.get('content'):
                                    file_content_to_send = att_info['content']
                                elif att_info.get('filepath') and os.path.exists(att_info['filepath']):
                                    # Se for um filepath, o TelegramAdapter pode lê-lo ou passamos bytes
                                    file_content_to_send = att_info['filepath'] # TelegramAdapter pode lidar com path
                                else:
                                    print(f"MonitorNewEmailsAndNotifyUseCase: Conteúdo do anexo '{original_fname}' não encontrado.")
                                    continue

                                if self.email_app_service.notification_service and file_content_to_send:
                                    self.email_app_service.notification_service.send_file(
                                        file_path_or_bytes=file_content_to_send,
                                        recipient_id=self.default_notification_recipient,
                                        filename=normalized_fname,
                                        caption=f"Anexo de: {clean_sender}\nAssunto: {clean_subject}"
                                    )
                                    time.sleep(processing_delay_seconds) # Pequena pausa

                                # Limpar arquivo temporário se foi criado e um 'filepath' foi retornado
                                if att_info.get('filepath') and os.path.exists(att_info['filepath']):
                                    try:
                                        os.remove(att_info['filepath'])
                                    except Exception as e_rm:
                                        print(f"MonitorNewEmailsAndNotifyUseCase: Erro ao remover anexo temporário '{att_info['filepath']}': {e_rm}")
                        else:
                            print(f"MonitorNewEmailsAndNotifyUseCase: Método download_attachments não retornou anexos para {email_message.message_id}")


                    # Marcar como processado no final
                    self.db_repository.add_processed_email(
                        message_id=email_message.message_id, # Corrigido para message_id
                        processed_at=email_message.timestamp, # Usar o timestamp do e-mail para consistência
                        account_email=account.email_address
                    )
                    processed_count += 1
                    print(f"MonitorNewEmailsAndNotifyUseCase: E-mail '{email_message.subject}' processado e notificado.")
                    time.sleep(processing_delay_seconds) # Pausa entre processamento de e-mails

                except Exception as e:
                    print(f"MonitorNewEmailsAndNotifyUseCase: Erro ao processar e-mail ID {email_message.message_id} (Assunto: {email_message.subject}): {e}")
                    # Decidir se deve marcar como processado mesmo em caso de erro para não tentar de novo.
                    # Por segurança (evitar loops de erro), vamos marcar.
                    # Mas em um sistema real, pode haver uma lógica de retentativa ou "quarentena".
                    if email_message.message_id and email_message.timestamp: # Garante que temos o ID
                        self.db_repository.add_processed_email(
                            message_id=email_message.message_id, # Corrigido para message_id
                            processed_at=datetime.datetime.now(), # Usar now() para erro
                            account_email=account.email_address
                        )
                        print(f"MonitorNewEmailsAndNotifyUseCase: E-mail ID {email_message.message_id} marcado como processado após erro para evitar repetição.")
                    # Continuar para o próximo e-mail

            if processed_count > 0:
                 print(f"MonitorNewEmailsAndNotifyUseCase: {processed_count} e-mails processados com sucesso para {account_email_address}.")
            current_last_id = self.db_repository.get_last_processed_email_id(account.email_address) # Renomeado
            print(f"MonitorNewEmailsAndNotifyUseCase: Novo checkpoint para {account_email_address} é {current_last_id}")


        except Exception as e:
            print(f"MonitorNewEmailsAndNotifyUseCase: Erro geral durante a execução para {account_email_address}: {e}")
            # Considerar logar stacktrace completo aqui
        finally:
            email_service_adapter.logout(session_or_client)
            print(f"MonitorNewEmailsAndNotifyUseCase: Logout da conta {account_email_address} concluído.")

        return processed_count
