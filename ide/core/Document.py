import markdown
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
)

class DocumentDialog(QDialog):
    """Dialog to display README.md documentation"""

    def __init__(self, readme_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workspace IDE")
        self.setMinimumWidth(800)
        self.setMinimumHeight(800)

        # Apply dark theme styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2B2B2B;
            }
            QTextBrowser {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3C3F41;
                padding: 15px;
                font-size: 15px;
            }
            QPushButton {
                background-color: #3C3F41;
                color: #CCC;
                border: 1px solid #555;
                padding: 6px 20px;
                border-radius: 3px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4A9EFF;
                color: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("📖 Workspace IDE")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #4A9EFF; padding: 5px;")
        layout.addWidget(header)

        # Text browser to display markdown (with HTML rendering)
        #self.text_browser = QTextEdit()
        #self.text_browser.setReadOnly(True)
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)  # Optional: allows clicking links

        layout.addWidget(self.text_browser)

        # Load and display README
        self.load_readme(readme_path)

        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_readme(self, readme_path):
        """Load and display README.md file"""
        try:
            if not readme_path.exists():
                self.text_browser.setHtml(
                    "<h2 style='color: #E74C3C;'>⚠️ README.md Not Found</h2>"
                    f"<p>The documentation file was not found at:</p>"
                    f"<p><code>{readme_path}</code></p>"
                    "<p>Please create a README.md file in your workspace root directory.</p>"
                )
                return

            with open(readme_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # Convert markdown to HTML
            html_content = self.markdown_to_html(markdown_content)

            # Apply custom styling to the HTML
            styled_html = f"""
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        color: #CCCCCC;
                    }}
                    h1 {{
                        color: #4A9EFF;
                        border-bottom: 2px solid #4A9EFF;
                        padding-bottom: 10px;
                        margin-top: 24px;
                        margin-bottom: 16px;
                    }}
                    h2 {{
                        color: #5DADE2;
                        margin-top: 24px;
                        margin-bottom: 12px;
                    }}
                    h3 {{
                        color: #7FB3D5;
                        margin-top: 20px;
                        margin-bottom: 10px;
                    }}
                    h4 {{
                        color: #85C1E9;
                        margin-top: 16px;
                        margin-bottom: 8px;
                    }}
                    code {{
                        background-color: #3C3F41;
                        padding: 2px 6px;
                        border-radius: 3px;
                        color: #FFC66D;
                        font-family: 'Courier New', monospace;
                        font-size: 0.9em;
                    }}
                    pre {{
                        background-color: #1E1E1E;
                        border: 1px solid #3C3F41;
                        border-radius: 5px;
                        padding: 15px;
                        overflow-x: auto;
                        margin: 12px 0;
                        line-height: 1.4;
                    }}
                    pre code {{
                        background: none;
                        padding: 0;
                        color: #A9B7C6;
                        display: block;
                    }}
                    a {{ color: #4A9EFF; text-decoration: none; }}
                    a:hover {{ text-decoration: underline; }}
                    ul, ol {{
                        margin-left: 20px;
                        margin-top: 8px;
                        margin-bottom: 8px;
                        padding-left: 20px;
                    }}
                    li {{
                        margin: 2px 0;
                        padding: 0;
                        line-height: 1.5;
                    }}
                    li p {{
                        margin: 0;
                        padding: 0;
                    }}
                    blockquote {{
                        border-left: 4px solid #4A9EFF;
                        padding-left: 15px;
                        margin-left: 0;
                        margin-top: 12px;
                        margin-bottom: 12px;
                        color: #999;
                        font-style: italic;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin: 15px 0;
                    }}
                    th, td {{
                        border: 1px solid #3C3F41;
                        padding: 10px;
                        text-align: left;
                    }}
                    th {{
                        background-color: #3C3F41;
                        color: #4A9EFF;
                        font-weight: bold;
                    }}
                    img {{
                        max-width: 100%;
                        height: auto;
                        display: inline-block;
                        margin: 2px;
                    }}
                    hr {{
                        border: none;
                        border-top: 1px solid #3C3F41;
                        margin: 20px 0;
                    }}
                    p {{
                        margin: 8px 0;
                    }}
                </style>
            </head>
            <body>
                {html_content}
            </body>
            </html>
            """

            self.text_browser.setHtml(styled_html)

        except Exception as e:
            self.text_browser.setHtml(
                f"<h2 style='color: #E74C3C;'>⚠️ Error Loading Documentation</h2>"
                f"<p>An error occurred while loading the README.md file:</p>"
                f"<p><code>{str(e)}</code></p>"
            )


    def markdown_to_html(self, markdown_text):
        """Convert markdown to HTML using markdown library with better list handling"""
        try:
            import markdown

            html = markdown.markdown(
                markdown_text,
                extensions=[
                    'fenced_code',
                    'tables',
                    'extra',
                    'nl2br',                    # Converts newlines to <br> (good for simple line breaks)
                    'sane_lists'                # THIS IS THE KEY: removes <p> tags inside list items
                ]
            )

            return html

        except ImportError:
            return """
                <h2 style='color: #E74C3C;'>⚠️ Markdown Package Required</h2>
                <p>The <code>markdown</code> package is required to display documentation.</p>
                <p><strong>To install it, run:</strong></p>
                <pre><code>pip install markdown</code></pre>
                <p>After installation, restart the IDE and try again.</p>
            """

