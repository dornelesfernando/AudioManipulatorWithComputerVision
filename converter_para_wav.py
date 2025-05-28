import os
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

def converter_audio_para_wav(caminho_arquivo_entrada, caminho_arquivo_saida = None):
    """
    Converte um arquivo de áudio para o formato WAV.

    Args:
        caminho_arquivo_entrada (str): O caminho para o arquivo de áudio de entrada.
        caminho_arquivo_saida (str, optional): O caminho para salvar o arquivo WAV de saída.
            Se None, o arquivo WAV será salvo na mesma pasta do arquivo de entrada
            com o mesmo nome, mas com a extensão .wav.

    Returns:
        str: O caminho para o arquivo WAV gerado, ou None se a conversão falhar.
    """
    if not os.path.exists(caminho_arquivo_entrada):
        print(f"Erro: Arquivo de entrada não encontrado em '{caminho_arquivo_entrada}'")
        return None

    nome_base, extensao_original = os.path.splitext(caminho_arquivo_entrada)

    if caminho_arquivo_saida is None:
        caminho_arquivo_saida = nome_base + ".wav"
    elif not caminho_arquivo_saida.lower().endswith(".wav"):
        # Garante que o arquivo de saída tenha a extensão .wav
        # Poderia também criar a pasta se ela não existir com os.makedirs(os.path.dirname(caminho_arquivo_saida), exist_ok=True)
        print("Aviso: O caminho de saída não termina com .wav. A extensão .wav será usada.")
        base_saida, _ = os.path.splitext(caminho_arquivo_saida)
        caminho_arquivo_saida = base_saida + ".wav"


    try:
        print(f"Carregando '{caminho_arquivo_entrada}'...")
        # Tenta carregar o áudio. pydub tentará detectar o formato.
        # Para formatos específicos como webm, pode ser útil especificar: format="webm"
        # Mas geralmente a autodeterminação funciona se o FFmpeg estiver configurado.
        audio = AudioSegment.from_file(caminho_arquivo_entrada)
        
        print(f"Convertendo para WAV e salvando em '{caminho_arquivo_saida}'...")
        # Exporta o áudio para o formato WAV
        # Parâmetros comuns para WAV: format="wav", codec="pcm_s16le"
        audio.export(caminho_arquivo_saida, format="wav", codec="pcm_s16le")
        
        print("Conversão concluída com sucesso!")
        return caminho_arquivo_saida
        
    except CouldntDecodeError:
        print(f"Erro: Não foi possível decodificar o arquivo '{caminho_arquivo_entrada}'.")
        print("Verifique se o arquivo é um formato de áudio válido e se o FFmpeg está instalado e no PATH do sistema.")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a conversão: {e}")
        return None

if __name__ == "__main__":
    print("--- Conversor de Áudio para WAV ---")
    
    arquivo_entrada = input("Digite o caminho completo para o arquivo de áudio que você quer converter (ex: music/Addicted.webm): ")

    caminho_wav_gerado = converter_audio_para_wav(arquivo_entrada)

    if caminho_wav_gerado:
        print(f"\nArquivo WAV gerado: {caminho_wav_gerado}")
        print("Agora você pode usar este arquivo .wav no seu programa principal.")
    else:
        print("\nA conversão falhou.")