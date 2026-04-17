"""模块安装方式选择对话框。"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class ModuleInstallRequest:
    install_kind: str
    source: str
    github_token: str = ""
    remember_github_token: bool = False


class ModuleInstallDialog(QDialog):
    """提供本地 ZIP 与 GitHub URL 两种生产安装入口。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("安装模块")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #1e1e28;
            }
            QLabel {
                color: white;
            }
            QLineEdit {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.16);
                border-radius: 6px;
                padding: 8px 10px;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                background: rgba(255, 255, 255, 0.03);
            }
            QTabBar::tab {
                background: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.75);
                padding: 10px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background: rgba(99, 102, 241, 0.35);
                color: white;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        intro = QLabel("选择模块安装来源。安装前会执行清单校验与 GitHub 升级源检查。")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: rgba(255,255,255,0.72);")
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_local_tab(), "本地 ZIP")
        self.tabs.addTab(self._build_github_tab(), "GitHub 源")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_btn:
            ok_btn.setText("开始检查")
        if cancel_btn:
            cancel_btn.setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        buttons.setStyleSheet(
            """
            QPushButton {
                padding: 8px 20px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton[text="开始检查"] {
                background-color: #4ade80;
                color: black;
            }
            QPushButton[text="取消"] {
                background-color: rgba(255,255,255,0.1);
                color: white;
            }
            """
        )
        layout.addWidget(buttons)

    def _build_local_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_field_label("ZIP 文件"))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("选择模块 ZIP 安装包")
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._browse_zip)
        row.addWidget(self.local_path_input, 1)
        row.addWidget(browse_btn)

        row_widget = QWidget()
        row_widget.setLayout(row)
        layout.addWidget(row_widget)

        layout.addWidget(self._build_field_label("GitHub Token（私有升级仓库可填）"))

        self.local_token_input = QLineEdit()
        self.local_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.local_token_input.setPlaceholderText("如果模块升级仓库是私有仓库，在这里填 Token")
        layout.addWidget(self.local_token_input)

        layout.addWidget(
            self._build_hint_label(
                "要求 ZIP 内包含单一模块根目录，且 `module.yaml` 必须声明 `upgrade_source.repo`。"
            )
        )

        self.local_remember_check = QCheckBox("保存这个 Token，后续更新这个模块时自动使用")
        self.local_remember_check.setStyleSheet("color: rgba(255,255,255,0.72);")
        layout.addWidget(self.local_remember_check)
        layout.addWidget(
            self._build_hint_label(
                "只保存在当前应用，不会上传到 GitHub。安装成功后，会自动绑定到安装包声明的升级仓库。"
            )
        )
        layout.addStretch()
        return widget

    def _build_github_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_field_label("GitHub 仓库"))
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("owner/repo 或 GitHub 仓库 URL")
        layout.addWidget(self.repo_input)

        layout.addWidget(self._build_field_label("GitHub Token（私有仓库必填）"))

        self.repo_token_input = QLineEdit()
        self.repo_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.repo_token_input.setPlaceholderText("公开仓库可留空；私有仓库请填写可读取 Release 的 Token")
        layout.addWidget(self.repo_token_input)

        layout.addWidget(
            self._build_hint_label(
                "仓库必须发布 GitHub Release，且每个可安装版本只能上传一个 `.zip` 模块安装包。"
            )
        )

        self.repo_remember_check = QCheckBox("保存这个 Token，后续更新这个仓库时自动使用")
        self.repo_remember_check.setStyleSheet("color: rgba(255,255,255,0.72);")
        layout.addWidget(self.repo_remember_check)
        layout.addWidget(
            self._build_hint_label(
                "只保存在当前应用，不会上传到 GitHub。后续检查更新或升级这个仓库时会自动复用。"
            )
        )
        layout.addStretch()
        return widget

    @staticmethod
    def _build_field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("color: white; font-size: 13px; font-weight: 600;")
        return label

    @staticmethod
    def _build_hint_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        label.setStyleSheet("color: rgba(255,255,255,0.6); font-size: 12px;")
        return label

    def _browse_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择模块 ZIP 安装包",
            "",
            "ZIP 文件 (*.zip);;所有文件 (*)",
        )
        if path:
            self.local_path_input.setText(path)

    def _accept_if_valid(self) -> None:
        try:
            self.get_request()
        except ValueError as exc:
            QMessageBox.warning(self, "输入无效", str(exc))
            return
        self.accept()

    def get_request(self) -> ModuleInstallRequest:
        if self.tabs.currentIndex() == 0:
            source = self.local_path_input.text().strip()
            if not source:
                raise ValueError("请选择本地 ZIP 安装包")
            github_token = self.local_token_input.text().strip()
            remember = self.local_remember_check.isChecked()
            if remember and not github_token:
                raise ValueError("勾选保存 GitHub Token 时必须先输入 Token")
            return ModuleInstallRequest(
                install_kind="local_zip",
                source=source,
                github_token=github_token,
                remember_github_token=remember,
            )

        source = self.repo_input.text().strip()
        if not source:
            raise ValueError("请输入 GitHub 仓库地址")
        github_token = self.repo_token_input.text().strip()
        remember = self.repo_remember_check.isChecked()
        if remember and not github_token:
            raise ValueError("勾选保存 GitHub Token 时必须先输入 Token")
        return ModuleInstallRequest(
            install_kind="github_release",
            source=source,
            github_token=github_token,
            remember_github_token=remember,
        )
