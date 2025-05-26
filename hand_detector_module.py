import cv2
import mediapipe as mp
import numpy as np

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
        self.results = None

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
    
    def find_positions(self, 
                      img: np.ndarray,
                      draw_points: bool = True):
        
        all_hands_landmarks = []

        if self.results and self.results.multi_hand_landmarks:
            for hand_idx, hand_landmarks in enumerate(self.results.multi_hand_landmarks):
                hand_landmark_list = []
                height, width, _ = img.shape

                for id, lm in enumerate(hand_landmarks.landmark):
                    center_x = int(lm.x * width)
                    center_y = int(lm.y * height)

                    hand_landmark_list.append([id, center_x, center_y])

                    if draw_points:
                        cv2.circle(img, (center_x, center_y), 5, (255, 0, 0), cv2.FILLED)

                all_hands_landmarks.append({"id": hand_idx, "landmarks": hand_landmark_list, "handedness": self.results.multi_handedness[hand_idx]})
        return all_hands_landmarks