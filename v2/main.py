import cv2
import time
import math
import os
import sys
import numpy as np
import sounddevice as sd
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

# --- Configurações da Forma de Onda (Waveform) ---
WAVEFORM_HEIGHT_PX = 120 
WAVEFORM_WINDOW_DURATION_S = 3.0
WAVEFORM_COLOR = (255, 255, 255)
WAVEFORM_CENTER_LINE_COLOR = (255, 255, 255)
WAVEFORM_LINE_THICKNESS = 1

# --- Função de Callback para reprodução de áudio ---
def audio_playback_callback(outdata, frames, time_info, status):
    global current_playback_frame, playback_active, audio_data_global, sample_rate_global

    if status:
        if status.output_underflow: print("Alerta: Output underflow no stream de áudio!")
        if status.output_overflow: print("Alerta: Output overflow no stream de áudio!")
        # print(f"Status do stream de áudio: {status}") 

    if playback_active and audio_data_global is not None and sample_rate_global > 0:
        remaining_frames_in_song = len(audio_data_global) - current_playback_frame
        frames_to_process_from_song = min(frames, remaining_frames_in_song)

        if frames_to_process_from_song > 0:
            original_chunk = audio_data_global[current_playback_frame : current_playback_frame + frames_to_process_from_song]
            processed_chunk = original_chunk.astype(np.float32)
            
            # Bloco de efeitos removido pois 'effects_controller_global' não era utilizado.
            
            actual_processed_frames = len(processed_chunk)
            frames_to_fill_in_outdata = min(actual_processed_frames, frames)

            if frames_to_fill_in_outdata > 0:
                chunk_to_output = processed_chunk[:frames_to_fill_in_outdata]
                
                # Ajuste de canais (mono para estéreo ou vice-versa)
                if chunk_to_output.ndim == 1 and outdata.ndim == 2 and outdata.shape[1] == 2:
                    chunk_to_output = np.tile(chunk_to_output[:, np.newaxis], (1, 2))
                elif chunk_to_output.ndim == 2 and chunk_to_output.shape[1] == 2 and outdata.ndim == 1:
                    chunk_to_output = chunk_to_output[:, 0]
                elif chunk_to_output.ndim == 2 and chunk_to_output.shape[1] == 1 and outdata.ndim == 1:
                    chunk_to_output = chunk_to_output[:,0]

                try:
                    if chunk_to_output.shape[0] <= outdata.shape[0] and \
                       (chunk_to_output.ndim == outdata.ndim and \
                       (chunk_to_output.ndim == 1 or chunk_to_output.shape[1] == outdata.shape[1])):
                        outdata[:chunk_to_output.shape[0]] = chunk_to_output
                    else:
                        outdata[:frames_to_fill_in_outdata] = 0 
                except ValueError:
                    outdata[:frames_to_fill_in_outdata] = 0
            
            if frames_to_fill_in_outdata < frames:
                outdata[frames_to_fill_in_outdata:] = 0
            
            current_playback_frame += frames_to_process_from_song
            if current_playback_frame >= len(audio_data_global):
                current_playback_frame = 0 # Loop da música
        else:
            outdata[:] = 0
            current_playback_frame = 0
    else:
        outdata[:] = 0

