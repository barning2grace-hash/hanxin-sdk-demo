// 用法：HanXinDemo license.lic 图片.jpg
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using SinoMatrixSdk;

if (args.Length < 2)
{
    Console.WriteLine("用法：HanXinDemo license.lic 图片.jpg");
    return;
}

HanXin.LoadLicense(args[0]);                      // 程序启动时调用一次
Console.WriteLine(HanXin.Version);

// 1. 识别：读图 → 转 8 位灰度 → Decode
using (var bitmap = new Bitmap(args[1]))
{
    byte[] gray = ToGray(bitmap);
    var watch = System.Diagnostics.Stopwatch.StartNew();
    string? text = HanXin.Decode(gray, bitmap.Width, bitmap.Height, bitmap.Width, timeLimitMs: 2000);
    Console.WriteLine(text is null ? "未识别" : $"识别结果（{watch.ElapsedMilliseconds} ms）：{text}");
}

// 2. 生成：文本 → 8 位灰度 → 保存 PNG
byte[] pixels = HanXin.Encode("追溯码：SMHX-2026-000123\n产地：浙江杭州", out int width, out int height);
SaveGrayPng(pixels, width, height, "hanxin.png");
Console.WriteLine($"已生成 hanxin.png（{width}×{height}）");

// 任意格式的 Bitmap 转成紧凑排列的 8 位灰度（每行 width 字节）
static byte[] ToGray(Bitmap bitmap)
{
    int w = bitmap.Width, h = bitmap.Height;
    var data = bitmap.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
    try
    {
        var row = new byte[w * 3];
        var gray = new byte[w * h];
        for (int y = 0; y < h; y++)
        {
            Marshal.Copy(data.Scan0 + y * data.Stride, row, 0, row.Length);
            for (int x = 0; x < w; x++)            // 24 位像素按 B、G、R 排列
                gray[y * w + x] = (byte)((row[x * 3] * 29 + row[x * 3 + 1] * 150 + row[x * 3 + 2] * 77) >> 8);
        }
        return gray;
    }
    finally { bitmap.UnlockBits(data); }
}

static void SaveGrayPng(byte[] gray, int w, int h, string path)
{
    using var bitmap = new Bitmap(w, h, PixelFormat.Format24bppRgb);
    var data = bitmap.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
    try
    {
        var row = new byte[w * 3];
        for (int y = 0; y < h; y++)
        {
            for (int x = 0; x < w; x++)
                row[x * 3] = row[x * 3 + 1] = row[x * 3 + 2] = gray[y * w + x];
            Marshal.Copy(row, 0, data.Scan0 + y * data.Stride, row.Length);
        }
    }
    finally { bitmap.UnlockBits(data); }
    bitmap.Save(path, ImageFormat.Png);
}
