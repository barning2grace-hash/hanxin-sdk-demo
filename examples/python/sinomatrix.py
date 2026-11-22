"""SinoMatrix 汉信码 SDK —— Python ctypes 封装（Python 3.8+，64 位）。

把本文件和 SinoMatrix.dll（Linux 为 libSinoMatrix.so）放在同一目录，或把路径传给 SinoMatrix()。
读取图片文件需要 Pillow：pip install pillow（iPhone 的 HEIC 照片另装 pillow-heif）。

0.5.0 起可以直接传彩色、16 位和 YUV 图像：
    sdk.decode_file("photo.jpg")                       # JPG/PNG/BMP/TIFF/WebP/GIF，16 位 PNG/TIFF
    sdk.decode_array(cv2.imread("photo.jpg"))           # OpenCV BGR，numpy 数组切片也不复制
    sdk.decode_image(rgba, w, h, "rgba", stride)        # 任意内存缓冲区
"""
import ctypes as C
import os
import sys

c_int, c_uint32, c_uint64, c_double, c_void_p = C.c_int, C.c_uint32, C.c_uint64, C.c_double, C.c_void_p

STATUS = {0: "Ok", 1: "InvalidArgument", 2: "NotSupported", 3: "DecodeFailed", 4: "EncodeFailed",
          5: "InternalError", 6: "LicenseError", 7: "Timeout", 8: "Cancelled"}


class ImageView(C.Structure):
    _fields_ = [("data", c_void_p), ("width", c_int), ("height", c_int), ("stride", c_int)]


# 像素格式（0.5.0+）。名称就是内存里的字节顺序；yuv420 只传 Y 平面（NV12/NV21/I420/YV12 通用）。
PIXEL_FORMATS = {"gray": 0, "l": 0, "rgb": 1, "bgr": 2, "rgba": 3, "bgra": 4, "argb": 5, "abgr": 6,
                 "gray16": 7, "yuv420": 8, "nv12": 8, "nv21": 8, "i420": 8, "yv12": 8, "yuyv": 9, "yuy2": 9,
                 "uyvy": 10}
BYTES_PER_PIXEL = {0: 1, 1: 3, 2: 3, 3: 4, 4: 4, 5: 4, 6: 4, 7: 2, 8: 1, 9: 2, 10: 2}
# 彩色转灰度方式："luma" 默认；"min" 取最暗通道，适合黄、青、红等彩色油墨印在浅色底上的码
COLOR_CONVERSIONS = {"luma": 0, "min": 1, "red": 2, "green": 3, "blue": 4}


class Image(C.Structure):
    _fields_ = [("structSize", c_uint32), ("format", c_int), ("data", c_void_p), ("width", c_int),
                ("height", c_int), ("stride", c_int), ("colorConversion", c_int)]


class OwnedBuffer(C.Structure):
    _fields_ = [("data", c_void_p), ("width", c_int), ("height", c_int), ("stride", c_int), ("size", c_uint64)]


class OwnedString(C.Structure):
    _fields_ = [("data", c_void_p), ("size", c_uint64)]

    def text(self):
        # 以 size 为准读取 UTF-8，内容中可能包含 \0
        return C.string_at(self.data, self.size).decode("utf-8", "replace") if self.data and self.size else ""


class EncodeOptions(C.Structure):
    _fields_ = [("eccLevel", c_int), ("preferredVersion", c_int), ("quietZoneModules", c_int),
                ("modulePixels", c_int), ("preferUriMode", c_int)]


class DecodeOptionsV2(C.Structure):
    _fields_ = [("structSize", c_uint32), ("expectedVersion", c_int), ("assumePureSymbol", c_int),
                ("enableQualityAnalysis", c_int), ("searchLevel", c_int),
                ("roiX", c_int), ("roiY", c_int), ("roiWidth", c_int), ("roiHeight", c_int),
                ("timeLimitMs", c_int), ("maxCandidates", c_int),
                ("cancelCallback", c_void_p), ("cancelContext", c_void_p), ("flags", c_uint32)]


class Quality(C.Structure):
    _fields_ = [(n, c_double) for n in (
        "rmin rmax gt symbolContrast localContrastMin localContrastMean modulation moduleModulation "
        "axialInconsistency gridInconsistency gridRmsX gridRmsY printingGain moduleSizePx zx zy quietZoneModules "
        "gradeSymbolContrast gradeModulation gradeAxialInconsistency gradeGridInconsistency overallGrade").split()] + \
        [(n, c_int) for n in ("moduleCount", "sampleCropX", "sampleCropY", "sampleCropSize")]


