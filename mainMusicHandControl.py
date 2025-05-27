import cv2
import time
import math
import os
import numpy as np
import sounddevice as sd

# Importando classes de módulos
from hand_detector_module import HandDetector
from volume_control_module import SystemVolumeControl
from audio_control_module import AudioControl

# --- Variáveis Globais para Reprodução de Áudio ---
current_playback_frame = 0
playback_active = False
audio_data_global = None
sample_rate_global = 0
playback_stream = None

# --- Função de Callback para reprodução de áudio ---
def audio_playback_callback(outdata, frames, time_info, status):
    global current_playback_frame, playback_active, audio_data_global, sample_rate_global

    if status:
        print(f"Status do stream de áudio: {status}")

    if playback_active and audio_data_global is not None:
        remaining_frames = len(audio_data_global) - current_playback_frame

        if remaining_frames >= frames:
            chunk = audio_data_global[current_playback_frame : current_playback_frame + frames]
            outdata[:] = chunk
            current_playback_frame += frames
        else: # Fim do áudio ou áudio restante menor que 'frames'
            if remaining_frames > 0: # Copia o que restou
                outdata[:remaining_frames] = audio_data_global[current_playback_frame : current_playback_frame + remaining_frames]
                outdata[remaining_frames:] = 0 # Preenche o resto com o silencio (Valor zerado para que não haja som)
            else:
                outdata[:] = 0 # Silencio

            # Reinicia para o loop (ou para, se não quiser loop)
            # Para que não esteja em loop deve-se comentar a linha abaixo e definir playback_active = false
            current_playback_frame = 0
            # playback_active = False
    else:
        outdata[:] = 0 # Preenche com silêncio se não estiver ativo ou sem áudio

