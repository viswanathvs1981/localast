"""Repository management for multi-repo support."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


def add_repository(
    connection: sqlite3.Connection,
    name: str,
    path: Path,
    default_branch: Optional[str] = None,
) -> int:
    """Register a repository in the database.

    Parameters
    ----------
    connection:
        Database connection
    name:
        Unique name for the repository
    path:
        Absolute path to repository
    default_branch:
        Default branch name (e.g., 'main', 'master')

    Returns
    -------
    Repository ID

    Raises
    ------
    ValueError:
        If repository with same name already exists
    """
    cursor = connection.cursor()
    
    # Check if repo already exists
    existing = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (name,)
    ).fetchone()
    
    if existing:
        raise ValueError(f"Repository '{name}' already registered")
    
    # Insert new repository
    cursor.execute(
        """INSERT INTO repo (name, path, default_branch, indexed_at)
           VALUES (?, ?, ?, ?)""",
        (name, str(path.resolve()), default_branch, datetime.now().isoformat()),
    )
    
    repo_id = cursor.lastrowid
    connection.commit()
    return repo_id


def get_repository_by_name(
    connection: sqlite3.Connection, name: str
) -> Optional[Dict]:
    """Get repository information by name.

    Parameters
    ----------
    connection:
        Database connection
    name:
        Repository name

    Returns
    -------
    Dictionary with repo info or None if not found
    """
    cursor = connection.cursor()
    row = cursor.execute(
        """SELECT id, name, path, default_branch, indexed_at, last_commit
           FROM repo WHERE name = ?""",
        (name,),
    ).fetchone()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "name": row[1],
        "path": row[2],
        "default_branch": row[3],
        "indexed_at": row[4],
        "last_commit": row[5],
    }


def get_repository_by_id(
    connection: sqlite3.Connection, repo_id: int
) -> Optional[Dict]:
    """Get repository information by ID.

    Parameters
    ----------
    connection:
        Database connection
    repo_id:
        Repository ID

    Returns
    -------
    Dictionary with repo info or None if not found
    """
    cursor = connection.cursor()
    row = cursor.execute(
        """SELECT id, name, path, default_branch, indexed_at, last_commit
           FROM repo WHERE id = ?""",
        (repo_id,),
    ).fetchone()
    
    if not row:
        return None
    
    return {
        "id": row[0],
        "name": row[1],
        "path": row[2],
        "default_branch": row[3],
        "indexed_at": row[4],
        "last_commit": row[5],
    }


def list_repositories(connection: sqlite3.Connection) -> List[Dict]:
    """List all registered repositories.

    Parameters
    ----------
    connection:
        Database connection

    Returns
    -------
    List of repository dictionaries
    """
    cursor = connection.cursor()
    rows = cursor.execute(
        """SELECT id, name, path, default_branch, indexed_at, last_commit
           FROM repo ORDER BY name"""
    ).fetchall()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "path": row[2],
            "default_branch": row[3],
            "indexed_at": row[4],
            "last_commit": row[5],
        }
        for row in rows
    ]


def remove_repository(connection: sqlite3.Connection, name: str) -> bool:
    """Remove a repository and all its associated data.

    Parameters
    ----------
    connection:
        Database connection
    name:
        Repository name

    Returns
    -------
    True if removed, False if not found
    """
    cursor = connection.cursor()
    
    # Check if exists
    existing = cursor.execute(
        "SELECT id FROM repo WHERE name = ?", (name,)
    ).fetchone()
    
    if not existing:
        return False
    
    # Delete (cascade will handle related tables)
    cursor.execute("DELETE FROM repo WHERE name = ?", (name,))
    connection.commit()
    return True


def update_repository_index_time(
    connection: sqlite3.Connection, repo_id: int, commit_id: Optional[str] = None
) -> None:
    """Update the last indexed timestamp for a repository.

    Parameters
    ----------
    connection:
        Database connection
    repo_id:
        Repository ID
    commit_id:
        Latest commit SHA that was indexed
    """
    cursor = connection.cursor()
    cursor.execute(
        """UPDATE repo SET indexed_at = ?, last_commit = ?
           WHERE id = ?""",
        (datetime.now().isoformat(), commit_id, repo_id),
    )
    connection.commit()


def get_repository_stats(connection: sqlite3.Connection, repo_id: int) -> Dict:
    """Get statistics about a repository.

    Parameters
    ----------
    connection:
        Database connection
    repo_id:
        Repository ID

    Returns
    -------
    Dictionary with statistics
    """
    cursor = connection.cursor()
    
    files = cursor.execute(
        "SELECT COUNT(*) FROM files WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    symbols = cursor.execute(
        """SELECT COUNT(*) FROM symbols 
           WHERE file_id IN (SELECT id FROM files WHERE repo_id = ?)""",
        (repo_id,),
    ).fetchone()[0]
    
    commits = cursor.execute(
        "SELECT COUNT(DISTINCT commit_id) FROM version WHERE repo_id = ?",
        (repo_id,),
    ).fetchone()[0]
    
    changes = cursor.execute(
        "SELECT COUNT(*) FROM change_event WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    embeddings = cursor.execute(
        "SELECT COUNT(*) FROM emb WHERE repo_id = ?", (repo_id,)
    ).fetchone()[0]
    
    return {
        "files": files,
        "symbols": symbols,
        "commits": commits,
        "changes": changes,
        "embeddings": embeddings,
    }




