# Outlook Email to Telegram Notifier

Este projeto automatiza o envio de notificações para o Telegram sempre que um novo e-mail chega na sua caixa de entrada do Outlook Desktop. O script lê assunto, remetente, corpo do e-mail e envia todos os anexos para um grupo ou canal do Telegram.
Ideal para ambientes corporativos que utilizam Microsoft Outlook e não têm suporte a IMAP/POP externo.

---

## Funcionalidades

* Monitora novos e-mails de uma conta selecionada do Outlook (não envia e-mails antigos).
* Encaminha o texto do e-mail (assunto, remetente, corpo) para o Telegram com formatação HTML.
* Envia todos os anexos do e-mail para o Telegram.
* Persistência do último e-mail processado: mesmo após reiniciar, nunca repete e-mails já enviados.
* Delay automático entre envio de anexos para evitar bloqueio por excesso de requisições.
* Tratamento de nomes de arquivos de anexos e sanitização do texto para evitar erros de API.

---

## Pré-requisitos

* **Windows** com Microsoft Outlook (2010 ou superior) instalado e configurado.
* **Python 3.8+** instalado.
* **Conta no Telegram** (grupo ou canal para notificação).
* Permissões de administrador se necessário (para acessar o Outlook via COM).

### Bibliotecas Python necessárias

Abra o terminal/prompt de comando na pasta do projeto e execute:

```sh
pip install pywin32 requests python-dotenv certifi
python -m pip install --upgrade certifi
python -m certifi
```

* `pywin32`: Automação do Outlook.
* `requests`: Comunicação HTTP com a API do Telegram.
* `python-dotenv`: Carregamento do arquivo `.env` com suas configurações.
* `certifi`: Corrige problemas de SSL e certificados em ambiente corporativo.

---

## Como configurar o bot do Telegram

### 1. Criar um bot

* Procure por [@BotFather](https://t.me/BotFather) no Telegram.
* Envie `/newbot`, siga as instruções e salve o **TOKEN** fornecido.

### 2. Criar o grupo/canal

* Crie um grupo ou canal no Telegram.
* Adicione o bot criado como membro do grupo.

### 3. Descobrir o `chat_id` do grupo

* No grupo, envie qualquer mensagem.
* Acesse no navegador:

  ```
  https://api.telegram.org/botSEU_TOKEN/getUpdates
  ```

  Procure pelo campo `"chat":{"id":-XXXXXXXXXX,...`.
  O número (negativo) é o seu **CHAT\_ID**.

---

## Configurando o projeto

### 1. Crie um arquivo `.env` com:

```
TELEGRAM_TOKEN=seu_token_aqui
CHAT_ID=seu_chat_id_aqui
```

### 2. Coloque o arquivo `automail.py` na mesma pasta.

---

## Como usar

1. Abra o Outlook, certifique-se de que a conta que deseja monitorar está ativa.
2. Execute o script:

```sh
python automail.py
```

3. O terminal vai listar todas as contas do Outlook. Digite o número da conta que deseja monitorar.

4. O script irá ignorar e-mails antigos e processar apenas os novos que chegarem.
   Você verá logs detalhados no console com data/hora de cada verificação.

---

## Explicação do funcionamento

* O script monitora a caixa de entrada da conta Outlook selecionada.
* Lê e armazena o `EntryID` do último e-mail processado no arquivo `last_entryid.txt` junto da data/hora.
* Em cada ciclo (default: 5 minutos), verifica se há novos e-mails:

  * Se houver, envia mensagem para o Telegram com remetente, assunto e corpo do e-mail.
  * Todos os anexos são enviados para o grupo, um por um, com um atraso de 3 segundos entre cada envio para evitar limites da API.
  * Se o e-mail já foi enviado anteriormente, ele é ignorado (mesmo após reiniciar).
* O texto do e-mail é sanitizado e truncado para evitar erros 400 da API do Telegram.
* Nomes de arquivos de anexo são limpos para evitar caracteres inválidos.

---

## Solução de problemas

* **Erro 400 Bad Request no Telegram:**
  O script sanitiza caracteres especiais e trunca textos grandes. Verifique se o chat\_id está correto e o bot é membro do grupo.

* **Erro SSL/CERTIFICATE\_VERIFY\_FAILED:**
  Use `certifi` como no código e execute:

  ```sh
  python -m pip install --upgrade certifi
  python -m certifi
  ```

* **429 Too Many Requests:**
  O Telegram limita o envio de mensagens/arquivos. O script adiciona `time.sleep(3)` entre anexos. Diminua a frequência de verificação se necessário.

* **Envio de anexos com nomes estranhos/falha:**
  O código remove caracteres não permitidos dos nomes dos arquivos.

---

## Observações

* O script só pode rodar no Windows com Outlook instalado.
* O bot só consegue enviar arquivos de até 50MB (limite do Telegram para bots).
* O delay entre anexos pode ser aumentado se você continuar recebendo erros 429.
* O ciclo de verificação (default: 5 minutos) pode ser alterado modificando `time.sleep(300)` no código.

---

## Licença

Projeto livre para uso educacional e institucional.

---

## Sugestões ou dúvidas?

Abra uma *issue* ou entre em contato pelo Telegram.
