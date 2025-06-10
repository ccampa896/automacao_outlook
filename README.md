# Outlook Email to Telegram Notifier

## Arquitetura do Projeto

Este projeto foi recentemente reestruturado para seguir princípios de **Clean Architecture**, visando maior modularidade, testabilidade, manutenibilidade e escalabilidade. A organização do código agora se baseia nas seguintes camadas principais:

-   **Domain (Domínio):** Contém as entidades de negócios (ex: `EmailMessage`, `EmailAccount`) e as interfaces que definem os contratos para repositórios e serviços externos. É o núcleo da aplicação, independente de frameworks e detalhes de infraestrutura.
-   **Application (Aplicação):** Orquestra os fluxos de dados e a lógica de negócios através de casos de uso (`Use Cases`) e serviços de aplicação. Depende do Domínio, mas não da Infraestrutura diretamente (usa as interfaces do Domínio).
-   **Infrastructure (Infraestrutura):** Contém as implementações concretas das interfaces definidas no Domínio. Isso inclui adaptadores para interagir com serviços externos (Outlook, API do Telegram), o banco de dados (SQLite), e o carregamento de configurações.
-   **Interfaces (ou Presentation):** Responsável pela interação com o mundo exterior, como a Interface de Linha de Comando (CLI) que permite ao usuário operar a aplicação.

Essa separação de responsabilidades resulta em um código mais organizado, fácil de entender, testar e evoluir.

---

Este projeto automatiza o envio de notificações para o Telegram sempre que um novo e-mail chega na sua caixa de entrada do Outlook Desktop. O script lê assunto, remetente, corpo do e-mail e envia todos os anexos para um grupo ou canal do Telegram, **exceto imagens PNG, JPG e GIF** (essas imagens não são enviadas).

Ideal para ambientes corporativos que utilizam Microsoft Outlook e não têm suporte a IMAP/POP externo.

---

## Funcionalidades

*   **Monitoramento de E-mails:** Monitora novas mensagens em contas de e-mail configuradas (inicialmente focado em Outlook com automação local).
*   **Seleção de Conta Outlook:** Permite ao usuário selecionar qual conta específica monitorar, caso haja múltiplas contas configuradas no perfil local do Outlook (via CLI).
*   **Checkpointing Inteligente:** Na primeira execução para uma conta, marca o e-mail mais recente como um "checkpoint", processando apenas mensagens novas dali em diante para evitar o envio de e-mails antigos.
*   **Persistência Robusta:** Utiliza um banco de dados SQLite para registrar e-mails já processados, garantindo que não haja reenvio de notificações, mesmo após reinícios da aplicação. O nome do arquivo do banco de dados é configurável (padrão: `automail.db`).
*   **Notificações Detalhadas para Telegram:**
    *   Envia informações do e-mail (remetente, assunto, corpo) formatadas em HTML para um chat do Telegram.
    *   Realiza sanitização e truncamento automático de mensagens longas para compatibilidade com a API do Telegram.
*   **Processamento de Anexos:**
    *   Envia todos os anexos de e-mails (exceto tipos de imagem comuns como PNG, JPG, GIF) para o Telegram.
    *   Normaliza nomes de arquivos para remover caracteres problemáticos.
    *   Inclui um pequeno delay configurável (via CLI) entre o envio de múltiplos anexos para respeitar os limites da API do Telegram.
*   **Interface de Linha de Comando (CLI):** Operação completa da aplicação através de comandos intuitivos, incluindo:
    *   Monitoramento contínuo com intervalo configurável.
    *   Gerenciamento de contas de e-mail (adicionar, listar).
*   **Configurável:** Suporte a configurações personalizadas através de um arquivo `.env` (token do Telegram, chat ID, configurações de banco de dados, conta de e-mail padrão, etc.).
*   **Feedback no Console:** Fornece informações sobre as operações em andamento e possíveis erros diretamente no console (este feedback será aprimorado com um sistema de logging estruturado em futuras atualizações).
*   **Arquitetura Modular:** Código reestruturado seguindo princípios de Clean Architecture para melhor manutenibilidade, testabilidade e extensibilidade.