if __name__ == '__main__':

    # --- CARREGAMENTO DO ÁUDIO ---
    audio_controller = AudioControl()
    audio_file_path = input("Digite o caminho para o seu arquivo de áudio (ex: sua_musica.wav): ")
    
    audio_loaded_successfully = audio_controller.load_audio(audio_file_path)
    if audio_loaded_successfully:
        print(f"Áudio '{os.path.basename(audio_file_path)}' carregado e pronto para uso.")
        audio_data_global = audio_controller.audio_data # Disponibiliza os dados globalmente
        sample_rate_global = audio_controller.sample_rate # Disponibiliza a taxa de amostragem globalmente
        playback_active = True # Ativa a reprodução

        try:
            # sd.default.samplerate = sample_rate_global # Opcional, mas pode ser bom
            sd.default.channels = audio_controller.num_channels # Define canais padrão

            playback_stream = sd.OutputStream(
                samplerate = sample_rate_global,
                channels = audio_controller.num_channels,
                callback = audio_playback_callback,
                dtype = audio_controller.audio_data.dtype
            )

            playback_stream.start()
            print(f"Stream de áudio inciado a {sample_rate_global} Hz, {audio_controller.num_channels} canal(is)")
        except Exception as e:
            print(f"Falha ao iniciar o stream de áudio: {e}")
            playback_active = False
            audio_loaded_successfully = False
    else:
        print(f"Falha ao carregar áudio. Reprodução de áudio desativada.")

    # --- CONFIGURAÇÃO DA CÂMERA ---
    wCam, hCam = 1920, 1080
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Erro ao abrir a câmera.")
        if playback_stream: playback_stream.close() # Fecha o Stream se a câmera falhar
        exit()
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, wCam)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, hCam)
    wCam_actual = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    hCam_actual = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Resolução da câmera: {wCam_actual}x{hCam_actual}")

    previousTime = 0

    # Inicializa o detector de mãos
    detector = HandDetector(number_hands = 2, min_detection_confidence = 0.7)

    volume_controller = SystemVolumeControl()
    if volume_controller.volume is None:
        print("Continuando sem controle de volume")

    # volume_controller.set_max_db_override(-25.0) # Controle de volume máximo personalizado

    # Faixa de distâncias para interpolação 
    HAND_DIST_MIN_ONE_HAND = 30
    HAND_DIST_MAX_ONE_HAND = 200
    HAND_DIST_MIN_TWO_HAND = 30
    HAND_DIST_MAX_TWO_HAND = 500

    volume_porcentage_display = 0

    # --- LOOP PRINCIPAL ---
    while True:
        # Incializa captura de imagem
        success, img = capture.read()
        if not success:
            print("Erro ao capturar imagem.")
            break

        # Espelha a tela
        img = cv2.flip(img, 1)

        # Encontra mãos e as desenha
        img = detector.find_hands(img, draw_hands = True)
        detected_hands_data = detector.find_positions(img, draw_points = False)

        if detected_hands_data:
            if len(detected_hands_data) == 1:
                hand_data = detected_hands_data[0]
                landmarks = hand_data.get("landmarks")
                
                if landmarks and len(landmarks) > 8:
                    x1, y1 = landmarks[4][1], landmarks[4][2]
                    x2, y2 = landmarks[8][1], landmarks[8][2]
                                    
                    cv2.circle(img, (x1, y1), 10, (255, 255, 0), cv2.FILLED)
                    cv2.circle(img, (x2, y2), 10, (255, 0, 255), cv2.FILLED)
                    cv2.line(img, (x1, y1), (x2, y2), (255, 255, 255), 3)
                    
                    length =  math.hypot(x2 - x1, y2 - y1)
                    # print(length)

                    if volume_controller.volume:
                        volume_porcentage_display = volume_controller.set_volume_percentage(length, HAND_DIST_MIN_ONE_HAND, HAND_DIST_MAX_ONE_HAND)

                    if length < HAND_DIST_MIN_ONE_HAND:
                        cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
            elif len(detected_hands_data) == 2:
                landmarks1 = detected_hands_data[0].get("landmarks")
                landmarks2 = detected_hands_data[1].get("landmarks")

                if (landmarks1 and len(landmarks1) > 8) and (landmarks2 and len(landmarks2) > 8):
                    # Captura das localizações dos pontos
                    h1x1, h1y1 = landmarks1[4][1], landmarks1[4][2]
                    h1x2, h1y2 = landmarks1[8][1], landmarks1[8][2]
                    h1cx, h1cy = (h1x1 + h1x2) // 2, (h1y1 + h1y2) // 2
                    cv2.circle(img, (h1cx, h1cy), 10, (255, 0, 0), cv2.FILLED)

                    h2x1, h2y1 = landmarks2[4][1], landmarks2[4][2]                
                    h2x2, h2y2 = landmarks2[8][1], landmarks2[8][2]  
                    h2cx, h2cy = (h2x1 + h2x2) // 2, (h2y1 + h2y2) // 2
                    cv2.circle(img, (h2cx, h2cy), 10, (255, 0, 0), cv2.FILLED)

                    # Volume
                    cv2.line(img, (h1cx, h1cy), (h2cx, h2cy), (255, 255, 255), 3)
                    
                    length =  math.hypot(h2cx - h1cx, h2cy - h1cy)
                    # print(length)

                    if volume_controller.volume:
                        volume_porcentage_display = volume_controller.set_volume_percentage(length, HAND_DIST_MIN_TWO_HAND, HAND_DIST_MAX_TWO_HAND)

                    if length < HAND_DIST_MIN_TWO_HAND:
                        cv2.line(img, (h1cx, h1cy), (h2cx, h2cy), (0, 255, 0), 3)

                    # Reverb
                    lengthReverb = math.hypot(h1x2 - h1x1, h1y2 - h1y1)
                    cv2.line(img, (h1x1, h1y1), (h1x2, h1y2), (255, 0, 0), 3)

                    # Pitch, Shift/Transposição
                    lengthTimbre = math.hypot(h2x2 - h2x1, h2y2 - h2y1)
                    cv2.line(img, (h2x1, h2y1), (h2x2, h2y2), (0, 0, 255), 3)
                
        # Framerate
        currentTime = time.time()
        fps = 1 / (currentTime - previousTime) if (currentTime - previousTime) != 0 else 0
        previousTime = currentTime
        cv2.putText(img, f"FPS: {int(fps)}", (30, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 1)
        
        # Apresentação do volume em tela
        cv2.putText(img, f"Vol: {int(volume_porcentage_display)}%", (30, 100), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 1)

        cv2.imshow("Hand Gesture Control", img)
        
        key = cv2.waitKey(20) & 0xFF
        if key == ord('q') or key == ord('Q'):
            break 

    # --- FINALIZAÇÃO ---
    print("Encerrando o programa...")
    if playback_stream is not None:
        print("Parando o stream de áudio")
        playback_stream.stop()
        playback_stream.close()
        print("Stream de áudio parado.")
        
    capture.release() # Libera a webCam
    cv2.destroyAllWindows() # Fecha as janelas abertas pelo OpenCV
    print("Recursos liberados. Fim.")