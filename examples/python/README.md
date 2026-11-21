# Python 示例

把 SDK 包里的运行库（Windows `SinoMatrix.dll`，Linux `libSinoMatrix.so`）复制到本目录，再准备好 `license.lic`。

```bash
pip install pillow                       # 读写图片
python batch_decode.py license.lic ../../test-images
python make_code.py license.lic          # 生成 hanxin.png 并回读
pip install opencv-python
python camera_frame.py license.lic ../../test-images/light.jpg   # 不传图片时读摄像头
```
