# 策略配置详解 (Configuration)

蛛行演略（crawler4j）的核心强大之处在于其灵活的 **TSM (Task Strategy Management)** 系统。通过配置不同的策略 (`TaskStrategy`)，您可以控制任务在何时、何地以及如何运行。

## 📝 策略模型概览

一个完整的策略配置包含以下五个核心维度：

1.  **资源选择 (Resource Selector)**: 决定任务在哪种环境运行。
2.  **弹性伸缩 (Scaling Policy)**: 决定在资源不足时如何处理。
3.  **执行目标 (Execution Context)**: 定义具体运行哪个业务模块。
4.  **容错控制 (Retry Policy)**: 定义失败重试规则。
5.  **清理策略 (Teardown Policy)**: 定义任务结束后的资源回收方式。

## 🔧 配置详解

以下是 `TaskStrategy` 的 YAML 配置示例及字段详解：

```yaml
id: "ctrip-daily-flight"
name: "携程机票每日抓取"
description: "每天抓取一次机票价格"

# 1. 资源选择: 寻找合适的环境
selector:
  env_type: "chrome"          # 环境类型: chrome, android, virtual_browser
  match_labels:               # 标签匹配 (精确匹配)
    region: "cn-shanghai"
    network: "proxy-enabled"
  wait_timeout: 60            # 等待资源超时 (秒)
  sort_strategy: "best_fit"   # 选择策略: fifo, random, best_fit

# 2. 弹性伸缩: 资源不足怎么办？
scaling:
  mode: "elastic"             # elastic (自动创建) | strict (仅用现有)
  max_concurrency: 5          # 最大并发实例数
  min_idle: 1                 # 保持最小空闲实例 (预热)
  creation_timeout: 120       # 创建新环境超时 (秒)

# 3. 执行目标: 做什么？
execution:
  module: "ctrip-flight"      # 目标模块 ID
  workflow: "search_flight"   # 执行的工作流
  timeout: 600                # 单次执行超时 (秒)
  params:                     # 传递给脚本的初始参数
    dept_city: "SHA"
    arr_city: "PEK"

# 4. 容错控制: 失败了怎么办？
retry:
  max_attempts: 3             # 最大重试次数
  new_env_on_retry: true      # 重试时是否更换环境 (应对 IP 封禁)
  retry_on_condition:         # 触发重试的错误特征 (Regex)
    - "Network Error"
    - "Captcha Detected"

# 5. 清理策略: 结束后怎么收场？
teardown:
  on_success: "recycle"       # 成功后: recycle (回收复用) | destroy (销毁)
  on_failure: "keep_alive"    # 失败后: keep_alive (保留现场供排查)
  on_timeout: "destroy"       # 超时后: destroy (强制销毁)
```

## 💡 关键概念说明

### 环境类型 (EnvType)
*   `chrome`: 标准桌面 Chrome 浏览器环境。
*   `android`: 连接的 Android 真机或模拟器。
*   `virtual_browser`: 基于指纹技术的虚拟浏览器环境。

### 匹配规则 (Match Rules)
`selector` 支持高级的 AST 匹配规则，不仅仅是简单的标签相。例如：
*   选择内存大于 8GB 的节点。
*   选择 IP 归属地为"北京"或"上海"的节点。

### 生命周期控制 (Teardown)
*   **Recycle**: 清理 Cookie 和缓存后放入空闲池，供下个任务复用（效率最高）。
*   **Destroy**: 彻底关闭浏览器/容器释放资源（最干净）。
*   **Keep Alive**: 任务结束后保持浏览器打开。通常用于 **调试** 场景，结合 `on_failure` 使用效果极佳。
