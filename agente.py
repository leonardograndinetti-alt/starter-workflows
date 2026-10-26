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
    # Usar modo Headless Moderno
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # Burlar detecção padrão de automação
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # Ocultar o atributo navigator.webdriver via CDP (Chrome DevTools Protocol)
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
def enviar_email_alerta(itens_encontrados):
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: Variáveis de e-mail não configuradas. Notificação não enviada.")
        return

    try:
        mensagem = MIMEMultipart()
        mensagem["From"] = EMAIL_ORIGEM
        mensagem["To"] = EMAIL_DESTINO
        mensagem["Subject"] = f"Alerta Leilão RF: {len(itens_encontrados)} lote(s) encontrado(s)"

        corpo = f"Foram encontrados {len(itens_encontrados)} lote(s)/item(ns) de interesse na Receita Federal:\n\n"
        for idx, item in enumerate(itens_encontrados, 1):
            corpo += f"--- Lote/Item {idx} ---\n{item}\n\n"
        
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
# EXECUÇÃO DO SCRAPING
# ==============================================================================
def buscar_itens():
    print(f"[-] Acessando o portal da Receita Federal: {URL_EDITAIS}")
    driver = inicializar_driver()

    try:
        driver.get(URL_EDITAIS)
        
        # Aguarda a página carregar o elemento body
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Faz uma busca ampla em blocos e tabelas
        elementos = soup.find_all(['div', 'tr', 'li', 'article'])
        
        lotes_relevantes = []
        elementos_vistos = set()

        for el in elementos:
            texto = el.get_text(separator=" ", strip=True)
            if 20 < len(texto) < 1000 and texto not in elementos_vistos:
                if contem_palavras_chave(texto):
                    lotes_relevantes.append(texto)
                    elementos_vistos.add(texto)

        print(f"[+] Total de lotes/itens encontrados: {len(lotes_relevantes)}")

        if lotes_relevantes:
            for idx, item in enumerate(lotes_relevantes, 1):
                print(f"\n[Item {idx}]: {item[:150]}...")
            enviar_email_alerta(lotes_relevantes)
        else:
            print("[-] Nenhum lote contendo celulares ou TVs foi localizado nesta verificação.")

    except Exception as e:
        print(f"[!] Erro durante a execução do scraping: {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    buscar_itens()
