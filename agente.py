import os
import time
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
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
# INICIALIZAÇÃO DO DRIVER COM UN DETECTED-CHROMEDRIVER + WEBDRIVER-MANAGER
# ==============================================================================
def inicializar_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # O ChromeDriverManager baixa e alinha o binário do ChromeDriver na versão exata do Chrome instalado
    driver_path = ChromeDriverManager().install()
    print(f"[-] ChromeDriver alinhado via webdriver-manager em: {driver_path}")
    
    driver = uc.Chrome(options=options, driver_executable_path=driver_path)
    return driver

def contem_palavras_chave(texto):
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in PALAVRAS_CHAVE)

# ==============================================================================
# ENVIO DE E-MAIL DE ALERTA
# ==============================================================================
def enviar_email_alerta(itens_encontrados):
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: Variáveis de e-mail não configuradas no ambiente. Notificação não enviada.")
        return

    try:
        mensagem = MIMEMultipart()
        mensagem["From"] = EMAIL_ORIGEM
        mensagem["To"] = EMAIL_DESTINO
        mensagem["Subject"] = f"Alerta Leilão RF: {len(itens_encontrados)} lote(s) encontrado(s)"

        corpo = f"Foram encontrados {len(itens_encontrados)} lote(s)/item(ns) de interesse no portal da Receita Federal:\n\n"
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
    print(f"[-] Acessando portal com undetected-chromedriver: {URL_EDITAIS}")
    driver = inicializar_driver()

    try:
        driver.get(URL_EDITAIS)
        # Aguarda a renderização das requisições assíncronas (Angular/SPA)
        time.sleep(12)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cards = soup.find_all(['div', 'tr', 'li'], class_=re.compile(r'(card|item|linha|row)', re.I))
        
        lotes_relevantes = []
        for card in cards:
            texto = card.get_text(separator=" ", strip=True)
            if contem_palavras_chave(texto) and texto not in lotes_relevantes:
                lotes_relevantes.append(texto)

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
