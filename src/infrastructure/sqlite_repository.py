import sqlite3
from typing import List, Optional, Any
from src.domain.models import EmailAccount
from src.domain.interfaces import DatabaseRepository, ProcessedEmailRepository # Importar ProcessedEmailRepository
import os
import datetime # Adicionado para timestamps

class SQLiteRepository(DatabaseRepository, ProcessedEmailRepository): # Herdar da nova interface
    """
    Implementação de DatabaseRepository usando SQLite.
    Gerencia tanto contas de e-mail quanto o estado de e-mails processados.
    """
    def __init__(self, db_name: str = "automail.db"):
        """
        Inicializa o repositório SQLite.
        :param db_name: Nome do arquivo do banco de dados SQLite.
        """
        self.db_name = db_name
        self._create_tables_if_not_exists()

    def _get_connection(self) -> sqlite3.Connection:
        """Retorna uma nova conexão com o banco de dados."""
        conn = sqlite3.connect(self.db_name)
        conn.row_factory = sqlite3.Row # Acessar colunas pelo nome
        return conn

    def _create_tables_if_not_exists(self):
        """Cria as tabelas necessárias no banco de dados se elas ainda não existirem."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Tabela para EmailAccount
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_accounts (
                email_address TEXT PRIMARY KEY,
                password TEXT NOT NULL, -- Em um cenário real, isso deveria ser criptografado
                account_type TEXT NOT NULL,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)

        # Tabela para rastrear e-mails processados (para evitar re-notificação)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_emails (
                entry_id TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL,
                account_email TEXT -- Opcional: para rastrear por conta, se necessário no futuro
            )
        """)
        # Criar índice para account_email em processed_emails para buscas mais rápidas se usado
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processed_emails_account_email
            ON processed_emails (account_email, processed_at DESC)
        """)


        # Tabela para logs de e-mail (exemplo, se necessário)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS email_logs (
        #         log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         account_email TEXT,
        #         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        #         action TEXT, -- Ex: "SENT", "RECEIVED_ERROR"
        #         details TEXT,
        #         FOREIGN KEY (account_email) REFERENCES email_accounts(email_address)
        #     )
        # """)

        conn.commit()
        conn.close()

    # --- Métodos para EmailAccount ---
    def add_account(self, account: EmailAccount) -> EmailAccount:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO email_accounts (email_address, password, account_type, is_active)
                VALUES (?, ?, ?, ?)
            """, (account.email_address, account.password, account.account_type, account.is_active))
            conn.commit()
            return account
        except sqlite3.IntegrityError:
            raise ValueError(f"Conta de e-mail já existe: {account.email_address}")
        finally:
            conn.close()

    def get_account(self, email_address: str) -> Optional[EmailAccount]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_accounts WHERE email_address = ?", (email_address,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return EmailAccount(
                email_address=row["email_address"],
                password=row["password"],
                account_type=row["account_type"],
                is_active=bool(row["is_active"])
            )
        return None

    def list_accounts(self, is_active: Optional[bool] = None) -> List[EmailAccount]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM email_accounts"
        params = []
        if is_active is not None:
            query += " WHERE is_active = ?"
            params.append(is_active)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        accounts = []
        for row in rows:
            accounts.append(EmailAccount(
                email_address=row["email_address"],
                password=row["password"],
                account_type=row["account_type"],
                is_active=bool(row["is_active"])
            ))
        return accounts

    def update_account(self, account: EmailAccount) -> EmailAccount:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE email_accounts
            SET password = ?, account_type = ?, is_active = ?
            WHERE email_address = ?
        """, (account.password, account.account_type, account.is_active, account.email_address))
        conn.commit()

        if cursor.rowcount == 0:
            conn.close()
            raise ValueError(f"Conta de e-mail não encontrada para atualização: {account.email_address}")

        conn.close()
        return account

    def delete_account(self, email_address: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM email_accounts WHERE email_address = ?", (email_address,))
        conn.commit()
        deleted_rows = cursor.rowcount
        conn.close()
        return deleted_rows > 0

    # --- Métodos para Processed Emails (Rastreamento de Notificações) ---
    # Implementação da interface ProcessedEmailRepository
    def add_processed_email(self, message_id: str, account_email: str, processed_at: datetime.datetime) -> None:
        """Adiciona um message_id de e-mail à tabela de e-mails processados para uma conta específica."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Usar message_id consistentemente com a interface
            cursor.execute("""
                INSERT OR IGNORE INTO processed_emails (entry_id, processed_at, account_email)
                VALUES (?, ?, ?)
            """, (message_id, processed_at.strftime("%Y-%m-%d %H:%M:%S.%f"), account_email))
            conn.commit()
        except sqlite3.IntegrityError:
            # Este bloco é teoricamente redundante devido ao OR IGNORE, mas mantido por segurança.
            print(f"SQLiteRepository: Message ID {message_id} já existe em processed_emails (IntegrityError).")
        finally:
            conn.close()

    def is_email_processed(self, message_id: str, account_email: str) -> bool:
        """
        Verifica se um message_id de e-mail já foi processado para uma conta específica.
        EntryID (message_id) é geralmente globalmente único para Exchange/Outlook,
        mas filtrar por account_email adiciona uma camada de isolamento se necessário.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        # Usar message_id consistentemente. A coluna no DB é entry_id.
        cursor.execute("SELECT 1 FROM processed_emails WHERE entry_id = ? AND account_email = ?", (message_id, account_email))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_last_processed_email_id(self, account_email: str) -> Optional[str]:
        """
        Recupera o message_id (EntryID) do último e-mail processado para uma conta específica.
        Renomeado de get_latest_processed_entry_id.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        # A coluna no DB é entry_id.
        cursor.execute("""
            SELECT entry_id FROM processed_emails
            WHERE account_email = ?
            ORDER BY processed_at DESC
            LIMIT 1
        """, (account_email,))
        row = cursor.fetchone()
        conn.close()
        return row["entry_id"] if row else None # row["entry_id"] é o message_id

    def set_initial_checkpoint(self, message_id: str, account_email: str, processed_at: datetime.datetime) -> None:
        """
        Define um marco inicial de processamento para uma conta específica,
        marcando um e-mail como já processado.
        'processed_at' é o timestamp do e-mail que está sendo marcado.
        """
        self.add_processed_email(message_id, account_email, processed_at)
        print(f"SQLiteRepository: Marco inicial definido. Message ID: {message_id} para conta: {account_email} em {processed_at}")


# Exemplo de uso (para teste rápido das novas funcionalidades)
if __name__ == '__main__':
    DB_TEST_FILE = "test_automail_processed.db"
    if os.path.exists(DB_TEST_FILE):
        os.remove(DB_TEST_FILE)

    repo = SQLiteRepository(db_name=DB_TEST_FILE)
    print(f"Banco de dados '{DB_TEST_FILE}' criado/conectado.")

    # --- Testando Funcionalidades de Processed Emails ---
    print("\n--- Testando Processed Emails ---")
    now = datetime.datetime.now()
    entry_id1 = "id_email_abc"
    entry_id2 = "id_email_def"
    entry_id3 = "id_email_xyz_conta2"

    # Adicionar e verificar
    # --- Testando Funcionalidades de Processed Emails (adaptado para novas assinaturas) ---
    print("\n--- Testando Processed Emails (com ProcessedEmailRepository) ---")
    now = datetime.datetime.now()
    acc_email_1 = "user1@example.com"
    acc_email_2 = "user2@example.com"

    msg_id1_u1 = "msg1_user1"
    msg_id2_u1 = "msg2_user1"
    msg_id1_u2 = "msg1_user2"

    # Adicionar e verificar para user1
    print(f"'{msg_id1_u1}' para '{acc_email_1}' processado? {repo.is_email_processed(msg_id1_u1, acc_email_1)}") # False
    repo.add_processed_email(msg_id1_u1, acc_email_1, now)
    print(f"'{msg_id1_u1}' para '{acc_email_1}' processado? {repo.is_email_processed(msg_id1_u1, acc_email_1)}") # True

    # Tentar adicionar novamente (não deve dar erro devido ao OR IGNORE)
    repo.add_processed_email(msg_id1_u1, acc_email_1, now + datetime.timedelta(seconds=1))

    # Adicionar mais um para user1
    time_msg2_u1 = now + datetime.timedelta(minutes=1)
    repo.add_processed_email(msg_id2_u1, acc_email_1, time_msg2_u1)

    # Adicionar um para user2
    time_msg1_u2 = now + datetime.timedelta(minutes=2)
    repo.add_processed_email(msg_id1_u2, acc_email_2, time_msg1_u2)

    # Testar get_last_processed_email_id
    last_u1 = repo.get_last_processed_email_id(acc_email_1)
    print(f"Último Message ID processado para '{acc_email_1}': {last_u1}") # Esperado: msg_id2_u1
    assert last_u1 == msg_id2_u1

    last_u2 = repo.get_last_processed_email_id(acc_email_2)
    print(f"Último Message ID processado para '{acc_email_2}': {last_u2}") # Esperado: msg_id1_u2
    assert last_u2 == msg_id1_u2

    last_u3_nonexistent = repo.get_last_processed_email_id("nonexistent@example.com")
    print(f"Último Message ID processado para 'nonexistent@example.com': {last_u3_nonexistent}") # Esperado: None
    assert last_u3_nonexistent is None

    # Testar set_initial_checkpoint
    initial_id_u1 = "checkpoint_msg_user1"
    checkpoint_time = datetime.datetime.now() - datetime.timedelta(days=1) # Um dia atrás
    repo.set_initial_checkpoint(initial_id_u1, acc_email_1, checkpoint_time)
    print(f"'{initial_id_u1}' para '{acc_email_1}' processado (após checkpoint)? {repo.is_email_processed(initial_id_u1, acc_email_1)}") # True

    # O último processado para acc_email_1 ainda deve ser msg_id2_u1 porque seu processed_at é mais recente
    last_u1_after_checkpoint = repo.get_last_processed_email_id(acc_email_1)
    print(f"Último Message ID processado para '{acc_email_1}' após set_initial_checkpoint com data antiga: {last_u1_after_checkpoint}")
    assert last_u1_after_checkpoint == msg_id2_u1 # Pois msg_id2_u1 foi processado "depois" do checkpoint_time

    # Testar is_email_processed para um ID não existente em uma conta existente
    print(f"'non_existent_msg' para '{acc_email_1}' processado? {repo.is_email_processed('non_existent_msg', acc_email_1)}") # False


    # --- Testes de EmailAccount (copiados do original para garantir que não quebraram) ---
    print("\n--- Testando add_account (legado) ---")
    try:
        acc1 = repo.add_account(EmailAccount("test1@example.com", "pass1", "outlook", True))
        print(f"Adicionada: {acc1}")
    except ValueError as e:
        print(f"Erro ao adicionar conta já existente (esperado se executado antes sem limpar DB): {e}")


    if os.path.exists(DB_TEST_FILE):
        os.remove(DB_TEST_FILE)
        print(f"\nBanco de dados de teste '{DB_TEST_FILE}' removido.")
