"""Configuration file parser for JSON, YAML, XML, and other formats."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


@dataclass
class ConfigNode:
    """Represents a node in a configuration file hierarchy."""
    
    key: str
    value: Any
    value_type: str  # "string", "number", "boolean", "array", "object", "null"
    key_path: str  # Full dot-notation path (e.g., "database.connection.host")
    line_number: Optional[int] = None
    children: List[ConfigNode] = field(default_factory=list)
    parent: Optional[ConfigNode] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "key": self.key,
            "value": str(self.value) if not isinstance(self.value, (dict, list)) else None,
            "value_type": self.value_type,
            "key_path": self.key_path,
            "line_number": self.line_number,
            "children": [child.to_dict() for child in self.children],
        }


@dataclass
class ConfigFile:
    """Represents a parsed configuration file."""
    
    path: Path
    format: str  # "json", "yaml", "xml", "toml", etc.
    root_nodes: List[ConfigNode]
    raw_content: str
    hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "path": str(self.path),
            "format": self.format,
            "root_nodes": [node.to_dict() for node in self.root_nodes],
            "hash": self.hash,
        }
    
    def get_node_by_path(self, key_path: str) -> Optional[ConfigNode]:
        """Get a node by its key path (e.g., 'database.connection.host')."""
        for node in self.root_nodes:
            if node.key_path == key_path:
                return node
            # Search recursively
            result = self._search_children(node, key_path)
            if result:
                return result
        return None
    
    def _search_children(self, node: ConfigNode, key_path: str) -> Optional[ConfigNode]:
        """Recursively search children for a key path."""
        for child in node.children:
            if child.key_path == key_path:
                return child
            result = self._search_children(child, key_path)
            if result:
                return result
        return None


def detect_config_format(path: Path) -> Optional[str]:
    """Detect configuration file format from extension."""
    ext = path.suffix.lower()
    
    if ext in (".json", ".jsonc"):
        return "json"
    elif ext in (".yaml", ".yml"):
        return "yaml"
    elif ext == ".xml":
        return "xml"
    elif ext == ".toml":
        return "toml"
    elif ext in (".ini", ".cfg"):
        return "ini"
    elif ext == ".properties":
        return "properties"
    
    # Check common config file names
    name = path.name.lower()
    if name in ("dockerfile", ".dockerignore"):
        return "docker"
    elif name.startswith(".env"):
        return "env"
    elif name in ("makefile", "gnumakefile"):
        return "makefile"
    
    return None


def _get_value_type(value: Any) -> str:
    """Determine the type of a configuration value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, (int, float)):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    else:
        return "unknown"


def _build_nodes_from_dict(data: Dict[str, Any], parent_path: str = "", parent: Optional[ConfigNode] = None) -> List[ConfigNode]:
    """Build ConfigNode tree from a dictionary."""
    nodes = []
    
    for key, value in data.items():
        key_path = f"{parent_path}.{key}" if parent_path else key
        value_type = _get_value_type(value)
        
        node = ConfigNode(
            key=key,
            value=value if value_type not in ("object", "array") else None,
            value_type=value_type,
            key_path=key_path,
            parent=parent,
        )
        
        # Recursively process nested dictionaries
        if isinstance(value, dict):
            node.children = _build_nodes_from_dict(value, key_path, node)
        # Process arrays
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    array_key_path = f"{key_path}[{i}]"
                    array_node = ConfigNode(
                        key=f"[{i}]",
                        value=None,
                        value_type="object",
                        key_path=array_key_path,
                        parent=node,
                    )
                    array_node.children = _build_nodes_from_dict(item, array_key_path, array_node)
                    node.children.append(array_node)
                else:
                    node.children.append(ConfigNode(
                        key=f"[{i}]",
                        value=item,
                        value_type=_get_value_type(item),
                        key_path=f"{key_path}[{i}]",
                        parent=node,
                    ))
        
        nodes.append(node)
    
    return nodes


def _parse_json(path: Path, content: str) -> List[ConfigNode]:
    """Parse JSON configuration file."""
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return _build_nodes_from_dict(data)
        elif isinstance(data, list):
            # Top-level array
            nodes = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    nodes.extend(_build_nodes_from_dict(item, f"[{i}]"))
            return nodes
        else:
            return []
    except json.JSONDecodeError:
        return []


