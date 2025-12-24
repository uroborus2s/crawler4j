# 快速开始：自动化爬虫 GUI

## 前提条件

1. **Python 3.10+** 已安装。
2. **指纹浏览器** 已安装 (二选一):
   - **BitBrowser**: 从 [bitbrowser.net](https://www.bitbrowser.net/) 下载安装
   - **VirtualBrowser**: 从官方渠道下载安装
3. 确保浏览器 API 已开启:
   - BitBrowser: 设置 -> API 接口 -> 开启
   - 记录 API 地址和端口 (如 `127.0.0.1:54345`)

## 安装

```bash
# 克隆仓库
git clone <repo_url>
cd crawler4j

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器 (首次运行)
playwright install chromium
```

## 运行应用

```bash
# 启动 GUI
python src/main.py
```

## 首次配置

### 1. 选择指纹浏览器

- 打开应用后，进入 **设置** 页面
- 在 **浏览器类型** 下拉框中选择 `BitBrowser` 或 `VirtualBrowser`
- 系统会自动检测所选浏览器是否已安装:
  - ✅ 已安装: 显示绿色勾
  - ❌ 未安装: 显示红色叉，提示下载链接
- 输入 API 地址 (如 `http://127.0.0.1:54345`)

### 2. 导入携程账号

- 进入 **携程账号** 标签页
- 点击 **导入** 并选择 CSV 文件
- CSV 格式: `手机号,密码` (每行一个账号)

### 3. 导入劳保账号

- 进入 **劳保账号** 标签页
- 点击 **导入** 并选择 CSV 文件
- CSV 格式: `手机号,密码` (每行一个账号)

### 4. 启动自动化

- 返回 **控制台** 页面
- 设置 **并发数量** (如 5)
- 点击 **开始** 按钮
- 查看日志和浏览器窗口

## 常见问题

**Q: 提示"浏览器未安装"怎么办？**
A: 请确保已正确安装 BitBrowser 或 VirtualBrowser，并且应用程序路径位于默认位置或已添加到系统 PATH。

**Q: API 连接失败怎么办？**
A: 请确保指纹浏览器已启动，且 API 服务已开启。检查端口号是否正确。
