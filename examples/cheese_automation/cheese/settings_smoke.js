const core = require('cheese-js');

const app = core.app;
const base = core.base;
const device = core.device;

function check(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

function main() {
    const width = device.getScreenWidth();
    const height = device.getScreenHeight();
    check(width > 0 && height > 0, `无效屏幕尺寸: ${width}x${height}`);

    check(app.openApp("com.android.settings"), "无法打开 Android 系统设置");
    base.sleep(1500);

    const foregroundPackage = app.getForegroundPkg();
    check(
        foregroundPackage === "com.android.settings",
        `前台应用不是系统设置: ${foregroundPackage}`,
    );

    console.log(JSON.stringify({
        status: "passed",
        test: "android_settings_smoke",
        screen: `${width}x${height}`,
        foregroundPackage,
    }));
}

main();