---
## Pré-requisitos

*   **Sistema Operacional:** Windows.
*   **Microsoft Outlook:** Versão Desktop (2010 ou superior) instalada e configurada, caso deseje monitorar contas Outlook locais via COM.
*   **Python:** Versão 3.8 ou superior. Recomenda-se o uso de um [ambiente virtual](https://docs.python.org/3/tutorial/venv.html).
*   **Conta no Telegram:** Um bot do Telegram e um chat ID (de grupo ou canal) para onde as notificações serão enviadas.
*   **Arquivo de Configuração:** Um arquivo `.env` na raiz do projeto para armazenar configurações e segredos (detalhes abaixo).
*   **Permissões:** Permissões de administrador no Windows podem ser necessárias se o acesso ao Outlook via COM for restrito.

### Bibliotecas Python Necessárias

Todas as dependências Python do projeto estão listadas no arquivo `requirements.txt`. Para instalá-las, após criar e ativar seu ambiente virtual, navegue até a pasta raiz do projeto no seu terminal e execute:

```bash
pip install -r requirements.txt
```

Isso instalará `pywin32` (para automação do Outlook local), `requests` (para a API do Telegram), `python-dotenv` (para o arquivo `.env`), `certifi` (para certificados SSL), e quaisquer outras dependências que possam ter sido adicionadas.

**Nota sobre `certifi`:** Em ambientes corporativos com firewalls ou proxies SSL, pode ser necessário garantir que os certificados raiz estejam atualizados. Se encontrar erros de SSL (`CERTIFICATE_VERIFY_FAILED`):
```bash
python -m pip install --upgrade certifi
# O comando `python -m certifi` (executado sozinho) apenas mostra o caminho do arquivo de certificados.
# A atualização dos certificados é feita através do pip install --upgrade certifi.
# Em alguns casos, especialmente em instalações Python mais antigas ou customizadas no Windows,
# pode ser necessário executar um script que acompanha a instalação do certifi para instalar
# os certificados no repositório do Windows, mas isso é menos comum recentemente.
```

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

A configuração da aplicação é gerenciada através de um arquivo `.env` localizado na raiz do seu projeto. Crie este arquivo se ele ainda não existir.

### Variáveis de Ambiente no Arquivo `.env`

Aqui está um exemplo de como seu arquivo `.env` pode se parecer e as variáveis que ele pode conter:

```env
# Token do seu Bot do Telegram (obtido do @BotFather)
TELEGRAM_BOT_TOKEN="SEU_TOKEN_AQUI"

# ID do Chat do Telegram para onde as notificações serão enviadas (grupo ou canal)
TELEGRAM_DEFAULT_CHAT_ID="SEU_CHAT_ID_AQUI"

# (Opcional) Nome do arquivo do banco de dados SQLite.
# Se não definido, o padrão "automail.db" será usado pela aplicação.
# DATABASE_NAME="meu_automail.db"

# (Opcional) Endereço de e-mail da conta que será usada por padrão pela CLI
# se nenhum e-mail de conta for especificado em comandos como `monitor-emails`.
# DEFAULT_EMAIL_ACCOUNT="seu_email@dominio.com"

# (Opcional) Define o método de autenticação para o Outlook.
# A aplicação tentará usar "graph_api" se a biblioteca 'msal' estiver disponível,
# caso contrário, usará "local_win32" (automação COM local).
# Você pode forçar um tipo específico descomentando uma das linhas abaixo:
# OUTLOOK_AUTH_TYPE="local_win32"
# OUTLOOK_AUTH_TYPE="graph_api"

# (Opcional) Credenciais para Microsoft Graph API (necessário se OUTLOOK_AUTH_TYPE="graph_api")
# Requer registro prévio da aplicação no Azure Active Directory.
# OUTLOOK_CLIENT_ID="seu_client_id_do_azure_ad"
# OUTLOOK_CLIENT_SECRET="seu_client_secret_do_azure_ad"
# OUTLOOK_TENANT_ID="seu_tenant_id_do_azure_ad"

# (Opcional) Destinatário padrão para notificações administrativas da aplicação (ex: falhas de login)
# Pode ser o mesmo que TELEGRAM_DEFAULT_CHAT_ID ou um chat de admin diferente.
# ADMIN_NOTIFICATION_RECIPIENT="ID_CHAT_ADMIN"
```

**Observações:**

*   Substitua `"SEU_TOKEN_AQUI"` e `"SEU_CHAT_ID_AQUI"` (e outras variáveis de exemplo) com seus valores reais.
*   As variáveis comentadas (`#`) são opcionais ou exemplos; descomente e ajuste conforme necessário.
*   **NÃO adicione o arquivo `.env` ao seu sistema de controle de versão (Git)** se ele contiver segredos. O arquivo `.gitignore` (se existir no projeto) deve ser configurado para ignorar `.env`.

---
## Como usar

A aplicação agora é operada através de uma Interface de Linha de Comando (CLI). Certifique-se de que seu [ambiente virtual esteja ativado](#bibliotecas-python-necessárias) e que você esteja na pasta raiz do projeto.

### Executando a Aplicação

O ponto de entrada principal da aplicação é `src/main.py`. Você pode executá-la como um módulo Python a partir da raiz do projeto:

```bash
python -m src.main [comando] [opções]
```

Alternativamente, dependendo da configuração do seu PYTHONPATH, você pode executar diretamente o script (também da raiz do projeto):

```bash
python src/main.py [comando] [opções]
```

Se nenhum comando for fornecido, a ajuda da CLI será exibida listando todos os comandos disponíveis.

### Comando Principal: `monitor-emails`

Este é o comando central para monitorar uma conta de e-mail e enviar notificações para o Telegram.

**Exemplo de uso básico (execução única para verificar e-mails novos):**

```bash
python -m src.main monitor-emails --account seu_email@dominio.com
```

**Monitoramento contínuo (ex: a cada 5 minutos / 300 segundos):**

```bash
python -m src.main monitor-emails --account seu_email@dominio.com --loop-interval 300
```

**Argumentos do comando `monitor-emails`:**

*   `--account SEU_EMAIL`: Especifica o endereço de e-mail da conta que você deseja monitorar. Esta conta já deve ter sido adicionada à aplicação (veja o comando `add-account` abaixo). Se a variável `DEFAULT_EMAIL_ACCOUNT` estiver definida no seu arquivo `.env`, este argumento se torna opcional e o valor do `.env` será usado.
*   `--loop-interval SEGUNDOS`: (Opcional) Habilita o monitoramento contínuo. O programa verificará novos e-mails no intervalo de segundos especificado. Se omitido, o comando executa apenas uma vez. Pressione `Ctrl+C` para interromper o monitoramento contínuo.
*   `--folder NOME_DA_PASTA`: (Opcional) Especifica a pasta de e-mail a ser monitorada (ex: "Caixa de Entrada", "Inbox", "Sent Items"). O padrão é "Inbox".
*   `--delay SEGUNDOS`: (Opcional) Pequeno delay em segundos entre o processamento de múltiplos e-mails ou envio de múltiplos anexos para evitar sobrecarga de APIs. Padrão: 2 segundos.

**Seleção de Conta do Outlook (para múltiplas contas no perfil local):**

Se você estiver monitorando uma conta Outlook configurada para usar o modo `local_win32` (automação COM local) e seu perfil do Outlook tiver múltiplas contas (MAPI stores) configuradas:

1.  Ao executar o comando `monitor-emails` para essa conta, a aplicação listará as contas Outlook detectadas no seu perfil.
2.  Você será solicitado a digitar o número correspondente à conta que deseja monitorar nesta sessão.
3.  A aplicação então prosseguirá monitorando a caixa de entrada da conta selecionada.

**Primeira Execução (Checkpointing):**

Na primeira vez que você monitora uma conta específica (ou se o banco de dados de emails processados for novo/resetado), a aplicação estabelecerá um "checkpoint" com base no e-mail mais recente encontrado nessa conta. Nenhum e-mail anterior a este checkpoint será processado ou notificado. A partir daí, apenas e-mails que chegarem *após* este checkpoint serão considerados novos. Este comportamento previne o envio de todo o histórico de e-mails na primeira execução.

### Outros Comandos Úteis

*   **Adicionar uma conta de e-mail à aplicação:**
    ```bash
    python -m src.main add-account seu_novo_email@dominio.com --type outlook
    ```
    Você será solicitado a digitar a senha de forma segura. O tipo (`--type`) pode ser `outlook`, `gmail` (se implementado), etc., conforme suportado pela configuração da aplicação.

*   **Listar todas as contas de e-mail configuradas na aplicação:**
    ```bash
    python -m src.main list-accounts
    ```

*   **Verificar e-mails (apenas lista no console, sem enviar notificações completas):**
    ```bash
    python -m src.main check-emails --account seu_email@dominio.com --limit 5
    ```

*   **Enviar uma notificação de teste direta via Telegram (requer Telegram configurado no `.env`):**
    ```bash
    python -m src.main send-notification "Esta é uma mensagem de teste para o Telegram"
    ```
    (Pode requerer `--recipient SEU_CHAT_ID` se `TELEGRAM_DEFAULT_CHAT_ID` não estiver no `.env`)

### Obtendo Ajuda

Para ver todos os comandos e opções globais disponíveis, execute:
```bash
python -m src.main --help
```
E para obter ajuda sobre um comando específico (por exemplo, `monitor-emails`):
```bash
python -m src.main monitor-emails --help
```

---
## Explicação do funcionamento

A aplicação opera com uma arquitetura modular para processar e-mails e enviar notificações:

1.  **Interface de Linha de Comando (CLI):**
    *   O usuário interage com a aplicação através de comandos na CLI (gerenciada por `src/interfaces/cli.py`).
    *   O comando principal, `monitor-emails`, inicia o processo de verificação de novos e-mails para uma conta especificada.
    *   Se configurado para monitoramento contínuo (`--loop-interval`), a CLI gerencia o ciclo de repetição e espera.

2.  **Orquestração da Lógica:**
    *   A CLI utiliza Casos de Uso (como `MonitorNewEmailsAndNotifyUseCase` em `src/application/use_cases.py`) e Serviços de Aplicação (como `EmailAppService` em `src/application/services.py`) para coordenar as tarefas.
    *   Esses componentes da camada de Aplicação não interagem diretamente com APIs externas ou bancos de dados, mas sim com abstrações (interfaces de repositórios e serviços) definidas no Domínio.

3.  **Interação com o Provedor de E-mail (Outlook):**
    *   O `OutlookAdapter` (em `src/infrastructure/outlook_adapter.py`) é responsável por toda a comunicação com o Microsoft Outlook.
    *   No modo `local_win32` (padrão para instalações com Outlook Desktop), ele usa automação COM para:
        *   Listar as contas MAPI (perfis de e-mail) disponíveis no Outlook local, se houver múltiplas.
        *   Permitir a seleção da conta a ser monitorada através da CLI.
        *   Acessar a pasta de e-mails especificada (ex: "Caixa de Entrada") da conta selecionada.
        *   Listar novas mensagens e extrair seus detalhes (remetente, assunto, corpo, data, `EntryID`).
        *   Baixar anexos dos e-mails.
    *   (O adaptador também possui estrutura para suportar a API do Microsoft Graph como uma alternativa futura).

4.  **Gerenciamento de Estado e Checkpointing (Banco de Dados SQLite):**
    *   A aplicação utiliza um banco de dados SQLite (o nome do arquivo é configurável via `.env`, com padrão `automail.db`), gerenciado pelo `SQLiteRepository` (em `src/infrastructure/sqlite_repository.py`).
    *   **Prevenção de Duplicidade:** Uma tabela (`processed_emails`) armazena o `EntryID` (identificador único do e-mail no Outlook) de cada e-mail que já foi processado e notificado, crucialmente associado ao endereço da conta monitorada. Isso garante que, mesmo após reiniciar a aplicação, um e-mail não seja processado múltiplas vezes para a mesma conta.
    *   **Checkpoint Inicial:** Na primeira vez que uma conta específica é monitorada (ou se o banco de dados de emails processados for novo), o `EntryID` do e-mail mais recente encontrado nessa conta é salvo como "checkpoint". Apenas e-mails recebidos *após* este ponto são considerados para notificação, prevenindo o envio de todo o histórico de e-mails.
    *   **Contas de Usuário:** Opcionalmente, o banco de dados também pode armazenar detalhes de contas de e-mail adicionadas através da CLI (tabela `email_accounts`).

5.  **Processamento e Preparação da Notificação:**
    *   A camada de Aplicação prepara a mensagem para o Telegram:
        *   O corpo do e-mail, remetente e assunto são sanitizados (para remover caracteres HTML potencialmente problemáticos) e formatados usando tags HTML básicas para o Telegram.
        *   Mensagens muito longas são automaticamente truncadas para não exceder os limites da API do Telegram, com uma indicação de truncamento.
        *   Nomes de arquivos de anexos são normalizados para remover caracteres inválidos e garantir compatibilidade.
    *   Anexos que são tipos de imagem comuns (PNG, JPG, GIF, etc., conforme definido em `src/application/utils.py`) são ignorados e não são enviados.

6.  **Envio para o Telegram:**
    *   O `TelegramAdapter` (em `src/infrastructure/telegram_adapter.py`) recebe a mensagem de texto formatada e os arquivos de anexos (não-imagem).
    *   Ele envia essas informações para a API do Bot do Telegram, que então encaminha para o grupo ou canal especificado no `TELEGRAM_DEFAULT_CHAT_ID` (configurado no `.env`).
    *   Um pequeno delay (configurável via CLI com `--delay`) é aplicado entre o envio de múltiplos anexos do mesmo e-mail para evitar bloqueios por excesso de requisições à API do Telegram.

7.  **Configuração Centralizada:**
    *   Todas as configurações essenciais, como tokens de API, IDs de chat, nome do banco de dados, e configurações de adaptadores, são carregadas do arquivo `.env` na raiz do projeto pelo `DotEnvConfigRepository`.

---
## Solução de problemas

*   **Erro `ModuleNotFoundError` ao executar `python -m src.main ...`**
    *   Certifique-se de que você está executando o comando a partir da **pasta raiz do projeto** (a pasta que contém o diretório `src` e o arquivo `.env`).
    *   Verifique se seu ambiente virtual Python (se estiver usando um) está ativado.

*   **Configurações não carregadas / Erros de Token ou Chat ID:**
    *   Verifique se o arquivo `.env` existe na raiz do projeto e se ele contém as variáveis corretas (ex: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_DEFAULT_CHAT_ID`). Veja a seção "Configurando o Projeto".
    *   Certifique-se de que não há erros de digitação nos nomes das variáveis ou nos seus valores dentro do arquivo `.env`.

*   **Problemas com a API do Telegram:**
    *   **Erro 400 Bad Request:** Geralmente indica que o `TELEGRAM_DEFAULT_CHAT_ID` está incorreto ou o bot não é membro do grupo/canal de destino. Verifique esses dados no Telegram. A aplicação tenta sanitizar e truncar mensagens, mas combinações de caracteres muito incomuns ainda podem, raramente, causar problemas.
    *   **Erro `message is too long`:** A aplicação já trunca mensagens para o limite do Telegram. Se este erro ocorrer, pode ser devido a uma formatação HTML excessiva ou caracteres especiais não previstos que, mesmo após a sanitização, resultam em uma mensagem problemática para a API.
    *   **Erro 429 Too Many Requests:** A API do Telegram impõe limites de quantas mensagens/arquivos podem ser enviados em um curto período.
        *   A aplicação já inclui um delay entre o envio de múltiplos anexos do mesmo e-mail (configurável via `--delay` no comando `monitor-emails`).
        *   Se você monitora e-mails com muita frequência (usando `--loop-interval` com um valor muito baixo no comando `monitor-emails`), pode encontrar este erro. Considere aumentar o intervalo.
    *   **Erro SSL/CERTIFICATE\_VERIFY\_FAILED:**
        *   Este erro pode ocorrer em redes corporativas com inspeção SSL ou firewalls.
        *   Certifique-se de que a biblioteca `certifi` está atualizada: `python -m pip install --upgrade certifi`. (Veja também a nota sobre `certifi` na seção "Pré-requisitos").
        *   Em alguns casos, pode ser necessário configurar `requests` para usar um proxy corporativo ou certificados customizados (esta é uma configuração avançada não coberta por este README).

*   **Problemas com o Outlook (modo `local_win32`):**
    *   **Nenhuma conta Outlook encontrada ou erro ao listar contas na CLI:**
        *   Certifique-se de que o Microsoft Outlook Desktop está instalado, devidamente configurado com pelo menos uma conta de e-mail, e em execução.
        *   A conta que você deseja usar deve estar ativa e funcionando no Outlook.
        *   Em alguns ambientes Windows, pode ser necessário executar o terminal/prompt de comando como Administrador para permitir que a aplicação acesse o Outlook via automação COM.
    *   **Conta desejada não aparece na lista de seleção da CLI:**
        *   Verifique se a conta está totalmente configurada e sincronizada dentro do seu Microsoft Outlook Desktop.
        *   A aplicação lista os "MAPI stores" (contas de e-mail de nível superior) detectados no seu perfil Outlook. Se a conta estiver configurada de forma aninhada ou incomum, ela pode não ser detectada como um store principal.
    *   **Erro ao acessar e-mails ou anexos específicos:** Pode indicar um problema com o item de e-mail particular no Outlook (ex: corrompido) ou restrições de permissão. Verifique o e-mail diretamente no Outlook.

*   **Problemas com Anexos:**
    *   **Anexos com nomes estranhos/falha no envio:** A aplicação normaliza os nomes dos arquivos para remover caracteres potencialmente problemáticos. Se um anexo específico consistentemente falhar, pode haver um problema com o próprio arquivo ou um nome de arquivo extremamente complexo que a normalização não consegue tratar perfeitamente para a API do Telegram.
    *   **Imagens não são enviadas:** Isso é um comportamento esperado e configurado. A aplicação está definida para ignorar anexos de tipos de imagem comuns (PNG, JPG, GIF, etc.) para focar no conteúdo de documentos.

*   **Problemas com o Banco de Dados SQLite (padrão: `automail.db`):**
    *   **Erro ao criar ou escrever no arquivo do banco de dados:** Verifique as permissões de escrita na pasta onde a aplicação está sendo executada.
    *   **Banco de dados corrompido (raro):** Se suspeitar de corrupção, você pode apagar ou renomear o arquivo do banco de dados (ex: `automail.db`). A aplicação irá recriá-lo na próxima execução. **Atenção:** Isso fará com que a aplicação perca todo o histórico de e-mails já processados, e o checkpointing será reiniciado para todas as contas (e-mails antigos não serão reprocessados, mas o "marco zero" para cada conta será o e-mail mais recente no momento da recriação do banco).

*   **Uso da CLI:**
    *   **Comando não reconhecido ou opção inválida:** Utilize `python -m src.main --help` para ver a lista de todos os comandos disponíveis e suas descrições. Para ajuda sobre um comando específico e suas opções, use `python -m src.main [nome_do_comando] --help`.

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

[end of README.md]
