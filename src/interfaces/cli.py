import argparse
import getpass # Para senhas de forma mais segura
from typing import Optional
import time # Importar o módulo time
from src.application.use_cases import (
    SendEmailUseCase,
    CheckNewEmailsUseCase,
    AddEmailAccountUseCase,
    NotifyAboutNewEmailsUseCase,
    MonitorNewEmailsAndNotifyUseCase # Importar o novo UseCase
)
from src.application.services import EmailAppService, NotificationAppService
# SQLiteRepository já está importado
# ConfigRepository já está importado
# Adapters já estão importados
from src.infrastructure.sqlite_repository import SQLiteRepository
from src.infrastructure.config import DotEnvConfigRepository, create_example_env_file
from src.infrastructure.telegram_adapter import TelegramAdapter # Para o NotificationService
# Importar adaptadores de e-mail que podem ser necessários
from src.infrastructure.outlook_adapter import OutlookAdapter
# Adicionar aqui importações de outros adaptadores (ex: GmailAdapter) quando existirem

def setup_dependencies():
    """
    Configura e injeta as dependências da aplicação.
    Retorna uma tupla com os serviços de aplicação configurados.
    """
    # 0. Criar .env de exemplo se não existir (para facilitar setup inicial)
    create_example_env_file() # Cria .env com placeholders se não existir

    # 1. Repositório de Configuração
    config_repo = DotEnvConfigRepository()
    app_config = config_repo.load_config()

    # 2. Repositório de Banco de Dados
    db_name = app_config.get("DATABASE_NAME", "automail.db")
    db_repo = SQLiteRepository(db_name=db_name)

    # 3. Serviços de Notificação (ex: Telegram)
    telegram_bot_token = app_config.get("TELEGRAM_BOT_TOKEN")
    telegram_default_chat_id = app_config.get("TELEGRAM_DEFAULT_CHAT_ID")

    notification_adapter = None
    if telegram_bot_token:
        telegram_config = {
            "TELEGRAM_BOT_TOKEN": telegram_bot_token,
            "TELEGRAM_DEFAULT_CHAT_ID": telegram_default_chat_id
        }
        notification_adapter = TelegramAdapter(config=telegram_config)
        print("CLI: Serviço de notificação Telegram configurado.")
    else:
        print("CLI: Token do Telegram não encontrado. Notificações via Telegram desabilitadas.")

    # 4. Instanciar o EmailAppService (principal serviço de aplicação)
    # O EmailAppService carregará dinamicamente os adaptadores de e-mail (Outlook, Gmail, etc.)
    # com base na configuração e no tipo de conta.
    # É importante que as classes dos adaptadores (ex: OutlookAdapter) estejam importadas neste escopo
    # para que o importlib.import_module funcione corretamente no EmailAppService.
    email_app_service = EmailAppService(
        db_repository=db_repo,
        config_repository=config_repo,
        notification_service=notification_adapter # Passa o adapter, não o service
    )

    # 5. (Opcional) Instanciar outros serviços de aplicação, como NotificationAppService
    notification_app_service = None
    if notification_adapter:
        notification_app_service = NotificationAppService(
            notification_service=notification_adapter,
            config_repository=config_repo
        )

    # Retornar também o db_repo para o MonitorNewEmailsAndNotifyUseCase
    return email_app_service, notification_app_service, app_config, db_repo


