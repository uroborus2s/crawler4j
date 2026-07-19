# CR-023 HTTP/2 运行时依赖根因报告

## 基本信息

- Work item：`CR-023`
- 问题来源：`ctrip_crawler` 携程小程序房型列表请求失败
- 受影响路径：宿主源码安装、wheel 安装和 PyInstaller 桌面发布物中的模块运行进程
- 当前状态：`root_cause_found`，用户输入已明确确认根因与修复范围

## 现象

- Bug 症状：构造 `httpx.Client(http2=True)` 抛出缺少 `h2` 的 `ImportError`。
- 复现结果：宿主 `.venv` 中 `h2/hpack/hyperframe/brotli` 均不可导入，同一异常稳定复现。
- 边界：请求未发出，不是代理、TLS、携程协议协商或业务响应问题。

## 调查

- 模块源码明确使用 `http2=True`，并要求服务端最终协商为 `HTTP/2`。
- 模块项目依赖与锁文件完整，但模块 ZIP 安装器没有依赖安装动作。
- 宿主仅依赖基础 `httpx`，锁文件没有 extras 的传递依赖。
- 宿主模块预检仅执行根包导入；根包导入不触发延迟请求路径。

## 根因

- 直接原因：宿主 Python 运行环境缺少 `h2`，并同时缺少当前模块契约要求的 `brotli`。
- 根源原因：模块绕过统一 Core 能力直接使用第三方网络栈，而宿主依赖、锁文件和冻结发布配置也未提供对应实现；导入预检无法发现延迟构造的可选能力。
- 假设验证：见 `.factory/workitems/CR-023/evidence/root-cause-reproduction.md`。

## 修复边界

- 将宿主依赖提升为 `httpx[http2,brotli]>=0.28.1`，同步 lock 和发布配置。
- 通过 full runtime `ctx.tools.call("http.request")` 统一提供 HTTP 能力，模块不再直接 import 或安装第三方实现包。
- 显式收集 `h2/hpack/hyperframe/brotli`，提供可在源码和冻结入口运行的能力检查。
- 增加包元数据、源码解释器、隔离 wheel 和冻结发布物回归。
- 保持模块 ZIP 不安装依赖，不降级或回退 HTTP/2。
- 通用模块能力声明/依赖协商单独登记后续架构项。
- `ctrip_crawler` 需要在其外部仓库将同步 transport 改接异步宿主方法；当前宿主工作项不把未完成的外部接线写成已验收。

## 结论

- 根因明确：是。
- 修复授权：用户委托中明确写明“背景与已确认根因”、首选修复和验收结论，并要求测试、提交。
- 剩余风险：桌面发布物必须在各目标平台分别重建并执行冻结运行时 smoke；当前 macOS 可提供本机证据，Windows 仍需 Windows 构建机复验。