if __name__ == '__main__':

    # --- CARREGAMENTO DO ÁUDIO ---
    audio_controller = AudioControl()
    
    # audio_file_path = input("Digite o caminho para o seu arquivo de áudio (ex: sua_musica.wav): ")
    MUSIC_DIR = "music"
    music_files = []

    if os.path.isdir(MUSIC_DIR):
        supported_formats = ('.wav', '.mp3', '.flac', '.ogg')
        music_files = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.lower().endswith(supported_formats)]
    
    if not music_files:
        print(f"ERRO: Nenhum arquivo de música encontrado em '{MUSIC_DIR}'. Coloque músicas na pasta e reinicie.")
        exit()

    print(f"Músicas encontradas: {len(music_files)}")

    audio_file_path = music_files[0] 
    audio_loaded_successfully = audio_controller.load_audio(audio_file_path)

    if audio_loaded_successfully:
        print(f"Áudio '{os.path.basename(audio_file_path)}' carregado e pronto para uso.")
        audio_data_global = audio_controller.audio_data
        sample_rate_global = audio_controller.sample_rate
                
        playback_active = True

        try:
            sd.default.channels = audio_controller.num_channels
            playback_stream = sd.OutputStream(
                samplerate=sample_rate_global,
                channels=audio_controller.num_channels,
                callback=audio_playback_callback, 
                dtype=audio_controller.audio_data.dtype,
                blocksize=1024 
            )
            playback_stream.start()
            print(f"Stream de áudio iniciado a {sample_rate_global} Hz, {audio_controller.num_channels} canal(is).")
        except Exception as e:
            print(f"Falha ao iniciar o stream de áudio: {e}")
            playback_active = False
            audio_loaded_successfully = False
    else:
        print(f"Falha ao carregar áudio. Funcionalidades de áudio desativadas.")
        exit()

    # --- CONFIGURAÇÃO DA CÂMERA ---
    wCam, hCam = 1920, 1080
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Erro ao abrir a câmera.")
        if playback_stream: playback_stream.close()
        exit()
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, wCam)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, hCam)
    wCam_actual = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    hCam_actual = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Resolução da câmera: {wCam_actual}x{hCam_actual}")

    previousTime = 0
    detector = HandDetector(number_hands=2, min_detection_confidence=0.7)
    volume_controller = SystemVolumeControl()
    if volume_controller.volume is None:
        print("Falha ao inicializar SystemVolumeControl.")

    # Faixas para gestos
    VOL_DIST_MIN_ONE_HAND = 30
    VOL_DIST_MAX_ONE_HAND = 80 # Renomeado de HAND_DIST_MAX_FINGERS_EFFECTS
    VOL_DIST_MIN_TWO_HANDS = 50
    VOL_DIST_MAX_TWO_HANDS = 300
    
    volume_percentage_display = 0.0

    app_mode = 'playback' # Modos: 'playback' ou 'selection'
    
    selected_song_index = 0 # Inicia na primeira música
    current_playing_index = 0 # Para saber qual está tocando
    selection_cooldown = 0
    SELECTION_COOLDOWN_TIME = 1.0 # 1 segundo de cooldown para "clicar"

    # --- Variáveis de Navegação (Scroll) ---
    navigation_cooldown = 0
    NAVIGATION_COOLDOWN_TIME = 0.5 # Cooldown mais rápido para scroll
    last_finger_y = 0
    NAVIGATION_Y_THRESHOLD = 30 # Pixels de movimento vertical para scrollar

    # --- Constantes da UI da Lista ---
    LIST_X_START = 100
    LIST_Y_CENTER = 70
    LIST_ITEM_HEIGHT = 30 # Espaçamento entre itens
    LIST_COLOR_PREV_NEXT = (180, 180, 180) # Cinza
    LIST_COLOR_CURRENT = (0, 255, 255) # Amarelo/Ciano
    LIST_COLOR_PLAYING = (0, 255, 0) # Verde para a que está tocando
    LIST_FONT_SCALE_PREV_NEXT = 0.5
    LIST_FONT_SCALE_CURRENT = 0.8
    LIST_FONT_THICKNESS_CURRENT = 1
    LIST_FONT_THICKNESS_PREV_NEXT = 1
    PINCH_THRESHOLD = 25 # Distância para "clicar"

    # --- NOVO: Variáveis de Troca de Modo por Gesto ---
    mode_toggle_cooldown = 0
    MODE_TOGGLE_COOLDOWN_TIME = 1.0 # 1 segundo de cooldown para evitar troca rápida
    MODE_TOGGLE_THRESHOLD = 35 # Distância para polegar-mindinho

    # --- LOOP PRINCIPAL ---
    while True:
        success, img = capture.read()
        if not success: break
        img = cv2.flip(img, 1)
        
        img = detector.find_hands(img, draw_hands=True)
        detected_hands_data = detector.find_positions(img, draw_points=False)

        # ======= CONTROLE DE TECLAS =======
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'): 
            break 
        elif key == ord('m'):
            if app_mode == 'playback':
                app_mode = 'selection'
                last_finger_y = 0
                print("Modo: Seleção de Música")
            else:
                app_mode = 'playback'
                print("Modo: Playback/Controle")

        gesture_detected = False
        # Só checa o gesto se o cooldown tiver passado
        if detected_hands_data and (currentTime - mode_toggle_cooldown > MODE_TOGGLE_COOLDOWN_TIME):
            for hand_data in detected_hands_data: # Checa em CADA mão
                landmarks = hand_data.get("landmarks")
                
                # Precisa de todos os 21 landmarks para checar o mindinho (índice 20)
                if landmarks and len(landmarks) > 20: 
                    x_thumb, y_thumb = landmarks[4][1], landmarks[4][2]
                    x_pinky, y_pinky = landmarks[20][1], landmarks[20][2]

                    length = math.hypot(x_pinky - x_thumb, y_pinky - y_thumb)

                    if length < MODE_TOGGLE_THRESHOLD:
                        # Feedback visual da troca de modo
                        cv2.line(img, (x_thumb, y_thumb), (x_pinky, y_pinky), (255, 0, 255), 4)
                        
                        gesture_detected = True
                        break # Encontrou o gesto, para o loop de mãos

        # Se o gesto foi detectado E o cooldown passou:
        if gesture_detected:
            mode_toggle_cooldown = currentTime # Aplica o cooldown
            
            # A lógica que antes era da tecla 'm' agora está aqui
            if app_mode == 'playback':
                app_mode = 'selection'
                last_finger_y = 0
                print("Modo: Seleção de Música")
            else:
                app_mode = 'playback'
                print("Modo: Playback/Controle")

        # --- Lógica de Modos ---
        # (O seu 'if app_mode == 'selection':' começa logo abaixo)
        font_face = cv2.FONT_HERSHEY_SIMPLEX

        if app_mode == 'selection':
            y_prev = LIST_Y_CENTER - LIST_ITEM_HEIGHT
            y_curr = LIST_Y_CENTER
            y_next = LIST_Y_CENTER + LIST_ITEM_HEIGHT

            # Desenha "Anterior" (se existir)
            if selected_song_index > 0:
                prev_song_name = os.path.basename(music_files[selected_song_index - 1])
                cv2.putText(img, prev_song_name, (LIST_X_START, y_prev), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)
                
            # Desenha "Anterior" (se existir)
            if selected_song_index > 1:
                prev_song_name = os.path.basename(music_files[selected_song_index - 2])
                cv2.putText(img, prev_song_name, (LIST_X_START, y_prev -25), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)

            # Desenha "Atual" (Sempre existe)
            curr_song_name = os.path.basename(music_files[selected_song_index])
            
            # Decide a cor: Verde se for a que está tocando, Amarela se for só a selecionada
            color_current = LIST_COLOR_PLAYING if selected_song_index == current_playing_index else LIST_COLOR_CURRENT
            
            # Adiciona indicadores de seleção
            cv2.putText(img, f"> {curr_song_name} <", (LIST_X_START, y_curr), font_face, 
                        LIST_FONT_SCALE_CURRENT, color_current, LIST_FONT_THICKNESS_CURRENT)

            # Desenha "Próxima" (se existir)
            if selected_song_index < len(music_files) - 1:
                next_song_name = os.path.basename(music_files[selected_song_index + 1])
                cv2.putText(img, next_song_name, (LIST_X_START, y_next), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)
                
            if selected_song_index < len(music_files) - 2:
                next_song_name = os.path.basename(music_files[selected_song_index + 2])
                cv2.putText(img, next_song_name, (LIST_X_START, y_next + 25), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)

        gesture_detected = False
        # Só checa o gesto se o cooldown tiver passado
        if detected_hands_data and (currentTime - mode_toggle_cooldown > MODE_TOGGLE_COOLDOWN_TIME):
            for hand_data in detected_hands_data: # Checa em CADA mão
                landmarks = hand_data.get("landmarks")
                
                # Precisa de todos os 21 landmarks para checar o mindinho (índice 20)
                if landmarks and len(landmarks) > 20: 
                    x_thumb, y_thumb = landmarks[4][1], landmarks[4][2]
                    x_pinky, y_pinky = landmarks[20][1], landmarks[20][2]

                    length = math.hypot(x_pinky - x_thumb, y_pinky - y_thumb)

                    if length < MODE_TOGGLE_THRESHOLD:
                        # Feedback visual da troca de modo
                        cv2.line(img, (x_thumb, y_thumb), (x_pinky, y_pinky), (255, 0, 255), 4)
                        
                        gesture_detected = True
                        break # Encontrou o gesto, para o loop de mãos

        # Se o gesto foi detectado E o cooldown passou:
        if gesture_detected:
            mode_toggle_cooldown = currentTime # Aplica o cooldown
            
            # A lógica que antes era da tecla 'm' agora está aqui
            if app_mode == 'playback':
                app_mode = 'selection'
                last_finger_y = 0
                print("Modo: Seleção de Música")
            else:
                app_mode = 'playback'
                print("Modo: Playback/Controle")

        # --- Lógica de Modos ---
        # (O seu 'if app_mode == 'selection':' começa logo abaixo)
        font_face = cv2.FONT_HERSHEY_SIMPLEX
        
        if app_mode == 'selection':
            # --- MODO DE SELEÇÃO DE MÚSICA (Mão 1 = Scroll, Mão 2 = Click) ---
            
            # 1. Desenhar a Lista (Anterior, Atual, Próxima)
            # (Esta parte da UI não muda)
            y_prev = LIST_Y_CENTER - LIST_ITEM_HEIGHT
            y_curr = LIST_Y_CENTER
            y_next = LIST_Y_CENTER + LIST_ITEM_HEIGHT

            if selected_song_index > 0:
                prev_song_name = os.path.basename(music_files[selected_song_index - 1])
                cv2.putText(img, prev_song_name, (LIST_X_START, y_prev), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)

            curr_song_name = os.path.basename(music_files[selected_song_index])
            color_current = LIST_COLOR_PLAYING if selected_song_index == current_playing_index else LIST_COLOR_CURRENT
            cv2.putText(img, f"> {curr_song_name} <", (LIST_X_START, y_curr), font_face, 
                        LIST_FONT_SCALE_CURRENT, color_current, LIST_FONT_THICKNESS_CURRENT)

            if selected_song_index < len(music_files) - 1:
                next_song_name = os.path.basename(music_files[selected_song_index + 1])
                cv2.putText(img, next_song_name, (LIST_X_START, y_next), font_face, 
                            LIST_FONT_SCALE_PREV_NEXT, LIST_COLOR_PREV_NEXT, LIST_FONT_THICKNESS_PREV_NEXT)

            # 2. Processar Gestos de Seleção
            if detected_hands_data:
                # --- MÃO 1 (SCROLL) ---
                # Assumimos que a primeira mão detectada (index 0) é a de scroll.
                hand_1_data = detected_hands_data[0]
                landmarks_1 = hand_1_data.get("landmarks")
                
                if landmarks_1 and len(landmarks_1) > 8:
                    # Posição do indicador da Mão 1
                    x_finger, y_finger = landmarks_1[8][1], landmarks_1[8][2] 

                    # Desenha o "cursor"
                    cv2.circle(img, (x_finger, y_finger), 10, (0, 0, 255), cv2.FILLED) 

                    # --- Gesto de Navegação (Scroll Up/Down) ---
                    if last_finger_y == 0: 
                        last_finger_y = y_finger
                    
                    y_delta = y_finger - last_finger_y 

                    if currentTime - navigation_cooldown > NAVIGATION_COOLDOWN_TIME:
                        if y_delta > NAVIGATION_Y_THRESHOLD: # Moveu para baixo
                            if selected_song_index < len(music_files) - 1:
                                selected_song_index += 1
                                navigation_cooldown = currentTime
                        
                        elif y_delta < -NAVIGATION_Y_THRESHOLD: # Moveu para cima
                            if selected_song_index > 0:
                                selected_song_index -= 1
                                navigation_cooldown = currentTime
                        
                        if abs(y_delta) > NAVIGATION_Y_THRESHOLD:
                            last_finger_y = y_finger 
                    
                    if abs(y_delta) < NAVIGATION_Y_THRESHOLD / 2:
                         last_finger_y = y_finger

                    # --- MÃO 2 (CLICK) ---
                    # Verifica se a SEGUNDA mão existe e está fazendo o gesto de "pinch"
                    if len(detected_hands_data) == 2:
                        hand_2_data = detected_hands_data[1]
                        landmarks_2 = hand_2_data.get("landmarks")

                        if landmarks_2 and len(landmarks_2) > 8:
                            # Coordenadas do Polegar (Mão 2)
                            x_thumb2, y_thumb2 = landmarks_2[4][1], landmarks_2[4][2] 
                            # Coordenadas do Indicador (Mão 2)
                            x_finger2, y_finger2 = landmarks_2[8][1], landmarks_2[8][2] 
                            
                            # Desenha o gesto de clique (bom para debug)
                            cv2.line(img, (x_thumb2, y_thumb2), (x_finger2, y_finger2), (0, 255, 0), 3)
                            
                            length = math.hypot(x_finger2 - x_thumb2, y_finger2 - y_thumb2)

                            # --- Gesto de "Selecionar" (Pinch na Mão 2) ---
                            if length < PINCH_THRESHOLD and (currentTime - selection_cooldown > SELECTION_COOLDOWN_TIME):
                                
                                # Evita recarregar a música que já está tocando
                                if selected_song_index == current_playing_index:
                                    print("Música já está tocando. Voltando ao modo playback.")
                                    app_mode = 'playback'
                                    selection_cooldown = currentTime
                                else:
                                    selection_cooldown = currentTime # Ativa o cooldown
                                    
                                    # --- AÇÃO: TROCAR MÚSICA ---
                                    song_to_load = music_files[selected_song_index]
                                    print(f"Selecionado: {song_to_load}")

                                    if playback_stream:
                                        playback_stream.stop()
                                        playback_stream.close()
                                        print("Stream de áudio anterior parado.")
                                    
                                    audio_loaded = audio_controller.load_audio(song_to_load)
                                    
                                    if audio_loaded:
                                        audio_data_global = audio_controller.audio_data
                                        sample_rate_global = audio_controller.sample_rate
                                        current_playback_frame = 0
                                        playback_active = True
                                        audio_file_path = song_to_load 
                                        current_playing_index = selected_song_index 
                                        
                                        try:
                                            sd.default.channels = audio_controller.num_channels
                                            playback_stream = sd.OutputStream(
                                                samplerate=sample_rate_global, channels=audio_controller.num_channels,
                                                callback=audio_playback_callback, dtype=audio_controller.audio_data.dtype,
                                                blocksize=1024 
                                            )
                                            playback_stream.start()
                                            print(f"Novo stream iniciado para {os.path.basename(song_to_load)}")
                                            app_mode = 'playback' 
                                        except Exception as e:
                                            print(f"Falha ao trocar de música: {e}")
                                            playback_active = False
                                    else:
                                        print(f"Falha ao carregar {song_to_load}")
            
            elif not detected_hands_data:
                # Se nenhuma mão for detectada, reseta a posição Y de referência
                last_finger_y = 0

        elif app_mode == 'playback':
            if detected_hands_data:
                if len(detected_hands_data) == 1:
                    # --- LÓGICA DE VOLUME COM UMA MÃO ---
                    hand_data = detected_hands_data[0]
                    landmarks = hand_data.get("landmarks")
                    if landmarks and len(landmarks) > 8:
                        x1, y1 = landmarks[4][1], landmarks[4][2] # Polegar
                        x2, y2 = landmarks[8][1], landmarks[8][2] # Indicador
                        cv2.circle(img, (x1, y1), 10, (120, 255, 0), cv2.FILLED)
                        cv2.circle(img, (x2, y2), 10, (0, 120, 255), cv2.FILLED)
                        cv2.line(img, (x1, y1), (x2, y2), (200, 200, 200), 2)
                        length_one_hand = math.hypot(x2 - x1, y2 - y1)
                        
                        if volume_controller.volume: 
                            volume_percentage_display = volume_controller.set_volume_percentage(
                                length_one_hand, VOL_DIST_MIN_ONE_HAND, VOL_DIST_MAX_ONE_HAND
                            )
                        if length_one_hand < VOL_DIST_MIN_ONE_HAND:
                            cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                elif len(detected_hands_data) == 2:
                    # --- LÓGICA DE VOLUME COM DUAS MÃOS E WAVEFORM ---
                    landmarks1 = detected_hands_data[0].get("landmarks") 
                    landmarks2 = detected_hands_data[1].get("landmarks") 
                    
                    if (landmarks1 and len(landmarks1) > 8) and (landmarks2 and len(landmarks2) > 8):
                        h1_thumb_x, h1_thumb_y = landmarks1[4][1], landmarks1[4][2]
                        h1_index_x, h1_index_y = landmarks1[8][1], landmarks1[8][2]
                        h1cx_vol = (h1_thumb_x + h1_index_x) // 2 
                        h1cy_vol = (h1_thumb_y + h1_index_y) // 2

                        h2_thumb_x, h2_thumb_y = landmarks2[4][1], landmarks2[4][2]
                        h2_index_x, h2_index_y = landmarks2[8][1], landmarks2[8][2]
                        h2cx_vol = (h2_thumb_x + h2_index_x) // 2
                        h2cy_vol = (h2_thumb_y + h2_index_y) // 2

                        # --- LÓGICA DE VOLUME COM DUAS MÃOS ---
                        length_volume_two_hands = math.hypot(h2cx_vol - h1cx_vol, h2cy_vol - h1cy_vol)
                        if volume_controller.volume:
                            volume_percentage_display = volume_controller.set_volume_percentage(length_volume_two_hands, VOL_DIST_MIN_TWO_HANDS, VOL_DIST_MAX_TWO_HANDS)
                        
                        if length_volume_two_hands < VOL_DIST_MIN_TWO_HANDS:
                            cv2.line(img, (h1cx_vol, h1cy_vol), (h2cx_vol, h2cy_vol), (0, 255, 255), 2) # Linha de feedback

                        # --- DESENHAR A FORMA DE ONDA DINAMICAMENTE ENTRE AS MÃOS ---
                        if audio_loaded_successfully and playback_active and audio_data_global is not None and sample_rate_global > 0 and audio_controller.num_channels is not None:
                            
                            wave_x_start = min(h1cx_vol, h2cx_vol)
                            wave_x_end = max(h1cx_vol, h2cx_vol)
                            dynamic_waveform_width_px = wave_x_end - wave_x_start
                            
                            dynamic_y_center = (h1cy_vol + h2cy_vol) // 2
                            
                            if dynamic_waveform_width_px > 10: # Só desenha se houver largura mínima
                                window_samples = int(WAVEFORM_WINDOW_DURATION_S * sample_rate_global)
                                center_offset_audio = window_samples // 2
                                start_sample_abs_audio = current_playback_frame - center_offset_audio
                                
                                audio_segment_shape = (window_samples, audio_data_global.shape[1]) if audio_data_global.ndim > 1 else (window_samples,)
                                audio_segment_raw = np.zeros(audio_segment_shape, dtype=audio_data_global.dtype)

                                for i in range(window_samples):
                                    sample_to_get = (start_sample_abs_audio + i) % len(audio_data_global)
                                    audio_segment_raw[i] = audio_data_global[sample_to_get]
                                
                                if audio_controller.num_channels > 1:
                                    waveform_display_data = np.mean(audio_segment_raw, axis=1)
                                else:
                                    waveform_display_data = audio_segment_raw

                                samples_per_pixel_dynamic = len(waveform_display_data) / dynamic_waveform_width_px

                                for x_local in range(dynamic_waveform_width_px):
                                    s_start = int(x_local * samples_per_pixel_dynamic)
                                    s_end = int((x_local + 1) * samples_per_pixel_dynamic)
                                    s_end = min(s_end, len(waveform_display_data))

                                    if s_start < s_end:
                                        sample_slice = waveform_display_data[s_start:s_end]
                                        min_val, max_val = np.min(sample_slice), np.max(sample_slice)
                                        
                                        y_draw_min = int(dynamic_y_center - max_val * (WAVEFORM_HEIGHT_PX / 2))
                                        y_draw_max = int(dynamic_y_center - min_val * (WAVEFORM_HEIGHT_PX / 2))
                                        
                                        draw_x_coord = wave_x_start + x_local
                                        cv2.line(img, (draw_x_coord, y_draw_min), 
                                                    (draw_x_coord, y_draw_max), 
                                                    WAVEFORM_COLOR, WAVEFORM_LINE_THICKNESS)
                                # Linha central dinâmica
                                cv2.line(img, (wave_x_start, dynamic_y_center), 
                                            (wave_x_end, dynamic_y_center), 
                                            WAVEFORM_CENTER_LINE_COLOR, 1)
                        
                        cv2.line(img, (h1_thumb_x, h1_thumb_y), (h1_index_x, h1_index_y), (255, 0, 0), 3) 
                        cv2.line(img, (h2_thumb_x, h2_thumb_y), (h2_index_x, h2_index_y), (255, 165, 0), 3) 

        # --- EXIBIÇÕES DE TEXTO NA TELA ---
        currentTime = time.time()
        deltaTime = currentTime - previousTime
        fps = 1 / deltaTime if deltaTime > 0 else 0
        previousTime = currentTime
        
        font_face = cv2.FONT_HERSHEY_SIMPLEX; font_scale = 0.7; font_thickness = 1
        text_y_start = 200; text_y_offset = 30

        cv2.putText(img,f"FPS: {int(fps)}",(30, text_y_start),font_face,font_scale,(0,255,0),font_thickness)
        cv2.putText(img,f"Vol: {int(volume_percentage_display)}%",(30, text_y_start+ text_y_offset),font_face,font_scale,(255,100,100),font_thickness)

        # Print no console removido para evitar poluição.
        
        cv2.imshow("Hand Gesture Control FX", img)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'): break 
            
    # --- FINALIZAÇÃO ---
    print("Encerrando...")
    if playback_stream: print("Parando áudio..."); playback_stream.stop(); playback_stream.close(); print("Áudio parado.")
    if capture.isOpened(): capture.release()
    cv2.destroyAllWindows(); print("Recursos liberados.")