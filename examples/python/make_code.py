"""生成汉信码 PNG：python make_code.py license.lic"""
import sys

from PIL import Image
from sinomatrix import SinoMatrix

sdk = SinoMatrix()
sdk.load_license(sys.argv[1])

text = "追溯码：SMHX-2026-000123\n产地：浙江杭州"
width, height, pixels = sdk.encode(text, module_pixels=8, quiet_zone=4)
Image.frombytes("L", (width, height), pixels).save("hanxin.png")
print("已保存 hanxin.png", width, height)
print("回读：", sdk.decode_file("hanxin.png") == text)
