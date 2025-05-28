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
from reverb_control_module import ReverbControl # Classe que agora lida com Reverb e Delay

# --- Variáveis Globais para Reprodução de Áudio e Efeitos ---
current_playback_frame = 0
playback_active = False
audio_data_global = None
sample_rate_global = 0
playback_stream = None

# Efeitos
effects_controller_global = None
reverb_wet_level_gesture = 0.0
delay_mix_gesture = 0.0

# --- Configurações da Forma de Onda (Waveform) ---
WAVEFORM_HEIGHT_PX = 120 
WAVEFORM_WINDOW_DURATION_S = 3.0
WAVEFORM_COLOR = (255, 255, 255)
WAVEFORM_CENTER_LINE_COLOR = (255, 255, 255)
WAVEFORM_LINE_THICKNESS = 1

troca = True
tempo_inicial_em_segundos = time.time() + 100000
aux = True

# --- Função de Callback para reprodução e efeitos de áudio ---
def audio_playback_callback(outdata, frames, time_info, status):
    global current_playback_frame, playback_active, audio_data_global, sample_rate_global
    global effects_controller_global # pitch_semitones removido daqui

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

            if effects_controller_global is not None:
                try:
                    processed_chunk = effects_controller_global.process(processed_chunk)
                except Exception as e:
                    print(f"Erro no processamento de efeitos: {e}")
            
            actual_processed_frames = len(processed_chunk)
            frames_to_fill_in_outdata = min(actual_processed_frames, frames)

            if frames_to_fill_in_outdata > 0:
                chunk_to_output = processed_chunk[:frames_to_fill_in_outdata]
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
                current_playback_frame = 0 
        else:
            outdata[:] = 0
            current_playback_frame = 0
    else:
        outdata[:] = 0

