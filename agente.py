import os
import time
import re
import ssl
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

# Dicionário de busca focado em equipamentos de TI, informática e eletrônicos
PALAVRAS_CHAVE = [
    r'\bcelular\b', r'\bsmartphone\b', r'\biphone\b', r'\bsamsung\b', r'\bxiaomi\b',
    r'\btv\b', r'\btelevisao\b', r'\btelevisor\b', r'\bsmart tv\b',
    r'\bnotebook\b', r'\blaptop\b', r'\bmacbook\b', r'\bcomputador\b', r'\bpc\b',
    r'\btablet\b', r'\bipad\b', r'\bmonitor\b', r'\bplaca de video\b', r'\bgpu\b',
    r'\brtx\b', r'\bgtx\b', r'\brazen\b', r'\bryzen\b', r'\bintel\b',
    r'\bprocessador\b', r'\bmemoria ram\b', r'\bssd\b', r'\bhd externo\b',
    r'\bplaystation\b', r'\bps4\b', r'\bps5\b', r'\bxbox\b', r'\bnintendo\b',
    r'\broteador\b', r'\bperifericos\b', r'\bheadset\b', r'\bteclado\b', r'\bmouse\b'
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
    
    # Burlar detecção padrão de bot no Selenium
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
# ENVIO DE E-MAIL DE ALERTA (SMTP STARTTLS NA PORTA 587 COM REENTREGA)
# ==============================================================================
def enviar_email_alerta(achados):
    if not (EMAIL_ORIGEM and SENHA_APP and EMAIL_DESTINO):
        print("[!] ATENÇÃO: Variáveis EMAIL_ORIGEM, SENHA_APP ou EMAIL_DESTINO não configuradas no ambiente.")
        return

    mensagem = MIMEMultipart()
    mensagem["From"] = EMAIL_ORIGEM.strip()
    mensagem["To"] = EMAIL_DESTINO.strip()
    
    total_lotes = sum(len(lotes) for lotes in achados.values())
    mensagem["Subject"] = f"Alerta Leilão RF (Informática): {total_lotes} lote(s) encontrado(s)"

    corpo = f"Foram encontrados {total_lotes} lote(s) com itens de informática/eletrônicos nos editais abertos:\n\n"
    
    for edital, lotes in achados.items():
        corpo += f"=========================================\n"
        corpo += f"EDITAL: {edital}\n"
        corpo += f"=========================================\n"
        for idx, lote in enumerate(lotes, 1):
            corpo += f"  Lote {idx}:\n  {lote}\n\n"
    
    corpo += f"\nAcesse o portal diretamente em: {URL_EDITAIS}"
    mensagem.attach(MIMEText(corpo, "plain"))

    # Sanitização da senha
    senha_limpa = str(SENHA_APP).strip().replace(" ", "")
    contexto_ssl = ssl.create_default_context()

    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        try:
            print(f"[-] Conectando ao SMTP do Gmail via STARTTLS (smtp.gmail.com:587) [Tentativa {tentativa}/{max_tentativas}]...")
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.ehlo()
                server.starttls(context=contexto_ssl)
                server.ehlo()
                server.login(EMAIL_ORIGEM.strip(), senha_limpa)
                server.send_message(mensagem)
                
            print(f"[+] Alerta enviado com sucesso para {EMAIL_DESTINO}")
            break
        except Exception as e:
            print(f"[!] Tentativa {tentativa} falhou: {e}")
            if tentativa < max_tentativas:
                time.sleep(3)
            else:
                print(f"[!] Erro definitivo ao enviar e-mail após {max_tentativas} tentativas.")

# ==============================================================================
# PROCESSAMENTO DE LOTES DENTRO DE UM EDITAL
# ==============================================================================
def extrair_lotes_do_edital(driver, nome_edital):
    time.sleep(8)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    blocos = soup.find_all(['tr', 'div', 'article'], class_=re.compile(r'(lote|card|item|linha|row)', re.I))
    if not blocos:
        blocos = soup.find_all(['div', 'section'])

    lotes_encontrados = []
    textos_vistos = set()

    for bloco in blocos:
        texto = bloco.get_text(separator=" ", strip=True)
        if 30 < len(texto) < 1200 and texto not in textos_vistos:
            if contem_palavras_chave(texto):
                lotes_encontrados.append(texto)
                textos_vistos.add(texto)

    print(f"  [->] Edital '{nome_edital}': {len(lotes_encontrados)} lote(s) de informática localizados.")
    return lotes_encontrados

# ==============================================================================
# EXECUÇÃO DO SCRAPING
# ==============================================================================
def buscar_itens():
    print(f"[-] Acessando o portal de editais da Receita Federal: {URL_EDITAIS}")
    driver = inicializar_driver()
    achados_por_edital = {}

    try:
        driver.get(URL_EDITAIS)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(10)

        # Mapeia todos os links de editais disponíveis
        links_editais = driver.find_elements(By.XPATH, "//a[contains(@href, 'edital') or contains(@href, 'lote') or contains(text(), 'Edital') or contains(text(), 'EDITAL')]")
        
        if not links_editais:
            links_editais = driver.find_elements(By.TAG_NAME, "a")

        urls_ou_elementos = []
        for el in links_editais:
            href = el.get_attribute("href")
            texto = el.text.strip() or "Edital Sem Nome"
            if href and "javascript" not in href:
                urls_ou_elementos.append((texto, href, el))

        # Remove links duplicados
        urls_unicas = list({href: (texto, href, el) for texto, href, el in urls_ou_elementos}.values())

        print(f"[+] Total de editais abertos localizados: {len(urls_unicas)}")

        if not urls_unicas:
            print("[-] Nenhum edital foi localizado na página principal.")
            return

        url_lista = driver.current_url

        for idx, (nome, href, elemento) in enumerate(urls_unicas, 1):
            print(f"\n[-] Inspecionando edital {idx}/{len(urls_unicas)}: {nome[:60]}")
            
            try:
                driver.get(href)
                lotes = extrair_lotes_do_edital(driver, nome)
                if lotes:
                    achados_por_edital[nome] = lotes

            except Exception as err_edital:
                print(f"[!] Erro ao processar o edital '{nome}': {err_edital}")
            
            driver.get(url_lista)
            time.sleep(5)

        if achados_por_edital:
            enviar_email_alerta(achados_por_edital)
        else:
            print("\n[-] Nenhum lote com itens de informática foi localizado nos editais abertos.")

    except Exception as e:
        print(f"[!] Erro durante a execução do agente: {e}")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    buscar_itens()
