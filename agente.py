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
# As credenciais são lidas diretamente dos GitHub Secrets
EMAIL_ORIGEM = os.getenv("EMAIL_ORIGEM")
SENHA_APP = os.getenv("SENHA_APP")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")

# Palavras-chave monitoradas nos editais e lotes
PALAVRAS_CHAVE = [
    r'\bcelular\b', r'\bsmartphone\b', r'\biphone\b', r'\bsamsung\b', r'\bxiaomi\b',
    r'\btv\b', r'\btelevisao\b', r'\btelevisor\b', r'\bsmart tv\b'
]

URL_EDITAIS = "https://www25.receita.fazenda.gov.br/sle-sociedade/portal/editais-disponiveis"

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================
def inicializar_driver():
    """Configura o Google Chrome para execução em contêineres e CI/CD."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def contem_palavras_chave(texto):
    """Verifica se o texto do lote possui alguma das palavras-chave monitoradas."""
    texto_lower = texto.lower()
    return any(re.search(p, texto_lower) for p in PALAVRAS_CHAVE)

def enviar_email_alerta(itens_encontrados):
    """Envia notificação via e-mail utilizando servidor SMTP do Gmail."""
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: As variáveis EMAIL_ORIGEM, SENHA_APP e EMAIL_DESTINO não foram fornecidas. O e-mail não será enviado.")
        return

    try:
        mensagem = MIMEMultipart()
        mensagem["From"] = EMAIL_ORIGEM
        mensagem["To"] = EMAIL_DESTINO
        mensagem["Subject"] = f"Alerta Leilão Receita Federal: {len(itens_encontrados)} lote(s) encontrado(s)"

        corpo = f"Foram encontrados {len(itens_encontrados)} lote(s)/item(ns) de interesse nos editais disponíveis:\n\n"
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
        print(f"[!] Erro ao enviar e-mail de alerta: {e}")

# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================
def buscar_itens():
    print(f"[-] Acessando o portal da Receita Federal: {URL_EDITAIS}")
    driver = inicializar_driver()

    try:
        driver.get(URL_EDITAIS)
        wait = WebDriverWait(driver, 20)
        
        # Aguarda o carregamento dos cards/elementos dos editais na página
        wait.until(EC.presence_of_element_located((
            By.XPATH, "//div[contains(@class, 'card') or contains(@class, 'edital') or contains(text(), 'Edital')]"
        )))
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        cards = soup.find_all(['div', 'tr'], class_=re.compile(r'(card|item|linha|row)', re.I))
        
        lotes_relevantes = []
        for card in cards:
            texto_card = card.get_text(separator=" ", strip=True)
            if contem_palavras_chave(texto_card):
                lotes_relevantes.append(texto_card)

        print(f"[+] Total de lotes/itens relevantes encontrados: {len(lotes_relevantes)}")

        if lotes_relevantes:
            for idx, item in enumerate(lotes_relevantes, 1):
                print(f"\n[Item {idx}]: {item[:150]}...")
            
            enviar_email_alerta(lotes_relevantes)
        else:
            print("[-] Nenhum item contendo celulares ou TVs foi localizado nesta verificação.")

    except Exception as e:
        print(f"[!] Erro durante o scraping: {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    buscar_itens()
