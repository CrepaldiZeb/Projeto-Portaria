import requests
import time
import os
import pygame

# Configurações gerais
BASE_URL = "http://localhost:7851/api"  
DOWNLOAD_BASE_URL = "http://localhost:7851"  # URL base para arquivos
MODEL_NAME = "xtts"
VOICE = "female_07.wav"
LANGUAGE = "pt"
SPEED = 1.1
TEMPERATURE = 1.0
TIMEOUT_SECONDS = 60

def check_server_ready():
    """Verifica se o servidor TTS está pronto com timeout."""
    print("Verificando se o servidor está pronto...")
    start_time = time.time()
    while True:
        try:
            response = requests.get(f"{BASE_URL}/ready", timeout=5)
            if response.status_code == 200 and response.text.strip().lower() == "ready":
                print("Servidor pronto!")
                break
            else:
                print("Aguardando o servidor iniciar...")
        except requests.exceptions.RequestException as e:
            print(f"Erro na conexão: {e}")

        time.sleep(2)
        if time.time() - start_time > TIMEOUT_SECONDS:
            print("Timeout: O servidor não respondeu dentro do tempo limite.")
            exit(1)

def switch_deepspeed(enable=True):
    """Ativa ou desativa o modo DeepSpeed."""
    params = {"new_deepspeed_value": str(enable).lower()}
    response = requests.post(f"{BASE_URL}/deepspeed", params=params)
    if response.status_code == 200:
        print("DeepSpeed ativado com sucesso.")
    else:
        print(f"Falha ao ativar DeepSpeed: {response.text}")

def download_file(file_url, output_name):
    """Faz o download do arquivo de áudio do servidor."""
    try:
        response = requests.get(file_url, timeout=10)
        if response.status_code == 200:
            with open(output_name, "wb") as f:
                f.write(response.content)
            print(f"Arquivo salvo em: {output_name}")
            return True
        else:
            print(f"Erro ao baixar o arquivo: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Erro ao baixar o arquivo: {e}")
        return False

def generate_speech(text):
    """Gera fala e faz download do arquivo via URL retornada pela API."""
    print("Gerando fala...")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data_payload = {
        "text_input": text,
        "text_filtering": "none",
        "character_voice_gen": VOICE,
        "rvccharacter_voice_gen": "Disabled",
        "language": LANGUAGE,
        "speed": SPEED,
        "temperature": TEMPERATURE,
        "output_file_name": "output",
        "output_file_timestamp": False
    }
    try:
        response = requests.post(f"{BASE_URL}/tts-generate", headers=headers, data=data_payload, timeout=1000)
        if response.status_code == 200:
            result = response.json()
            file_url = f"{DOWNLOAD_BASE_URL}{result['output_file_url']}"
            print(f"Baixando arquivo de: {file_url}")
            if download_file(file_url, "output.wav"):
                print("Download concluído com sucesso.")
            else:
                print("Erro: Não foi possível baixar o arquivo de áudio.")
        else:
            print(f"Erro ao gerar fala: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Erro ao gerar fala: {e}")


def play_audio():
    pygame.mixer.init()
    pygame.mixer.music.load("output.wav")
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        continue

    pygame.mixer.quit()

def initialize():
    check_server_ready()
    switch_deepspeed(True)
    texto = "Hi"
    generate_speech(texto)
