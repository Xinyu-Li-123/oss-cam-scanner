from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QWidget,
)

from oss_cam_scanner.binders import (
    AdjustPageBinder,
    ExportPageBinder,
    ImageListBinder,
    PreviewPageBinder,
)
from oss_cam_scanner.controllers import (
    EditController,
    ExportController,
    ImportController,
    PreviewController,
)
from oss_cam_scanner.stores import (
    DocumentStore,
    ExportState,
    PreferenceState,
    PreviewState,
)
from oss_cam_scanner.widgets.adjust_page import AdjustPage
from oss_cam_scanner.widgets.empty_page import EmptyPage
from oss_cam_scanner.widgets.export_page import ExportPage
from oss_cam_scanner.widgets.image_list import ImageListView
from oss_cam_scanner.widgets.preview_page import PreviewPage


class ScannerWindow(QMainWindow):
    def __init__(self, startup_paths: list[Path] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("OSS Cam Scanner")

        self._store = DocumentStore(self)
        self._preview_state = PreviewState(self)
        self._export_state = ExportState(self)
        self._settings = QSettings(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            "oss-cam-scanner",
            "oss-cam-scanner",
        )
        self._preference_state = PreferenceState(self._settings, self)

        self._import_controller = ImportController(self._store)
        self._edit_controller = EditController(self._store, self._preview_state)
        self._preview_controller = PreviewController(
            self._store,
            self._preview_state,
            self._preference_state,
        )
        self._export_controller = ExportController(self._store, self._export_state)

        self._sidebar = ImageListView()
        self._stack = QStackedWidget()
        self._empty_page = EmptyPage()
        self._adjust_page = AdjustPage()
        self._preview_page = PreviewPage()
        self._export_page = ExportPage()

        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._adjust_page)
        self._stack.addWidget(self._preview_page)
        self._stack.addWidget(self._export_page)

        self._sidebar_binder = ImageListBinder(self._sidebar, self._store, self)
        self._adjust_binder = AdjustPageBinder(
            self._adjust_page,
            self._store,
            self._edit_controller,
            self,
        )
        self._preview_binder = PreviewPageBinder(
            self._preview_page,
            self._store,
            self._preview_state,
            self._preview_controller,
            self,
        )
        self._export_binder = ExportPageBinder(
            self._export_page,
            self._store,
            self._export_state,
            self._export_controller,
            self,
        )

        self._build_layout()
        self._build_toolbar()
        self._connect_app_level_signals()

        if startup_paths:
            self.add_images(startup_paths)

    def add_images(self, paths: list[Path]) -> None:
        result = self._import_controller.add_images(paths)
        for failure in result.failures:
            QMessageBox.warning(
                self,
                "Open Image Failed",
                f"{failure.path}\n\n{failure.error}",
            )
        if result.imported_indices and self._store.current_index() < 0:
            self._store.set_current_index(result.imported_indices[0])

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        if self._stack.currentWidget() == self._preview_page:
            self._preview_page.refresh_preview()

    def _build_layout(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.addWidget(self._sidebar, 1)
        layout.addWidget(self._stack, 4)
        self.setCentralWidget(root)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        file_menu = QMenu("File", self)
        open_action = QAction("Open Images", self)
        open_action.triggered.connect(self._choose_images)
        file_menu.addAction(open_action)

        export_action = QAction("Export", self)
        export_action.triggered.connect(self._show_export_page)
        file_menu.addAction(export_action)

        file_button = QToolButton(self)
        file_button.setText("File")
        file_button.setMenu(file_menu)
        file_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(file_button)

        preference_menu = QMenu("Preference", self)
        apply_filters_action = QAction("Apply First Saved Filters To All Pages", self)
        apply_filters_action.setCheckable(True)
        apply_filters_action.setChecked(
            self._preference_state.apply_first_saved_filters_to_all_pages()
        )
        apply_filters_action.toggled.connect(
            self._preference_state.set_apply_first_saved_filters_to_all_pages
        )
        preference_menu.addAction(apply_filters_action)

        preference_button = QToolButton(self)
        preference_button.setText("Preference")
        preference_button.setMenu(preference_menu)
        preference_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(preference_button)

    def _connect_app_level_signals(self) -> None:
        self._empty_page.open_images_requested.connect(self._choose_images)
        self._store.current_index_changed.connect(self._show_selected_index)

        self._adjust_binder.preview_ready.connect(self._show_preview_page)
        self._adjust_binder.preview_failed.connect(self._show_preview_failed)

        self._preview_binder.back_requested.connect(self._show_adjustment)
        self._preview_binder.preview_failed.connect(self._show_preview_operation_failed)
        self._preview_binder.save_failed.connect(self._show_save_failed)
        self._preview_binder.next_requested.connect(self._select_next_index)
        self._preview_binder.export_requested.connect(self._show_export_page)

        self._export_binder.back_requested.connect(self._show_current_or_first_image)
        self._export_binder.export_images_path_requested.connect(
            self._choose_export_image_directory
        )
        self._export_binder.export_pdfs_path_requested.connect(
            self._choose_export_pdf_directory
        )
        self._export_binder.export_combined_pdf_path_requested.connect(
            self._choose_combined_pdf_path
        )
        self._export_binder.export_complete.connect(self._show_export_complete)
        self._export_binder.export_failed.connect(self._show_export_failed)

    def _choose_images(self) -> None:
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All Files (*)",
        )
        self.add_images([Path(filename) for filename in filenames])

    def _show_selected_index(self, index: int) -> None:
        if index < 0:
            self._stack.setCurrentWidget(self._empty_page)
            return
        self._show_adjustment()

    def _show_adjustment(self) -> None:
        if self._store.current_item() is None:
            self._stack.setCurrentWidget(self._empty_page)
            return
        self._adjust_binder.refresh_from_current_item()
        self._stack.setCurrentWidget(self._adjust_page)

    def _show_preview_page(self) -> None:
        self._stack.setCurrentWidget(self._preview_page)
        self._preview_binder.refresh_action_visibility()
        self._preview_binder.refresh_preview()

    def _select_next_index(self, index: int) -> None:
        self._store.set_current_index(index)
        self._show_adjustment()

    def _show_current_or_first_image(self) -> None:
        if self._store.current_index() >= 0:
            self._show_adjustment()
            return
        if self._store.items():
            self._store.set_current_index(0)
            return
        self._stack.setCurrentWidget(self._empty_page)

    def _show_export_page(self) -> None:
        self._export_binder.sync_saved_items()
        if not self._export_binder.has_saved_items():
            QMessageBox.information(
                self,
                "Nothing To Export",
                "Save at least one page before exporting.",
            )
            return
        self._stack.setCurrentWidget(self._export_page)

    def _choose_export_image_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Export Images")
        if directory:
            self._export_binder.export_images_to(Path(directory))

    def _choose_export_pdf_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Export PDFs")
        if directory:
            self._export_binder.export_pdfs_to(Path(directory))

    def _choose_combined_pdf_path(self) -> None:
        stem = self._export_binder.first_output_stem()
        directory = self._export_binder.first_output_directory()
        first_path = directory / f"{stem}-combined-scan.pdf"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Combined PDF",
            str(first_path),
            "PDF File (*.pdf)",
        )
        if filename:
            self._export_binder.export_combined_pdf_to(Path(filename))

    def _show_preview_failed(self, message: str) -> None:
        QMessageBox.warning(
            self,
            "Preview Failed",
            f"Could not warp document region.\n\n{message}",
        )

    def _show_save_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Save Failed", message)

    def _show_preview_operation_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Preview Failed", message)

    def _show_export_complete(self, message: str) -> None:
        QMessageBox.information(self, "Export Complete", message)

    def _show_export_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Export Failed", message)
