import numpy as np
from pedalboard import Pedalboard, Reverb, Delay

class ReverbControl:
    def __init__(self, 
                 sample_rate, 
                 initial_room_size = 0.85, 
                 initial_damping = 0.2, 
                 initial_wet_level = 0.0, 
                 initial_delay_seconds = 0.6, 
                 initial_delay_feedback = 0.65, 
                 initial_delay_mix = 0.0):
        """
        Inicializa o controlador de Reverb e delay.

        Args:
            sample_rate (int): A taxa de amostragem do áudio.
            initial_room_size (float): Tamanho da sala inicial para o reverb (0.0 a 1.0).
            initial_damping (float): Amortecimento inicial do reverb (0.0 a 1.0).
            initial_wet_level (float): Nível de 'wet' (efeito) inicial (0.0 a 1.0).
        """
        if sample_rate <= 0:
            raise ValueError("A taxa de amostragem (sample_rate) deve ser positiva.")
            
        self.sample_rate = sample_rate

        # 1. Efeito de Reverb
        self.reverb_effect = Reverb(
            room_size = initial_room_size,
            damping = initial_damping,
            wet_level = initial_wet_level,
            dry_level = 1.0 - initial_wet_level, # Começa com o dry_level complementar
            width = 0.9 # Reverb mais amplo
        )

        # 2. Efeito de Delay
        self.delay_effect = Delay(
            delay_seconds=initial_delay_seconds,
            feedback=initial_delay_feedback,
            mix=initial_delay_mix  # Começa com o delay desligado (mix = 0)
        )

        # O Pedalboard pode conter múltiplos efeitos. Por agora, apenas o reverb.
        self.effects_board = Pedalboard([self.reverb_effect, self.delay_effect])
        print(f"Controlador de Efeitos (Reverb, Delay) inicializado. SR: {self.sample_rate} Hz")

    def set_wet_level(self, wet_level):
        """
        Define o nível de 'wet' (quantidade de efeito) do reverb.

        Args:
            wet_level (float): Nível de 'wet' entre 0.0 (totalmente seco) e 1.0 (totalmente molhado).
        """
        wet_level = np.clip(wet_level, 0.0, 1.0) # Garante que o valor esteja entre 0 e 1
        self.reverb_effect.wet_level = wet_level
        self.reverb_effect.dry_level = 1.0 - wet_level # Mantém o nível de saída total consistente

    def update_reverb_parameters(self, room_size=None, damping=None, width=None):
        """
        Atualiza outros parâmetros do reverb.

        Args:
            room_size (float, optional): Tamanho da sala (0.0 a 1.0).
            damping (float, optional): Amortecimento (0.0 a 1.0).
            width (float, optional): Largura do estéreo do reverb (0.0 a 1.0).
        """
        if room_size is not None:
            self.reverb_effect.room_size = np.clip(room_size, 0.0, 1.0)
        if damping is not None:
            self.reverb_effect.damping = np.clip(damping, 0.0, 1.0)
        if width is not None:
            self.reverb_effect.width = np.clip(width, 0.0, 1.0)

    # --- Métodos para Delay ---
    def set_delay_mix(self, mix_level):
        """ Define o nível de 'mix' (quantidade de efeito) do delay. """
        mix_level = np.clip(mix_level, 0.0, 1.0) # O mix do delay geralmente não passa muito de 0.5-0.7 para ser usual
        self.delay_effect.mix = mix_level

    def update_delay_parameters(self, delay_seconds=None, feedback=None):
        """ Atualiza outros parâmetros do delay. """
        if delay_seconds is not None:
            # Limites de exemplo para tempo de delay
            self.delay_effect.delay_seconds = np.clip(delay_seconds, 0.01, 4.0) 
        if feedback is not None:
            # Feedback < 1.0 para evitar auto-oscilação infinita
            self.delay_effect.feedback = np.clip(feedback, 0.0, 0.95)

    def process(self, audio_chunk_input):
        """
        Processa um chunk de áudio, aplicando o efeito de reverb.

        Args:
            audio_chunk_input (np.ndarray): O chunk de áudio de entrada (float32).
                                           Pode ser mono (samples,) ou estéreo (samples, channels).

        Returns:
            np.ndarray: O chunk de áudio processado com reverb.
                        Retorna o chunk original se ocorrer um erro.
        """
        if not isinstance(audio_chunk_input, np.ndarray):
            print("Erro no ReverbControl: Input não é um array NumPy.")
            return audio_chunk_input

        # Garante que o input seja float32, pois pedalboard espera isso
        audio_chunk = audio_chunk_input.astype(np.float32)

        # Pedalboard espera (samples, channels). Se for mono (samples,), converte.
        if audio_chunk.ndim == 1:
            # Converte mono para (samples, 1) para o pedalboard
            reverb_input = audio_chunk[:, np.newaxis]
        elif audio_chunk.ndim == 2:
            reverb_input = audio_chunk
        else:
            print("Erro no ReverbControl: Formato de áudio inesperado.")
            return audio_chunk_input # Retorna o original se o formato for inválido

        try:
            # Processa o áudio. A taxa de amostragem do board já foi definida.
            # O segundo argumento para board() é a taxa de amostragem DO CHUNK ATUAL,
            # que deve ser a mesma com a qual o board foi inicializado para evitar reamostragem.
            processed_chunk = self.effects_board(reverb_input, self.sample_rate)
            
            # Se o input era mono (samples,1) e o reverb produziu estéreo (samples,2),
            # e quisermos manter mono, podemos pegar um canal ou mixar.
            # No entanto, o efeito Reverb do pedalboard geralmente mantém o número de canais do input.
            # Se o input for (samples,1), a saída será (samples,1).
            # Se o input for (samples,2), a saída será (samples,2).

            # Se o input original era mono 1D, retorna mono 1D
            if audio_chunk_input.ndim == 1 and processed_chunk.ndim == 2 and processed_chunk.shape[1] == 1:
                return processed_chunk[:, 0] # Converte de volta para (samples,)
            
            return processed_chunk
        
        except Exception as e:
            print(f"Erro inesperado no ReverbControl.process: {e}")
            return audio_chunk_input # Retorna o original em caso de erro