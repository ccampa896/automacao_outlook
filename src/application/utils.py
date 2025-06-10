import re
import os

# Extensões de imagem para ignorar ao processar anexos de e-mail.
# Pode ser movido para configuração se precisar ser dinâmico.
SKIP_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}

def sanitize_html(html_content: str) -> str:
    """
    Limpa o conteúdo HTML para exibição segura ou para conversão para texto simples.
    Substitui caracteres HTML especiais e remove alguns caracteres de controle.
    Esta é uma sanitização básica. Para cenários complexos, considere bibliotecas como bleach.
    """
    if not isinstance(html_content, str):
        html_content = str(html_content) # Garante que é string

    # Substituir entidades HTML básicas
    text = html_content.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')

    # Remover caracteres de controle problemáticos (exceto tab, newline, carriage return)
    # \x00-\x08, \x0B (VT), \x0C (FF), \x0E-\x1F
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F]', '', text)

    # Opcional: remover tags HTML completamente para obter texto plano
    # text = re.sub(r'<[^>]+>', '', text) # Descomente se quiser remover todas as tags

    return text

def normalize_filename(filename: str) -> str:
    """
    Normaliza um nome de arquivo removendo caracteres inválidos ou problemáticos
    e substituindo-os por underscores. Garante que o nome não seja vazio.
    """
    if not filename: # Se o nome do arquivo original for None ou vazio
        return "anexo_sem_nome"

    # Remove ou substitui caracteres que são frequentemente problemáticos em sistemas de arquivos
    # ou URLs. Mantém letras, números, espaços, hífens, underscores e pontos.
    # Outros caracteres são substituídos por underscore.
    normalized = re.sub(r'[^\w\-. ]', '_', filename)

    # Remove espaços em branco no início ou fim do nome
    normalized = normalized.strip()

    # Se o nome do arquivo ficar vazio após a normalização (ex: "!!!.txt" -> "___.___"),
    # retorna um nome padrão.
    if not normalized.strip("._ "): # Verifica se sobrou algo além de '.', '_' ou espaço
        return "anexo_normalizado_sem_nome"

    # Limitar o comprimento do nome do arquivo (opcional, mas bom para compatibilidade)
    max_len = 200 # Um limite razoável
    if len(normalized) > max_len:
        name_part, ext_part = os.path.splitext(normalized)
        ext_len = len(ext_part)
        name_part = name_part[:max_len - ext_len -1] # -1 para o ponto, se houver extensão
        normalized = name_part + ext_part

    return normalized


if __name__ == '__main__':
    print("--- Testando utils.py ---")

    # Testes para sanitize_html
    print("\n--- Testando sanitize_html ---")
    html1 = "<p>Olá & Bem-vindo!</p>\x07"
    clean1 = sanitize_html(html1)
    print(f"Original: '{html1}'\nLimpo:    '{clean1}' (Esperado: '&lt;p&gt;Olá &amp; Bem-vindo!&lt;/p&gt;')")
    assert clean1 == "&lt;p&gt;Olá &amp; Bem-vindo!&lt;/p&gt;"

    html2 = "Texto com <script>alert('XSS')</script> e caracteres como \x01\x0b."
    clean2 = sanitize_html(html2)
    print(f"Original: '{html2}'\nLimpo:    '{clean2}' (Esperado: 'Texto com &lt;script&gt;alert('XSS')&lt;/script&gt; e caracteres como .')")
    assert "&lt;script&gt;" in clean2 and "\x01" not in clean2

    # Testes para normalize_filename
    print("\n--- Testando normalize_filename ---")
    filenames = [
        " meu arquivo .txt ",
        "arquivo*com&caracteres?!especiais.docx",
        "../caminho/relativo/arquivo.pdf",
        "nome_longo_com_mais_de_255_caracteres_.........................................................................................................................................................................................................................................final.zip",
        "!!!.jpg",
        None,
        ""
    ]
    expected_filenames = [
        "meu arquivo .txt",
        "arquivo_com_caracteres__especiais.docx",
        "__caminho_relativo_arquivo.pdf", # Assume que não queremos preservar estrutura de path
        "nome_longo_com_mais_de_255_caracteres_.......................................................................................................................................................................................................................................final.zip", # Exemplo de truncamento (simplificado)
        "___.jpg", # Ou "anexo_normalizado_sem_nome.jpg" dependendo da lógica exata
        "anexo_sem_nome",
        "anexo_sem_nome"
    ] # As expectativas podem precisar de ajuste fino com base na implementação exata de normalize_filename

    for i, fname in enumerate(filenames):
        norm_name = normalize_filename(fname)
        print(f"Original: '{fname}'\nNormalizado: '{norm_name}' (Esperado (aprox): '{expected_filenames[i]}')")
        # Adicionar asserts mais específicos se necessário, ex:
        if fname == " meu arquivo .txt ":
            assert norm_name == "meu arquivo .txt"
        if fname == "!!!.jpg":
            assert norm_name == "___.jpg" # Ou o que for decidido como padrão para nomes "vazios"
        if fname is None or fname == "":
            assert norm_name == "anexo_sem_nome"

    print("\n--- Fim dos testes de utils.py ---")
