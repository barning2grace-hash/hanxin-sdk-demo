"""SinoMatrix 汉信码 SDK —— Python ctypes 封装（Python 3.8+，64 位）。

把本文件和 SinoMatrix.dll 放在同一目录（或把 DLL 路径传给 load()）。
读取图片需要 Pillow：pip install pillow
"""
import ctypes as C
import os
import sys

c_int, c_uint32, c_uint64, c_double, c_void_p = C.c_int, C.c_uint32, C.c_uint64, C.c_double, C.c_void_p

STATUS = {0: "Ok", 1: "InvalidArgument", 2: "NotSupported", 3: "DecodeFailed", 4: "EncodeFailed",
          5: "InternalError", 6: "LicenseError", 7: "Timeout", 8: "Cancelled"}


class ImageView(C.Structure):
    _fields_ = [("data", c_void_p), ("width", c_int), ("height", c_int), ("stride", c_int)]


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

    def decode(self, gray, width, height, stride=None, time_limit_ms=500):
        """解码 8 位灰度数据。识别失败或超时返回 None；授权/参数错误抛出 SinoMatrixError。"""
        stride = stride or width
        buf = (C.c_ubyte * len(gray)).from_buffer_copy(gray)
        image = ImageView(C.cast(buf, c_void_p), width, height, stride)
        options = DecodeOptionsV2()
        self.dll.SinoMatrix_InitializeHanXinDecodeOptionsV2(C.byref(options))
        options.timeLimitMs = time_limit_ms
        result = DecodeResultV2()
        try:
            status = self.dll.SinoMatrix_HanXinDecodeGray8V2(image, C.byref(options), C.byref(result))
            if status == 0:
                return result.base.textUtf8.text()
            if status in (3, 7):
                return None
            raise SinoMatrixError(status, result.base.errorMessage.text())
        finally:
            self.dll.SinoMatrix_FreeHanXinDecodeResultV2(C.byref(result))

    def decode_file(self, path, time_limit_ms=500):
        """读取 PNG/JPG/BMP 等图片（需要 Pillow）并解码。"""
        from PIL import Image
        with Image.open(path) as im:
            gray = im.convert("L")
            return self.decode(gray.tobytes(), gray.width, gray.height, time_limit_ms=time_limit_ms)
