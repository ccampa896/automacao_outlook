import win32com.client
import os
import time
import requests
import certifi
import datetime
import re
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ENTRYID_FILE = "last_entryid.txt"

# --- 1. Função para "sanitizar" HTML para Telegram ---
def sanitize_html(text):
    # Remove tags HTML abertas não fechadas e caracteres problemáticos para o Telegram
    # Substitui <, > e & pelos equivalentes HTML
    text = str(text)
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Remove códigos de controle problemáticos do Outlook
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)
    return text

# --- 2. Limite de tamanho do texto do Telegram ---
def truncate_text(text, max_length=4000):
    if len(text) > max_length:
        return text[:max_length] + '\n\n(Mensagem truncada pelo limite do Telegram)'
    return text

# --- 3. Normalizar nomes de arquivos ---
def normalize_filename(fname):
    # Remove ou substitui caracteres problemáticos
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

def carregar_ultimo_entryid():
    if os.path.exists(ENTRYID_FILE):
        with open(ENTRYID_FILE, "r") as f:
            linha = f.read().strip()
            if linha:
                partes = linha.split("  ", 1)
                if len(partes) == 2:
                    return partes[0], partes[1]
                return partes[0], None
    return None, None

def salvar_ultimo_entryid(entryid, datahora):
    with open(ENTRYID_FILE, "w") as f:
        f.write(f"{entryid}  {datahora}")

def monitorar_caixa_entrada():
    print("Abrindo Outlook...")
    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    conta = escolher_conta(outlook)
    inbox = conta.Folders["Caixa de Entrada"]

    mensagens = inbox.Items
    mensagens.Sort("[ReceivedTime]", True)  # Mais recentes primeiro

    # Carrega último EntryID salvo (se houver)
    ultimo_id, ultima_datahora = carregar_ultimo_entryid()

    if ultimo_id:
        print(f"Arquivo de persistência encontrado (EntryID: {ultimo_id}, Data/Hora: {ultima_datahora}). Vai monitorar e-mails que chegarem após o último processado.")
    else:
        if len(mensagens) > 0:
            ultimo_id = mensagens[0].EntryID
            ultima_datahora = datetime.datetime.now().strftime("%d/%m/%Y - %H:%M")
            salvar_ultimo_entryid(ultimo_id, ultima_datahora)
            print(f"Ignorando {len(mensagens)} e-mails antigos. Só vai monitorar novos a partir de agora.")
        else:
            print("Nenhum e-mail encontrado. Vai monitorar todos os próximos.")

    print("Monitorando novos e-mails a cada 5 minutos...\n")
    while True:
        time.sleep(300)
        mensagens = inbox.Items
        mensagens.Sort("[ReceivedTime]", True)
        novos = []
        for msg in mensagens:
            if msg.EntryID == ultimo_id:
                break
            novos.append(msg)
        if novos:
            print(f"{len(novos)} novo(s) e-mail(is) recebido(s).")
            for msg in reversed(novos):
                try:
                    subject = sanitize_html(msg.Subject or '(Sem assunto)')
                    sender = sanitize_html(msg.SenderName or '(Sem remetente)')
                    body = sanitize_html(msg.Body or '(Sem corpo de texto)')
                    body = truncate_text(body)
                    text = f"<b>Novo e-mail!</b>\n<b>De:</b> {sender}\n<b>Assunto:</b> {subject}\n\n{body}"
                    send_telegram_text(text)
                    # Anexos
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
                        time.sleep(3)  # Aguarda 3 segundos entre os envios de anexos
                except Exception as e:
                    print(f"Erro ao processar novo e-mail: {e}")
            # Atualiza EntryID processado no disco, junto com data/hora
            ultimo_id = mensagens[0].EntryID
            ultima_datahora = datetime.datetime.now().strftime("%d/%m/%Y - %H:%M")
            salvar_ultimo_entryid(ultimo_id, ultima_datahora)
        else:
            agora = datetime.datetime.now().strftime("%d/%m/%Y - %H:%M")
            print(f"{agora} --> Nenhum e-mail novo.")

if __name__ == "__main__":
    monitorar_caixa_entrada()
