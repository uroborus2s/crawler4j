# CLI 手册 (CLI Manual)

`crawler4j-cli` (或 `crawler4j` 命令) 是插件开发的瑞士军刀。

## 基本用法

```bash
uv run crawler4j <command> [args]
```

## 命令详解

### `init`
初始化一个新的插件项目。

```bash
crawler4j init <project_name>
```

*   **参数**:
    *   `project_name`: 项目名称，将作为文件夹名。
    *   `--no-install`: 跳过依赖安装 (`uv sync`)。

### `add`
向当前项目添加一个新的任务脚本。

```bash
crawler4j add [task_name]
```

*   **参数**:
    *   `task_name`: (可选) 任务名称。若不填则会进入交互模式，询问名称、描述等信息。

### `list`
列出当前项目下的所有任务。

```bash
crawler4j list
```

### `build` (SDK 内置暂未包含，通常通过 uv build)
构建插件包。
*(注: 当前版本建议使用 `uv build` 进行标准 Python 包构建)*
