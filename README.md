# Crawler4j

Crawler4j 是一个基于 Python 的自动化监控与任务执行平台。它集成了网页自动化控制、验证码识别及流程管理功能，主要用于携程（Ctrip）和劳务平台的自动化作业。

## 🚀 核心功能

- **多平台自动化**：支持携程（Ctrip）和劳务平台的自动登录、任务搜索、领取及提交。
- **验证码识别**：内置 ddddocr 支持，能够自动处理复杂的图形验证码。
- **环境管理**：灵活管理不同的执行环境（如浏览器配置、代理等）。
- **账号体系**：支持多账号管理，方便在不同平台间切换。
- **现代化 UI**：基于 PyQt6 开发的图形界面，提供直观的可视化操作和实时日志反馈。
- **流程引擎**：基于 Playwright 的健壮工作流引擎，模拟人工操作，支持弹窗处理和动态加载。

## 🛠️ 技术栈

- **语言**: Python 3.12+
- **界面库**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
- **自动化驱动**: [Playwright](https://playwright.dev/python/)
- **OCR 识别**: [ddddocr](https://github.com/sml2h3/ddddocr)
- **数据处理**: Pandas
- **包管理**: [uv](https://github.com/astral-sh/uv)

## 📂 项目结构

```text
crawler4j/
├── src/
│   ├── automation/      # 自动化核心逻辑
│   │   ├── workflows/   # 平台特定工作流（Ctrip, Labor）
│   │   └── driver.py    # 浏览器驱动封装
│   ├── core/           # 核心业务逻辑与模型
│   ├── ui/              # PyQt6 界面组件
│   │   ├── pages/       # 各业务功能页面
│   │   └── dialogs/     # 交互对话框
│   ├── utils/           # 工具函数（数据库、OCR等）
│   └── main.py          # 程序入口
├── tests/               # 测试用例
├── pyproject.toml       # 项目配置与依赖说明
└── crawler.db           # 本地数据存储（SQLite）
```

## ⚙️ 安装与运行

### 1. 前置要求
确保已安装 [uv](https://github.com/astral-sh/uv)，这是本项目推荐的包管理工具。

### 2. 初始化环境
```bash
# 克隆项目
git clone https://github.com/your-repo/crawler4j.git
cd crawler4j

# 创建虚拟环境并安装依赖
uv sync

# 安装 Playwright 浏览器
uv run playwright install chromium
```

### 3. 启动应用
```bash
uv run start
# 或者直接运行 main.py
uv run python -m src.main
```

## ⚖️ 免责声明
本工具仅供学习和研究自动化技术使用。请在使用过程中严格遵守相关平台的政策、法律法规。开发者不对任何因不当使用该工具而导致的违规或损失负责。
