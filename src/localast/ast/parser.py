x"""Multi-language AST parsing using tree-sitter and built-in parsers.

Supports: Python, C#, JavaScript, TypeScript, and extensible for more languages.
Falls back to simple pattern matching for unsupported languages.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

# Try to import tree-sitter (optional dependency)
try:
    from tree_sitter import Language, Parser, Node
    from tree_sitter_python import language as python_language
    from tree_sitter_javascript import language as javascript_language
    from tree_sitter_typescript import language_typescript as typescript_language
    try:
        from tree_sitter_c_sharp import language as csharp_language
        CSHARP_AVAILABLE = True
    except ImportError:
        CSHARP_AVAILABLE = False
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Language = None
    Parser = None
    Node = None


@dataclass(slots=True)
class ParsedSymbol:
    """Minimal representation of a parsed symbol."""

    name: str
    path: Path
    start_line: int
    end_line: int
    kind: str
    parent_name: Optional[str] = None  # For nested symbols
    fqn: Optional[str] = None  # Fully qualified name
    signature: Optional[str] = None  # Function/method signature
    docstring: Optional[str] = None  # Documentation
    calls: List[str] = None  # Functions/methods called by this symbol
    
    def __post_init__(self):
        if self.calls is None:
            self.calls = []


# Language configuration
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".pyw": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".cs": "csharp",
    ".bicep": "bicep",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
}


def detect_language(path: Path) -> Optional[str]:
    """Detect programming language from file extension."""
    return LANGUAGE_EXTENSIONS.get(path.suffix.lower())


@dataclass
class FileImports:
    """Represents imports in a file."""
    path: Path
    imports: List[str]  # List of imported modules/packages


def extract_python_imports(path: Path) -> FileImports:
    """Extract imports from a Python file."""
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return FileImports(path=path, imports=[])
    
    imports = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    
    return FileImports(path=path, imports=imports)


def _parse_python_builtin(path: Path) -> List[ParsedSymbol]:
    """Parse Python using built-in ast module (fast, reliable). Extracts nested symbols and call graphs."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        module = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    symbols: List[ParsedSymbol] = []
    
    def extract_calls(node: ast.AST) -> List[str]:
        """Extract function/method calls from a node."""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    # For method calls like obj.method()
                    calls.append(child.func.attr)
        return calls
    
    def get_signature(node) -> str:
        """Extract function signature."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = []
            for arg in node.args.args:
                args.append(arg.arg)
            return f"{node.name}({', '.join(args)})"
        return node.name
    
    def get_docstring(node) -> Optional[str]:
        """Extract docstring from a node."""
        return ast.get_docstring(node)
    
    def process_node(node: ast.AST, parent_name: Optional[str] = None, parent_fqn: Optional[str] = None) -> None:
        """Process a node and its children recursively."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "function" if isinstance(node, ast.FunctionDef) else "async_function"
            fqn = f"{parent_fqn}.{node.name}" if parent_fqn else node.name
            
            end_line = getattr(node, "end_lineno", node.lineno)
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    path=path,
                    start_line=node.lineno,
                    end_line=end_line,
                    kind=kind,
                    parent_name=parent_name,
                    fqn=fqn,
                    signature=get_signature(node),
                    docstring=get_docstring(node),
                    calls=extract_calls(node),
                )
            )
            
            # Process nested functions
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    process_node(child, parent_name=node.name, parent_fqn=fqn)
        
        elif isinstance(node, ast.ClassDef):
            kind = "class"
            fqn = f"{parent_fqn}.{node.name}" if parent_fqn else node.name
            
            end_line = getattr(node, "end_lineno", node.lineno)
            symbols.append(
                ParsedSymbol(
                    name=node.name,
                    path=path,
                    start_line=node.lineno,
                    end_line=end_line,
                    kind=kind,
                    parent_name=parent_name,
                    fqn=fqn,
                    signature=node.name,
                    docstring=get_docstring(node),
                )
            )
            
            # Process methods and nested classes
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    process_node(child, parent_name=node.name, parent_fqn=fqn)
    
    # Process all top-level nodes
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            process_node(node)

    return symbols


