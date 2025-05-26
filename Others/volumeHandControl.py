import cv2
import time
import numpy as np
import mediapipe as mp
import math
from pycaw.pycaw import AudioUtilities
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL
import ctypes

class HandDetector:
    def __init__(self, 
                 mode: bool = False, 
                 number_hands: int = 2, 
                 model_complexity: int = 1,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        # Parametros de inicialização do Hands mediapipe
        self.mode = mode
        self.number_hands = number_hands
        self.complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Inicializando o Hands mediapipe
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(self.mode,
                                        self.number_hands,
                                        self.complexity,
                                        self.min_detection_confidence,
                                        self.min_tracking_confidence)
        
        # Inicializando o desenho do mediapipe
        self.mp_draw = mp.solutions.drawing_utils
        
    def find_hands(self, 
                   img: np.ndarray, 
                   draw_hands: bool = True):
        
        # Converte a imagem para RGB
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Faz a detecção das mãos --> Retorna um objeto com as landmarks (listas)
        self.results = self.hands.process(img_rgb)

        # Verifica se alguma mão foi detectada
        if self.results.multi_hand_landmarks:
            for hand_landmarks in self.results.multi_hand_landmarks:
                if draw_hands:  
                    # Desenha as landmarks na imagem
                    self.mp_draw.draw_landmarks(img,
                                                hand_landmarks,
                                                self.mp_hands.HAND_CONNECTIONS)
        return img
    
    def find_position(self, 
                      img: np.ndarray,
                      hand_number: int = 0,
                      draw_points: bool = True):
        
        self.required_landmark_list = []

        if self.results and self.results.multi_hand_landmarks:
            if len(self.results.multi_hand_landmarks) > hand_number:
                my_hand = self.results.multi_hand_landmarks[hand_number]

                for id, lm in enumerate(my_hand.landmark):
                    height, width, _ = img.shape
                    center_x = int(lm.x * width)
                    center_y = int(lm.y * height)

                    self.required_landmark_list.append([id, center_x, center_y])

                    if draw_points:
                            cv2.circle(img, (center_x, center_y), 5, (255, 0, 0), cv2.FILLED)

        return self.required_landmark_list

if __name__ == '__main__':
    
    #configuração da câmera
    wCam, hCam = 1280, 720
    capture = cv2.VideoCapture(0)
    capture.set(3, wCam)
    capture.set(4, hCam)

    if not capture.isOpened():
        print("Erro ao abrir a câmera.")
        exit()

    previusTime = 0
    Detector = HandDetector(False, 1)

    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
    minVol, maxVol, _ = volume.GetVolumeRange()
    # print(minVol, maxVol)

    while True:
        success, img = capture.read()
        if not success:
            print("Erro ao capturar imagem.")
            break

        img = Detector.find_hands(img)

        landmark_List = Detector.find_position(img)
        if landmark_List:
            # print(landmark_List[4], landmark_List[8])  # Posição do dedo indicador

            x1, y1 = landmark_List[4][1], landmark_List[4][2]
            x2, y2 = landmark_List[8][1], landmark_List[8][2]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            
            cv2.circle(img, (x1, y1), 10, (255, 255, 0), cv2.FILLED)
            cv2.circle(img, (x2, y2), 10, (255, 0, 255), cv2.FILLED)
            cv2.line(img, (x1, y1), (x2, y2), (255, 255, 255), 3)
            # cv2.circle(img, (cx, cy), 10, (255, 255, 255), cv2.FILLED)

            length =  math.hypot(x2 - x1, y2 - y1)
            #print(length)

            # Hand range = 30 - 210
            # Volume = -62 - 0

            vol = np.interp(length, [20, 170], [minVol, maxVol])
            volPercent = np.interp(length, [20, 170], [0, 100])
            # print(int(length), vol)
            volume.SetMasterVolumeLevel(vol, None)

            if length < 20:
                cv2.line(img, (x1, y1), (x2, y2), (0, 0, 0), 3)

            cv2.putText(img, f"Vol: {int(volPercent)}%", (30, 100), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 0, 0), 1)

        #Framerate
        currentTime = time.time()
        fps = 1 / (currentTime - previusTime)
        previusTime = currentTime
        cv2.putText(img,
                    f"FPS: {int(fps)}",
                    (30, 50),
                    cv2.FONT_HERSHEY_COMPLEX,
                    1,
                    (0, 0, 255),
                    1)

        cv2.imshow("MyImage", img)
        
        if cv2.waitKey(20) & 0xFF == ord('q'):
            break 

    capture.release() # Libera a webCam
    cv2.destroyAllWindows() # Fecha as janelas abertas pelo OpenCV