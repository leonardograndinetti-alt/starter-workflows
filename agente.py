import os
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==============================================================================
# CONFIGURAÇÕES E VARIÁVEIS DE AMBIENTE
# ==============================================================================
EMAIL_ORIGEM = os.getenv("EMAIL_ORIGEM")
SENHA_APP = os.getenv("SENHA_APP")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")

PALAVRAS_CHAVE = [
    r'\bcelular\b', r'\bsmartphone\b', r'\biphone\b', r'\bsamsung\b', r'\bxiaomi\b',
    r'\btv\b', r'\btelevisao\b', r'\btelevisor\b', r'\bsmart tv\b'
]

URL_EDITAIS = "https://www25.receita.fazenda.gov.br/sle-sociedade/portal/editais-disponiveis"

# ==============================================================================
# INICIALIZAÇÃO DO NAVEGADOR
# ==============================================================================
def inicializar_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': '''
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        '''
    })
    
    return driver

def contem_palavras_chave(texto):
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in PALAVRAS_CHAVE)

# ==============================================================================
# ENVIO DE E-MAIL DE ALERTA
# ==============================================================================
def enviar_email_alerta(achados):
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: Variáveis de e-mail não configuradas. Notificação ignorada.")
        return

    try:
        mensagem = MIMEMultipart()
        mensagem["From"] = EMAIL_ORIGEM
        mensagem["To"] = EMAIL_DESTINO
        
        total_lotes = sum(len(lotes) for lotes in achados.values())
        mensagem["Subject"] = f"Alerta Leilão RF (Galeão): {total_lotes} lote(s) com celular/TV"

        corpo = f"Foram encontrados {total_lotes} lote(s) com itens de interesse nos editais do Galeão:\n\n"
        
        for edital, lotes in achados.items():
            corpo += f"=========================================\n"
            corpo += f"EDITAL: {edital}\n"
            corpo += f"=========================================\n"
            for idx, lote in enumerate(lotes, 1):
                corpo += f"  Lote {idx}:\n  {lote}\n\n"
        
        corpo += f"\nAcesse o portal diretamente em: {URL_EDITAIS}"
        mensagem.attach(MIMEText(corpo, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ORIGEM, SENHA_APP)
        server.send_message(mensagem)
        server.quit()
        print(f"[+] Alerta enviado com sucesso para {EMAIL_DESTINO}")
    except Exception as e:
        print(f"[!] Erro ao enviar e-mail: {e}")

# ==============================================================================
# PROCESSAMENTO DE LOTES DENTRO DO EDITAL
# ==============================================================================
def extrair_lotes_do_edital(driver, nome_edital):
    time.sleep(8)  # Tempo de renderização do Angular
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # Mapeia blocos que representam lotes (cards, linhas de tabela ou divs com conteúdo)
    blocos = soup.find_all(['tr', 'div', 'article'], class_=re.compile(r'(lote|card|item|linha|row)', re.I))
    if not blocos:
        blocos = soup.find_all(['div', 'section'])

    lotes_encontrados = []
    textos_vistos = set()

    for bloco in blocos:
        texto = bloco.get_text(separator=" ", strip=True)
        # Filtra fragmentos irrelevantes e duplicados
        if 30 < len(texto) < 1200 and texto not in textos_vistos:
            if contem_palavras_chave(texto):
                lotes_encontrados.append(texto)
                textos_vistos.add(texto)

    print(f"  [->] Edital '{nome_edital}': {len(lotes_encontrados)} lote(s) contendo celular/TV.")
    return lotes_encontrados

# ==============================================================================
# EXECUÇÃO DO SCRAPING
# ==============================================================================
def buscar_itens():
    print(f"[-] Acessando o portal da Receita Federal: {URL_EDITAIS}")
    driver = inicializar_driver()
    achados_por_edital = {}

    try:
        driver.get(URL_EDITAIS)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(10)

        # Localiza todos os links ou botões de edital associados a 'Galeão'
        elementos_edital = driver.find_elements(By.XPATH, "//*[contains(translate(text(), 'GALEÃO', 'galeão'), 'galeão') or contains(translate(@aria-label, 'GALEÃO', 'galeão'), 'galeão')]/ancestor-or-self::a | //*[contains(translate(text(), 'GALEÃO', 'galeão'), 'galeão')]/ancestor-or-self::button")
        
        if not elementos_edital:
            # Busca genérica por elementos contendo a palavra Galeão
            elementos_edital = [el for el in driver.find_elements(By.TAG_NAME, "a") if "galeão" in el.text.lower()]

        urls_ou_titulos = []
        for el in elementos_edital:
            href = el.get_attribute("href")
            texto = el.text.strip() or "Edital Galeão"
            urls_ou_titulos.append((texto, href, el))

        print(f"[+] Total de editais do Galeão localizados: {len(urls_ou_titulos)}")

        if not urls_ou_titulos:
            print("[-] Nenhum edital referente ao Galeão foi encontrado nesta verificação.")
            return

        # Guarda a URL inicial da lista para retornar após inspecionar cada edital
        url_lista = driver.current_url

        for idx, (nome, href, elemento) in enumerate(urls_ou_titulos, 1):
            print(f"\n[-] Inspecionando edital {idx}/{len(urls_ou_titulos)}: {nome}")
            
            try:
                if href and href.startswith("http"):
                    driver.get(href)
                else:
                    # Clique via JavaScript caso seja uma SPA sem href direto
                    driver.execute_script("arguments[0].click();", elemento)
                
                lotes = extrair_lotes_do_edital(driver, nome)
                if lotes:
                    achados_por_edital[nome] = lotes

            except Exception as err_edital:
                print(f"[!] Erro ao processar o edital '{nome}': {err_edital}")
            
            # Retorna para a lista principal para abrir o próximo edital
            driver.get(url_lista)
            time.sleep(5)

        if achados_por_edital:
            enviar_email_alerta(achados_por_edital)
        else:
            print("\n[-] Nenhum lote com celulares ou TVs foi encontrado nos editais do Galeão.")

    except Exception as e:
        print(f"[!] Erro durante a execução do agente: {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    buscar_itens()
