"""批量识别一个文件夹里的汉信码图片：python batch_decode.py license.lic images/"""
import sys
import time
from pathlib import Path

from sinomatrix import SinoMatrix

sdk = SinoMatrix()
sdk.load_license(sys.argv[1])

for path in sorted(Path(sys.argv[2]).glob("*")):
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        continue
    start = time.perf_counter()
    text = sdk.decode_file(str(path), time_limit_ms=2000)
    ms = (time.perf_counter() - start) * 1000
    print(f"{path.name}\t{ms:.0f} ms\t{text if text is not None else '未识别'}")
