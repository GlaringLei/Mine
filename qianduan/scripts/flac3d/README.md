# FLAC3D SAV Web Export

`xieyaqian.f3sav` 是 FLAC3D 6 二进制保存文件，浏览器不能直接读取。这里的脚本在
FLAC3D 内恢复模型后提取两类表面：

- 非空 zone 与 null zone 的交界面：巷道/开挖表面
- 非空 zone 与模型外界的交界面：模型外边界

结果写入 `public/models/xieyaqian/model.glb`，并同步更新
`public/models/xieyaqian/manifest.json`。

## 运行

1. 在 FLAC3D 6 或能够恢复该版本 SAV 的新版 FLAC3D 中执行：

   ```text
   model restore "G:/Save/Grogramming/Vue3/data-v/xieyaqian.f3sav"
   ```

2. 打开 FLAC3D Python 控制台，执行：

   ```python
   execfile(r"G:\Save\Grogramming\Vue3\data-v\scripts\flac3d\export_xieyaqian_glb.py")
   ```

3. 导出结束后刷新前端页面。主界面的 `SAV 真实模型` 视图会读取生成的 GLB。

脚本只导出边界面，不会把原始 3.87 GB 体网格交给浏览器。颜色表示每个边界 zone
的最小主应力绝对值，单位为 MPa。
