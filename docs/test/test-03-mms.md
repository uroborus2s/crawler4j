# 测试设计文档：[Module-03] 模块管理系统 (MMS)

## 1. 测试范围与目标

本测试文档覆盖《需求规格说明书 5.1》及《详细设计文档 Module-03》中定义的所有功能需求 (FR)。
目标是验证模块管理器 (ModuleManager) 能正确发现、加载、校验标准模块包，并维护模块注册表 (Registry) 的一致性。

**测试对象**: `src.core.mms` 包
**核心类**: `ModuleManager`, `ModuleLoader`, `Manifest`

## 2. 功能需求测试 (FR Testing)

### FR-CORE-MM-001 模块发现 (Module Discovery)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_001 | **扫描多级目录** | 目录下有多个合法模块文件夹 | `scan_paths=['./modules']` | 返回所有合法模块的 Package 对象列表 | P0 |
| TC_MMS_002 | **忽略隐藏文件** | 目录下包含 `.git`, `__pycache__` | 同上 | 结果列表中不包含隐藏目录 | P2 |
| TC_MMS_003 | **空目录扫描** | 目录为空 | 同上 | 返回空列表，不报错 | P2 |

### FR-CORE-MM-002/003 Manifest 解析与校验 (Manifest Parsing)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_004 | **合法 Manifest 解析** | 存在 `module.yaml` | 标准 YAML 内容 | 解析成功，字段值正确 | P0 |
| TC_MMS_005 | **缺少必填字段** | 无 | `name` 缺失 | 抛出 `InvalidManifestError` | P1 |
| TC_MMS_006 | **字段类型错误** | 无 | `version: 1` (应为 str) | 抛出 `ValidationError` | P1 |
| TC_MMS_007 | **命名规范校验** | 无 | `name: "My Module"` (含空格) | 校验失败，提示只能包含字母数字下划线 | P1 |

### FR-CORE-MM-004 SDK 兼容性校验 (SDK Compatibility)

| 用例ID | 场景描述 | 前置条件 | 输入数据 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_008 | **兼容版本** | Current SDK=1.0.0 | `sdk_version: ">=1.0.0"` | 校验通过，模块状态 ACTIVE | P0 |
| TC_MMS_009 | **不兼容版本** | Current SDK=0.9.0 | `sdk_version: ">=1.0.0"` | 校验失败，模块状态 INCOMPATIBLE | P0 |
| TC_MMS_010 | **版本语法错误** | 无 | `sdk_version: "foo"` | 解析失败，视为无效模块 | P2 |

### FR-CORE-MM-006 安装/卸载/升级 (Lifecycle)

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_011 | **ZIP 安装 (Zip Slip 防御)** | 无 | 上传恶意构造的 `../sensitive` ZIP | 拦截解压，抛出 `SecurityError` | P0 |
| TC_MMS_012 | **正常安装** | 无 | 上传合法 ZIP | 1. 解压到 `modules/` 下<br>2. 注册表更新 | P0 |
| TC_MMS_013 | **覆盖安装 (Upgrade)** | 已存在旧版本 | 上传新版本 ZIP | 1. 旧目录被备份或替换<br>2. 版本号更新 | P1 |
| TC_MMS_014 | **卸载模块** | 模块存在 | 调用 `uninstall` | 1. 目录被删除<br>2. 注册表移除条目 | P1 |

### FR-CORE-MM-008 Settings Store

| 用例ID | 场景描述 | 前置条件 | 操作步骤 | 预期结果 | 优先级 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| TC_MMS_015 | **默认配置加载** | Manifest 含 `defaults` | 加载模块 | Config 中包含默认值 | P1 |
| TC_MMS_016 | **用户配置覆盖** | DB 中有 UserConfig | 加载模块 | Config 值优先使用 UserConfig | P0 |
| TC_MMS_017 | **配置热保存** | 模块运行中 | 调用 `save_settings` | DB 更新，如果不需重启则生效 | P1 |

## 3. 场景测试

### SC_MMS_001 模块依赖完整性检查
1. 模块 Python 代码中 `import pandas`。
2. 环境中未安装 `pandas`。
3. 加载模块 -> `ModuleLoader` 尝试 import entry points。
4. 验证：捕获 `ImportError`，将模块标记为 `BROKEN`，并在 UI 提示“缺少依赖 pandas”。

### SC_MMS_002 禁用与启用
1. 用户在 UI 点击“禁用 Module A”。
2. 系统更新 settings `is_enabled=False`。
3. 验证：
   - 调度器不再接受 Module A 的新任务提交。
   - UI 列表显示 Module A 为灰色。
   - 再次点击“启用”，恢复正常。
