"""
Browser Plugin - Safe docked DevTools + no crash on close
"""

PLUGIN_NAME = "Browser"
PLUGIN_VERSION = "1.5.0"

def get_widget(parent=None):
    from PyQt6.QtCore import QUrl, Qt
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QWidget, QTabWidget, QToolBar, QPushButton, QLineEdit,
        QVBoxLayout, QProgressBar, QLabel, QHBoxLayout, QSplitter
    )
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEnginePage

    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    # Toolbar
    toolbar = QToolBar()
    toolbar.setMovable(False)

    new_tab_btn = QPushButton("+")
    new_tab_btn.setFixedWidth(32)
    back_btn = QPushButton("←")
    forward_btn = QPushButton("→")
    reload_btn = QPushButton("↻")
    home_btn = QPushButton("🏠")

    find_btn = QPushButton("🔍")
    find_btn.setToolTip("Find in page")
    devtools_btn = QPushButton("🛠️")
    devtools_btn.setCheckable(True)
    devtools_btn.setToolTip("Toggle Developer Tools (docked)")

    zoom_out_btn = QPushButton("−")
    zoom_in_btn = QPushButton("+")
    zoom_label = QLabel("100%")
    zoom_label.setFixedWidth(50)
    zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    address_bar = QLineEdit()
    address_bar.setPlaceholderText("Enter URL or search...")
    address_bar.setClearButtonEnabled(True)

    toolbar.addWidget(new_tab_btn)
    toolbar.addWidget(back_btn)
    toolbar.addWidget(forward_btn)
    toolbar.addWidget(reload_btn)
    toolbar.addWidget(home_btn)
    toolbar.addWidget(find_btn)
    toolbar.addWidget(devtools_btn)
    toolbar.addSeparator()
    toolbar.addWidget(zoom_out_btn)
    toolbar.addWidget(zoom_label)
    toolbar.addWidget(zoom_in_btn)
    toolbar.addSeparator()
    toolbar.addWidget(address_bar)

    # Find bar
    find_bar = QWidget()
    find_bar.setVisible(False)
    find_layout = QHBoxLayout(find_bar)
    find_input = QLineEdit()
    find_input.setPlaceholderText("Find in page...")
    find_prev = QPushButton("↑")
    find_next = QPushButton("↓")
    find_close = QPushButton("×")
    find_label = QLabel("")
    find_layout.addWidget(QLabel("Find:"))
    find_layout.addWidget(find_input)
    find_layout.addWidget(find_prev)
    find_layout.addWidget(find_next)
    find_layout.addWidget(find_label)
    find_layout.addWidget(find_close)

    # Main splitter: web view on top, DevTools below
    main_splitter = QSplitter(Qt.Orientation.Vertical)

    tabs = QTabWidget()
    tabs.setTabsClosable(True)
    tabs.setMovable(True)
    tabs.setDocumentMode(True)

    # Progress bar
    progress_bar = QProgressBar()
    progress_bar.setMaximumHeight(4)
    progress_bar.setTextVisible(False)

    layout.addWidget(toolbar)
    layout.addWidget(find_bar)
    layout.addWidget(main_splitter)
    layout.addWidget(progress_bar)

    # Track DevTools per tab
    devtools_per_tab = {}

    def current_webview():
        widget = tabs.currentWidget()
        if isinstance(widget, QSplitter):
            return widget.widget(0)
        return None

    def current_devtools_view():
        widget = tabs.currentWidget()
        if isinstance(widget, QSplitter) and widget.count() > 1:
            return widget.widget(1)
        return None

    def update_nav_buttons():
        view = current_webview()
        back_btn.setEnabled(view.history().canGoBack() if view else False)
        forward_btn.setEnabled(view.history().canGoForward() if view else False)

    def update_address_bar():
        view = current_webview()
        if view and view.url().isValid():
            address_bar.setText(view.url().toString())
        else:
            address_bar.clear()

    def navigate_to_url():
        view = current_webview()
        if not view: return
        text = address_bar.text().strip()
        if not text: return
        url = QUrl.fromUserInput(text)
        if url.scheme() == "": url.setScheme("https")
        view.load(url)

    def go_home():
        view = current_webview()
        if view: view.load(QUrl("https://www.google.com"))

    def zoom_in():
        view = current_webview()
        if view: view.setZoomFactor(view.zoomFactor() + 0.1)
        update_zoom_label()

    def zoom_out():
        view = current_webview()
        if view: view.setZoomFactor(max(0.3, view.zoomFactor() - 0.1))
        update_zoom_label()

    def update_zoom_label():
        view = current_webview()
        if view:
            zoom_label.setText(f"{int(view.zoomFactor() * 100)}%")

    def toggle_find_bar():
        visible = not find_bar.isVisible()
        find_bar.setVisible(visible)
        if visible:
            find_input.setFocus()
            find_input.selectAll()
        else:
            current_webview().page().findText("") if current_webview() else None

    def find_text(forward=True):
        view = current_webview()
        if not view or not find_input.text(): return
        flags = QWebEnginePage.FindFlags()
        if not forward:
            flags |= QWebEnginePage.FindFlag.FindBackward
        view.page().findText(find_input.text(), flags,
                             lambda found: find_label.setText("Found" if found else "Not found"))

    def toggle_devtools():
        splitter = tabs.currentWidget()
        if not isinstance(splitter, QSplitter):
            return

        devtools = current_devtools_view()
        if devtools and devtools.isVisible():
            devtools.setVisible(False)
            devtools_btn.setChecked(False)
        else:
            if not devtools:
                # Create DevTools view
                dev_view = QWebEngineView()
                current_webview().page().setDevToolsPage(dev_view.page())
                splitter.addWidget(dev_view)
                splitter.setSizes([70, 30])  # 70% web, 30% devtools
                devtools_per_tab[id(current_webview())] = dev_view
            else:
                devtools.setVisible(True)
            devtools_btn.setChecked(True)

    def add_new_tab(url=None, title="New Tab"):
        if url is None:
            url = QUrl("https://www.google.com")
        elif isinstance(url, str):
            url = QUrl.fromUserInput(url)

        view = QWebEngineView()
        view.load(url)

        # Splitter: web view + optional devtools
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(view)
        splitter.setStretchFactor(0, 1)

        index = tabs.addTab(splitter, title)
        tabs.setCurrentIndex(index)

        def on_title_changed(t):
            display = t[:40] + "..." if len(t) > 40 else t or "Untitled"
            tabs.setTabText(index, display)

        def on_load_progress(p):
            progress_bar.setValue(p)
            progress_bar.setVisible(0 < p < 100)
            if p < 100:
                tabs.setTabText(index, f"Loading ({p}%)")
            else:
                on_title_changed(view.page().title())

        view.iconChanged.connect(lambda icon: tabs.setTabIcon(index, icon) if not icon.isNull() else None)
        view.titleChanged.connect(on_title_changed)
        view.loadProgress.connect(on_load_progress)
        view.loadFinished.connect(lambda: (progress_bar.setVisible(False), update_nav_buttons(), update_address_bar(), update_zoom_label()))
        view.urlChanged.connect(update_address_bar)
        view.loadStarted.connect(lambda: progress_bar.setVisible(True))

        # Clean up DevTools reference if tab closed
        def cleanup_tab():
            if id(view) in devtools_per_tab:
                del devtools_per_tab[id(view)]
        tabs.tabCloseRequested.connect(lambda i: cleanup_tab() if i == index else None)

        update_nav_buttons()
        update_address_bar()
        update_zoom_label()

        return view

    # Connections
    new_tab_btn.clicked.connect(lambda: add_new_tab())
    back_btn.clicked.connect(lambda: current_webview().back() if current_webview() else None)
    forward_btn.clicked.connect(lambda: current_webview().forward() if current_webview() else None)
    reload_btn.clicked.connect(lambda: current_webview().reload() if current_webview() else None)
    home_btn.clicked.connect(go_home)
    find_btn.clicked.connect(toggle_find_bar)
    devtools_btn.clicked.connect(toggle_devtools)

    zoom_in_btn.clicked.connect(zoom_in)
    zoom_out_btn.clicked.connect(zoom_out)
    address_bar.returnPressed.connect(navigate_to_url)

    find_next.clicked.connect(lambda: find_text(True))
    find_prev.clicked.connect(lambda: find_text(False))
    find_close.clicked.connect(toggle_find_bar)
    find_input.returnPressed.connect(lambda: find_text(True))

    tabs.currentChanged.connect(lambda idx: (
        update_address_bar(),
        update_nav_buttons(),
        update_zoom_label(),
        devtools_btn.setChecked(current_devtools_view() is not None and current_devtools_view().isVisible())
    ) if idx >= 0 else None)

    tabs.tabCloseRequested.connect(lambda index: (
        tabs.removeTab(index),
        add_new_tab() if tabs.count() == 0 else None
    ))

    # First tab
    add_new_tab(title="Home")

    main_splitter.addWidget(tabs)
    main_splitter.setStretchFactor(0, 1)

    return container