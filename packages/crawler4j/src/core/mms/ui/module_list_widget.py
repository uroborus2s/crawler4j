"""模块列表页。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import (
    ModuleSource,
    ModuleStatus,
    get_module_registry,
    get_module_release_service,
)
from src.core.mms.models import ModuleInfo
from src.core.mms.release_service import ModuleUpdateInfo
from src.core.mms.ui.install_preview_dialog import InstallPreviewDialog
from src.core.mms.ui.module_install_dialog import ModuleInstallDialog, ModuleInstallRequest
from src.ui.components.data_table import SkyDataTable


@dataclass
class ModuleDisplayItem:
    """模块显示项包装。"""

    raw: ModuleInfo
    display_name_str: str


class ModuleListWidget(QWidget):
    """全屏模块管理列表。"""

    open_detail = pyqtSignal(object)

    STATUS_COLORS = {
        ModuleStatus.ENABLED: "#4ade80",
        ModuleStatus.DISABLED: "#9ca3af",
        ModuleStatus.INCOMPATIBLE: "#facc15",
        ModuleStatus.INVALID: "#f87171",
    }
    STATUS_TEXT = {
        ModuleStatus.ENABLED: "已启用",
        ModuleStatus.DISABLED: "已禁用",
        ModuleStatus.INCOMPATIBLE: "不兼容",
        ModuleStatus.INVALID: "无效",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modules: list[ModuleInfo] = []
        self._update_states: dict[str, ModuleUpdateInfo] = {}
        self._update_errors: dict[str, str] = {}
        self._update_check_task: asyncio.Task | None = None
        self._update_check_seq = 0
        self._pending_tasks: set[asyncio.Task] = set()
        self._update_check_running = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("模块管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()

        self.install_btn = QPushButton("📥 安装模块")
        self.install_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
            """
        )
        self.install_btn.clicked.connect(self._install_module)
        header.addWidget(self.install_btn)

        self.dev_link_btn = QPushButton("🔗 添加开发模块")
        self.dev_link_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(245, 158, 11, 0.85);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background: rgba(245, 158, 11, 1); }
            """
        )
        self.dev_link_btn.clicked.connect(self._register_dev_link)
        header.addWidget(self.dev_link_btn)

        self.check_updates_btn = QPushButton("⬆ 检查更新")
        self.check_updates_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(59, 130, 246, 0.85);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(59, 130, 246, 1); }
            """
        )
        self.check_updates_btn.clicked.connect(self._check_updates)
        header.addWidget(self.check_updates_btn)

        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            """
        )
        self.refresh_btn.clicked.connect(lambda: self.load_data(force_refresh=True))
        header.addWidget(self.refresh_btn)

        layout.addLayout(header)

        self.loading_bar = QProgressBar()
        self.loading_bar.setMaximum(0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(3)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        columns = [
            ("name", "名称", 160),
            ("display_name", "显示名", 240),
            ("version", "版本", 150),
            ("status", "状态", 120),
            ("actions", "操作", None),
        ]
        self.table = SkyDataTable(columns=columns)
        self.table.set_render_callback(self._render_row)
        layout.addWidget(self.table)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)

    def load_data(self, *, force_refresh: bool = False):
        """同步加载本地模块列表，并异步检查升级状态。"""
        self.table.set_loading(True)
        self.error_label.hide()

        try:
            registry = get_module_registry()
            if force_refresh:
                registry.refresh()
            self._modules = registry.list_modules()
            display_items = [
                ModuleDisplayItem(raw=module, display_name_str=module.manifest.display_name or module.name)
                for module in self._modules
            ]
            self.table.set_data(display_items)
            self._update_stats_label()
        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        finally:
            self.table.set_loading(False)

        self._schedule_update_check(notify=False)

    def _render_row(self, row: int, item: ModuleDisplayItem, table):
        module = item.raw
        table.setRowHeight(row, 52)

        name_item = QTableWidgetItem(module.name)
        name_item.setData(Qt.ItemDataRole.UserRole, module)
        table.setItem(row, 0, name_item)
        table.setItem(row, 1, QTableWidgetItem(item.display_name_str))

        version_text = module.manifest.version
        update_state = self._update_states.get(module.name)
        if update_state and update_state.has_update:
            version_text = f"{module.manifest.version} → {update_state.latest_version}"
        version_item = QTableWidgetItem(version_text)
        if update_state and update_state.has_update:
            version_item.setForeground(QColor("#60a5fa"))
            version_item.setToolTip(f"检测到可升级版本 {update_state.latest_version}")
        elif module.name in self._update_errors:
            version_item.setToolTip(self._update_errors[module.name])
        table.setItem(row, 2, version_item)

        status_text = self.STATUS_TEXT.get(module.status, module.status.value)
        status_item = QTableWidgetItem(status_text)
        if module.status in self.STATUS_COLORS:
            status_item.setForeground(QColor(self.STATUS_COLORS[module.status]))
        table.setItem(row, 3, status_item)

        table.setCellWidget(row, 4, self._create_action_widget(module))

    def _create_action_widget(self, module: ModuleInfo) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        detail_btn = QPushButton("详情 →")
        detail_btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            """
        )
        detail_btn.clicked.connect(lambda _, m=module: self.open_detail.emit(m))
        layout.addWidget(detail_btn)

        if module.status == ModuleStatus.ENABLED:
            toggle_btn = QPushButton("禁用")
            toggle_btn.setStyleSheet(
                "background: #f87171; color: white; border: none; padding: 5px 8px; border-radius: 3px;"
            )
            toggle_btn.clicked.connect(lambda _, n=module.name: self._disable_module(n))
        else:
            toggle_btn = QPushButton("启用")
            toggle_btn.setStyleSheet(
                "background: #4ade80; color: black; border: none; padding: 5px 8px; border-radius: 3px;"
            )
            toggle_btn.clicked.connect(lambda _, n=module.name: self._enable_module(n))
        if module.status in {ModuleStatus.INVALID, ModuleStatus.INCOMPATIBLE}:
            toggle_btn.setEnabled(False)
        layout.addWidget(toggle_btn)

        if module.source == ModuleSource.EXTERNAL:
            update_state = self._update_states.get(module.name)
            if update_state and update_state.has_update:
                upgrade_btn = QPushButton("升级")
                upgrade_btn.setToolTip(f"升级到 {update_state.latest_version}")
                upgrade_btn.setStyleSheet(
                    "background: #60a5fa; color: black; border: none; padding: 5px 10px; border-radius: 3px;"
                )
                upgrade_btn.clicked.connect(lambda _, n=module.name: self._upgrade_module(n))
                layout.addWidget(upgrade_btn)
            elif self._update_check_running:
                checking_btn = QPushButton("检查中")
                checking_btn.setEnabled(False)
                checking_btn.setStyleSheet(
                    "background: rgba(255,255,255,0.08); color: rgba(255,255,255,0.55); border: none; padding: 5px 10px; border-radius: 3px;"
                )
                layout.addWidget(checking_btn)

        if module.source == ModuleSource.DEV_LINK:
            remove_btn = QPushButton("移除开发链接")
            remove_btn.setToolTip("移除开发链接，不删除本地源码")
            remove_btn.setStyleSheet(
                """
                QPushButton {
                    background: rgba(248, 113, 113, 0.85);
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                }
                QPushButton:hover { background: rgba(248, 113, 113, 1); }
                """
            )
            remove_btn.clicked.connect(lambda _, n=module.name: self._remove_dev_link(n))
            layout.addWidget(remove_btn)

        if module.source == ModuleSource.EXTERNAL:
            uninstall_btn = QPushButton("🗑️")
            uninstall_btn.setToolTip("卸载模块")
            uninstall_btn.setStyleSheet(
                "background: #9ca3af; color: white; border: none; padding: 5px 8px; border-radius: 3px;"
            )
            uninstall_btn.clicked.connect(lambda _, n=module.name: self._uninstall_module(n))
            layout.addWidget(uninstall_btn)

        return widget

    def _track_task(self, coroutine) -> None:
        try:
            task = asyncio.create_task(coroutine)
        except RuntimeError:
            coroutine.close()
            QMessageBox.warning(self, "当前不可用", "当前界面没有可用的异步事件循环，无法执行该操作。")
            return
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    def _set_busy(self, busy: bool, *, checking_updates: bool = False) -> None:
        self.loading_bar.setVisible(busy)
        self.install_btn.setEnabled(not busy)
        self.dev_link_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.check_updates_btn.setEnabled(not busy or checking_updates)

    def _update_stats_label(self) -> None:
        total = len(self._modules)
        enabled_count = sum(1 for module in self._modules if module.status == ModuleStatus.ENABLED)
        update_count = sum(1 for state in self._update_states.values() if state.has_update)
        if update_count:
            self.stats_label.setText(f"共 {total} 个模块，{enabled_count} 个启用，{update_count} 个可升级")
        else:
            self.stats_label.setText(f"共 {total} 个模块，{enabled_count} 个启用")

    def _schedule_update_check(self, *, notify: bool) -> None:
        self._update_check_seq += 1
        seq = self._update_check_seq
        if self._update_check_task and not self._update_check_task.done():
            self._update_check_task.cancel()
        coroutine = self._check_updates_async(seq, notify=notify)
        try:
            self._update_check_task = asyncio.create_task(coroutine)
        except RuntimeError:
            coroutine.close()
            self._update_check_running = False
            self.check_updates_btn.setText("⬆ 检查更新")
            return
        self._pending_tasks.add(self._update_check_task)
        self._update_check_task.add_done_callback(self._pending_tasks.discard)

    def _check_updates(self) -> None:
        self._schedule_update_check(notify=True)

    async def _check_updates_async(self, seq: int, *, notify: bool) -> None:
        external_modules = [
            module for module in self._modules
            if module.source == ModuleSource.EXTERNAL and module.manifest.upgrade_source.repo
        ]
        self._update_check_running = True
        self.check_updates_btn.setText("检查中…")
        self.table.refresh()
        try:
            if not external_modules:
                if notify:
                    QMessageBox.information(self, "检查完成", "当前没有可检查在线升级的正式模块。")
                return

            service = get_module_release_service()
            results = await asyncio.gather(
                *(service.check_for_update(module) for module in external_modules),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            return
        else:
            if seq != self._update_check_seq:
                return

            self._update_states = {}
            self._update_errors = {}
            for module, result in zip(external_modules, results, strict=False):
                if isinstance(result, Exception):
                    self._update_errors[module.name] = str(result)
                    continue
                self._update_states[module.name] = result

            self._update_stats_label()

            if notify:
                update_count = sum(1 for state in self._update_states.values() if state.has_update)
                if self._update_errors:
                    error_modules = "、".join(sorted(self._update_errors.keys()))
                    QMessageBox.warning(
                        self,
                        "检查完成",
                        f"检测到 {update_count} 个可升级模块。\n以下模块检查失败：{error_modules}",
                    )
                else:
                    QMessageBox.information(
                        self,
                        "检查完成",
                        f"检测到 {update_count} 个可升级模块。",
                    )
        finally:
            if seq == self._update_check_seq:
                self._update_check_running = False
                self.check_updates_btn.setText("⬆ 检查更新")
                self.table.refresh()

    def _install_module(self):
        dialog = ModuleInstallDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        self._track_task(self._install_module_async(dialog.get_request()))

    async def _install_module_async(self, request: ModuleInstallRequest) -> None:
        self._set_busy(True)
        try:
            service = get_module_release_service()
            if request.install_kind == "local_zip":
                preview = await service.prepare_local_install(request.source)
            else:
                preview = await service.prepare_github_install(request.source)

            dialog = InstallPreviewDialog(
                preview.manifest,
                preview.warnings,
                self,
                title="确认安装模块",
                confirm_text="确认安装",
                source_details=preview.describe_source(),
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                return

            registry = get_module_registry()
            module_info = registry.install(preview.archive_path)
            QMessageBox.information(self, "成功", f"已安装模块: {module_info.name}")
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "安装失败", str(e))
        finally:
            self._set_busy(False)

    def _register_dev_link(self):
        path = QFileDialog.getExistingDirectory(self, "选择开发模块目录")
        if not path:
            return
        self._track_task(self._register_dev_link_async(path))

    async def _register_dev_link_async(self, path: str) -> None:
        self._set_busy(True)
        try:
            service = get_module_release_service()
            manifest, warnings = await service.prepare_dev_link(path)
            source_details = [
                ("安装来源", "开发模块"),
                ("源码目录", str(Path(path).expanduser().resolve())),
                ("GitHub 仓库", manifest.upgrade_source.repo),
            ]
            dialog = InstallPreviewDialog(
                manifest,
                warnings,
                self,
                title="确认添加开发模块",
                confirm_text="确认添加",
                source_details=source_details,
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                return

            registry = get_module_registry()
            module_info = registry.register_dev_link(path)
            message = (
                f"已添加开发模块: {module_info.name}\n"
                "当前模块来源会切换为“开发链接”，可在 ATM 中发起任务调试。"
            )
            QMessageBox.information(self, "成功", message)
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "添加开发模块失败", str(e))
        finally:
            self._set_busy(False)

    def _upgrade_module(self, module_name: str) -> None:
        self._track_task(self._upgrade_module_async(module_name))

    async def _upgrade_module_async(self, module_name: str) -> None:
        self._set_busy(True)
        try:
            registry = get_module_registry()
            module = registry.get_module(module_name)
            if not module:
                raise ValueError(f"模块不存在: {module_name}")

            service = get_module_release_service()
            preview = await service.prepare_module_upgrade(module)
            source_details = [("当前版本", module.manifest.version), *preview.describe_source()]
            dialog = InstallPreviewDialog(
                preview.manifest,
                preview.warnings,
                self,
                title="确认升级模块",
                confirm_text="确认升级",
                source_details=source_details,
            )
            if dialog.exec() != dialog.DialogCode.Accepted:
                return

            installed = registry.install(preview.archive_path)
            QMessageBox.information(
                self,
                "升级成功",
                f"模块 {installed.name} 已升级到 v{installed.manifest.version}",
            )
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "升级失败", str(e))
        finally:
            self._set_busy(False)

    def _uninstall_module(self, name: str):
        reply = QMessageBox.question(
            self,
            "确认卸载",
            f"确定要卸载模块 '{name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            registry = get_module_registry()
            registry.uninstall(name)
            QMessageBox.information(self, "成功", f"已卸载模块: {name}")
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "卸载失败", str(e))

    def _remove_dev_link(self, name: str):
        reply = QMessageBox.question(
            self,
            "确认移除",
            f"确定要移除开发模块 '{name}' 的开发链接吗？\n本地源码目录不会被删除。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            registry = get_module_registry()
            removed = registry.remove_dev_link(name)
            if not removed:
                QMessageBox.warning(self, "移除失败", f"未找到开发链接: {name}")
                return

            fallback = registry.get_module(name)
            if fallback:
                source_label = "内置模块" if fallback.source == ModuleSource.BUILTIN else "正式安装模块"
                QMessageBox.information(
                    self,
                    "已切换",
                    f"已移除开发链接，当前已回退到 {source_label}: {name}",
                )
            else:
                QMessageBox.information(self, "已移除", f"已移除开发链接: {name}")
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "移除失败", str(e))

    def _enable_module(self, name: str):
        try:
            registry = get_module_registry()
            registry.enable_module(name)
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "启用失败", str(e))

    def _disable_module(self, name: str):
        try:
            registry = get_module_registry()
            registry.disable_module(name)
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "禁用失败", str(e))