def _parse_with_tree_sitter(path: Path, language: str) -> List[ParsedSymbol]:
    """Parse file using tree-sitter (multi-language support)."""
    if not TREE_SITTER_AVAILABLE:
        return []
    
    # Get language parser
    ts_lang = None
    if language == "python":
        ts_lang = Language(python_language())
    elif language == "javascript":
        ts_lang = Language(javascript_language())
    elif language == "typescript":
        ts_lang = Language(typescript_language())
    elif language == "csharp" and CSHARP_AVAILABLE:
        ts_lang = Language(csharp_language())
    
    if not ts_lang:
        return []
    
    try:
        source = path.read_bytes()
    except OSError:
        return []
    
    parser = Parser()
    try:
        # Try new API (tree-sitter >= 0.21)
        parser.language = ts_lang
    except AttributeError:
        # Fallback to old API (tree-sitter < 0.21)
        parser.set_language(ts_lang)
    tree = parser.parse(source)
    
    symbols: List[ParsedSymbol] = []
    
    # Define queries for different languages
    if language == "python":
        queries = ["function_definition", "class_definition"]
    elif language in ("javascript", "typescript"):
        queries = ["function_declaration", "class_declaration", "method_definition"]
    elif language == "csharp":
        queries = ["method_declaration", "class_declaration", "interface_declaration"]
    else:
        queries = ["function_definition", "class_definition"]
    
    def visit_node(node: Node) -> None:
        """Recursively visit tree nodes."""
        node_type = node.type
        
        # Check if this is a symbol we care about
        if node_type in queries or node_type.endswith("_definition") or node_type.endswith("_declaration"):
            name_node = None
            
            # Try to find the name node (varies by language)
            for child in node.children:
                if child.type == "identifier" or child.type == "property_identifier":
                    name_node = child
                    break
            
            if name_node:
                name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="ignore")
                
                # Determine kind
                kind = "unknown"
                if "function" in node_type or "method" in node_type:
                    kind = "function"
                elif "class" in node_type:
                    kind = "class"
                elif "interface" in node_type:
                    kind = "interface"
                
                symbols.append(
                    ParsedSymbol(
                        name=name,
                        path=path,
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        kind=kind,
                    )
                )
        
        # Recursively visit children
        for child in node.children:
            visit_node(child)
    
    visit_node(tree.root_node)
    return symbols


def _parse_regex_fallback(path: Path, language: str) -> List[ParsedSymbol]:
    """Parse using regex patterns (fallback for unsupported languages)."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    
    symbols: List[ParsedSymbol] = []
    lines = content.splitlines()
    
    # Language-specific patterns
    patterns = []
    
    if language == "csharp":
        # C# patterns: class, interface, method, property
        patterns = [
            (r'^\s*(?:public|private|protected|internal)?\s*(?:static|virtual|override|abstract)?\s*class\s+(\w+)', "class"),
            (r'^\s*(?:public|private|protected|internal)?\s*interface\s+(\w+)', "interface"),
            (r'^\s*(?:public|private|protected|internal)?\s*(?:static|virtual|override|abstract|async)?\s*\w+\s+(\w+)\s*\(', "function"),
        ]
    elif language == "bicep":
        # Bicep patterns: resource, module, output, param
        patterns = [
            (r'^\s*resource\s+(\w+)', "resource"),
            (r'^\s*module\s+(\w+)', "module"),
            (r'^\s*param\s+(\w+)', "param"),
            (r'^\s*output\s+(\w+)', "output"),
            (r'^\s*var\s+(\w+)', "variable"),
        ]
    elif language == "go":
        # Go patterns: func, type, interface
        patterns = [
            (r'^\s*func\s+(?:\(.*?\)\s+)?(\w+)\s*\(', "function"),
            (r'^\s*type\s+(\w+)\s+struct', "class"),
            (r'^\s*type\s+(\w+)\s+interface', "interface"),
        ]
    elif language in ("javascript", "typescript"):
        # JS/TS patterns (fallback if tree-sitter fails)
        patterns = [
            (r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)', "function"),
            (r'^\s*(?:export\s+)?class\s+(\w+)', "class"),
            (r'^\s*(?:export\s+)?interface\s+(\w+)', "interface"),
            (r'^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(', "function"),
        ]
    
    for line_num, line in enumerate(lines, 1):
        for pattern, kind in patterns:
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                # Estimate end line (we don't have accurate info in regex mode)
                end_line = line_num + 10  # Rough estimate
                
                symbols.append(
                    ParsedSymbol(
                        name=name,
                        path=path,
                        start_line=line_num,
                        end_line=end_line,
                        kind=kind,
                    )
                )
    
    return symbols


def parse_file(path: Path) -> List[ParsedSymbol]:
    """Parse a single file and extract symbols.
    
    Uses the best available parser for the language:
    1. Built-in parser (Python: ast module)
    2. Tree-sitter (if available and language supported)
    3. Regex fallback (basic pattern matching)
    
    Parameters
    ----------
    path:
        Path to source file
    
    Returns
    -------
    List of parsed symbols
    """
    language = detect_language(path)
    
    if not language:
        return []
    
    # Python: prefer built-in ast module (faster, more reliable)
    if language == "python":
        return _parse_python_builtin(path)
    
    # Try tree-sitter for supported languages
    if TREE_SITTER_AVAILABLE and language in ("javascript", "typescript", "csharp"):
        symbols = _parse_with_tree_sitter(path, language)
        if symbols:
            return symbols
    
    # Fallback to regex parsing
    return _parse_regex_fallback(path, language)


def parse_symbols(paths: Iterable[Path]) -> List[ParsedSymbol]:
    """Parse multiple files into :class:`ParsedSymbol` instances.
    
    Supports multiple languages based on file extension.
    
    Parameters
    ----------
    paths:
        Paths to source files or directories
    
    Returns
    -------
    List of all parsed symbols
    """
    symbols: List[ParsedSymbol] = []
    
    for raw_path in paths:
        path = raw_path.resolve()
        
        if not path.is_file():
            continue
        
        # Check if this is a supported language
        if detect_language(path):
            symbols.extend(parse_file(path))
    
    return symbols