def _parse_yaml(path: Path, content: str) -> List[ConfigNode]:
    """Parse YAML configuration file."""
    if not YAML_AVAILABLE:
        return []
    
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return _build_nodes_from_dict(data)
        elif isinstance(data, list):
            nodes = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    nodes.extend(_build_nodes_from_dict(item, f"[{i}]"))
            return nodes
        else:
            return []
    except yaml.YAMLError:
        return []


def _parse_xml(path: Path, content: str) -> List[ConfigNode]:
    """Parse XML configuration file."""
    try:
        root = ET.fromstring(content)
        
        def xml_to_nodes(element: ET.Element, parent_path: str = "", parent: Optional[ConfigNode] = None) -> List[ConfigNode]:
            """Convert XML element tree to ConfigNode tree."""
            nodes = []
            
            key = element.tag
            key_path = f"{parent_path}.{key}" if parent_path else key
            
            # Get text content
            text = element.text.strip() if element.text else None
            has_children = len(element) > 0
            
            node = ConfigNode(
                key=key,
                value=text if not has_children else None,
                value_type="string" if text and not has_children else "object",
                key_path=key_path,
                parent=parent,
            )
            
            # Add attributes as children
            for attr_key, attr_value in element.attrib.items():
                attr_node = ConfigNode(
                    key=f"@{attr_key}",
                    value=attr_value,
                    value_type="string",
                    key_path=f"{key_path}.@{attr_key}",
                    parent=node,
                )
                node.children.append(attr_node)
            
            # Process child elements
            for child in element:
                child_nodes = xml_to_nodes(child, key_path, node)
                node.children.extend(child_nodes)
            
            nodes.append(node)
            return nodes
        
        return xml_to_nodes(root)
    except ET.ParseError:
        return []


def parse_config_file(path: Path) -> Optional[ConfigFile]:
    """Parse a configuration file and return structured representation.
    
    Supports: JSON, YAML, XML
    
    Parameters
    ----------
    path : Path
        Path to configuration file
        
    Returns
    -------
    ConfigFile or None
        Parsed configuration file, or None if parsing failed
    """
    if not path.is_file():
        return None
    
    format = detect_config_format(path)
    if not format:
        return None
    
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    
    # Compute hash
    import hashlib
    hash_value = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    # Parse based on format
    nodes = []
    if format == "json":
        nodes = _parse_json(path, content)
    elif format == "yaml":
        nodes = _parse_yaml(path, content)
    elif format == "xml":
        nodes = _parse_xml(path, content)
    
    if not nodes:
        return None
    
    return ConfigFile(
        path=path,
        format=format,
        root_nodes=nodes,
        raw_content=content,
        hash=hash_value,
    )


@dataclass
class ConfigDiff:
    """Represents differences between two configuration files."""
    
    added: List[str]  # Key paths added in new config
    removed: List[str]  # Key paths removed from old config
    modified: List[Tuple[str, Any, Any]]  # (key_path, old_value, new_value)
    unchanged: List[str]  # Key paths that didn't change


def compare_configs(old_config: ConfigFile, new_config: ConfigFile) -> ConfigDiff:
    """Compare two configuration files and return differences.
    
    Parameters
    ----------
    old_config : ConfigFile
        Original configuration
    new_config : ConfigFile
        New configuration to compare
        
    Returns
    -------
    ConfigDiff
        Object containing all differences
    """
    def get_all_paths(nodes: List[ConfigNode]) -> Dict[str, Any]:
        """Extract all key paths and values from nodes."""
        paths = {}
        
        def traverse(node: ConfigNode):
            if node.value is not None:
                paths[node.key_path] = node.value
            for child in node.children:
                traverse(child)
        
        for node in nodes:
            traverse(node)
        
        return paths
    
    old_paths = get_all_paths(old_config.root_nodes)
    new_paths = get_all_paths(new_config.root_nodes)
    
    added = [path for path in new_paths if path not in old_paths]
    removed = [path for path in old_paths if path not in new_paths]
    
    modified = []
    unchanged = []
    
    for path in old_paths:
        if path in new_paths:
            if old_paths[path] != new_paths[path]:
                modified.append((path, old_paths[path], new_paths[path]))
            else:
                unchanged.append(path)
    
    return ConfigDiff(
        added=added,
        removed=removed,
        modified=modified,
        unchanged=unchanged,
    )




