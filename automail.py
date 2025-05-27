import win32com.client
import os
import time
import requests
import certifi
import datetime
import re
import sqlite3
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

DB_FILE = "email_sent.db"

def sanitize_html(text):
    text = str(text)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    return text

def truncate_text(text, max_length=4000):
    if len(text) > max_length:
        return text[:max_length] + '\n\n(Mensagem truncada pelo limite do Telegram)'
    return text

def normalize_filename(fname):
    fname = re.sub(r'[^\w\-. ]', '_', fname)
    if not fname.strip():
        fname = "anexo_sem_titulo"
    return fname

def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, data=data, timeout=10, verify=certifi.where())
        r.raise_for_status()
        print("Texto enviado ao Telegram.")
    except Exception as e:
        print(f"Erro ao enviar texto ao Telegram: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Detalhe do erro: {e.response.text}")

def send_telegram_file(filename, file_bytes, mime_type="application/octet-stream"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    files = {
        "document": (filename, file_bytes, mime_type)
    }
    data = {
        "chat_id": CHAT_ID
    }
    try:
        r = requests.post(url, data=data, files=files, timeout=20, verify=certifi.where())
        r.raise_for_status()
        print(f"Arquivo {filename} enviado ao Telegram.")
    except Exception as e:
        print(f"Erro ao enviar anexo ao Telegram: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Detalhe do erro: {e.response.text}")

def escolher_conta(outlook):
    print("Contas encontradas no Outlook:")
    for i, folder in enumerate(outlook.Folders):
        print(f"{i}: {folder.Name}")
    while True:
        try:
            idx = int(input("Digite o número da conta desejada: "))
            if 0 <= idx < len(outlook.Folders):
                return outlook.Folders[idx]
            else:
                print("Número inválido. Tente novamente.")
        except ValueError:
            print("Digite um número válido.")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sent_emails (
            entry_id TEXT PRIMARY KEY,
            sent_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def already_sent(entry_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM sent_emails WHERE entry_id = ?", (entry_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_as_sent(entry_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO sent_emails (entry_id, sent_at) VALUES (?, ?)",
        (entry_id, datetime.datetime.now().strftime("%d/%m/%Y - %H:%M"))
    )
    conn.commit()
    conn.close()

def get_last_checkpoint():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT entry_id FROM sent_emails ORDER BY sent_at DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def set_initial_checkpoint(entry_id):
    # Salva apenas o EntryID do e-mail mais recente sem processar nada, como marco inicial
    mark_as_sent(entry_id)
    print(f"Primeira execução: Definindo marco inicial. EntryID inicial: {entry_id}")

def monitorar_caixa_entrada():
    print("Abrindo Outlook...")
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    conta = escolher_conta(outlook)
    inbox = conta.Folders["Caixa de Entrada"]
    mensagens = inbox.Items
    mensagens.Sort("[ReceivedTime]", True)

    init_db()
    last_checkpoint = get_last_checkpoint()

    if not last_checkpoint:
        # Primeira execução: define o marco zero, não processa e-mail algum
        if len(mensagens) > 0:
            entry_id = mensagens[0].EntryID
            set_initial_checkpoint(entry_id)
            print("Marcação de marco inicial realizada. Os e-mails anteriores não serão processados.")
        else:
            print("Nenhum e-mail na caixa de entrada. Vai monitorar os próximos.")
        last_checkpoint = get_last_checkpoint()

    print("Monitorando novos e-mails a cada 5 minutos...\n")
    while True:
        time.sleep(300)
        mensagens = inbox.Items
        mensagens.Sort("[ReceivedTime]", True)
        novos = []
        for msg in mensagens:
            entry_id = msg.EntryID
            if entry_id == last_checkpoint:
                break
            if already_sent(entry_id):
                continue  # Apenas por segurança, não processa já enviados
            novos.append(msg)
        if novos:
            print(f"{len(novos)} novo(s) e-mail(is) recebido(s).")
            for msg in reversed(novos):
                entry_id = msg.EntryID
                try:
                    subject = sanitize_html(msg.Subject or '(Sem assunto)')
                    sender = sanitize_html(msg.SenderName or '(Sem remetente)')
                    body = sanitize_html(msg.Body or '(Sem corpo de texto)')
                    body = truncate_text(body)
                    text = f"<b>Novo e-mail!</b>\n<b>De:</b> {sender}\n<b>Assunto:</b> {subject}\n\n{body}"
                    send_telegram_text(text)
                    attachments = msg.Attachments
                    for i in range(attachments.Count):
                        attachment = attachments.Item(i+1)
                        fname = normalize_filename(attachment.FileName)
                        temp_path = os.path.join(os.getcwd(), fname)
                        attachment.SaveAsFile(temp_path)
                        with open(temp_path, "rb") as f:
                            file_bytes = f.read()
                        send_telegram_file(fname, file_bytes)
                        os.remove(temp_path)
                        time.sleep(3)
                    mark_as_sent(entry_id)
                except Exception as e:
                    print(f"Erro ao processar novo e-mail: {e}")
            # Atualiza o marco para o próximo ciclo
            last_checkpoint = get_last_checkpoint()
        else:
            agora = datetime.datetime.now().strftime("%d/%m/%Y - %H:%M")
            print(f"{agora} --> Nenhum e-mail novo.")

if __name__ == "__main__":
    monitorar_caixa_entrada()
