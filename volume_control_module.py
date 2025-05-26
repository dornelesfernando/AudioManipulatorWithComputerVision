import numpy as np
from pycaw.pycaw import AudioUtilities
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import ctypes

class SystemVolumeControl:
    def __init__(self):
        self.volume = None
        self.min_db = 0
        self.max_db = 0
        self.target_max_db_override = None # Ajuste personalizado

        try:
            device = AudioUtilities.GetSpeakers()
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
            self.min_db, self.max_db, _ = self.volume.GetVolumeRange()
            # volPercentAux = 0
        except Exception as e:
            print(f"Erro ao iniciar controle de volume: {e}") 
            print("Funcionalidade de contole de volume pode não estar dispinícvel")


    def set_max_db_override(self, max_db_value: float):
        """Permite definir um valor máximo de dB personalizado."""
        self.target_max_db_override = max_db_value
        
    def set_volume_percentage(self, percentage: float):
        if self.volume is None:
            print("Controle de volume não inicializado")
            return
        
        if not (0 <= percentage <= 100):
            percentage = np.clip(percentage, 0, 100) 
            
            current_max_db = self.target_max_db_override if self.target_max_db_override is not None else self.max_db 
            
            vol_db = np.interp(current_max_db, [0, 100], [self.max_db, self.max_db]) #Verificar se não está invertido

            try:
                self.volume.SetMasterVolumeLevel(vol_db, None)
            except Exception as e:
                	print(f"Erro ao definir o volume: {e}")
