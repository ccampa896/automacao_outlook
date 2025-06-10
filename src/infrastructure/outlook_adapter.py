from typing import List, Optional, Any, Dict
from src.domain.models import EmailMessage, EmailAccount, CalendarEvent, Task, Contact, AttachmentData
from src.domain.interfaces import EmailService, DatabaseRepository
import datetime
import os # Para manipulação de caminhos e arquivos temporários
import tempfile # Para criar arquivos temporários seguros
import base64 # Para decodificar anexos da Graph API

# Tentar importar bibliotecas específicas do Outlook.
# Se não estiverem presentes, o adaptador não funcionará, mas o resto da aplicação sim.
try:
    import win32com.client
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    # print("OutlookAdapter: Biblioteca 'pywin32' não encontrada. Funcionalidade local do Outlook desabilitada.")

try:
    import requests
    from msal import ConfidentialClientApplication
    MSAL_AVAILABLE = True
except ImportError:
    MSAL_AVAILABLE = False
    # print("OutlookAdapter: Bibliotecas 'requests' e 'msal' não encontradas. Funcionalidade do Microsoft Graph API desabilitada.")


class OutlookAdapter(EmailService):
    """
    Adaptador para interagir com e-mails, calendário e tarefas do Outlook.
    Pode usar a API do Microsoft Graph (preferencial) ou automação local com pywin32 (legado).
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None, db_repository: Optional[DatabaseRepository] = None):
        """
        Inicializa o adaptador do Outlook.
        :param config: Dicionário de configuração contendo chaves como:
                       'auth_type': 'graph_api' ou 'local_win32'
                       Para 'graph_api': 'graph_client_id', 'graph_client_secret', 'graph_tenant_id', 'graph_scopes'
                       Para 'local_win32': (nenhuma configuração específica por enquanto)
        :param db_repository: Repositório de banco de dados para buscar senhas ou tokens (se necessário).
        """
        self.config = config or {}
        self.db_repository = db_repository # Pode ser usado para buscar senhas ou tokens de atualização
        self.auth_type = self.config.get("auth_type", "graph_api" if MSAL_AVAILABLE else "local_win32")

        self.graph_client_id = self.config.get("OUTLOOK_CLIENT_ID")
        self.graph_client_secret = self.config.get("OUTLOOK_CLIENT_SECRET")
        self.graph_tenant_id = self.config.get("OUTLOOK_TENANT_ID")
        self.graph_scopes = self.config.get("graph_scopes", ["https://graph.microsoft.com/.default"])

        self.msal_app = None
        self.graph_token = None

        if self.auth_type == "graph_api" and not MSAL_AVAILABLE:
            raise ImportError("Módulos 'msal' e 'requests' são necessários para autenticação Graph API.")
        if self.auth_type == "local_win32" and not WIN32COM_AVAILABLE:
            raise ImportError("Módulo 'pywin32' é necessário para automação local do Outlook.")

        print(f"OutlookAdapter inicializado com tipo de autenticação: {self.auth_type}")

    def _get_graph_token(self, account: EmailAccount) -> Optional[str]:
        """Obtém um token de acesso para o Microsoft Graph API."""
        if not self.graph_client_id or not self.graph_client_secret or not self.graph_tenant_id:
            print("OutlookAdapter (Graph): Client ID, Client Secret ou Tenant ID não configurados.")
            return None

        if not self.msal_app:
            authority = f"https://login.microsoftonline.com/{self.graph_tenant_id}"
            self.msal_app = ConfidentialClientApplication(
                client_id=self.graph_client_id,
                authority=authority,
                client_credential=self.graph_client_secret
            )

        # Tentar obter token do cache
        token_result = self.msal_app.acquire_token_silent(scopes=self.graph_scopes, account=None)

        if not token_result:
            print("OutlookAdapter (Graph): Token não encontrado no cache, adquirindo novo token...")
            # Adquirir token usando client credentials flow (para cenários de backend)
            # Para cenários de usuário, um fluxo interativo ou device code flow seria necessário na primeira vez.
            # Este exemplo foca no client credentials flow.
            # Se você precisar de "delegated permissions" (atuar como um usuário),
            # o fluxo de autenticação precisará ser diferente (ex: device code, auth code grant).
            # O password do EmailAccount pode ser usado em fluxos ROPC (Resource Owner Password Credentials),
            # mas ROPC não é recomendado por razões de segurança.
            # Por simplicidade, este exemplo usará client_credentials, que são permissões de aplicação,
            # não permissões delegadas de um usuário específico, a menos que o app esteja configurado para isso.
            token_result = self.msal_app.acquire_token_for_client(scopes=self.graph_scopes)

        if "access_token" in token_result:
            self.graph_token = token_result["access_token"]
            # print("OutlookAdapter (Graph): Token de acesso adquirido com sucesso.")
            return self.graph_token
        else:
            print("OutlookAdapter (Graph): Falha ao adquirir token de acesso.")
            print(f"  Erro: {token_result.get('error')}")
            print(f"  Descrição: {token_result.get('error_description')}")
            return None

    def login(self, account: EmailAccount, session_to_reuse: Optional[Dict] = None) -> Any:
        """
        Realiza login na conta de e-mail.
        Para Graph API, obtém o token.
        Para win32com, estabelece conexão com Outlook.Application e lista as stores (contas MAPI).
        :param account: A conta de e-mail principal para login (para Graph API user_principal_name).
        :param session_to_reuse: (Para local_win32) Uma sessão existente para tentar reutilizar a conexão Outlook.Application.
        :return: Um dicionário de sessão ou None em caso de falha.
        """
        print(f"OutlookAdapter: Tentando login para {account.email_address} usando {self.auth_type}")
        if self.auth_type == "graph_api":
            # O "login" aqui é obter o token. A conta de e-mail específica (account.email_address)
            # será usada nos endpoints da API para especificar o usuário (ex: /users/{user_id_or_upn}/messages).
            # Se estiver usando client credentials, a API opera no contexto da aplicação,
            # a menos que permissões de ApplicationAccessPolicy sejam configuradas no Exchange Online.
            if self._get_graph_token(account):
                # Para Graph, a "sessão" pode ser o próprio token ou o adaptador configurado
                return {"auth_type": "graph_api", "token": self.graph_token, "user_principal_name": account.email_address}
            return None
        elif self.auth_type == "local_win32":
            if not WIN32COM_AVAILABLE: return None

            outlook_app_instance = None
            current_selected_store_id = None

            if session_to_reuse and session_to_reuse.get("outlook_app"):
                outlook_app_instance = session_to_reuse["outlook_app"]
                current_selected_store_id = session_to_reuse.get("selected_store_id") # Preserve previous selection if any
                print("OutlookAdapter (local_win32): Reutilizando instância Outlook.Application da sessão fornecida.")
            else:
                try:
                    outlook_app_instance = win32com.client.Dispatch("Outlook.Application")
                    print("OutlookAdapter (local_win32): Nova instância Outlook.Application criada.")
                except Exception as e_dispatch:
                    print(f"OutlookAdapter (local_win32): Falha ao despachar Outlook.Application: {e_dispatch}")
                    return None

            try:
                namespace = outlook_app_instance.GetNamespace("MAPI")
                available_stores = []
                for i, store_folder_com_obj in enumerate(namespace.Folders):
                    try:
                        store_id = store_folder_com_obj.StoreID
                        display_name = store_folder_com_obj.Name
                        available_stores.append({"id": store_id, "name": display_name, "original_index": i})
                    except Exception as e_store:
                        print(f"OutlookAdapter (local_win32): Erro ao acessar informações do store no índice {i}: {e_store}")
                        continue

                print(f"OutlookAdapter (local_win32): {len(available_stores)} conta(s) MAPI detectada(s).")

                if not current_selected_store_id: # If not preserved from a reused session, determine default
                    if namespace.DefaultStore:
                        current_selected_store_id = namespace.DefaultStore.StoreID
                        print(f"OutlookAdapter (local_win32): Loja padrão do perfil ({namespace.DefaultStore.Name}) definida como selecionada.")
                    elif available_stores:
                        current_selected_store_id = available_stores[0]['id']
                        print(f"OutlookAdapter (local_win32): Usando o primeiro store '{available_stores[0]['name']}' como selecionado.")

                return {
                    "auth_type": "local_win32",
                    "outlook_app": outlook_app_instance,
                    "user_email": account.email_address,
                    "available_stores": available_stores,
                    "selected_store_id": current_selected_store_id
                }
            except Exception as e:
                print(f"OutlookAdapter (local_win32): Falha ao listar stores ou determinar store padrão: {e}")
                return None
        return None

    def _get_selected_store_folder(self, session: Any) -> Optional[Any]:
        """
        Helper para obter o objeto StoreFolder selecionado para o modo local_win32.
        Retorna o StoreFolder da conta selecionada, ou o DefaultStore do perfil,
        ou o primeiro Store se nenhum estiver explicitamente selecionado ou o DefaultStore não estiver acessível.
        """
        if not WIN32COM_AVAILABLE or not session or session.get("auth_type") != "local_win32":
            return None

        outlook_app = session.get("outlook_app")
        if not outlook_app:
            return None

        namespace = outlook_app.GetNamespace("MAPI")
        selected_store_id = session.get("selected_store_id")

        if selected_store_id:
            for store_info in session.get("available_stores", []):
                if store_info["id"] == selected_store_id:
                    # Precisamos do objeto Folder real do namespace.Folders
                    # O índice original foi armazenado para isso.
                    original_idx = store_info.get("original_index")
                    if original_idx is not None and original_idx < len(namespace.Folders):
                         # Verificar se o store ainda é o mesmo pelo StoreID antes de retornar
                        candidate_store = namespace.Folders.Item(original_idx + 1) # PyWin32 COM collections são 1-based
                        if candidate_store and candidate_store.StoreID == selected_store_id:
                            return candidate_store
                    # Fallback: iterar se o índice não funcionar (raro, mas para robustez)
                    for store_folder_obj in namespace.Folders:
                        try:
                            if store_folder_obj.StoreID == selected_store_id:
                                return store_folder_obj
                        except:
                            continue # Ignorar stores que não têm StoreID
            print(f"OutlookAdapter (local_win32): Store selecionado com ID '{selected_store_id}' não encontrado na coleção atual. Usando fallback.")
            # Fallback se o StoreID selecionado não for encontrado (ex: conta removida)

        # Fallback para o DefaultStore do perfil ou o primeiro store da lista
        try:
            if namespace.DefaultStore:
                # print("OutlookAdapter (local_win32): Usando DefaultStore do perfil.")
                return namespace.DefaultStore
        except Exception as e_def_store:
            print(f"OutlookAdapter (local_win32): Erro ao acessar DefaultStore: {e_def_store}. Tentando primeiro store.")

        if namespace.Folders.Count > 0:
            try:
                # print("OutlookAdapter (local_win32): Usando o primeiro store da coleção Folders.")
                return namespace.Folders[0] # PyWin32 COM collections são 1-based, mas Folders[0] funciona como o primeiro item.
                                            # Para ser mais explícito: namespace.Folders.Item(1)
            except Exception as e_first_store:
                print(f"OutlookAdapter (local_win32): Erro ao acessar o primeiro store: {e_first_store}")

        print("OutlookAdapter (local_win32): Nenhum store do Outlook pôde ser determinado.")
        return None


    def list_available_accounts(self, session: Any) -> List[Dict[str, str]]:
        """
        Lista as contas MAPI (stores) disponíveis no perfil do Outlook para local_win32.
        Retorna uma lista de dicionários com 'id' (StoreID) e 'name' de cada conta.
        """
        if not session or session.get("auth_type") != "local_win32":
            return []
        return session.get("available_stores", [])

    def select_outlook_account(self, session: Any, account_store_id: str) -> bool:
        """
        Seleciona a conta (store) do Outlook a ser usada para operações subsequentes no modo local_win32.
        :param session: O dicionário de sessão.
        :param account_store_id: O StoreID da conta a ser selecionada (obtido de list_available_accounts).
        :return: True se a seleção foi bem-sucedida, False caso contrário.
        """
        if not session or session.get("auth_type") != "local_win32":
            print("OutlookAdapter: select_outlook_account só é aplicável para sessões local_win32.")
            return False

        available_stores = session.get("available_stores", [])
        found_store = False
        for store_info in available_stores:
            if store_info["id"] == account_store_id:
                found_store = True
                break

        if found_store:
            session["selected_store_id"] = account_store_id
            selected_store_name = next((s['name'] for s in available_stores if s['id'] == account_store_id), "ID Desconhecido")
            print(f"OutlookAdapter (local_win32): Conta do Outlook selecionada: {selected_store_name} (ID: {account_store_id})")
            return True
        else:
            print(f"OutlookAdapter (local_win32): Falha ao selecionar conta. Store ID '{account_store_id}' não encontrado na lista de contas disponíveis.")
            return False

    def logout(self, session: Any) -> None:
        """
        Realiza logout ou limpa a sessão.
        Para Graph API, pode limpar o token. Para win32com, não há um logout explícito.
        """
        if not session: return
        auth_type = session.get("auth_type")
        print(f"OutlookAdapter: Logout para {auth_type}")
        if auth_type == "graph_api":
            self.graph_token = None
            # Limpar cache do MSAL para a conta se necessário (mais complexo, depende do tipo de conta no MSAL)
            # if self.msal_app and session.get("user_principal_name"):
            #     accounts = self.msal_app.get_accounts(username=session.get("user_principal_name"))
            #     for acc in accounts:
            #         self.msal_app.remove_account(acc)
            print("OutlookAdapter (Graph): Token local limpo.")
        elif auth_type == "local_win32":
            # Não há um método de logout explícito para win32com. A conexão é liberada quando o objeto é destruído.
            # session["outlook_app"] = None # Pode ajudar o garbage collector
            print("OutlookAdapter (local_win32): Sessão local finalizada (sem ação explícita de logout).")

    def send_email(self, session: Any, message: EmailMessage) -> bool:
        """Envia um e-mail."""
        if not session: return False
        auth_type = session.get("auth_type")
        user_email = session.get("user_principal_name") or session.get("user_email") # Graph ou Local

        print(f"OutlookAdapter: Enviando e-mail de {message.sender} para {message.recipient} via {auth_type}")

        if auth_type == "graph_api":
            token = session.get("token")
            if not token: return False

            endpoint = f"https://graph.microsoft.com/v1.0/users/{user_email}/sendMail"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            email_data = {
                "message": {
                    "subject": message.subject,
                    "body": {
                        "contentType": "HTML", # ou "Text"
                        "content": message.body
                    },
                    "toRecipients": [
                        {"emailAddress": {"address": recip}} for recip in message.recipient.split(';') if recip.strip()
                    ],
                    # TODO: Adicionar CC, CCO, Anexos
                },
                "saveToSentItems": "true"
            }
            try:
                response = requests.post(endpoint, headers=headers, json=email_data)
                response.raise_for_status() # Levanta exceção para status HTTP 4xx/5xx
                print(f"OutlookAdapter (Graph): E-mail enviado com sucesso. Status: {response.status_code}")
                return True
            except requests.exceptions.RequestException as e:
                print(f"OutlookAdapter (Graph): Erro ao enviar e-mail: {e}")
                if e.response is not None:
                    print(f"OutlookAdapter (Graph): Detalhes do erro: {e.response.text}")
                return False

        elif auth_type == "local_win32":
            outlook = session.get("outlook_app")
            if not outlook: return False
            try:
                mail_item = outlook.CreateItem(0) # 0: olMailItem
                mail_item.Subject = message.subject
                mail_item.HTMLBody = message.body # ou .Body para texto plano
                mail_item.To = message.recipient
                # TODO: Adicionar CC, CCO, Anexos
                # if message.attachments:
                #     for attachment_path in message.attachments:
                #         mail_item.Attachments.Add(attachment_path)
                mail_item.Send()
                print(f"OutlookAdapter (local_win32): E-mail enviado para {message.recipient}")
                return True
            except Exception as e:
                print(f"OutlookAdapter (local_win32): Erro ao enviar e-mail: {e}")
                return False
        return False

    def list_emails(self, session: Any, folder: str = "Inbox", limit: int = 20, search_criteria: Optional[dict] = None) -> List[EmailMessage]:
        print(f"OutlookAdapter: Listando e-mails da pasta '{folder}' (limite: {limit})")
        # Implementação de placeholder
        # A implementação real exigiria chamadas à API do Graph ou iteração sobre itens do Outlook com win32com
        if WIN32COM_AVAILABLE and session and session.get("auth_type") == "local_win32":
            # outlook_app = session.get("outlook_app") # Já está na sessão
            # namespace = outlook_app.GetNamespace("MAPI") # Obtido dentro de _get_selected_store_folder

            target_store_folder = self._get_selected_store_folder(session)
            if not target_store_folder:
                print("OutlookAdapter (local_win32): Não foi possível determinar o store para listar e-mails.")
                return []

            # Mapeamento de nome de pasta para índice (simplificado)
            folder_map = {
                "inbox": 6, # olFolderInbox
                "sent items": 5, # olFolderSentMail
                "drafts": 16, # olFolderDrafts
                "deleted items": 3 # olFolderDeletedItems
            }
            folder_id = folder_map.get(folder.lower(), 6) # Padrão para Inbox (olFolderInbox)

            actual_folder_to_list = None
            try:
                if folder.lower() == "inbox" or folder_id == 6 : # Explicitamente Inbox
                    actual_folder_to_list = target_store_folder.GetDefaultFolder(6) # olFolderInbox
                elif folder_id: # Outra pasta padrão conhecida
                     actual_folder_to_list = target_store_folder.GetDefaultFolder(folder_id)
                else: # Tentar pelo nome da pasta (pode ser uma pasta customizada)
                    actual_folder_to_list = target_store_folder.Folders[folder]

                print(f"OutlookAdapter (local_win32): Listando e-mails da pasta '{actual_folder_to_list.Name}' no store '{target_store_folder.Name}'.")

            except Exception as e_folder:
                print(f"OutlookAdapter (local_win32): Pasta '{folder}' (ID: {folder_id}) não encontrada no store '{target_store_folder.Name}'. Erro: {e_folder}. Usando Inbox como fallback.")
                try:
                    actual_folder_to_list = target_store_folder.GetDefaultFolder(6) # Fallback para Inbox do store selecionado
                except Exception as e_inbox_fallback:
                    print(f"OutlookAdapter (local_win32): Falha ao acessar Inbox do store '{target_store_folder.Name}'. Erro: {e_inbox_fallback}")
                    return []


            messages = []
            # Ordenar por data de recebimento (mais recentes primeiro)
            email_items = actual_folder_to_list.Items
            email_items.Sort("[ReceivedTime]", True)

            for i, item in enumerate(email_items):
                if i >= limit: break
                if item.Class == 43: # 43 representa olMail
                    try:
                        # Convertendo o formato de data/hora do Outlook
                        received_time_str = item.ReceivedTime.strftime('%Y-%m-%d %H:%M:%S')
                        dt_object = datetime.datetime.strptime(received_time_str, '%Y-%m-%d %H:%M:%S')

                        # Criar EmailMessage sem anexos inicialmente; eles serão baixados sob demanda.
                        # A lista de anexos no EmailMessage pode conter metadados, mas não o conteúdo em si,
                        # a menos que o adapter decida pré-carregar (o que não faremos aqui para list_emails).
                        email_obj = EmailMessage(
                            message_id=item.EntryID,
                            sender=item.SenderName or item.SenderEmailAddress,
                            recipient=item.To,
                            subject=item.Subject,
                            body=item.HTMLBody or item.Body, # Priorizar HTMLBody se disponível
                            timestamp=dt_object,
                            is_read=not item.UnRead, # UnRead é True se não lido
                            folder=folder,
                            attachments=[] # Inicialmente vazio; popular com metadados se a API permitir sem download completo
                        )
                        # Se a API do Outlook (win32com) permitir obter informações básicas dos anexos
                        # sem baixá-los completamente, poderíamos popular email_obj.attachments aqui
                        # com objetos AttachmentData contendo filename, content_type, etc., mas sem content_bytes.
                        # Ex:
                        # if item.Attachments.Count > 0:
                        #     for att_idx in range(1, item.Attachments.Count + 1):
                        #         outlook_att = item.Attachments.Item(att_idx)
                        #         email_obj.attachments.append(AttachmentData(
                        #             filename=outlook_att.FileName,
                        #             # attachment_id_on_server=outlook_att.Index # ou algum outro ID se disponível
                        #             # content_type=? # Mime type pode não estar facilmente disponível aqui
                        #         ))
                        messages.append(email_obj)
                    except Exception as e:
                        print(f"OutlookAdapter (local_win32): Erro ao processar e-mail: {e}, Subject: {getattr(item, 'Subject', 'N/A')}")
            print(f"OutlookAdapter (local_win32): {len(messages)} e-mails recuperados de '{folder}'.")
            return messages
        elif session and session.get("auth_type") == "graph_api":
            # Implementação com Graph API (placeholder)
            print("OutlookAdapter (Graph): list_emails não totalmente implementado.")
            # Exemplo de endpoint: /users/{id|userPrincipalName}/mailFolders/{id|wellKnownName}/messages
            # wellKnownName pode ser 'inbox', 'sentitems', etc.
            # Adicionar $top=limit, $filter para search_criteria, $select para campos específicos
            return []

        return [
            # EmailMessage(sender="dummy@example.com", recipient="me@example.com", subject="Dummy Email 1", body="Hello!", folder=folder, message_id="dummy1"),
            # EmailMessage(sender="another@example.com", recipient="me@example.com", subject="Dummy Email 2", body="Hi there!", folder=folder, message_id="dummy2", is_read=True),
        ]

    def get_email(self, session: Any, message_id: str, folder: str = "Inbox") -> Optional[EmailMessage]:
        print(f"OutlookAdapter: Buscando e-mail ID '{message_id}' na pasta '{folder}'")
        # Placeholder
        # Graph API: /users/{id|userPrincipalName}/messages/{messageId}
        # Win32com: Namespace.GetItemFromID(message_id)
        return None

    def mark_as_read(self, session: Any, message_id: str, folder: str = "Inbox") -> bool:
        print(f"OutlookAdapter: Marcando e-mail ID '{message_id}' como lido na pasta '{folder}'")
        # Placeholder
        # Graph API: PATCH /users/{id|userPrincipalName}/messages/{messageId} com {"isRead": true}
        # Win32com: mailItem.UnRead = False; mailItem.Save()
        return False

    def move_email(self, session: Any, message_id: str, source_folder: str, destination_folder: str) -> bool:
        print(f"OutlookAdapter: Movendo e-mail ID '{message_id}' de '{source_folder}' para '{destination_folder}'")
        # Placeholder
        # Graph API: /users/{id|userPrincipalName}/messages/{messageId}/move com {"destinationId": "folder_id_or_wellKnownName"}
        # Win32com: mailItem.Move(destinationFolderObject)
        return False

    def delete_email(self, session: Any, message_id: str, folder: str = "Inbox") -> bool:
        print(f"OutlookAdapter: Deletando e-mail ID '{message_id}' da pasta '{folder}'")
        # Placeholder
        # Graph API: DELETE /users/{id|userPrincipalName}/messages/{messageId}
        # Win32com: mailItem.Delete()
        return False

    def create_folder(self, session: Any, folder_name: str) -> bool:
        print(f"OutlookAdapter: Criando pasta '{folder_name}'")
        # Placeholder
        # Graph API: POST /users/{id|userPrincipalName}/mailFolders com {"displayName": folder_name}
        # Win32com: parentFolder.Folders.Add(folder_name)
        return False

    def download_attachments(self, session: Any, message_id: str, mail_folder: Optional[str] = None) -> List[AttachmentData]:
        """
        Baixa todos os anexos de um e-mail específico.
        `mail_folder` é ignorado no win32com, pois o message_id (EntryID) é global.
        Pode ser relevante para Graph API se o ID da mensagem não for global.
        """
        if not session:
            print("OutlookAdapter: Sessão inválida para download_attachments.")
            return []

        auth_type = session.get("auth_type")
        user_identifier = session.get("user_principal_name") or session.get("user_email")
        downloaded_attachments_data: List[AttachmentData] = []

        if auth_type == "local_win32":
            if not WIN32COM_AVAILABLE: return []
            outlook_app = session.get("outlook_app") # Necessário para GetNamespace
            if not outlook_app:
                print("OutlookAdapter (local_win32): Instância do Outlook não disponível na sessão.")
                return []

            # O EntryID é geralmente global, então GetItemFromID pode ser chamado no namespace raiz.
            # No entanto, o mail_item retornado já estará associado ao seu store correto.
            # Se houver problemas, pode ser necessário obter o item a partir do store_folder específico.
            # Ex: mail_item = target_store_folder.GetItemFromID(message_id) - mas StoreFolder não tem GetItemFromID.
            # Portanto, namespace.GetItemFromID é a abordagem correta.
            namespace = outlook_app.GetNamespace("MAPI")
            try:
                mail_item = namespace.GetItemFromID(message_id)

                if not mail_item or mail_item.Class != 43: # 43 = olMailItem
                    print(f"OutlookAdapter (local_win32): Item com ID {message_id} não é um e-mail válido ou acessível.")
                    return []

                if mail_item.Attachments.Count > 0:
                    temp_dir = tempfile.mkdtemp(prefix="outlook_att_")
                    print(f"OutlookAdapter (local_win32): Baixando anexos para {message_id} em {temp_dir}")

                    for i in range(1, mail_item.Attachments.Count + 1):
                        attachment = mail_item.Attachments.Item(i)
                        original_filename = attachment.FileName
                        # Sanitize filename before saving (embora win32com possa lidar com isso)
                        # normalized_filename = normalize_filename(original_filename) # utils.normalize_filename

                        temp_file_path = os.path.join(temp_dir, original_filename)

                        try:
                            attachment.SaveAsFile(temp_file_path)
                            with open(temp_file_path, "rb") as f:
                                content_bytes = f.read()

                            att_data = AttachmentData(
                                filename=original_filename,
                                content_bytes=content_bytes,
                                filepath=temp_file_path, # Guardar para possível limpeza externa se necessário
                                # content_type pode ser difícil de obter de forma confiável com win32com
                            )
                            downloaded_attachments_data.append(att_data)
                            print(f"OutlookAdapter (local_win32): Anexo '{original_filename}' baixado e lido ({len(content_bytes)} bytes).")

                            # O UseCase é responsável por remover o temp_file_path se ele foi usado.
                            # Ou podemos remover aqui se o content_bytes é o primário.
                            # Se o UseCase usa o filepath, não remover aqui.
                            # Por segurança, se content_bytes está populado, o filepath não é mais estritamente necessário
                            # para o adapter, mas o UseCase pode querer usá-lo.
                            # Para simplificar, o UseCase vai lidar com a limpeza se ele usar o filepath.
                            # Se o UseCase só usar content_bytes, poderíamos remover aqui.
                            # Vamos seguir o padrão que o UseCase limpa se o filepath for fornecido e usado.

                        except Exception as e_save:
                            print(f"OutlookAdapter (local_win32): Erro ao salvar ou ler anexo '{original_filename}': {e_save}")
                            # Se falhar, garantir que o arquivo temporário não fique órfão se foi criado
                            if os.path.exists(temp_file_path):
                                try:
                                    os.remove(temp_file_path)
                                except OSError:
                                    pass # Ignorar erro na remoção aqui
                    # Não remover temp_dir aqui, pois os filepaths dentro de AttachmentData podem ser usados pelo chamador.
                    # O chamador (UseCase) deve ser responsável por limpar os arquivos temporários se ele os usar.
                    # Se o UseCase só usa content_bytes, então os filepaths não são mais necessários após este ponto.
                    # No MonitorNewEmailsAndNotifyUseCase, ele espera 'filepath' ou 'content'.
                    # Se 'filepath' é usado, ele o remove.

                else:
                    print(f"OutlookAdapter (local_win32): E-mail {message_id} não possui anexos.")

            except Exception as e:
                print(f"OutlookAdapter (local_win32): Erro ao acessar e-mail ou anexos para ID {message_id}: {e}")

            # Opcional: remover o diretório temporário se todos os arquivos foram lidos em bytes
            # e os filepaths não são mais necessários. Mas é mais seguro deixar o UseCase gerenciar.
            # if temp_dir and os.path.exists(temp_dir):
            #     import shutil
            #     shutil.rmtree(temp_dir, ignore_errors=True)


        elif auth_type == "graph_api":
            token = session.get("token")
            if not token or not user_identifier:
                print("OutlookAdapter (Graph): Token ou User Principal Name ausente para download_attachments.")
                return []

            endpoint = f"https://graph.microsoft.com/v1.0/users/{user_identifier}/messages/{message_id}/attachments"
            headers = {"Authorization": f"Bearer {token}"}

            try:
                response = requests.get(endpoint, headers=headers)
                response.raise_for_status()
                attachments_metadata = response.json().get("value", [])

                for att_meta in attachments_metadata:
                    att_id = att_meta.get("id")
                    att_name = att_meta.get("name")
                    att_content_type = att_meta.get("contentType")
                    # att_is_inline = att_meta.get("isInline", False) # Se precisar tratar diferente

                    # Para obter o conteúdo do anexo
                    content_endpoint = f"{endpoint}/{att_id}/$value" # Pega o conteúdo raw
                    content_response = requests.get(content_endpoint, headers=headers)
                    content_response.raise_for_status()

                    # O conteúdo da Graph API para $value já vem em bytes.
                    # Se não fosse $value, e fosse um JSON com `contentBytes`, seria base64.
                    content_bytes = content_response.content

                    att_data = AttachmentData(
                        filename=att_name,
                        content_bytes=content_bytes,
                        content_type=att_content_type
                        # attachment_id_on_server=att_id # Se precisar
                    )
                    downloaded_attachments_data.append(att_data)
                    print(f"OutlookAdapter (Graph): Anexo '{att_name}' baixado ({len(content_bytes)} bytes).")

            except requests.exceptions.RequestException as e_graph:
                print(f"OutlookAdapter (Graph): Erro ao baixar anexos para {message_id}: {e_graph}")
                if hasattr(e_graph, 'response') and e_graph.response is not None:
                    print(f"OutlookAdapter (Graph): Detalhes: {e_graph.response.text}")
            except Exception as e_gen:
                 print(f"OutlookAdapter (Graph): Erro geral ao processar anexos para {message_id}: {e_gen}")


        return downloaded_attachments_data

    # --- Métodos de Calendário ---
    def create_event(self, session: Any, event: CalendarEvent) -> Optional[CalendarEvent]:
        print(f"OutlookAdapter: Criando evento '{event.subject}'")
        # Placeholder
        # Graph API: POST /users/{id|userPrincipalName}/events
        # Win32com: outlook.CreateItem(1) # 1: olAppointmentItem
        return None

    def list_events(self, session: Any, start_date: Any, end_date: Any) -> List[CalendarEvent]:
        print(f"OutlookAdapter: Listando eventos de '{start_date}' a '{end_date}'")
        # Placeholder
        # Graph API: /users/{id|userPrincipalName}/calendarview?startDateTime={start}&endDateTime={end}
        # Win32com: Iterate appointments in calendar folder, filter by date
        return []

    # --- Métodos de Tarefas ---
    def create_task(self, session: Any, task: Task) -> Optional[Task]:
        print(f"OutlookAdapter: Criando tarefa '{task.subject}'")
        # Placeholder
        # Graph API: POST /users/{id|userPrincipalName}/todo/lists/{listId}/tasks
        # Win32com: outlook.CreateItem(3) # 3: olTaskItem
        return None

    def list_tasks(self, session: Any, only_pending: bool = True) -> List[Task]:
        print(f"OutlookAdapter: Listando tarefas (pendentes: {only_pending})")
        # Placeholder
        # Graph API: /users/{id|userPrincipalName}/todo/lists/{listId}/tasks
        # Win32com: Iterate tasks in tasks folder
        return []

    # --- Métodos de Contatos ---
    def list_contacts(self, session: Any, search_query: Optional[str] = None) -> List[Contact]:
        print(f"OutlookAdapter: Listando contatos (query: '{search_query}')")
        # Placeholder
        # Graph API: /users/{id|userPrincipalName}/contacts
        # Win32com: Iterate contacts in contacts folder
        return []


if __name__ == '__main__':
    print("--- Testando OutlookAdapter ---")
    # Para testar, você precisaria de um ambiente com Outlook configurado (para local_win32)
    # ou credenciais válidas da API do Graph e um arquivo .env com elas.

    # Exemplo de como carregar config (requer DotEnvConfigRepository e um .env)
    try:
        from src.infrastructure.config import DotEnvConfigRepository
        config_repo = DotEnvConfigRepository() # Tenta carregar .env
        app_config = config_repo.load_config()

        # Configuração para o adaptador do Outlook (exemplo)
        outlook_cfg = {
            "auth_type": app_config.get("OUTLOOK_AUTH_TYPE", "local_win32"), # 'graph_api' or 'local_win32'
            "OUTLOOK_CLIENT_ID": app_config.get("OUTLOOK_CLIENT_ID"),
            "OUTLOOK_CLIENT_SECRET": app_config.get("OUTLOOK_CLIENT_SECRET"),
            "OUTLOOK_TENANT_ID": app_config.get("OUTLOOK_TENANT_ID"),
            "graph_scopes": ["https://graph.microsoft.com/.default"],
        }
        print(f"Configuração do adaptador Outlook: {outlook_cfg['auth_type']}")

    except ImportError:
        print("DotEnvConfigRepository não encontrado, usando config dummy.")
        app_config = {}
        outlook_cfg = {"auth_type": "local_win32" if WIN32COM_AVAILABLE else "graph_api"}


    # Criar conta dummy para teste
    dummy_account = EmailAccount(
        email_address=app_config.get("DEFAULT_EMAIL_ACCOUNT", "seu_email_outlook@example.com"), # Use um e-mail real para testar
        password="dummy_password", # Não usado por win32com se já logado, Graph API requer outro fluxo para senha
        account_type="outlook"
    )

    adapter = OutlookAdapter(config=outlook_cfg)

    print(f"\n--- Testando Login ({outlook_cfg['auth_type']}) ---")
    session_info = adapter.login(dummy_account)

    if session_info:
        print(f"Login bem-sucedido. Sessão: {session_info.get('auth_type')}")

        print("\n--- Testando List Emails (Inbox) ---")
        emails = adapter.list_emails(session_info, folder="Inbox", limit=5)
        if emails:
            for email in emails:
                print(f"  De: {email.sender}, Assunto: {email.subject}, Lida: {email.is_read}, Data: {email.timestamp}")
        else:
            print("  Nenhum e-mail encontrado ou falha ao listar.")

        # print("\n--- Testando List Emails (Sent Items) ---")
        # sent_emails = adapter.list_emails(session_info, folder="Sent Items", limit=2)
        # if sent_emails:
        #     for email in sent_emails:
        #         print(f"  De: {email.sender}, Assunto: {email.subject}, Lida: {email.is_read}, Data: {email.timestamp}")
        # else:
        #     print("  Nenhum e-mail enviado encontrado ou falha ao listar.")


        # Teste de envio de e-mail (CUIDADO: ISSO ENVIARÁ UM E-MAIL REAL)
        # print("\n--- Testando Send Email ---")
        # test_send = input("Deseja enviar um e-mail de teste? (s/N): ").lower()
        # if test_send == 's':
        #     recipient_email = input("Digite o e-mail do destinatário: ")
        #     if recipient_email:
        #         email_to_send = EmailMessage(
        #             sender=dummy_account.email_address,
        #             recipient=recipient_email,
        #             subject="Teste Automatizado - OutlookAdapter",
        #             body="Este é um e-mail de teste enviado pelo OutlookAdapter."
        #         )
        #         success = adapter.send_email(session_info, email_to_send)
        #         print(f"Resultado do envio: {'Sucesso' if success else 'Falha'}")
        #     else:
        #         print("Destinatário não fornecido. Teste de envio pulado.")
        # else:
        #     print("Teste de envio de e-mail pulado.")

        adapter.logout(session_info)
        print("\nLogout concluído.")
    else:
        print(f"Falha no login para {dummy_account.email_address} usando {outlook_cfg['auth_type']}.")
        if outlook_cfg['auth_type'] == 'local_win32' and not WIN32COM_AVAILABLE:
            print("  Verifique se a biblioteca 'pywin32' está instalada.")
        elif outlook_cfg['auth_type'] == 'graph_api' and not MSAL_AVAILABLE:
            print("  Verifique se as bibliotecas 'msal' e 'requests' estão instaladas.")
        elif outlook_cfg['auth_type'] == 'graph_api':
            print("  Verifique as configurações da API do Graph (Client ID, Secret, Tenant ID) no seu arquivo .env.")
        elif outlook_cfg['auth_type'] == 'local_win32':
             print("  Verifique se o Microsoft Outlook está em execução e configurado.")


    print("\n--- Fim dos testes do OutlookAdapter ---")
