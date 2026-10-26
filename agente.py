import os
import time
import re
import subprocess
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

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
# DETECÇÃO DE VERSÃO E INICIALIZAÇÃO DO DRIVER
# ==============================================================================
def obter_versao_chrome():
    """Identifica a versão major do Google Chrome instalado no sistema via subprocess."""
    try:
        out = subprocess.check_output(["google-chrome", "--version"]).decode("utf-8")
        match = re.search(r"Google Chrome (\d+)\.", out)
        if match:
            versao_major = int(match.group(1))
            print(f"[-] Versão do Google Chrome detectada no sistema: {versao_major}")
            return versao_major
    except Exception as e:
        print(f"[!] Não foi possível detectar a versão via subprocess: {e}")
    return None

def inicializar_driver():
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    versao_chrome = obter_versao_chrome()
    
    # Força o undetected-chromedriver a usar a mesma versão major do browser
    if versao_chrome:
        driver = uc.Chrome(options=options, version_main=versao_chrome)
    else:
        driver = uc.Chrome(options=options)
        
    return driver

def contem_palavras_chave(texto):
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in PALAVRAS_CHAVE)

# ==============================================================================
# ENVIO DE E-MAIL
# ==============================================================================
def enviar_email_alerta(itens_encontrados):
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: Variáveis de e-mail não configuradas. Notificação ignorada.")
        return

    try:
        mensagem = MIMEMultipart()
        mensagem["From"] = EMAIL_ORIGEM
        mensagem["To"] = EMAIL_DESTINO
        mensagem["Subject"] = f"Alerta Leilão RF: {len(itens_encontrados)} lote(s) encontrado(s)"

        corpo = f"Foram encontrados {len(itens_encontrados)} lote(s)/item(ns) de interesse na Receita Federal:\n\n"
        for idx, item in enumerate(itens_encontrados, 1):
            corpo += f"--- Lote/Item {idx} ---\n{item}\n\n"
        
        corpo += f"\nAcesse o portal: {URL_EDITAIS}"
        mensagem.attach(MIMEText(corpo, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ORIGEM, SENHA_APP)
        server.send_message(mensagem)
        server.quit()
        print(f"[+] Alerta de e-mail enviado com sucesso para {EMAIL_DESTINO}")
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
        print(f"[!] Erro durante o scraping: {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    buscar_itens()
