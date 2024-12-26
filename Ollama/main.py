import requests
import sys
import os


tts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../Text_to_Speech/all_talk/Docker'))

if tts_path not in sys.path:
    sys.path.insert(0, tts_path)

import tts


def main():
    tts.initialize()
    url = "http://localhost:11434/"

    while True:
        prompt = input("Digite o prompt para o llm: ")


        response = requests.post(url + "api/generate", json={
            "model": "llama3.2",
            "prompt": prompt,
            "stream": False
        })


        if response.status_code == 200:
            tts.generate_speech(response.json()['response'])
            tts.play_audio()

        else:
            print("\nErro ao gerar fala")
        
        saida = input("\nDeseja sair? (s/n)\n")
        if saida == "s":
            break

main()