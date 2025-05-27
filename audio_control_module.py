import soundfile as sf
import numpy as np
import os

class AudioControl():
    def __init__(self):
        self.filepath = None
        self.audio_data = None
        self.sample_rate = None
        self.num_channels = None
        self.duration_seconds = None

    def load_audio(self, filepath, target_dtype='float32'):
        if not os.path.exists(filepath):
            print(f"Erro: Arquivo não encontrado em '{filepath}'")
            self._reset_attributes()
            return False
        
        try:
            # Lê arquivo de áudio
            audio_data, sample_rate = sf.read(filepath, dtype = target_dtype)

            self.filepath = filepath
            self.audio_data = audio_data
            self.sample_rate = sample_rate

            if self.audio_data.ndim == 1:
                self.num_chennels = 1 # Mono
            else:
                self.num_chennels = audio_data.shape[1] # Pega o número de colunas (canais)

            self.duration_seconds = len(self.audio_data) / self.sample_rate

            print(f"\n--- Informações do Áudio Carregado ---")
            print(f"Arquivo: {os.path.basename(self.filepath)}")
            print(f"Taxa de Amostragem (sample rate): {self.sample_rate} Hz")
            print(f"Número de Canais {self.num_chennels}")
            print(f"Duração: {self.duration_seconds:.2f} segundos")
            print(f"Tipo de Dadp (dtype): {self.audio_data.dtype}")
            print(f"Formato do Array (Shape): {self.audio_data.shape}")

            if audio_data.dtype == np.float32 or audio_data.dtype == np.float64:
                print(f"Valores (Min, Max): {np.min(self.audio_data):.4f}, {np.max(self.audio_data):.4f}")
            elif audio_data.dtype == np.float16:
                print(f"Valores (Min, Max): {np.min(self.audio_data)}, {np.max(self.audio_data)}")

            return True

        except sf.LibsndfileError as e:
            print(f"Erro ao ler o arquivo de áudio com soundfile: {e}")
            print(f"Verifique se o formato do arquivo é suportado ou se há dependências faltando (ex.: libsndfile, FFmpeg para MP3).")
            self._reset_attributes()
            return None, None, None
        except Exception as e:
            print(f"Ocorreu um erro inesperado ao carregar o áudio: {e}")
            self._reset_attributes()
            return None, None, None
    
    def _reset_attributes(self):
        self.filepath = None
        self.audio_data = None
        self.sample_rate = None
        self.num_channels = None
        self.duration_seconds = None

    def get_info(self):
        '''
        Retorna um dicionário com as informações de áudio carregado.
        '''

        if self.audio_data is None:
            return None
        
        return {
            "filepath": self.filepath,
            "sample_rate": self.sample_rate,
            "channels": self.num_channels,
            "duration": self.duration_seconds,
            "dtype": self.audio_data.dtype,
            "shape": self.audio_data.shape
        }