class EncodeResult(C.Structure):
    _fields_ = [("status", c_int)] + [(n, c_int) for n in (
        "version size maskPattern dataCodewords eccCodewords totalCodewords quietZoneModules modulePixels "
        "eccLevel mode").split()] + [("payloadBytes", c_uint64), ("modules", OwnedBuffer), ("rendered", OwnedBuffer),
                                     ("errorMessage", OwnedString), ("logText", OwnedString)]


class DecodeResult(C.Structure):
    _fields_ = [(n, c_int) for n in "status version size maskPattern structuralDistance eccLevel mode".split()] + \
        [("textUtf8", OwnedString), ("errorMessage", OwnedString), ("logText", OwnedString)] + \
        [(n, c_int) for n in "roiX roiY roiWidth roiHeight".split()] + \
        [("modules", OwnedBuffer), ("diagnosticGrid", OwnedBuffer), ("diagnosticModulation", OwnedBuffer),
         ("quality", Quality)]


class PayloadSegment(C.Structure):
    _fields_ = [("mode", c_int), ("eci", c_int), ("bytes", OwnedBuffer), ("textUtf8", OwnedString),
                ("textAvailable", c_int)]


class DecodeResultV2(C.Structure):
    _fields_ = [("base", DecodeResult), ("segments", C.POINTER(PayloadSegment)), ("segmentCount", c_uint64)]


class SinoMatrixError(RuntimeError):
    def __init__(self, status, message):
        super().__init__(f"{STATUS.get(status, status)}: {message}")
        self.status = status


