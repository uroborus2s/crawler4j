# macOS Vendor Assets

将需要随内部 macOS 发布流程复用、但不适合直接提交到仓库的大体积第三方分发物放在这里。

当前默认约定：

- `sparkle/`：解压后的 Sparkle 分发目录
  - `sparkle/Sparkle.framework`
  - `sparkle/bin/generate_appcast`
  - 其他 Sparkle 官方分发自带资源

若不想把 Sparkle 放在仓库工作区，也可以在发布前设置：

- `CRAWLER4J_SPARKLE_ROOT=/absolute/path/to/sparkle`

发布脚本 `uv run package-macos-internal-release` 会优先读取该环境变量；未设置时才回退到本目录下的默认路径。
