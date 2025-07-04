import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QScrollArea, QFrame, QFileIconProvider, QGridLayout,
    QPushButton, QHBoxLayout, QRubberBand
)
from PyQt5.QtCore import Qt, QMimeData, QSize, QUrl, QFileInfo, QRect, QPoint
from PyQt5.QtGui import QPixmap, QDrag, QIcon

if sys.platform == "win32":
    import ctypes

def get_system_icon(file_path):
    if sys.platform == "win32":
        # Use SHGetFileInfo to get system icon for the file (by extension or file itself)
        SHGFI_ICON = 0x100
        SHGFI_SMALLICON = 0x1
        shfileinfo = ctypes.create_string_buffer(352)
        ret = ctypes.windll.shell32.SHGetFileInfoW(
            file_path, 0, shfileinfo, ctypes.sizeof(shfileinfo), SHGFI_ICON | SHGFI_SMALLICON
        )
        if ret:
            hicon = ctypes.cast(shfileinfo[0:8], ctypes.POINTER(ctypes.c_void_p)).contents.value
            if hicon:
                from PyQt5.QtWinExtras import QtWin
                icon = QtWin.fromHICON(hicon)
                ctypes.windll.user32.DestroyIcon(hicon)
                pixmap = icon.pixmap(64, 64)
                return pixmap
    else:
        # Use QFileIconProvider for Linux/macOS
        provider = QFileIconProvider()
        if os.path.exists(file_path):
            icon = provider.icon(QFileInfo(file_path))
        elif os.path.splitext(file_path)[1]:
            # Create a dummy file with the extension to get the icon
            ext = os.path.splitext(file_path)[1]
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=ext) as tmp:
                icon = provider.icon(QFileInfo(tmp.name))
        else:
            icon = provider.icon(QFileIconProvider.File)
        return icon.pixmap(64, 64)
    # fallback: generic icon
    return QIcon.fromTheme("text-x-generic").pixmap(64, 64)

class FileWidget(QFrame):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("background-color: #232323; color: white;")
        self.setFixedWidth(100)
        self.setAcceptDrops(False)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setSpacing(2)

        icon_pixmap = get_system_icon(file_path)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon_pixmap)
        self.icon_label.setAlignment(Qt.AlignCenter)
        vbox.addWidget(self.icon_label)

        self.name_label = QLabel(os.path.basename(file_path))
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setWordWrap(True)
        vbox.addWidget(self.name_label)

        self.setProperty("selected", False)
        self.update_style()

    def update_style(self):
        if self.property("selected"):
            self.setStyleSheet("background-color: #444488; color: white; border: 2px solid #6fa3ef;")
        else:
            self.setStyleSheet("background-color: #232323; color: white; border: none;")

    def set_selected(self, selected):
        self.setProperty("selected", selected)
        self.update_style()

    def is_selected(self):
        return self.property("selected")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            url = "file:///" + os.path.abspath(self.file_path).replace("\\", "/")
            mime.setUrls([QUrl(url)])
            drag.setMimeData(mime)
            drag.setPixmap(self.icon_label.pixmap())
            drag.exec_(Qt.CopyAction)

class DropArea(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #121212;")
        self.grid = QGridLayout(self)
        self.grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.grid.setSpacing(10)
        self.file_count = 0
        self.files_per_row = 4
        self.file_widgets = []
        self.rubber_band = None
        self.origin = QPoint()
        self.plus_label = QLabel("+", self)
        self.plus_label.setAlignment(Qt.AlignCenter)
        self.plus_label.setStyleSheet("color: #6fa3ef; font-size: 96px; font-weight: bold;")
        self.plus_label.hide()
        self.update_plus_label()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_plus_label()

    def update_plus_label(self):
        if self.file_count == 0:
            self.plus_label.show()
            self.plus_label.setGeometry(0, 0, self.width(), self.height())
        else:
            self.plus_label.hide()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.isfile(file_path):
                self.add_file(file_path)
        event.acceptProposedAction()
        self.update_plus_label()

    def add_file(self, file_path):
        widget = FileWidget(file_path)
        row = self.file_count // self.files_per_row
        col = self.file_count % self.files_per_row
        self.grid.addWidget(widget, row, col)
        self.file_widgets.append(widget)
        self.file_count += 1
        self.update_plus_label()

    def remove_selected_files(self):
        to_remove = [w for w in self.file_widgets if w.is_selected()]
        for widget in to_remove:
            self.grid.removeWidget(widget)
            widget.setParent(None)
            self.file_widgets.remove(widget)
            self.file_count -= 1
        self.relayout_files()
        self.update_plus_label()

    def relayout_files(self):
        # Remove all widgets from grid and re-add in order
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)
        for idx, widget in enumerate(self.file_widgets):
            row = idx // self.files_per_row
            col = idx % self.files_per_row
            self.grid.addWidget(widget, row, col)

    def clear_selection(self):
        for widget in self.file_widgets:
            widget.set_selected(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            if not self.rubber_band:
                self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()
            self.clear_selection()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.rubber_band:
            rect = QRect(self.origin, event.pos()).normalized()
            self.rubber_band.setGeometry(rect)
            for widget in self.file_widgets:
                widget_rect = widget.geometry().translated(widget.parentWidget().geometry().topLeft())
                if rect.intersects(widget.geometry()):
                    widget.set_selected(True)
                else:
                    widget.set_selected(False)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.rubber_band:
            self.rubber_band.hide()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.remove_selected_files()
        else:
            super().keyPressEvent(event)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dropflow")
        self.setStyleSheet("background-color: #121212; color: white;")
        self.resize(800, 600)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(10, 10, 10, 10)
        vbox.setSpacing(10)

        # Pin button at top right
        hbox = QHBoxLayout()
        hbox.addStretch()
        self.pin_button = QPushButton("📌")
        self.pin_button.setFixedSize(36, 36)
        self.pin_button.setStyleSheet("background: transparent; font-size: 24px; border: none; color: #6fa3ef;")
        self.pin_button.setCheckable(True)
        self.pin_button.setToolTip("Toggle always on top")
        self.pin_button.clicked.connect(self.toggle_always_on_top)
        hbox.addWidget(self.pin_button)
        vbox.addLayout(hbox)

        self.drop_area = DropArea()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.drop_area)
        scroll.setStyleSheet("background-color: #121212; border: none;")
        vbox.addWidget(scroll)

        self.setFocusPolicy(Qt.StrongFocus)
        self.drop_area.setFocusPolicy(Qt.StrongFocus)

    def toggle_always_on_top(self):
        if self.pin_button.isChecked():
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.show()

    def keyPressEvent(self, event):
        # Forward key events to drop_area for Del key
        self.drop_area.keyPressEvent(event)
        super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())