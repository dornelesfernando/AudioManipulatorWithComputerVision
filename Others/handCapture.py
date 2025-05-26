import cv2
import mediapipe as mp
import numpy as np
import time             # framerate

class HandDetector:
    def __init__(self, 
                 mode: bool = False, 
                 number_hands: int = 4, 
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

if __name__ == "__main__":
    #Abrindo a webcam
    capture = cv2.VideoCapture(0)

    Detector = HandDetector()

    while True:
        _, img = capture.read()

        # Manipulação da imagem
        img = Detector.find_hands(img)

        cv2.imshow("Minha WebCam", img)

        # Condição de parada
        if cv2.waitKey(20) & 0xFF == ord('q'):
            break
