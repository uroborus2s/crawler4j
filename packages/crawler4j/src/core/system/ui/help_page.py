"""In-app public documentation viewer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QTextCharFormat, QTextCursor, QTextDocument
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.button import StyledButton
from src.utils.paths import get_docs_root


@dataclass(frozen=True)
class HelpDocEntry:
    doc_id: str
    group_id: str
    label: str
    relative_path: str


class FittedImageTextBrowser(QTextBrowser):
    """Scale local Markdown images to the visible content width."""

    IMAGE_MARGIN = 32

    def loadResource(self, resource_type: int, name: QUrl):
        if resource_type == QTextDocument.ResourceType.ImageResource and name.isLocalFile():
            path = Path(name.toLocalFile())
            if path.exists():
                image = QImage(str(path))
                if not image.isNull():
                    max_width = max(1, self.viewport().width() - self.IMAGE_MARGIN)
                    if image.width() > max_width:
                        return image.scaledToWidth(
                            max_width,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    return image
        return super().loadResource(resource_type, name)


class HelpPage(QWidget):
    """Embedded viewer for the bundled public docs tree."""

    GROUP_LABEL_ROLE = Qt.ItemDataRole.UserRole + 1
    LINK_COLOR = "#8bd3ff"

    DOC_ENTRIES = [
        HelpDocEntry("docs-index", "", "开始前", "01-getting-started/index.md"),
        HelpDocEntry("guide-index", "user-guide", "指南概览", "02-user-guide/index.md"),
        HelpDocEntry("user-guide", "user-guide", "开始使用", "02-user-guide/user-guide.md"),
        HelpDocEntry("installation", "user-guide", "首次安装", "02-user-guide/installation.md"),
        HelpDocEntry("configuration", "user-guide", "首次设置", "02-user-guide/configuration.md"),
        HelpDocEntry("usage", "user-guide", "日常使用", "02-user-guide/usage.md"),
        HelpDocEntry("admin-guide", "user-guide", "管理员指南", "02-user-guide/admin-guide.md"),
        HelpDocEntry("job-detail-guide", "user-guide", "作业说明", "02-user-guide/job-detail-guide.md"),
        HelpDocEntry("developer-index", "developer-guide", "开发指南概览", "03-developer-guide/index.md"),
        HelpDocEntry("developer-quickstart", "developer-guide", "快速开始", "03-developer-guide/quickstart.md"),
        HelpDocEntry("developer-core-concepts", "developer-guide", "核心概念", "03-developer-guide/core-concepts.md"),
        HelpDocEntry("developer-module-structure", "developer-guide", "模块结构", "03-developer-guide/module-structure.md"),
        HelpDocEntry("reference-core-capabilities", "developer-guide", "Core 能力参考", "03-developer-guide/reference-core-capabilities.md"),
        HelpDocEntry(
            "developer-sdk-cli-reference",
            "developer-guide",
            "SDK / CLI 参考",
            "03-developer-guide/reference-sdk-and-cli.md",
        ),
        HelpDocEntry(
            "developer-ui-and-data-table",
            "developer-guide",
            "UI / Data Table",
            "03-developer-guide/ui-and-data-table.md",
        ),
        HelpDocEntry("developer-debugging", "developer-guide", "调试", "03-developer-guide/debugging.md"),
        HelpDocEntry("build-modules", "developer-guide", "构建", "03-developer-guide/build-modules.md"),
        HelpDocEntry("developer-shipping", "developer-guide", "发布", "03-developer-guide/shipping.md"),
        HelpDocEntry(
            "developer-troubleshooting",
            "developer-guide",
            "故障排查",
            "03-developer-guide/troubleshooting.md",
        )
    ]
    DOC_GROUPS = [
        ("user-guide", "使用指南"),
        ("developer-guide", "开发指南"),
    ]
    DEFAULT_DOC_ID = "docs-index"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._entries_by_id = {entry.doc_id: entry for entry in self.DOC_ENTRIES}
        self._doc_items_by_id: dict[str, QTreeWidgetItem] = {}
        self._group_items_by_id: dict[str, QTreeWidgetItem] = {}
        self._resolved_paths: dict[Path, str] = {}
        self.docs_root = get_docs_root()
        self._setup_ui()
        self.load_data()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_tree = QTreeWidget()
        self.nav_tree.setFixedWidth(260)
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setIndentation(18)
        self.nav_tree.setRootIsDecorated(False)
        self.nav_tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_tree.setStyleSheet("""
            QTreeWidget {
                background-color: rgba(30, 30, 40, 0.9);
                border: none;
                border-right: 1px solid rgba(255, 255, 255, 0.1);
                outline: none;
            }
            QTreeWidget::item {
                min-height: 26px;
                color: rgba(255, 255, 255, 0.78);
            }
            QTreeWidget::item:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            QTreeWidget::item:selected {
                background: rgba(99, 102, 241, 0.3);
                color: white;
            }
            QTreeWidget::item:disabled {
                color: rgba(255, 255, 255, 0.35);
            }
        """)
        self.nav_tree.currentItemChanged.connect(self._on_nav_changed)
        self.nav_tree.itemClicked.connect(self._on_nav_clicked)
        self.nav_tree.itemExpanded.connect(self._on_group_expanded)
        self.nav_tree.itemCollapsed.connect(self._on_group_collapsed)

        for entry in self.DOC_ENTRIES:
            if entry.group_id:
                continue
            item = QTreeWidgetItem([entry.label])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.doc_id)
            self.nav_tree.addTopLevelItem(item)
            self._doc_items_by_id[entry.doc_id] = item

        for group_id, label in self.DOC_GROUPS:
            group_item = QTreeWidgetItem()
            group_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            group_item.setData(0, self.GROUP_LABEL_ROLE, label)
            group_item.setExpanded(True)
            self._set_group_item_label(group_item)
            self.nav_tree.addTopLevelItem(group_item)
            self._group_items_by_id[group_id] = group_item

        for entry in self.DOC_ENTRIES:
            if not entry.group_id:
                continue
            item = QTreeWidgetItem([entry.label])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.doc_id)
            self._group_items_by_id[entry.group_id].addChild(item)
            self._doc_items_by_id[entry.doc_id] = item

        layout.addWidget(self.nav_tree)

        content = QWidget()
        content.setStyleSheet("background-color: #1a1a24;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addStretch()

        self.back_btn = StyledButton("← 后退", variant="secondary", min_height=36, min_width=92)
        self.back_btn.clicked.connect(self._go_back)
        self.back_btn.setEnabled(False)
        header.addWidget(self.back_btn)

        self.forward_btn = StyledButton("→ 前进", variant="secondary", min_height=36, min_width=92)
        self.forward_btn.clicked.connect(self._go_forward)
        self.forward_btn.setEnabled(False)
        header.addWidget(self.forward_btn)

        self.home_btn = StyledButton("⌂ 首页", variant="secondary", min_height=36, min_width=92)
        self.home_btn.clicked.connect(self._go_home)
        header.addWidget(self.home_btn)

        content_layout.addLayout(header)
        self.current_doc_label = None

        self.browser = FittedImageTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setOpenLinks(False)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.browser.setStyleSheet(self._browser_widget_style())
        self.browser.document().setDefaultStyleSheet(self._browser_content_style())
        self.browser.anchorClicked.connect(self._open_link)
        self.browser.sourceChanged.connect(self._on_source_changed)
        self.browser.backwardAvailable.connect(self.back_btn.setEnabled)
        self.browser.forwardAvailable.connect(self.forward_btn.setEnabled)
        content_layout.addWidget(self.browser, 1)

        layout.addWidget(content)

    def load_data(self) -> None:
        self.docs_root = get_docs_root()
        self.browser.setSearchPaths([str(self.docs_root)])
        self._resolved_paths = {}

        available_doc_ids: list[str] = []
        for doc_id, item in self._doc_items_by_id.items():
            entry = self._entries_by_id[doc_id]
            path = self._doc_path(entry)
            exists = path.exists()
            item.setText(0, entry.label if exists else f"{entry.label}（缺失）")
            item.setFlags(
                Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                if exists
                else Qt.ItemFlag.NoItemFlags
            )
            if exists:
                available_doc_ids.append(doc_id)
                self._resolved_paths[path.resolve()] = doc_id

        current_source = self._source_path()
        if current_source and current_source.exists() and self._is_public_doc(current_source):
            self._sync_nav_to_path(current_source)
            self._update_doc_meta(current_source)
            return

        default_doc_id = self.DEFAULT_DOC_ID if self.DEFAULT_DOC_ID in available_doc_ids else None
        if default_doc_id is None and available_doc_ids:
            default_doc_id = available_doc_ids[0]

        if default_doc_id:
            self.nav_tree.setEnabled(True)
            self._open_doc(default_doc_id)
            return

        self.nav_tree.setEnabled(False)
        self.browser.setMarkdown(
            "# 未找到内置文档\n\n"
            "当前运行目录里没有打包后的公开文档，请检查发布产物是否包含 `docs/` 下的公开说明页。"
        )

    def _doc_path(self, entry: HelpDocEntry) -> Path:
        return self.docs_root / entry.relative_path

    def _source_path(self) -> Optional[Path]:
        source = self.browser.source()
        if not source.isValid():
            return None
        local_file = source.toLocalFile()
        if not local_file:
            return None
        return Path(local_file)

    def _open_doc(self, doc_id: str) -> None:
        entry = self._entries_by_id[doc_id]
        path = self._doc_path(entry)
        if not path.exists():
            if self.current_doc_label is not None:
                self.current_doc_label.setText(f"文档缺失：{path}")
            self.browser.setMarkdown(f"# 文档缺失\n\n未找到 `{entry.relative_path}`。")
            return
        self.browser.setSource(QUrl.fromLocalFile(str(path)))

    def _on_nav_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None:
            return
        doc_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not doc_id:
            return
        source_path = self._source_path()
        if source_path and self._resolved_paths.get(source_path.resolve()) == doc_id:
            return
        self._open_doc(doc_id)

    def _on_nav_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if item.childCount() <= 0:
            return
        item.setExpanded(not item.isExpanded())

    def _on_group_expanded(self, item: QTreeWidgetItem) -> None:
        if item.childCount() <= 0:
            return
        self._set_group_item_label(item)

    def _on_group_collapsed(self, item: QTreeWidgetItem) -> None:
        if item.childCount() <= 0:
            return
        self._set_group_item_label(item)

    def _on_source_changed(self, source: QUrl) -> None:
        local_file = source.toLocalFile()
        if not local_file:
            return
        path = Path(local_file)
        self._apply_link_style()
        self._sync_nav_to_path(path)
        self._update_doc_meta(path)

    def _open_link(self, url: QUrl) -> None:
        if url.scheme() and url.scheme() not in {"file", "qrc"}:
            QDesktopServices.openUrl(url)
            return

        base = self.browser.source()
        resolved = base.resolved(url) if base.isValid() else url
        if not resolved.isValid():
            return

        if resolved.isLocalFile():
            path = Path(resolved.toLocalFile())
            if self._is_public_doc(path):
                self.browser.setSource(resolved)
                return

        QDesktopServices.openUrl(resolved)

    def _sync_nav_to_path(self, path: Path) -> None:
        doc_id = self._resolved_paths.get(path.resolve())
        if doc_id is None:
            return
        item = self._doc_items_by_id.get(doc_id)
        if item is None:
            return
        if self.nav_tree.currentItem() is item:
            return
        self.nav_tree.blockSignals(True)
        self.nav_tree.setCurrentItem(item)
        self.nav_tree.blockSignals(False)

    def _update_doc_meta(self, path: Path) -> None:
        if self.current_doc_label is None:
            return
        resolved_path = path.resolve()
        doc_id = self._resolved_paths.get(resolved_path)
        if doc_id is not None:
            label = self._entries_by_id[doc_id].label
        else:
            try:
                label = str(resolved_path.relative_to(self.docs_root.resolve()))
            except ValueError:
                label = path.name
        self.current_doc_label.setText(f"当前文档：{label}")

    def _is_public_doc(self, path: Path) -> bool:
        try:
            path.resolve().relative_to(self.docs_root.resolve())
            return True
        except ValueError:
            return False

    def _go_back(self) -> None:
        self.browser.backward()

    def _go_forward(self) -> None:
        self.browser.forward()

    def _go_home(self) -> None:
        self._open_doc(self.DEFAULT_DOC_ID)

    def _set_group_item_label(self, item: QTreeWidgetItem) -> None:
        label = str(item.data(0, self.GROUP_LABEL_ROLE) or item.text(0) or "").strip()
        arrow = "▾" if item.isExpanded() else "▸"
        item.setText(0, f"{arrow}  {label}")

    def _apply_link_style(self) -> None:
        document = self.browser.document()
        ranges: list[tuple[int, int]] = []

        block = document.firstBlock()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isAnchor():
                    ranges.append((fragment.position(), fragment.length()))
                iterator += 1
            block = block.next()

        if not ranges:
            return

        cursor = QTextCursor(document)
        for start, length in ranges:
            cursor.setPosition(start)
            cursor.setPosition(start + length, QTextCursor.MoveMode.KeepAnchor)
            format_update = QTextCharFormat()
            format_update.setForeground(QColor(self.LINK_COLOR))
            format_update.setFontUnderline(True)
            cursor.mergeCharFormat(format_update)

    @staticmethod
    def _browser_widget_style() -> str:
        return """
            QTextBrowser {
                background: rgba(15, 15, 20, 0.92);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                padding: 16px;
                selection-background-color: rgba(99, 102, 241, 0.4);
            }
        """

    @staticmethod
    def _browser_content_style() -> str:
        return """
            body {
                color: #f5f7ff;
                background: transparent;
                line-height: 1.6;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #ffffff;
            }
            a {
                color: #8bd3ff;
                text-decoration: underline;
                font-weight: 600;
            }
            a:visited {
                color: #a7f3d0;
            }
            img {
                max-width: 100%;
                height: auto;
            }
            code, pre {
                color: #f8fafc;
            }
        """
