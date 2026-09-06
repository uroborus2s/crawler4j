# TASK-049 最终验证：保留硬件组合，六项配置对齐正常样本

日期：2026-09-06。以用户最新范围为准，之前取消硬件组合限制的实现/评审快照已被取代。

## 最终行为

- CPU/内存池保留约束，按用户最新要求将6/16改4/16：4/8、4/16、8/16、8/32、12/32。随机产生池外组合仍重选并回读验收；0/负数仍报风险；未新增样本中的12/16。
- UA mode0、screen mode0、language/timezone/location mode2，location enable1；speech_voices={mode:1,value:{}}，清掉旧固定语音列表。页面实际语音不要求为空。
- 旧 geo 不回写自定义指纹，仅 country 保留给原代理 payload；旧 geo 缺语言/时区/坐标的路径有回归。手动定位 repair 保留。
- 主版本、必要结构、显式自定义值、代理一致性和 WebRTC 检查保留；只移除不适用的屏幕池/强制 WOW64 修正及固定语音检查。
- 不修改现有环境、代理协议/URL/绑定、数据库或其他 Provider；未复制 Cookie/代理凭据/设备身份。

## 新鲜验证

工作目录项目根，Python 命令前缀均为 `UV_CACHE_DIR=/private/tmp/codex-uv-cache uv run --no-sync`。

- 最终范围 RED：`pytest packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py::test_randomized_fingerprint_patch_keeps_hardware_in_common_pool packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py::test_created_parameter_warnings_flag_inconsistent_fingerprint_values packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py::test_virtualbrowser_create_only_verifies_proxy_without_ip_table_fingerprint -q`，exit1，3 failed（恢复硬件池和空 voices 前的预期失败）。
- GREEN（worker 与父线程分别运行）：`pytest packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_fingerprint.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py -q`，exit0，83 passed in 2.31s。
- `ruff check` 上述3测试及 provider.py / virtualbrowser_fingerprint.py：exit0，All checks passed。
- `git diff --check`：exit0。
- 最终仅一处 docstring 文字订正发生在上述测试后，无逻辑修改，不重复整套测试。
- `check_code_shape.py` 全文件扫描有既有失败（实际 exit1，worker 首次误报 exit0 已纠正），来自旧 fixtures/lambda。最终 AST 对比 HEAD 与当前各文件嵌套命名函数/lambda 计数，无新增，exit0；本任务不扩散重构旧 fixtures，交 reviewer 审查接受基线例外。

## 其他证据与边界

- 模式依据：用户三个正常样本 139/141/142 与 VirtualBrowser 官方 create-browser API 文档；三个样本 speech_voices 都为 mode1/value{}。硬件组合按用户进一步明确保留原池。
- 初次只读加载三个样本的校验实验显示其代理 host 与 url=127.0.0.1 会触发项目既有一致性提示；该提示不是网站203的证据。本次不调整代理策略。
- 真实 VirtualBrowser 创建、页面 runtime、代理公网出口、账号登录、网站203、全仓测试及桌面构建均未运行。本次只证明本地配置逻辑通过相关回归，不能声明203已修复。

最终4/16常量调整后：worker再次运行同一3文件套件83passed、Ruff通过；reviewer独立运行同套检查通过。父线程只读断言最终五组及六项配置精确值通过。code-shape的lambda提示经HEAD45-49行核实为原有，reviewer已撤回新增判断并接受基线。