def main_cli():
    """Ponto de entrada principal para a interface de linha de comando."""

    # Modificar para receber db_repo também
    email_app_service, notification_app_service, app_config, db_repo = setup_dependencies()

    parser = argparse.ArgumentParser(description="AutoMail CLI - Automação de E-mails e Notificações.")
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # --- Comando: add-account ---
    parser_add_account = subparsers.add_parser("add-account", help="Adiciona uma nova conta de e-mail.")
    parser_add_account.add_argument("email", type=str, help="Endereço de e-mail da conta.")
    parser_add_account.add_argument("--type", type=str, help="Tipo da conta (ex: outlook, gmail).", default="outlook")
    # A senha será solicitada interativamente

    # --- Comando: send-email ---
    parser_send_email = subparsers.add_parser("send-email", help="Envia um e-mail.")
    parser_send_email.add_argument("--from", dest="from_email", type=str, help="E-mail da conta remetente.", required=False)
    parser_send_email.add_argument("--to", type=str, help="E-mail do destinatário.", required=True)
    parser_send_email.add_argument("--subject", type=str, help="Assunto do e-mail.", required=True)
    parser_send_email.add_argument("--body", type=str, help="Corpo do e-mail.", required=True)
    # TODO: Adicionar argumento para anexos

    # --- Comando: check-emails ---
    parser_check_emails = subparsers.add_parser("check-emails", help="Verifica novos e-mails para uma conta.")
    parser_check_emails.add_argument("--account", type=str, help="E-mail da conta a ser verificada.", required=False)
    parser_check_emails.add_argument("--folder", type=str, default="Inbox", help="Pasta a ser verificada.")
    parser_check_emails.add_argument("--limit", type=int, default=5, help="Número máximo de e-mails a listar.")

    # --- Comando: notify-new-emails ---
    parser_notify_emails = subparsers.add_parser("notify-new-emails", help="Verifica e notifica sobre novos e-mails.")
    parser_notify_emails.add_argument("--account", type=str, help="E-mail da conta a ser verificada.", required=False)
    parser_notify_emails.add_argument("--folder", type=str, default="Inbox", help="Pasta a ser verificada.")
    parser_notify_emails.add_argument("--recipient", type=str, help="ID do destinatário da notificação (opcional).")

    # --- Comando: monitor-emails (novo) ---
    parser_monitor_emails = subparsers.add_parser("monitor-emails", help="Monitora uma conta de e-mail por novos e-mails e envia notificações detalhadas.")
    parser_monitor_emails.add_argument("--account", type=str, help="E-mail da conta a ser monitorada.", required=False)
    parser_monitor_emails.add_argument("--folder", type=str, default="Inbox", help="Pasta a ser monitorada (padrão: Inbox).")
    parser_monitor_emails.add_argument("--delay", type=int, default=2, help="Delay em segundos entre o processamento de e-mails (padrão: 2).")
    parser_monitor_emails.add_argument("--loop-interval", type=int, default=None, help="Habilita o monitoramento contínuo, verificando e-mails no intervalo especificado em segundos. Ex: 300 para 5 minutos. Se não fornecido, executa apenas uma vez.")

    # --- Comando: list-accounts ---
    parser_list_accounts = subparsers.add_parser("list-accounts", help="Lista todas as contas de e-mail configuradas.")

    # --- Comando: send-notification (para teste direto do serviço de notificação) ---
    if notification_app_service: # Só adiciona o comando se o serviço estiver disponível
        parser_send_notification = subparsers.add_parser("send-notification", help="Envia uma notificação direta (ex: Telegram).")
        parser_send_notification.add_argument("message", type=str, help="Mensagem a ser enviada.")
        parser_send_notification.add_argument("--recipient", type=str, help="ID do destinatário (opcional, usa padrão se não fornecido).")

    args = parser.parse_args()

    # Determinar e-mail padrão se não fornecido nos argumentos
    default_email_account = app_config.get("DEFAULT_EMAIL_ACCOUNT")

    if args.command == "add-account":
        password = getpass.getpass(f"Digite a senha para {args.email}: ")
        use_case = AddEmailAccountUseCase(email_app_service)
        if use_case.execute(args.email, password, args.type):
            print(f"Conta {args.email} ({args.type}) adicionada com sucesso!")
            if not default_email_account:
                 print(f"Considere definir {args.email} como DEFAULT_EMAIL_ACCOUNT no seu arquivo .env")
        else:
            print(f"Falha ao adicionar conta {args.email}.")

    elif args.command == "send-email":
        from_account_email = args.from_email if args.from_email else default_email_account
        if not from_account_email:
            print("E-mail do remetente não especificado. Use --from ou defina DEFAULT_EMAIL_ACCOUNT no .env")
            return

        use_case = SendEmailUseCase(email_app_service)
        if use_case.execute(from_account_email, args.to, args.subject, args.body):
            print(f"E-mail enviado de {from_account_email} para {args.to} com sucesso!")
        else:
            print(f"Falha ao enviar e-mail de {from_account_email}.")

    elif args.command == "check-emails":
        account_to_check = args.account if args.account else default_email_account
        if not account_to_check:
            print("Conta para verificar não especificada. Use --account ou defina DEFAULT_EMAIL_ACCOUNT no .env")
            return

        use_case = CheckNewEmailsUseCase(email_app_service)
        emails = use_case.execute(account_to_check, args.folder, args.limit)
        if emails:
            print(f"\n--- E-mails encontrados para {account_to_check} na pasta {args.folder} ---")
            for email in emails:
                print(f"  De: {email.sender}")
                print(f"  Assunto: {email.subject}")
                print(f"  Data: {email.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"  Lido: {'Sim' if email.is_read else 'Não'}")
                print(f"  ID: {email.message_id}")
                print( "  Corpo (preview): " + email.body[:100].replace('\n', ' ').replace('\r', '') + "...")
                print("-" * 20)
        else:
            print(f"Nenhum e-mail novo encontrado para {account_to_check} na pasta {args.folder} ou falha ao buscar.")

    elif args.command == "notify-new-emails":
        account_to_notify = args.account if args.account else default_email_account
        if not account_to_notify:
            print("Conta para notificar não especificada. Use --account ou defina DEFAULT_EMAIL_ACCOUNT no .env")
            return

        if not email_app_service.notification_service:
            print("Serviço de notificação não está configurado no EmailAppService. Comando 'notify-new-emails' não pode ser executado.")
            return

        # Opcional: Se um recipient_id específico for fornecido via CLI para este comando
        notification_recipient_override = args.recipient

        use_case = NotifyAboutNewEmailsUseCase(email_app_service, notification_recipient=notification_recipient_override)
        num_notified = use_case.execute(account_to_notify, args.folder)
        if num_notified > 0:
            print(f"{num_notified} notificações sobre novos e-mails foram enviadas.")
        else:
            print("Nenhum e-mail novo encontrado para notificação ou falha no processo.")

    elif args.command == "list-accounts":
        accounts = email_app_service.list_all_accounts()
        if accounts:
            print("\n--- Contas de E-mail Configuradas ---")
            for acc in accounts:
                print(f"  E-mail: {acc.email_address}")
                print(f"  Tipo: {acc.account_type}")
                print(f"  Ativa: {'Sim' if acc.is_active else 'Não'}")
                # Não exibir senha
                print("-" * 20)
        else:
            print("Nenhuma conta de e-mail configurada.")

    elif args.command == "send-notification" and notification_app_service:
        success = notification_app_service.send_direct_notification(args.message, args.recipient)
        if success:
            print(f"Notificação enviada com sucesso para '{args.recipient or app_config.get('TELEGRAM_DEFAULT_CHAT_ID')}'!")
        else:
            print("Falha ao enviar notificação.")

    elif args.command == "monitor-emails":
        account_to_monitor = args.account if args.account else default_email_account
        if not account_to_monitor:
            print("Conta para monitorar não especificada. Use --account ou defina DEFAULT_EMAIL_ACCOUNT no .env")
            return

        if not email_app_service.notification_service:
            print("Serviço de notificação não está configurado. O monitoramento detalhado com notificações não funcionará.")
            # Poderia optar por sair ou continuar sem notificações se o UseCase permitir
            return


        outlook_session_for_use_case = None # Será a sessão potencialmente modificada pela seleção de store

        account_details = email_app_service.get_account_details(account_to_monitor)

        if account_details and account_details.account_type == 'outlook':
            # Obter a instância do adapter Outlook.
            # Usar _get_email_service é um acesso a método protegido, idealmente EmailAppService teria um método público.
            try:
                outlook_adapter = email_app_service._get_email_service(account_details.account_type)
                if isinstance(outlook_adapter, OutlookAdapter): # Confirmar que é o adapter correto
                    # Verificar se o adapter está no modo local_win32 internamente ou por config
                    # Para este exemplo, vamos assumir que o adapter.login() retorna None ou uma sessão
                    # que indica o auth_type se for relevante.

                    # 1. Login inicial para obter a lista de stores e a sessão
                    temp_session = outlook_adapter.login(account_details)

                    if temp_session and temp_session.get("auth_type") == "local_win32":
                        outlook_session_for_use_case = temp_session # Guardar esta sessão
                        available_stores = outlook_adapter.list_available_accounts(outlook_session_for_use_case)

                        if len(available_stores) > 1:
                            print("\nContas Outlook (Stores MAPI) disponíveis neste perfil:")
                            for i, store in enumerate(available_stores):
                                print(f"  {i+1}: {store['name']} (ID: {store['id']})")

                            current_selected_store_id = outlook_session_for_use_case.get("selected_store_id")
                            current_selected_name = "Nenhuma (usará padrão)"
                            if current_selected_store_id:
                                current_selected_name = next((s['name'] for s in available_stores if s['id'] == current_selected_store_id), current_selected_name)

                            print(f"Conta Outlook atualmente selecionada para esta sessão: {current_selected_name}")

                            try:
                                choice = input(f"Digite o número da conta para monitorar (ou Enter para usar a selecionada '{current_selected_name}'): ").strip()
                                if choice:
                                    selected_idx = int(choice) - 1
                                    if 0 <= selected_idx < len(available_stores):
                                        chosen_store_id = available_stores[selected_idx]['id']
                                        if outlook_adapter.select_outlook_account(outlook_session_for_use_case, chosen_store_id):
                                            print(f"Conta Outlook '{available_stores[selected_idx]['name']}' selecionada para este monitoramento.")
                                        else:
                                            print("Falha ao tentar selecionar a conta Outlook. Usando a padrão/anteriormente selecionada.")
                                    else:
                                        print("Seleção inválida. Usando a conta Outlook padrão/anteriormente selecionada.")
                                else:
                                    print(f"Nenhuma seleção feita. Usando a conta Outlook padrão/anteriormente selecionada: {current_selected_name}")
                            except ValueError:
                                print("Entrada inválida. Usando a conta Outlook padrão/anteriormente selecionada.")
                        elif available_stores:
                             print(f"Outlook: Usando a única conta/store MAPI disponível: {available_stores[0]['name']}")
                        # else: Nenhuma store, _get_selected_store_folder no adapter lidará com isso ou falhará.
                    # else: Não é local_win32 ou falha no login, então outlook_session_for_use_case permanece None
                else:
                    print("CLI: Não foi possível obter o OutlookAdapter ou não é uma instância de OutlookAdapter.")
            except Exception as e_adapter_get:
                print(f"CLI: Erro ao tentar obter ou usar o Outlook adapter: {e_adapter_get}")

        # Instanciar o MonitorNewEmailsAndNotifyUseCase
        monitor_use_case = MonitorNewEmailsAndNotifyUseCase(
            email_app_service=email_app_service,
            db_repository=db_repo,
            default_notification_recipient=app_config.get("DEFAULT_NOTIFICATION_RECIPIENT")
        )

        if args.loop_interval and args.loop_interval > 0:
            print(f"CLI: Iniciando monitoramento contínuo para {account_to_monitor} na pasta {args.folder} com intervalo de {args.loop_interval}s.")
            print("Pressione Ctrl+C para interromper.")
            try:
                while True:
                    print(f"CLI: Executando verificação ({time.strftime('%Y-%m-%d %H:%M:%S')})...")
                    processed_count = monitor_use_case.execute(
                        account_email_address=account_to_monitor,
                        folder_to_monitor=args.folder,
                        processing_delay_seconds=args.delay,
                        initial_outlook_session=outlook_session_for_use_case # Passar a sessão (pode ser None, será recriada se necessário)
                    )
                    print(f"CLI: Verificação concluída. {processed_count} e-mail(s) processado(s).")
                    # Resetar outlook_session_for_use_case para None para que a próxima iteração
                    # do loop possa (se necessário) re-selecionar a conta ou obter uma nova sessão fresca.
                    # Isso é importante se o COM object do outlook_app não for estável por longos períodos.
                    # No entanto, a lógica atual de login no adapter já pode recriar o outlook_app se necessário.
                    # Para maior robustez, forçar uma nova sessão (None) pode ser mais seguro para loops longos.
                    # outlook_session_for_use_case = None # Opcional: descomente para forçar nova sessão a cada loop.
                                                       # Se deixado, a sessão será reutilizada pelo adapter.login.

                    print(f"CLI: Aguardando {args.loop_interval} segundos para a próxima verificação...")
                    time.sleep(args.loop_interval)
            except KeyboardInterrupt:
                print("\nCLI: Monitoramento contínuo interrompido pelo usuário.")
            except Exception as e_loop:
                print(f"\nCLI: Erro durante o loop de monitoramento: {e_loop}")
            finally:
                print("CLI: Finalizando serviço de monitoramento.")
        else:
            print(f"CLI: Iniciando monitoramento único para a conta {account_to_monitor} na pasta {args.folder}...")
            processed_count = monitor_use_case.execute(
                account_email_address=account_to_monitor,
                folder_to_monitor=args.folder,
                processing_delay_seconds=args.delay,
                initial_outlook_session=outlook_session_for_use_case # Passar a sessão (pode ser None)
            )
            print(f"CLI: Monitoramento concluído. {processed_count} e-mail(s) processado(s).")

    elif args.command is None:
        parser.print_help()

if __name__ == "__main__":
    # Este __main__ é para quando o cli.py é executado diretamente.
    # O `main.py` na raiz do `src` será o ponto de entrada principal da aplicação,
    # que por sua vez poderá chamar `main_cli()`.
    print("AutoMail CLI - Iniciando...")
    main_cli()
