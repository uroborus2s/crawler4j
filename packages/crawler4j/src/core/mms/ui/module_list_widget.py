"""模块列表页。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.mms import (
    ModuleSource,
    ModuleStatus,
    get_github_credential_store,
    get_module_registry,
    get_module_release_service,
)
from src.core.mms.models import ModuleInfo
from src.core.mms.release_service import ModuleUpdateInfo
from src.core.mms.ui.dev_link_actions import remove_dev_link_and_describe
from src.core.mms.ui.install_preview_dialog import InstallPreviewDialog
from src.core.mms.ui.module_install_dialog import ModuleInstallDialog, ModuleInstallRequest
from src.core.persistence import get_module_data_store
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import attach_display_index, resolve_local_data_table_result


@dataclass
class ModuleDisplayItem:
    """模块显示项包装。"""

    raw: ModuleInfo
    display_name_str: str


class ModuleListWidget(QWidget):
    """全屏模块管理列表。"""

    open_detail = pyqtSignal(object)
    TABLE_SCHEMA = {
        "columns": [
            {"key": "__index__", "label": "序号", "type": "number", "width": 72, "align": "right", "sortable": False, "searchable": False},
            {"key": "name", "label": "名称", "type": "text", "width": 160},
            {"key": "display_name", "label": "显示名", "type": "text", "width": 240},
            {"key": "version", "label": "版本", "type": "text", "width": 150},
            {"key": "status", "label": "状态", "type": "text", "width": 120},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索模块名称、显示名或版本"},
            "sort": {
                "enabled": True,
                "default": [{"field": "display_name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 20, "page_size_options": [10, 20, 50, 100]},
        },
    }

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
        self._display_items: list[ModuleDisplayItem] = []
        self._table_rows: list[dict[str, Any]] = []
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

        self.table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.table.query_requested.connect(self._on_table_query_requested)
        self.table.row_clicked.connect(self._on_table_row_clicked)
        self.table.row_action_requested.connect(self._on_table_action_requested)
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
            self._display_items = [
                ModuleDisplayItem(raw=module, display_name_str=module.manifest.display_name or module.name)
                for module in self._modules
            ]
            self._refresh_table()
            self._update_stats_label()
        except Exception as e:
            self.error_label.setText(f"❌ 加载失败: {e}")
            self.error_label.show()
            return
        finally:
            self.table.set_loading(False)

        self._schedule_update_check(notify=False)

    def _refresh_table(self) -> None:
        self._table_rows = [self._build_table_row(item) for item in self._display_items]
        self.table.request_refresh()

    def _build_table_row(self, item: ModuleDisplayItem) -> dict[str, Any]:
        module = item.raw
        update_state = self._update_states.get(module.name)
        version_text = module.manifest.version
        version_tone = ""
        version_tooltip = ""
        if update_state and update_state.has_update:
            version_text = f"{module.manifest.version} → {update_state.latest_version}"
            version_tone = "info"
            version_tooltip = f"检测到可升级版本 {update_state.latest_version}"
        elif module.name in self._update_errors:
            version_tooltip = self._update_errors[module.name]

        status_text = self.STATUS_TEXT.get(module.status, module.status.value)
        return {
            "module": module,
            "module_name": module.name,
            "name": module.name,
            "display_name": item.display_name_str,
            "version": {
                "text": version_text,
                "tooltip": version_tooltip,
                "tone": version_tone,
                "sort_value": module.manifest.version,
            },
            "status": {
                "text": status_text,
                "tone": self._status_tone(module.status),
            },
            "actions": self._build_row_actions(module),
        }

    def _build_row_actions(self, module: ModuleInfo) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = [
            {"id": "detail", "label": "详情 →", "variant": "primary"},
        ]

        toggle_action = {
            "id": "disable" if module.status == ModuleStatus.ENABLED else "enable",
            "label": "禁用" if module.status == ModuleStatus.ENABLED else "启用",
            "variant": "danger" if module.status == ModuleStatus.ENABLED else "success",
            "enabled": module.status not in {ModuleStatus.INVALID, ModuleStatus.INCOMPATIBLE},
        }
        actions.append(toggle_action)

        if module.source == ModuleSource.EXTERNAL:
            update_state = self._update_states.get(module.name)
            if update_state and update_state.has_update:
                actions.append(
                    {
                        "id": "upgrade",
                        "label": "升级",
                        "tooltip": f"升级到 {update_state.latest_version}",
                        "variant": "info",
                    }
                )
            elif self._update_check_running:
                actions.append(
                    {
                        "id": "checking_updates",
                        "label": "检查中",
                        "enabled": False,
                        "variant": "secondary",
                    }
                )

        if module.source == ModuleSource.DEV_LINK:
            actions.append(
                {
                    "id": "remove_dev_link",
                    "label": "移除开发链接",
                    "tooltip": "移除开发链接，不删除本地源码",
                    "variant": "danger",
                }
            )

        if module.source == ModuleSource.EXTERNAL:
            actions.append(
                {
                    "id": "uninstall",
                    "label": "🗑️",
                    "tooltip": "卸载模块",
                    "variant": "secondary",
                }
            )
        return actions

    def _status_tone(self, status: ModuleStatus) -> str:
        return {
            ModuleStatus.ENABLED: "success",
            ModuleStatus.DISABLED: "neutral",
            ModuleStatus.INCOMPATIBLE: "warning",
            ModuleStatus.INVALID: "danger",
        }.get(status, "neutral")

    def _on_table_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._table_rows,
            columns=self.TABLE_SCHEMA["columns"],
            query=query,
        )
        self.table.apply_result(request_id, attach_display_index(result))

    def _on_table_row_clicked(self, row: dict[str, Any]) -> None:
        module = row.get("module")
        if isinstance(module, ModuleInfo):
            self.open_detail.emit(module)

    def _on_table_action_requested(self, action_id: str, row: dict[str, Any]) -> None:
        module_name = str(row.get("module_name") or "")
        module = row.get("module")
        if action_id == "detail" and isinstance(module, ModuleInfo):
            self.open_detail.emit(module)
        elif action_id == "enable" and module_name:
            self._enable_module(module_name)
        elif action_id == "disable" and module_name:
            self._disable_module(module_name)
        elif action_id == "upgrade" and module_name:
            self._upgrade_module(module_name)
        elif action_id == "remove_dev_link" and module_name:
            self._remove_dev_link(module_name)
        elif action_id == "uninstall" and module_name:
            self._uninstall_module(module_name)

    def _track_task(self, coroutine) -> None:
        try:
            task = asyncio.create_task(coroutine)
        except RuntimeError:
            coroutine.close()
            QMessageBox.warning(self, "当前不可用", "当前界面没有可用的异步事件循环，无法执行该操作。")
            return
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _exec_dialog_async(self, dialog: QDialog) -> int:
        loop = asyncio.get_running_loop()
        result_future = loop.create_future()

        def _resolve(result: int) -> None:
            if not result_future.done():
                result_future.set_result(result)

        dialog.finished.connect(_resolve)
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.open()
        try:
            return int(await result_future)
        finally:
            try:
                dialog.finished.disconnect(_resolve)
            except TypeError:
                pass

    async def _show_message_async(
        self,
        title: str,
        text: str,
        *,
        icon: QMessageBox.Icon,
    ) -> None:
        dialog = QMessageBox(self)
        dialog.setIcon(icon)
        dialog.setWindowTitle(title)
        dialog.setText(text)
        dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        await self._exec_dialog_async(dialog)

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
        self._refresh_table()
        try:
            if not external_modules:
                if notify:
                    await self._show_message_async(
                        "检查完成",
                        "当前没有可检查在线升级的正式模块。",
                        icon=QMessageBox.Icon.Information,
                    )
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
                    await self._show_message_async(
                        "检查完成",
                        f"检测到 {update_count} 个可升级模块。\n以下模块检查失败：{error_modules}",
                        icon=QMessageBox.Icon.Warning,
                    )
                else:
                    await self._show_message_async(
                        "检查完成",
                        f"检测到 {update_count} 个可升级模块。",
                        icon=QMessageBox.Icon.Information,
                    )
        finally:
            if seq == self._update_check_seq:
                self._update_check_running = False
                self.check_updates_btn.setText("⬆ 检查更新")
                self._refresh_table()

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
                preview = await service.prepare_local_install(
                    request.source,
                    github_token=request.github_token or None,
                )
            else:
                preview = await service.prepare_github_install(
                    request.source,
                    github_token=request.github_token or None,
                )

            dialog = InstallPreviewDialog(
                preview.manifest,
                preview.warnings,
                self,
                title="确认安装模块",
                confirm_text="确认安装",
                source_details=preview.describe_source(),
            )
            if await self._exec_dialog_async(dialog) != int(dialog.DialogCode.Accepted):
                return

            if request.remember_github_token and request.github_token:
                get_github_credential_store().set_token(
                    preview.manifest.upgrade_source.repo,
                    request.github_token,
                )

            registry = get_module_registry()
            module_info = registry.install(preview.archive_path)
            await self._show_message_async(
                "成功",
                f"已安装模块: {module_info.name}",
                icon=QMessageBox.Icon.Information,
            )
            self.load_data(force_refresh=True)
        except Exception as e:
            await self._show_message_async(
                "安装失败",
                str(e),
                icon=QMessageBox.Icon.Warning,
            )
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
            if await self._exec_dialog_async(dialog) != int(dialog.DialogCode.Accepted):
                return

            registry = get_module_registry()
            module_info = registry.register_dev_link(path)
            message = (
                f"已添加开发模块: {module_info.name}\n"
                "当前模块来源会切换为“开发链接”，可在 ATM 中发起任务调试。"
            )
            await self._show_message_async(
                "成功",
                message,
                icon=QMessageBox.Icon.Information,
            )
            self.load_data(force_refresh=True)
        except Exception as e:
            await self._show_message_async(
                "添加开发模块失败",
                str(e),
                icon=QMessageBox.Icon.Warning,
            )
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
            if await self._exec_dialog_async(dialog) != int(dialog.DialogCode.Accepted):
                return

            installed = await service.apply_module_upgrade(module, preview)
            await self._show_message_async(
                "升级成功",
                f"模块 {installed.name} 已升级到 v{installed.manifest.version}",
                icon=QMessageBox.Icon.Information,
            )
            self.load_data(force_refresh=True)
        except Exception as e:
            await self._show_message_async(
                "升级失败",
                str(e),
                icon=QMessageBox.Icon.Warning,
            )
        finally:
            self._set_busy(False)

    def _uninstall_module(self, name: str):
        warning_text = self._build_uninstall_warning_text(name)
        reply = QMessageBox.question(
            self,
            "⚠️ 确认卸载并清理数据",
            warning_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            registry = get_module_registry()
            removed = registry.uninstall(name)
            if not removed:
                QMessageBox.warning(self, "卸载失败", f"未能卸载模块: {name}")
                return
            QMessageBox.information(self, "成功", f"已卸载模块: {name}")
            self.load_data(force_refresh=True)
        except Exception as e:
            QMessageBox.warning(self, "卸载失败", str(e))

    def _build_uninstall_warning_text(self, name: str) -> str:
        lines = [
            f"确定要卸载模块 '{name}' 吗？",
            "",
            "此操作不可撤销，并会清理该模块的配置、托管数据、审计事件和宿主页面声明。",
        ]
        try:
            data_store = get_module_data_store()
            resources = data_store.list_data_resources(name)
        except Exception:
            resources = []
            data_store = None

        try:
            db_views = data_store.list_db_views(name) if data_store is not None else []
        except Exception:
            db_views = []

        if resources:
            lines.extend(["", "将清理的数据资源："])
            for resource in resources:
                resource_id = str(resource.get("resource_id") or "")
                storage_mode = str(resource.get("storage_mode") or "")
                cleanup_policy = str(resource.get("cleanup_policy") or "")
                physical_table_name = str(resource.get("physical_table_name") or "")
                if storage_mode == "custom_table":
                    action = "删除自定义物理表" if cleanup_policy == "drop_table" else "保留物理表" if cleanup_policy == "keep" else "清空自定义物理表"
                    lines.append(f"- {resource_id}: {action} {physical_table_name}")
                else:
                    lines.append(f"- {resource_id}: 删除 module_datasets 托管记录")
        else:
            lines.extend(["", "当前未发现已登记的数据资源，但仍会执行模块级配置和数据清理。"])

        if db_views:
            lines.extend(["", "将清理的数据库视图："])
            for db_view in db_views:
                view_id = str(db_view.get("view_id") or "")
                cleanup_policy = str(db_view.get("cleanup_policy") or "")
                physical_view_name = str(db_view.get("physical_view_name") or "")
                if cleanup_policy == "keep":
                    action = "保留数据库视图"
                elif cleanup_policy == "drop_table":
                    action = "删除物化统计表"
                else:
                    action = "删除数据库视图"
                lines.append(f"- {view_id}: {action} {physical_view_name}")

        lines.extend(["", "请确认已经备份需要保留的数据。"])
        return "\n".join(lines)

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
            result = remove_dev_link_and_describe(name)
            QMessageBox.information(self, result.title, result.message)
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
