import cv2
import time
import numpy as np
import math

# Importando classes de módulos
from hand_detector_module import HandDetector
from volume_control_module import SystemVolumeControl

if __name__ == '__main__':
    
    #configuração da câmera
    wCam, hCam = 480, 270
    capture = cv2.VideoCapture(0)
    if not capture.isOpened():
        print("Erro ao abrir a câmera.")
        exit()
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, wCam)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, hCam)

    previusTime = 0

    # Inicializa o detector de mãos
    detector = HandDetector(number_hands = 2, min_detection_confidence = 0.7)

    volume_controller = SystemVolumeControl()
    if volume_controller.volume is None:
        print("Continuando sem controle de volume")

    # volume_controller.set_max_db_override(-25.0) # Controle de volume máximo personalizado

    # Faixa de distâncias para interpolação 
    HAND_DIST_MIN_ONE_HAND = 20
    HAND_DIST_MAX_ONE_HAND = 150
    HAND_DIST_MIN_TWO_HAND = 30
    HAND_DIST_MAX_TWO_HAND = 250

    currentVolPercent = 0

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
                landmarks = hand_data["landmarks"]
                
                x1, y1 = landmarks[4][1], landmarks[4][2]
                x2, y2 = landmarks[8][1], landmarks[8][2]
                                
                cv2.circle(img, (x1, y1), 10, (255, 255, 0), cv2.FILLED)
                cv2.circle(img, (x2, y2), 10, (255, 0, 255), cv2.FILLED)
                cv2.line(img, (x1, y1), (x2, y2), (255, 255, 255), 3)
                
                length =  math.hypot(x2 - x1, y2 - y1)

                if volume_controller.volume:
                    volume_porcentage = volume_controller.set_volume_percentage(length, HAND_DIST_MIN_ONE_HAND, HAND_DIST_MAX_ONE_HAND)

                if length < HAND_DIST_MIN_ONE_HAND:
                    cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
            elif len(detected_hands_data) == 2:
                landmarks1 = detected_hands_data[0]["landmarks"]
                landmarks2 = detected_hands_data[1]["landmarks"]
                
                ## Captura das localizações dos pontos
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
                
                if volume_controller.volume:
                    volume_porcentage = volume_controller.set_volume_percentage(length, HAND_DIST_MIN_TWO_HAND, HAND_DIST_MAX_TWO_HAND)

                if length < HAND_DIST_MIN_ONE_HAND:
                    cv2.line(img, (x1, y1), (x2, y2), (0, 255, 0), 3)

                # Reverb
                cv2.line(img, (h1x1, h1y1), (h1x2, h1y2), (255, 0, 0), 3)
                lengthReverb = math.hypot(h1x2 - h1x1, h1y2 - h1y1)

                # Pitch, Shift/Transposição
                cv2.line(img, (h2x1, h2y1), (h2x2, h2y2), (0, 0, 255), 3)
                lengthTimbre = math.hypot(h2x2 - h2x1, h2y2 - h2y1)
                
        # Framerate
        currentTime = time.time()
        fps = 1 / (currentTime - previusTime) if (currentTime - previusTime) != 0 else 0
        previusTime = currentTime
        cv2.putText(img, f"FPS: {int(fps)}", (30, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 1)
        
        # Apresentação do volume em tela
        cv2.putText(img, f"Vol: {int(volume_porcentage)}%", (30, 100), cv2.FONT_HERSHEY_COMPLEX, 1, (0, 0, 255), 1)

        cv2.imshow("MyImage", img)
        
        key = cv2.waitKey(20) & 0xFF
        if key == (ord('q') or ord('Q')):
            break 
        
    capture.release() # Libera a webCam
    cv2.destroyAllWindows() # Fecha as janelas abertas pelo OpenCV