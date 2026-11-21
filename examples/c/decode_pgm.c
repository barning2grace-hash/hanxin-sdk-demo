/* 读取一张 PGM 灰度图并识别其中的汉信码。
 * 其他格式先转成 PGM，例如：convert photo.jpg -colorspace Gray photo.pgm（ImageMagick）
 * 用法：./decode_pgm license.lic photo.pgm [时间预算毫秒，默认 2000]
 */
#include "SinoMatrix.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned char* read_pgm(const char* path, int* width, int* height)
{
    FILE* f = fopen(path, "rb");
    if (!f) return NULL;
    int maxval = 0, c;
    char magic[3] = { 0 };
    if (fscanf(f, "%2s", magic) != 1 || magic[0] != 'P' || magic[1] != '5') { fclose(f); return NULL; }
    /* 跳过注释行 */
    int* fields[3] = { width, height, &maxval };
    for (int i = 0; i < 3; ++i) {
        while ((c = fgetc(f)) == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '#')
            if (c == '#') while ((c = fgetc(f)) != '\n' && c != EOF) {}
        ungetc(c, f);
        if (fscanf(f, "%d", fields[i]) != 1) { fclose(f); return NULL; }
    }
    fgetc(f); /* 头部后的一个空白字符 */
    if (*width <= 0 || *height <= 0 || maxval != 255) { fclose(f); return NULL; }
    unsigned char* pixels = malloc((size_t)*width * (size_t)*height);
    if (pixels && fread(pixels, 1, (size_t)*width * (size_t)*height, f) != (size_t)*width * (size_t)*height) {
        free(pixels);
        pixels = NULL;
    }
    fclose(f);
    return pixels;
}

int main(int argc, char** argv)
{
    if (argc < 3) { fprintf(stderr, "用法: %s license.lic image.pgm [毫秒]\n", argv[0]); return 2; }

    if (SinoMatrix_LoadLicenseFileUtf8(argv[1]) != SinoMatrixStatus_Ok) {
        SinoMatrixOwnedString msg = { 0 };
        SinoMatrix_GetLicenseMessage(&msg);
        fprintf(stderr, "授权加载失败: %.*s\n", (int)msg.size, msg.data ? msg.data : "");
        SinoMatrix_FreeOwnedString(&msg);
        return 1;
    }

    int width = 0, height = 0;
    unsigned char* gray = read_pgm(argv[2], &width, &height);
    if (!gray) { fprintf(stderr, "无法读取 %s（需要 8 位 P5 格式 PGM）\n", argv[2]); return 2; }

    SinoMatrixImageView image = { gray, width, height, width };
    SinoMatrixHanXinDecodeOptionsV2 options;
    SinoMatrix_InitializeHanXinDecodeOptionsV2(&options);
    options.timeLimitMs = argc > 3 ? atoi(argv[3]) : 2000;   /* 拍照图建议给 1～3 秒预算 */

    SinoMatrixHanXinDecodeResultV2 result = { 0 };
    SinoMatrixStatus status = SinoMatrix_HanXinDecodeGray8V2(image, &options, &result);
    if (status == SinoMatrixStatus_Ok) {
        fwrite(result.base.textUtf8.data, 1, (size_t)result.base.textUtf8.size, stdout);
        printf("\n版本 %d，纠错等级 L%d，位置 (%d, %d) %d×%d\n", result.base.version, (int)result.base.eccLevel,
            result.base.roiX, result.base.roiY, result.base.roiWidth, result.base.roiHeight);
    } else {
        printf("未识别（状态 %d）\n", (int)status);
    }
    SinoMatrix_FreeHanXinDecodeResultV2(&result);   /* 成功失败都要释放 */
    free(gray);
    return status == SinoMatrixStatus_Ok ? 0 : 3;
}