class SinoMatrix:
    """SDK 的 Python 封装。SDK 分配的结果都在方法内部释放。"""

    def __init__(self, dll_path=None):
        if dll_path is None:
            here = os.path.dirname(os.path.abspath(__file__))
            dll_path = os.path.join(here, "SinoMatrix.dll" if sys.platform == "win32" else "libSinoMatrix.so")
        self.dll = C.CDLL(dll_path)
        d = self.dll
        d.SinoMatrix_GetVersionString.restype = C.c_char_p
        d.SinoMatrix_LoadLicenseFileUtf8.argtypes = [C.c_char_p]
        d.SinoMatrix_GetLicenseMessage.argtypes = [C.POINTER(OwnedString)]
        d.SinoMatrix_GetMachineFingerprint.argtypes = [C.POINTER(OwnedString)]
        d.SinoMatrix_InitializeHanXinEncodeOptions.argtypes = [C.POINTER(EncodeOptions)]
        d.SinoMatrix_InitializeHanXinDecodeOptionsV2.argtypes = [C.POINTER(DecodeOptionsV2)]
        d.SinoMatrix_HanXinEncodeUtf8WithLength.argtypes = [C.c_char_p, c_uint64, C.POINTER(EncodeOptions),
                                                            C.POINTER(EncodeResult)]
        d.SinoMatrix_HanXinDecodeGray8V2.argtypes = [ImageView, C.POINTER(DecodeOptionsV2), C.POINTER(DecodeResultV2)]
        self.has_image_api = hasattr(d, "SinoMatrix_HanXinDecodeImage")   # 0.5.0+
        if self.has_image_api:
            d.SinoMatrix_HanXinDecodeImage.argtypes = [C.POINTER(Image), C.POINTER(DecodeOptionsV2),
                                                       C.POINTER(DecodeResultV2)]
        d.SinoMatrix_FreeOwnedString.argtypes = [C.POINTER(OwnedString)]
        d.SinoMatrix_FreeHanXinEncodeResult.argtypes = [C.POINTER(EncodeResult)]
        d.SinoMatrix_FreeHanXinDecodeResultV2.argtypes = [C.POINTER(DecodeResultV2)]

    @property
    def version(self):
        return self.dll.SinoMatrix_GetVersionString().decode()

    def machine_fingerprint(self):
        s = OwnedString()
        try:
            self.dll.SinoMatrix_GetMachineFingerprint(C.byref(s))
            return s.text()
        finally:
            self.dll.SinoMatrix_FreeOwnedString(C.byref(s))

    def load_license(self, path):
        status = self.dll.SinoMatrix_LoadLicenseFileUtf8(os.fsencode(os.path.abspath(path)) if sys.platform != "win32"
                                                         else os.path.abspath(path).encode("utf-8"))
        msg = OwnedString()
        self.dll.SinoMatrix_GetLicenseMessage(C.byref(msg))
        text = msg.text()
        self.dll.SinoMatrix_FreeOwnedString(C.byref(msg))
        if status != 0:
            raise SinoMatrixError(status, text)
        return text

    def encode(self, text, module_pixels=8, quiet_zone=4, ecc_level=0, version=0):
        """返回 (width, height, bytes)：8 位灰度、无行填充，0=黑 255=白。"""
        options = EncodeOptions()
        self.dll.SinoMatrix_InitializeHanXinEncodeOptions(C.byref(options))
        options.modulePixels, options.quietZoneModules = module_pixels, quiet_zone
        options.eccLevel, options.preferredVersion = ecc_level, version
        data = text.encode("utf-8")
        result = EncodeResult()
        try:
            status = self.dll.SinoMatrix_HanXinEncodeUtf8WithLength(data, len(data), C.byref(options), C.byref(result))
            if status != 0:
                raise SinoMatrixError(status, result.errorMessage.text())
            r = result.rendered
            rows = [C.string_at(r.data + y * r.stride, r.width) for y in range(r.height)]
            return r.width, r.height, b"".join(rows)
        finally:
            self.dll.SinoMatrix_FreeHanXinEncodeResult(C.byref(result))

    def encode_modules(self, text):
        """返回模块矩阵（list[list[bool]]，True=深色），用于自行绘制矢量图。"""
        options = EncodeOptions()
        self.dll.SinoMatrix_InitializeHanXinEncodeOptions(C.byref(options))
        data = text.encode("utf-8")
        result = EncodeResult()
        try:
            status = self.dll.SinoMatrix_HanXinEncodeUtf8WithLength(data, len(data), C.byref(options), C.byref(result))
            if status != 0:
                raise SinoMatrixError(status, result.errorMessage.text())
            m = result.modules
            return [[C.string_at(m.data + y * m.stride + x, 1)[0] < 128 for x in range(m.width)] for y in range(m.height)]
        finally:
            self.dll.SinoMatrix_FreeHanXinEncodeResult(C.byref(result))

    def _run_decode(self, call, time_limit_ms, roi):
        options = DecodeOptionsV2()
        self.dll.SinoMatrix_InitializeHanXinDecodeOptionsV2(C.byref(options))
        options.timeLimitMs = time_limit_ms
        if roi is not None:
            options.roiX, options.roiY, options.roiWidth, options.roiHeight = roi
        result = DecodeResultV2()
        try:
            status = call(C.byref(options), C.byref(result))
            if status == 0:
                return result.base.textUtf8.text()
            if status in (3, 7):
                return None
            raise SinoMatrixError(status, result.base.errorMessage.text())
        finally:
            self.dll.SinoMatrix_FreeHanXinDecodeResultV2(C.byref(result))

    @staticmethod
    def _address(data):
        """返回 (地址, 保活对象, 字节数)。bytes、可写缓冲区直接取地址，不复制。"""
        if isinstance(data, bytes):
            return C.cast(C.c_char_p(data), c_void_p).value, data, len(data)
        view = memoryview(data)
        if not view.c_contiguous:
            raise ValueError("缓冲区必须是连续内存；numpy 切片请用 decode_array")
        if view.readonly:
            buf = (C.c_ubyte * view.nbytes).from_buffer_copy(view)
        else:
            buf = (C.c_ubyte * view.nbytes).from_buffer(view.cast("B"))
        return C.addressof(buf), buf, view.nbytes

    def decode(self, gray, width, height, stride=None, time_limit_ms=500, roi=None):
        """解码 8 位灰度数据。识别失败或超时返回 None；授权/参数错误抛出 SinoMatrixError。

        roi=(x, y, w, h) 只在这个矩形里找码。"""
        stride = stride or width
        address, keep, size = self._address(gray)
        if size < (height - 1) * stride + width:
            raise ValueError("缓冲区比 width/height/stride 描述的小")
        image = ImageView(address, width, height, stride)
        try:
            return self._run_decode(
                lambda o, r: self.dll.SinoMatrix_HanXinDecodeGray8V2(image, o, r), time_limit_ms, roi)
        finally:
            del keep

    def decode_image(self, data, width, height, pixel_format="gray", stride=0, color="luma",
                     time_limit_ms=500, roi=None):
        """解码任意像素格式的内存图像（需要 0.5.0+ 运行库）。

        pixel_format: gray rgb bgr rgba bgra argb abgr gray16 yuv420(nv12/nv21/i420，只传 Y 平面) yuyv uyvy
        stride: 每行字节数，0 表示紧密排列。color: luma（默认）/ min / red / green / blue"""
        fmt = PIXEL_FORMATS[pixel_format.lower()] if isinstance(pixel_format, str) else int(pixel_format)
        if not self.has_image_api:
            if fmt != 0:
                raise SinoMatrixError(2, "彩色/YUV 输入需要 SinoMatrix 0.5.0 及以上的运行库")
            return self.decode(data, width, height, stride or width, time_limit_ms, roi)
        bpp = BYTES_PER_PIXEL.get(fmt, 0)
        address, keep, size = self._address(data) if not isinstance(data, int) else (data, None, None)
        if size is not None and bpp and size < (height - 1) * (stride or width * bpp) + width * bpp:
            raise ValueError("缓冲区比 width/height/stride 描述的小")
        image = Image(C.sizeof(Image), fmt, address, width, height, stride, COLOR_CONVERSIONS[color])
        try:
            return self._run_decode(
                lambda o, r: self.dll.SinoMatrix_HanXinDecodeImage(C.byref(image), o, r), time_limit_ms, roi)
        finally:
            del keep

    def decode_array(self, array, pixel_format=None, color="luma", time_limit_ms=500, roi=None):
        """解码 numpy 数组（OpenCV 图像）。行跨度直接读数组的 strides，切片不复制。

        二维 uint8 → gray，二维 uint16 → gray16，三通道默认 bgr（OpenCV），四通道默认 bgra；
        Pillow 转来的数组请写 pixel_format="rgb" / "rgba"。"""
        import numpy as np
        a = array
        if a.ndim == 3 and a.shape[2] == 1:
            a = a[:, :, 0]
        if a.ndim == 2:
            fmt = pixel_format or ("gray16" if a.dtype == np.uint16 else "gray")
            channels = 1
        elif a.ndim == 3 and a.shape[2] in (3, 4):
            channels = a.shape[2]
            fmt = pixel_format or ("bgr" if channels == 3 else "bgra")
        else:
            raise ValueError(f"不支持的数组形状 {a.shape}")
        want = np.uint16 if fmt == "gray16" else np.uint8
        if a.dtype != want:
            raise ValueError(f"{fmt} 需要 {np.dtype(want).name} 数组，得到 {a.dtype}")
        pixel_bytes = a.itemsize * channels
        # 每行内部必须连续，行与行之间可以有间隔（ROI 切片的情况）
        if a.strides[0] <= 0 or a.strides[1] != pixel_bytes or (a.ndim == 3 and a.strides[2] != a.itemsize):
            a = np.ascontiguousarray(a)
        h, w = a.shape[:2]
        return self.decode_image(a.ctypes.data, w, h, fmt, a.strides[0], color, time_limit_ms, roi)

    def decode_file(self, path, time_limit_ms=500, color="luma", roi=None):
        """读取图片文件（需要 Pillow）并解码。

        支持 PNG、JPG、BMP、TIFF、WebP、GIF 等 Pillow 能打开的格式；16 位 PNG/TIFF 保留全部灰阶；
        装了 pillow-heif 时也能读 iPhone 的 HEIC。"""
        from PIL import Image as PILImage
        try:
            import pillow_heif  # 可选
            pillow_heif.register_heif_opener()
        except ImportError:
            pass
        with PILImage.open(path) as im:
            im.load()
            mode = im.mode
            if not self.has_image_api:
                gray = im.convert("L")
                return self.decode(gray.tobytes(), gray.width, gray.height, time_limit_ms=time_limit_ms, roi=roi)
            if mode == "L":
                return self.decode(im.tobytes(), im.width, im.height, time_limit_ms=time_limit_ms, roi=roi)
            if mode in ("I;16", "I;16L"):
                return self.decode_image(im.tobytes(), im.width, im.height, "gray16", 0, color, time_limit_ms, roi)
            if mode in ("I;16B",):
                return self.decode_image(im.tobytes("raw", "I;16"), im.width, im.height, "gray16", 0, color,
                                         time_limit_ms, roi)
            if mode == "I":   # 32 位整数灰度，常见于 16 位 PNG
                arr = im.tobytes("raw", "I;16")  # 截取低 16 位
                return self.decode_image(arr, im.width, im.height, "gray16", 0, color, time_limit_ms, roi)
            if mode == "RGB":
                return self.decode_image(im.tobytes(), im.width, im.height, "rgb", 0, color, time_limit_ms, roi)
            if mode == "RGBA":
                return self.decode_image(im.tobytes(), im.width, im.height, "rgba", 0, color, time_limit_ms, roi)
            if mode in ("1", "LA", "La", "I;16N", "F"):
                gray = im.convert("L")
                return self.decode(gray.tobytes(), gray.width, gray.height, time_limit_ms=time_limit_ms, roi=roi)
            rgb = im.convert("RGB")   # P（调色板）、CMYK、YCbCr、LAB 等
            return self.decode_image(rgb.tobytes(), rgb.width, rgb.height, "rgb", 0, color, time_limit_ms, roi)
