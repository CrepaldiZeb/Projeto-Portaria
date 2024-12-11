import torch
import whisper
from faster_whisper import WhisperModel
import whisperx
import os
import time
import sys

# Função auxiliar para limpar o console
def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

def check_gpu(output):
    """Verifica se a GPU está disponível."""
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        output.append(f"✅ GPU encontrada: {gpu_name}")
        return "cuda"
    else:
        output.append("❌ GPU não encontrada. Usando CPU.")
        return "cpu"

def transcribe_with_openai_whisper(audio_path, device, output):
    """Transcrição usando o OpenAI Whisper."""
    start_time = time.time()
    model = whisper.load_model("medium", device=device)
    result = model.transcribe(audio_path, language="pt")
    end_time = time.time()
    output.append(f"\n### Transcrição com OpenAI Whisper ###")
    output.append(f"Tempo de Inferência: {end_time - start_time:.2f} segundos")
    output.append(f"Transcrição: {result['text']}")
    return result['text']

def transcribe_with_faster_whisper(audio_path, device, output):
    """Transcrição usando Faster Whisper."""
    start_time = time.time()
    model = WhisperModel("medium", device=device)
    segments, _ = model.transcribe(audio_path, language="pt")
    transcription = " ".join(segment.text for segment in segments)
    end_time = time.time()
    output.append("\n### Transcrição com Faster Whisper ###")
    output.append(f"Tempo de Inferência: {end_time - start_time:.2f} segundos")
    output.append(f"Transcrição: {transcription}")
    return transcription

def transcribe_with_whisperx(audio_path, device, output):
    """Transcrição usando WhisperX."""
    start_time = time.time()
    model = whisperx.load_model("medium", device=device, compute_type="float16")
    audio = whisperx.load_audio(audio_path)
    transcription_result = model.transcribe(audio, batch_size=8, language="pt")
    transcription = " ".join(segment['text'] for segment in transcription_result['segments'])
    end_time = time.time()
    output.append("\n### Transcrição com WhisperX ###")
    output.append(f"Tempo de Inferência: {end_time - start_time:.2f} segundos")
    output.append(f"Transcrição: {transcription}")
    return transcription

def main():
    """Função principal."""
    output = []  # Pilha para armazenar todas as saídas
    device = check_gpu(output)

    # Solicitar o nome do arquivo de áudio
    audio_files = ["Teste1.m4a", "Teste2.m4a", "Teste3.m4a"]
    for audio_file in audio_files:
        output.append(f"Teste: {audio_file}\n")
        if not os.path.isfile(audio_file):
            output.append(f"❌ Arquivo '{audio_file}' não encontrado! Coloque o arquivo no diretório atual e tente novamente.")
            clear_console()
            print("\n".join(output))
            return

        # Transcrevendo o áudio com os três modelos
        output.append(f"\nArquivo de áudio utilizado: {audio_file}")
        transcribe_with_openai_whisper(audio_file, device, output)
        transcribe_with_faster_whisper(audio_file, device, output)
        transcribe_with_whisperx(audio_file, device, output)

        # Limpar console e imprimir resultados finais
    clear_console()
    print("\n".join(output))

if __name__ == "__main__":
    main()
