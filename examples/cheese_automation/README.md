# Cheese 自动化示例模块

这是一个标准 `core-native-v2` 模块。Crawler4j 负责校验、打包和定位脚本；设备侧脚本由 Cheese 官方 VSCode/IDEA 插件执行。

## 校验与打包

```bash
uv run crawler4j check full
uv run crawler4j package build
uv run crawler4j package verify dist/cheese_automation-0.1.0.zip
```

安装模块后运行“Cheese 设置页冒烟测试”工作流，可取得包内脚本的绝对路径。脚本文件也可直接从模块目录读取：

```text
cheese/settings_smoke.js
```

## 设备侧运行

1. 在已授权的 Android 设备安装 Cheese，并授予无障碍权限。
2. 安装 Cheese 官方 VSCode/IDEA 插件，按官方说明连接设备。
3. 用插件运行 `cheese/settings_smoke.js`。
4. 脚本会检查屏幕尺寸、打开 Android 系统设置并验证前台包名；失败时直接抛出错误。

脚本不读取账号、剪贴板、IMEI、OAID 或位置，不使用 ADB、root、固定设备地址或凭据。

参考：[Cheese 官方文档](https://cheese.codeocean.net/)。
