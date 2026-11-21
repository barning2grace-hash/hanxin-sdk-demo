"""OpenCV 读到的画面直接识别（pip install opencv-python）。没有摄像头时用图片代替。"""
import sys

import cv2
from sinomatrix import SinoMatrix

sdk = SinoMatrix()
sdk.load_license(sys.argv[1])

frame = cv2.imread(sys.argv[2]) if len(sys.argv) > 2 else cv2.VideoCapture(0).read()[1]
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)            # 转成 8 位灰度
h, w = gray.shape
text = sdk.decode(gray.tobytes(), w, h, stride=w, time_limit_ms=300)   # 视频流里预算给小一点
print(text if text is not None else "这一帧没读到")
