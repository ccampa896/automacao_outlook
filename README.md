# Outlook Email to Telegram Notifier

Este projeto automatiza o envio de notificações para o Telegram sempre que um novo e-mail chega na sua caixa de entrada do Outlook Desktop. O script lê assunto, remetente, corpo do e-mail e envia todos os anexos para um grupo ou canal do Telegram, **exceto imagens PNG, JPG e GIF** (essas imagens não são enviadas).

Ideal para ambientes corporativos que utilizam Microsoft Outlook e não têm suporte a IMAP/POP externo.

---

## Funcionalidades

* Monitora novos e-mails de uma conta selecionada do Outlook (não envia e-mails antigos).
* Persistência robusta: utiliza banco de dados SQLite para garantir que e-mails não sejam reenviados, mesmo após reiniciar o script.
* Envia texto do e-mail (assunto, remetente, corpo) para o Telegram com formatação HTML e sanitização para evitar erros de API.
* Truncamento automático de textos longos para evitar erros do Telegram.
* Envia todos os anexos do e-mail para o Telegram, com nomes de arquivos normalizados, **exceto imagens PNG, JPG e GIF** (imagens não são enviadas).
* Delay automático entre envio de anexos para evitar bloqueio por excesso de requisições (limite do Telegram).
* Logs detalhados no console, incluindo data/hora de cada verificação e detalhes de erros.
* Checkpoint automático: na primeira execução, marca o e-mail mais recente como referência e só processa e-mails novos a partir daí.
* Compatível com múltiplas contas do Outlook: permite escolher qual conta monitorar.

---

## Pré-requisitos

* **Windows** com Microsoft Outlook (2010 ou superior) instalado e configurado.
* **Python 3.8+** instalado.
* **Conta no Telegram** (grupo ou canal para notificação).
* Permissões de administrador se necessário (para acessar o Outlook via COM).

### Bibliotecas Python necessárias

Abra o terminal/prompt de comando na pasta do projeto e execute:

```
pip install pywin32 requests python-dotenv certifi
```

* `pywin32`: Automação do Outlook.
* `requests`: Comunicação HTTP com a API do Telegram.
* `python-dotenv`: Carregamento do arquivo `.env` com suas configurações.
* `certifi`: Corrige problemas de SSL e certificados em ambiente corporativo.

Recomenda-se ainda rodar:

```
python -m pip install --upgrade certifi
python -m certifi
```

Para garantir que os certificados SSL estejam atualizados.

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

```
python automail.py
```

3. O terminal vai listar todas as contas do Outlook. Digite o número da conta que deseja monitorar.
4. Na **primeira execução**, o script irá ignorar e-mails antigos (marcando o e-mail mais recente como "marco zero") e processar apenas os novos que chegarem a partir daí.
5. Você verá logs detalhados no console com data/hora de cada verificação.

---

## Explicação do funcionamento

* O script monitora a caixa de entrada da conta Outlook selecionada.
* Utiliza um banco de dados SQLite (`email_sent.db`) para registrar todos os e-mails já enviados, garantindo que não haja duplicidade mesmo após reiniciar.
* Na primeira execução, marca o e-mail mais recente como referência (checkpoint) e só processa e-mails novos a partir desse ponto. E-mails anteriores **não são processados**.
* A cada ciclo (default: 5 minutos), verifica se há novos e-mails:

  * Se houver, envia mensagem para o Telegram com remetente, assunto e corpo do e-mail (com sanitização e truncamento para evitar erros 400 da API).
  * Todos os anexos **não-imagem** são enviados para o grupo, um por um, com um atraso de 3 segundos entre cada envio para evitar limites da API. **Anexos de imagem (png, jpg, gif) são ignorados!**
  * Se o e-mail já foi enviado anteriormente (EntryID registrado no banco), ele é ignorado (mesmo após reiniciar).
* Nomes de arquivos de anexo são normalizados para evitar caracteres inválidos.
* Logs detalhados são exibidos no console, incluindo erros detalhados da API do Telegram. Caso uma mensagem seja grande demais para o Telegram, ela é truncada automaticamente antes do envio.

---

## Solução de problemas

* **Erro 400 Bad Request no Telegram:**
  O script sanitiza caracteres especiais e trunca textos grandes. Verifique se o chat\_id está correto e se o bot é membro do grupo.

* **Erro `message is too long`:**
  O script já corta a mensagem para o limite do Telegram. Se persistir, verifique se há alguma combinação de caracteres ou HTML incomum.

* **Erro SSL/CERTIFICATE\_VERIFY\_FAILED:**
  Use `certifi` como no código e execute:

  ```
  python -m pip install --upgrade certifi
  python -m certifi
  ```

* **429 Too Many Requests:**
  O Telegram limita o envio de mensagens/arquivos. O script adiciona `time.sleep(3)` entre anexos. Diminua a frequência de verificação se necessário.

* **Envio de anexos com nomes estranhos/falha:**
  O código normaliza nomes de arquivos para evitar caracteres inválidos.

* **Problemas com múltiplas contas Outlook:**
  O script permite escolher a conta ao iniciar. Se não aparecerem todas, verifique permissões do Outlook.

---

## Observações

* O script só pode rodar no Windows com Outlook instalado.
* O bot só consegue enviar arquivos de até 50MB (limite do Telegram para bots).
* O delay entre anexos pode ser aumentado se você continuar recebendo erros 429.
* O ciclo de verificação (default: 5 minutos) pode ser alterado modificando o valor de `time.sleep(300)` no código.
* O banco de dados `email_sent.db` pode ser apagado para "resetar" o histórico de e-mails enviados (não recomendado em produção).
* **Anexos do tipo imagem (png, jpg, gif) são ignorados e não enviados ao Telegram.**

---

## Licença

Projeto livre para uso educacional e institucional.

---

## Sugestões ou dúvidas?

Contato *LinkedIn*: [Carlos Felipe Dalan Campanari](https://www.linkedin.com/in/carlos-campanari/)

---
