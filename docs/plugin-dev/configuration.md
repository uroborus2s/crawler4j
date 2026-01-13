# 插件配置详解 (Plugin Configuration)

每个插件都需要一个清单 (Manifest) 来告诉系统它包含哪些能力。在 Crawler4j 中，这通常通过 `module.yaml` 或 Python entry point 元数据来实现。

## 📝 基础元数据

关键字段说明：

| 字段 | 必填 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `name` | ✅ | 插件唯一 ID (全网唯一)。 | `com.example.flight` |
| `version` | ✅ | 语义化版本号。 | `1.0.0` |
| `entry_point` | ✅ | 插件入口包/类。 | `my_plugin.tasks` |
| `sdk_version` | ❌ | 依赖的 SDK 版本范围。 | `>=0.1.0` |
| `dependencies` | ❌ | 依赖的 Python 包列表。 | `["pandas>=2.0"]` |

## ⚙️ 默认配置 (Default Config)

插件可以定义自己的默认配置 Schema，系统会在 UI 上自动生成对应的配置表单。

```python
# 在 TaskScript 类定义中
class MyTask(TaskScript):
    default_config = {
        "url": "https://example.com",
        "retry_count": 3,
        "headless": True
    }
```

## 🔗 依赖管理

插件的依赖通过标准的 `pyproject.toml` 管理。

```toml
[project]
name = "my-crawler-plugin"
version = "0.1.0"
dependencies = [
    "crawler4j-sdk>=0.1.0",
    "beautifulsoup4>=4.12.0"
]
```

当用户安装插件时，Crawler4j 会解析 `dependencies` 并尝试在隔离环境中安装它们（如果环境支持）。
