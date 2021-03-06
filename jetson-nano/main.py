import socket
import struct
import cv2
import numpy as np
import Jetson.GPIO as GPIO
import time

#####################################
from qr_db_module import QR_DB_Module
from motor_module import Motor_Module
#####################################


def gstreamer_pipeline(
    sensor_id: int = 0,
    capture_width: int = 1280,
    capture_height: int = 720,
    display_width: int = 416,
    display_height: int = 416,
    framerate: int = 10,
    flip_method: int = 0,
) -> str:
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )


cap = cv2.VideoCapture(gstreamer_pipeline(sensor_id=1, flip_method=0), cv2.CAP_GSTREAMER)

IP = ''
PORT = 1234


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((IP, PORT))

GPIO.setmode(GPIO.BOARD)
GPIO.setup(15, GPIO.IN)

received_num = b''
reward = 0
is_button_clicked = False
qr_db_module = QR_DB_Module()
motor_module = Motor_Module(26, 24, 32, 33)


classes = { 1: 'PET plastic_bottle with_label', 2: 'PAPER coffee_cup without_cap',
            3: 'PET plastic_bottle with_label', 4: 'PET plastic_bottle without_label',
            5: 'CAN drink_can crushed', 6: 'CAN drink_can no_crushed'}

while True:
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(15, GPIO.IN)
    _, img = cap.read()
    # img = cv2.resize(img, None, fx=0.4, fy=0.4)
    result, frame = cv2.imencode('.jpg', img)
    data = np.array(frame)
    stringData = data.tostring()
    cur_object = None
    is_button_clicked = not GPIO.input(15)
    
    s.sendall((str(len(stringData))).encode().ljust(16) + stringData)
    received_num = s.recv(10)
    received_num = int(struct.unpack('f', received_num)[0])

    if received_num != -1:
        cur_reward = int(received_num % 1000)
        cur_object = classes[int(received_num/1000)]
        string = cur_object.split(' ')
        if string[0] == 'PET' and string[-1] == 'without_label':
            motor_module.move_two_motors(2, 9)
            motor_module.move_one_motor()
        elif string[0] == 'PAPER' and string[-1] in ['without_sticker','without_cap']:
            motor_module.move_two_motors(2, 12)
            motor_module.move_one_motor()
        elif string[0] == 'CAN':
            motor_module.move_two_motors(5, 12)
            motor_module.move_one_motor()
        motor_module.move_two_motors(2, 12)
        reward += cur_reward
        
    if is_button_clicked and reward > 0:
        personal_number = qr_db_module.get_barcode_info()
        if personal_number:
            qr_db_module.update_reward(personal_number, str(reward))
        reward = 0
        GPIO.cleanup()
