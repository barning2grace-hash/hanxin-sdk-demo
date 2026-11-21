/* SinoMatrix 汉信码 SDK —— C 快速上手：加载授权 → 编码 → 保存 PGM → 解码 */
#include "SinoMatrix.h"
#include <stdio.h>
#include <string.h>

static void print_owned(const char* label, SinoMatrixOwnedString s)
{
    /* 输出以 size 为准，不要用 strlen / %s */
    printf("%s", label);
    if (s.data != NULL)
        fwrite(s.data, 1, (size_t)s.size, stdout);
    printf("\n");
}

int main(int argc, char** argv)
{
    const char* licensePath = argc > 1 ? argv[1] : "license.lic";
    printf("%s\n", SinoMatrix_GetVersionString());

    /* 1. 加载授权：每个进程启动时调用一次 */
    if (SinoMatrix_LoadLicenseFileUtf8(licensePath) != SinoMatrixStatus_Ok) {
        SinoMatrixOwnedString msg = { 0 };
        SinoMatrix_GetLicenseMessage(&msg);
        print_owned("授权加载失败: ", msg);
        SinoMatrix_FreeOwnedString(&msg);
        return 1;
    }

    /* 2. 编码：UTF-8 文本 → 8 位灰度图（0=黑，255=白） */
    const char* text = "SinoMatrix 汉信码 SDK";
    SinoMatrixHanXinEncodeOptions encodeOptions;
    SinoMatrix_InitializeHanXinEncodeOptions(&encodeOptions);
    encodeOptions.modulePixels = 8;      /* 每个模块 8×8 像素 */
    encodeOptions.quietZoneModules = 4;  /* 四周留 4 个模块的静区 */

    SinoMatrixHanXinEncodeResult encoded = { 0 };
    SinoMatrixStatus status = SinoMatrix_HanXinEncodeUtf8WithLength(
        text, (uint64_t)strlen(text), &encodeOptions, &encoded);
    if (status != SinoMatrixStatus_Ok) {
        print_owned("编码失败: ", encoded.errorMessage);
        SinoMatrix_FreeHanXinEncodeResult(&encoded);
        return 2;
    }
    printf("编码成功: 版本 %d，%d×%d 模块，图像 %d×%d\n",
        encoded.version, encoded.size, encoded.size, encoded.rendered.width, encoded.rendered.height);

    /* 保存为 PGM（任何看图软件都能打开，也可换成你自己的图片库） */
    FILE* file = fopen("hanxin.pgm", "wb");
    if (file != NULL) {
        fprintf(file, "P5\n%d %d\n255\n", encoded.rendered.width, encoded.rendered.height);
        for (int y = 0; y < encoded.rendered.height; ++y)
            fwrite(encoded.rendered.data + (size_t)y * encoded.rendered.stride, 1,
                (size_t)encoded.rendered.width, file);
        fclose(file);
    }

    /* 3. 解码：把任意 8 位灰度图交给 V2 接口（这里直接用刚生成的图） */
    SinoMatrixImageView image;
    image.data = encoded.rendered.data;
    image.width = encoded.rendered.width;
    image.height = encoded.rendered.height;
    image.stride = encoded.rendered.stride;

    SinoMatrixHanXinDecodeOptionsV2 decodeOptions;
    SinoMatrix_InitializeHanXinDecodeOptionsV2(&decodeOptions);
    decodeOptions.timeLimitMs = 500;     /* 协作式时间预算，0 表示不限 */

    SinoMatrixHanXinDecodeResultV2 decoded = { 0 };
    status = SinoMatrix_HanXinDecodeGray8V2(image, &decodeOptions, &decoded);
    if (status == SinoMatrixStatus_Ok) {
        print_owned("解码结果: ", decoded.base.textUtf8);
        printf("版本 %d，纠错等级 L%d，分段 %llu 个\n",
            decoded.base.version, (int)decoded.base.eccLevel, (unsigned long long)decoded.segmentCount);
    } else {
        printf("未识别（状态 %d）\n", (int)status);
        print_owned("原因: ", decoded.base.errorMessage);
    }

    /* 4. 释放：成功和失败都要释放 SDK 分配的结果 */
    SinoMatrix_FreeHanXinDecodeResultV2(&decoded);
    SinoMatrix_FreeHanXinEncodeResult(&encoded);
    return status == SinoMatrixStatus_Ok ? 0 : 3;
}