if __name__ == '__main__':

    # --- CARREGAMENTO DO ÁUDIO ---
    audio_controller = AudioControl()
    audio_file_path = input("Digite o caminho para o seu arquivo de áudio (ex: sua_musica.wav): ")
    
    audio_loaded_successfully = audio_controller.load_audio(audio_file_path)
    if audio_loaded_successfully:
        print(f"Áudio '{os.path.basename(audio_file_path)}' carregado e pronto para uso.")
        audio_data_global = audio_controller.audio_data
        sample_rate_global = audio_controller.sample_rate
        
        try:
            effects_controller_global = ReverbControl(sample_rate_global) 
            print("Controlador de Efeitos (Reverb & Delay) global inicializado.")
        except Exception as e:
            print(f"Erro ao inicializar Controlador de Efeitos: {e}")
            effects_controller_global = None
        
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
    HAND_DIST_MIN_FINGERS = 30
    HAND_DIST_MAX_FINGERS_EFFECTS = 220 

    VOL_DIST_MIN_TWO_HANDS = 50
    VOL_DIST_MAX_TWO_HANDS = 500
    
    # Faixas para mapeamento de efeitos
    REVERB_MIN_WET = 0.0
    REVERB_MAX_WET = 1.0 
    DELAY_MIN_MIX = 0.0
    DELAY_MAX_MIX = 1.0 
    
    volume_percentage_display = 0.0
    reverb_display = 0.0
    delay_display = 0.0

    # --- LOOP PRINCIPAL ---
    while True:
        success, img = capture.read()
        if not success: break
        img = cv2.flip(img, 1)
        
        img = detector.find_hands(img, draw_hands=True)
        detected_hands_data = detector.find_positions(img, draw_points=False)

        if detected_hands_data:
            if len(detected_hands_data) == 1:
                hand_data = detected_hands_data[0]
                landmarks = hand_data.get("landmarks")
                if landmarks and len(landmarks) > 8:
                    x1, y1 = landmarks[4][1], landmarks[4][2]
                    x2, y2 = landmarks[8][1], landmarks[8][2]
                    cv2.circle(img, (x1, y1), 10, (120, 255, 0), cv2.FILLED)
                    cv2.circle(img, (x2, y2), 10, (0, 120, 255), cv2.FILLED)
                    cv2.line(img, (x1, y1), (x2, y2), (200, 200, 200), 2)
                    length_one_hand = math.hypot(x2 - x1, y2 - y1)
                    if volume_controller.volume: 
                         volume_percentage_display = volume_controller.set_volume_percentage(
                             length_one_hand, HAND_DIST_MIN_FINGERS, HAND_DIST_MAX_FINGERS_EFFECTS
                         )
                    if length_one_hand < HAND_DIST_MIN_FINGERS:
                        cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
            elif len(detected_hands_data) == 2:
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

                    # --- LÓGICA DE VOLUME COM DUAS MÃOS (mantida) ---
                    # A linha de conexão das mãos para volume agora será substituída pela waveform
                    # cv2.line(img, (h1cx_vol, h1cy_vol), (h2cx_vol, h2cy_vol), (255, 255, 255), 3) # <<< LINHA REMOVIDA/SUBSTITUÍDA
                    length_volume_two_hands = math.hypot(h2cx_vol - h1cx_vol, h2cy_vol - h1cy_vol)
                    if volume_controller.volume:
                        volume_percentage_display = volume_controller.set_volume_percentage(length_volume_two_hands, VOL_DIST_MIN_TWO_HANDS, VOL_DIST_MAX_TWO_HANDS)
                    # O feedback visual para o volume (linha amarela quando perto) pode ser mantido ou adaptado
                    if length_volume_two_hands < VOL_DIST_MIN_TWO_HANDS:
                         cv2.line(img, (h1cx_vol, h1cy_vol), (h2cx_vol, h2cy_vol), (0, 255, 255), 2) # Linha de feedback mais fina

                    # --- DESENHAR A FORMA DE ONDA DINAMICAMENTE ENTRE AS MÃOS ---
                    if audio_loaded_successfully and playback_active and audio_data_global is not None and sample_rate_global > 0 and audio_controller.num_channels is not None:
                        
                        # Define a área da waveform dinamicamente
                        wave_x_start = min(h1cx_vol, h2cx_vol)
                        wave_x_end = max(h1cx_vol, h2cx_vol)
                        dynamic_waveform_width_px = wave_x_end - wave_x_start
                        
                        # Posição Y central da waveform (média das posições Y das mãos)
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
                                    
                                    # Mapeia para a altura dinâmica
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
                    
                    # --- Controles de Reverb e Delay (mantidos) ---
                    lengthReverb = math.hypot(h1_index_x - h1_thumb_x, h1_index_y - h1_thumb_y)
                    cv2.line(img, (h1_thumb_x, h1_thumb_y), (h1_index_x, h1_index_y), (255, 0, 0), 3) 
                    if audio_loaded_successfully and effects_controller_global:
                        reverb_wet_level_gesture=np.interp(lengthReverb,[HAND_DIST_MIN_FINGERS,HAND_DIST_MAX_FINGERS_EFFECTS],[REVERB_MIN_WET,REVERB_MAX_WET])
                        effects_controller_global.set_wet_level(np.clip(reverb_wet_level_gesture,REVERB_MIN_WET,REVERB_MAX_WET));reverb_display=reverb_wet_level_gesture
                    
                    lengthDelayControl = math.hypot(h2_index_x - h2_thumb_x, h2_index_y - h2_thumb_y) 
                    cv2.line(img, (h2_thumb_x, h2_thumb_y), (h2_index_x, h2_index_y), (255, 165, 0), 3) 
                    if audio_loaded_successfully and effects_controller_global:
                        delay_mix_gesture=np.interp(lengthDelayControl,[HAND_DIST_MIN_FINGERS,HAND_DIST_MAX_FINGERS_EFFECTS],[DELAY_MIN_MIX,DELAY_MAX_MIX])
                        effects_controller_global.set_delay_mix(np.clip(delay_mix_gesture,DELAY_MIN_MIX,DELAY_MAX_MIX));delay_display=delay_mix_gesture

                    # print(f"h1_thumb_y: {h1_thumb_y} > h1_index_y: {h1_index_y}")
                    if h2_index_y > h2_thumb_y:
                        while troca:
                            if playback_stream: print("Parando áudio..."); playback_stream.stop(); playback_stream.close(); print("Áudio parado.")
                            tempo_inicial_em_segundos = time.time()
                            troca = False

                    if (time.time() - tempo_inicial_em_segundos >= 1) and aux:
                        aux = False
                        audio_loaded_successfully = audio_controller.load_audio("music/Addicted.wav")
                        if audio_loaded_successfully:
                            print(f"Áudio '{os.path.basename(audio_file_path)}' carregado e pronto para uso.")
                            audio_data_global = audio_controller.audio_data
                            sample_rate_global = audio_controller.sample_rate
                            
                            try:
                                effects_controller_global = ReverbControl(sample_rate_global) 
                                print("Controlador de Efeitos (Reverb & Delay) global inicializado.")
                            except Exception as e:
                                print(f"Erro ao inicializar Controlador de Efeitos: {e}")
                                effects_controller_global = None
                            
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
                        
            else: # Se nenhuma mão for detectada, não desenha a waveform dinâmica
                pass

        # --- EXIBIÇÕES DE TEXTO NA TELA ---
        currentTime = time.time()
        deltaTime = currentTime - previousTime
        fps = 1 / deltaTime if deltaTime > 0 else 0
        previousTime = currentTime
        
        font_face = cv2.FONT_HERSHEY_SIMPLEX; font_scale = 0.7; font_thickness = 1
        text_y_start = 30; text_y_offset = 30

        cv2.putText(img,f"FPS: {int(fps)}",(30,text_y_start),font_face,font_scale,(0,255,0),font_thickness)
        cv2.putText(img,f"Vol: {int(volume_percentage_display)}%",(30,text_y_start+text_y_offset),font_face,font_scale,(255,100,100),font_thickness)
        cv2.putText(img,f"Reverb: {reverb_display:.2f}",(30,text_y_start+2*text_y_offset),font_face,font_scale,(100,100,255),font_thickness)
        cv2.putText(img,f"Delay Mix: {delay_display:.2f}",(30,text_y_start+3*text_y_offset),font_face,font_scale,(255,165,0),font_thickness)

        print(f"FPS: {fps}\nVol: {volume_percentage_display}\nReverb: {reverb_display}\nDelay: {delay_display}\n")

        cv2.imshow("Hand Gesture Control FX", img)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'): break 
            
    # --- FINALIZAÇÃO ---
    print("Encerrando...")
    if playback_stream: print("Parando áudio..."); playback_stream.stop(); playback_stream.close(); print("Áudio parado.")
    if capture.isOpened(): capture.release()
    cv2.destroyAllWindows(); print("Recursos liberados.")