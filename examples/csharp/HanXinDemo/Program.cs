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

// 1. 识别：Bitmap 像素直接传给 SDK（0.5.0 起支持彩色，不用自己转灰度）
using (var bitmap = new Bitmap(args[1]))
{
    var data = bitmap.LockBits(new Rectangle(0, 0, bitmap.Width, bitmap.Height), ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
    try
    {
        var watch = System.Diagnostics.Stopwatch.StartNew();
        // Format24bppRgb 在内存里是 B、G、R 顺序，对应 SmPixelFormat.Bgr24
        string? text = HanXin.Decode(data.Scan0, data.Width, data.Height, data.Stride, SmPixelFormat.Bgr24, timeLimitMs: 2000);
        Console.WriteLine(text is null ? "未识别" : $"识别结果（{watch.ElapsedMilliseconds} ms）：{text}");
    }
    finally { bitmap.UnlockBits(data); }
}

// 2. 生成：文本 → 8 位灰度 → 保存 PNG
byte[] pixels = HanXin.Encode("追溯码：SMHX-2026-000123\n产地：浙江杭州", out int width, out int height);
SaveGrayPng(pixels, width, height, "hanxin.png");
Console.WriteLine($"已生成 hanxin.png（{width}×{height}）");

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
