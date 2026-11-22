/* SinoMatrix 0.5.0: decode a color (BGR) frame without converting it to gray first.
   Usage: decode_bgr license.lic
   The frame is synthesized from an encoded symbol so the sample runs anywhere. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "SinoMatrix.h"

static int decode_bgr(const uint8_t* bgr, int width, int height, int stride)
{
    /* doc-begin */
    SinoMatrixImage image;
    SinoMatrix_InitializeImage(&image, SinoMatrixPixelFormat_Bgr24, bgr, width, height, stride);
    /* image.colorConversion = SinoMatrixColorConversion_MinChannel;  彩色油墨时打开 */

    SinoMatrixHanXinDecodeOptionsV2 options;
    SinoMatrix_InitializeHanXinDecodeOptionsV2(&options);
    options.timeLimitMs = 500;

    SinoMatrixHanXinDecodeResultV2 result = { 0 };
    SinoMatrixStatus status = SinoMatrix_HanXinDecodeImage(&image, &options, &result);
    if (status == SinoMatrixStatus_Ok)
        printf("%.*s\n", (int)result.base.textUtf8.size, result.base.textUtf8.data);
    else
        printf("未识别（状态 %d）\n", (int)status);
    SinoMatrix_FreeHanXinDecodeResultV2(&result);
    /* doc-end */
    return status == SinoMatrixStatus_Ok ? 0 : 1;
}

int main(int argc, char** argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: decode_bgr license.lic\n");
        return 2;
    }
    if (SinoMatrix_LoadLicenseFileUtf8(argv[1]) != SinoMatrixStatus_Ok) {
        fprintf(stderr, "license not loaded\n");
        return 2;
    }

    const char* text = "SinoMatrix 0.5.0 BGR";
    SinoMatrixHanXinEncodeOptions eo;
    SinoMatrix_InitializeHanXinEncodeOptions(&eo);
    eo.modulePixels = 4;
    SinoMatrixHanXinEncodeResult enc = { 0 };
    if (SinoMatrix_HanXinEncodeUtf8WithLength(text, strlen(text), &eo, &enc) != SinoMatrixStatus_Ok) {
        fprintf(stderr, "encode failed\n");
        return 1;
    }

    /* Blue ink on light yellow paper, with 4 bytes of row padding. */
    const int w = enc.rendered.width, h = enc.rendered.height, stride = w * 3 + 4;
    uint8_t* bgr = (uint8_t*)calloc((size_t)stride * (size_t)h, 1);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x) {
            const int dark = enc.rendered.data[(size_t)y * (size_t)enc.rendered.stride + (size_t)x] < 128;
            uint8_t* p = bgr + (size_t)y * (size_t)stride + (size_t)x * 3;
            p[0] = dark ? 150 : 200;   /* B */
            p[1] = dark ? 40 : 245;    /* G */
            p[2] = dark ? 20 : 250;    /* R */
        }
    SinoMatrix_FreeHanXinEncodeResult(&enc);
    const int rc = decode_bgr(bgr, w, h, stride);
    free(bgr);
    return rc;
}
