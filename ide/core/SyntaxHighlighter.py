import re
from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Keyword format (orange-brown, bold)
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#CC7832"))
        self.keyword_format.setFontWeight(75)  # Bold

        # Built-in functions / types (purple)
        self.builtin_format = QTextCharFormat()
        self.builtin_format.setForeground(QColor("#9876AA"))

        # Strings (green)
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#6A8759"))

        # Comments (gray, italic)
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))
        self.comment_format.setFontItalic(True)

        # Numbers (blue)
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#6897BB"))

        # self / cls (same as keywords)
        self.self_format = QTextCharFormat()
        self.self_format.setForeground(QColor("#CC7832"))
        self.self_format.setFontWeight(75)

        # Python keywords
        self.keywords = [
            'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
            'break', 'class', 'continue', 'def', 'del', 'elif', 'else',
            'except', 'finally', 'for', 'from', 'global', 'if', 'import',
            'in', 'is', 'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise',
            'return', 'try', 'while', 'with', 'yield'
        ]

        # Common built-ins
        self.builtins = [
            'print', 'len', 'range', 'list', 'dict', 'set', 'tuple', 'str',
            'int', 'float', 'bool', 'object', 'type', 'super', 'property',
            'classmethod', 'staticmethod', 'enumerate', 'zip', 'map', 'filter',
            'open', 'input', 'abs', 'sum', 'max', 'min', 'sorted', 'reversed'
        ]

        # Compiled regex patterns for performance
        self.patterns = [
            # Numbers: decimal, float, scientific
            (re.compile(r'\b(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\b'), self.number_format),
            # Hex, binary, octal
            (re.compile(r'\b0[xX][0-9a-fA-F]+\b'), self.number_format),
            (re.compile(r'\b0[bB][01]+\b'), self.number_format),
            (re.compile(r'\b0[oO][0-7]+\b'), self.number_format),

            # Keywords (word boundaries)
            (re.compile(r'\b(' + '|'.join(re.escape(k) for k in self.keywords) + r')\b'), self.keyword_format),

            # Built-ins (careful: avoid matching after dot)
            (re.compile(r'\b(' + '|'.join(re.escape(b) for b in self.builtins) + r')\b'), self.builtin_format),

            # self and cls
            (re.compile(r'\b(self|cls)\b'), self.self_format),
        ]

    def highlightBlock(self, text: str):
        if not text:
            return

        # Find comment start (#)
        comment_match = re.search(r'#', text)
        if comment_match:
            comment_start = comment_match.start()
            self.setFormat(comment_start, len(text) - comment_start, self.comment_format)
            text_for_syntax = text[:comment_start]
        else:
            comment_start = len(text)
            text_for_syntax = text

        # String regex: supports f-strings, raw, bytes, triple/single/double quotes
        # Non-greedy matching with support for escaped quotes
        string_regex = re.compile(
            r'([fFrRbBuU]{0,2})'                     # optional prefixes
            r'(?:'
            r'"""(?:\\.|[^\\]|"(?!""))*?"""|'       # triple double (non-greedy)
            r"'''(?:\\.|[^\\]|'(?!''))*?'''|"       # triple single
            r'"(?:\\.|[^"\\])*"|'                   # double quoted
            r"'(?:\\.|[^'\\])*'"                    # single quoted
            r')'
        )

        # Highlight all strings (including multi-line ones that fit in this block)
        string_ranges = []
        for match in string_regex.finditer(text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.string_format)
            string_ranges.append((start, start + length))

        # Apply other highlighting only outside strings and comments
        for pattern, fmt in self.patterns:
            for match in pattern.finditer(text):
                start = match.start()
                end = match.end()

                # Skip if inside comment
                if start >= comment_start:
                    continue

                # Skip if inside any string
                if any(s_start <= start < s_end for s_start, s_end in string_ranges):
                    continue

                # Apply format
                self.setFormat(start, end - start, fmt)



class PhpHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Keywords (orange-brown, bold)
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor("#CC7832"))
        self.keyword_format.setFontWeight(75)

        # Built-in functions / types (purple)
        self.builtin_format = QTextCharFormat()
        self.builtin_format.setForeground(QColor("#9876AA"))

        # Variables ($var) (light blue)
        self.variable_format = QTextCharFormat()
        self.variable_format.setForeground(QColor("#A9B7C6"))

        # Strings (green)
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor("#6A8759"))

        # Comments (gray, italic)
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#808080"))
        self.comment_format.setFontItalic(True)

        # Numbers (blue)
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor("#6897BB"))

        # PHP keywords
        self.keywords = [
            'abstract', 'and', 'array', 'as', 'break', 'callable', 'case',
            'catch', 'class', 'clone', 'const', 'continue', 'declare',
            'default', 'do', 'echo', 'else', 'elseif', 'empty', 'enddeclare',
            'endfor', 'endforeach', 'endif', 'endswitch', 'endwhile', 'eval',
            'exit', 'extends', 'final', 'finally', 'for', 'foreach', 'function',
            'global', 'goto', 'if', 'implements', 'include', 'include_once',
            'instanceof', 'insteadof', 'interface', 'isset', 'list', 'match',
            'namespace', 'new', 'or', 'print', 'private', 'protected', 'public',
            'readonly', 'require', 'require_once', 'return', 'static',
            'switch', 'throw', 'trait', 'try', 'unset', 'use', 'var', 'while',
            'xor', 'yield'
        ]

        # Common PHP built-ins
        self.builtins = [
            'strlen', 'count', 'in_array', 'array_merge', 'array_map',
            'array_filter', 'explode', 'implode', 'substr', 'strpos',
            'str_replace', 'trim', 'ltrim', 'rtrim', 'printf', 'sprintf',
            'var_dump', 'print_r', 'json_encode', 'json_decode',
            'file_get_contents', 'file_put_contents', 'fopen', 'fclose',
            'is_array', 'is_string', 'is_int', 'is_float', 'is_bool',
            'isset', 'empty', 'die'
        ]

        # Compiled regex patterns
        self.patterns = [
            # Numbers (int, float, scientific)
            (re.compile(r'\b(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\b'), self.number_format),

            # Hex numbers
            (re.compile(r'\b0[xX][0-9a-fA-F]+\b'), self.number_format),

            # Keywords
            (re.compile(r'\b(' + '|'.join(re.escape(k) for k in self.keywords) + r')\b'),
             self.keyword_format),

            # Built-ins
            (re.compile(r'\b(' + '|'.join(re.escape(b) for b in self.builtins) + r')\b'),
             self.builtin_format),

            # Variables ($var, $this, $_POST, etc.)
            (re.compile(r'\$[a-zA-Z_][a-zA-Z0-9_]*'), self.variable_format),
        ]

    def highlightBlock(self, text: str):
        if not text:
            return

        # Single-line comments: // or #
        comment_match = re.search(r'//|#', text)
        comment_start = len(text)

        if comment_match:
            comment_start = comment_match.start()
            self.setFormat(comment_start, len(text) - comment_start, self.comment_format)
            text_for_syntax = text[:comment_start]
        else:
            text_for_syntax = text

        # Strings: single & double quoted, with escapes
        string_regex = re.compile(
            r'"(?:\\.|[^"\\])*"|'
            r"'(?:\\.|[^'\\])*'"
        )

        string_ranges = []
        for match in string_regex.finditer(text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.string_format)
            string_ranges.append((start, start + length))

        # Apply other patterns outside strings & comments
        for pattern, fmt in self.patterns:
            for match in pattern.finditer(text):
                start = match.start()
                end = match.end()

                # Skip comments
                if start >= comment_start:
                    continue

                # Skip strings
                if any(s <= start < e for s, e in string_ranges):
                    continue

                self.setFormat(start, end - start, fmt)
