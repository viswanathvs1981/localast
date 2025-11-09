"""Git history extraction and commit tracking."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    from git import Repo, Commit, Diff
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    Repo = None
    Commit = None
    Diff = None


@dataclass(slots=True)
class CommitInfo:
    """Metadata about a single commit."""

    commit_id: str
    parent_commit_id: Optional[str]
    author: str
    timestamp: datetime
    message: str
    files_changed: List[str]


class GitRepo:
    """Wrapper around gitpython for extracting repository history."""

    def __init__(self, repo_path: Path):
        if not GIT_AVAILABLE:
            raise RuntimeError(
                "GitPython is not installed. Install with: pip install gitpython"
            )
        
        self.repo_path = repo_path.resolve()
        try:
            self.repo = Repo(self.repo_path)
        except Exception as e:
            raise ValueError(f"Not a valid git repository: {repo_path}") from e

    @property
    def default_branch(self) -> str:
        """Get the default branch name (usually 'main' or 'master')."""
        try:
            return self.repo.active_branch.name
        except Exception:
            return "main"

    def get_commits(
        self, max_count: Optional[int] = None, since: Optional[str] = None
    ) -> List[CommitInfo]:
        """Extract commit history from the repository.

        Parameters
        ----------
        max_count:
            Maximum number of commits to retrieve (None for all)
        since:
            Only return commits after this commit SHA

        Returns
        -------
        List of CommitInfo objects
        """
        commits: List[CommitInfo] = []
        
        kwargs = {}
        if max_count:
            kwargs["max_count"] = max_count
        
        for commit in self.repo.iter_commits(**kwargs):
            if since and commit.hexsha == since:
                break
            
            parent_id = commit.parents[0].hexsha if commit.parents else None
            files_changed = list(commit.stats.files.keys())
            
            commit_info = CommitInfo(
                commit_id=commit.hexsha,
                parent_commit_id=parent_id,
                author=str(commit.author),
                timestamp=datetime.fromtimestamp(commit.committed_date),
                message=commit.message.strip(),
                files_changed=files_changed,
            )
            commits.append(commit_info)
        
        return commits

    def get_file_at_commit(self, commit_id: str, file_path: str) -> Optional[str]:
        """Retrieve file contents at a specific commit.

        Parameters
        ----------
        commit_id:
            Commit SHA
        file_path:
            Relative path to file in repository

        Returns
        -------
        File contents as string, or None if file doesn't exist at that commit
        """
        try:
            commit = self.repo.commit(commit_id)
            blob = commit.tree / file_path
            return blob.data_stream.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

    def get_diff(self, from_commit: str, to_commit: str) -> List[tuple[str, str, str]]:
        """Get diff between two commits.

        Parameters
        ----------
        from_commit:
            Starting commit SHA
        to_commit:
            Ending commit SHA

        Returns
        -------
        List of (file_path, change_type, diff_text) tuples
        """
        diffs: List[tuple[str, str, str]] = []
        
        try:
            commit_from = self.repo.commit(from_commit)
            commit_to = self.repo.commit(to_commit)
            
            for diff in commit_from.diff(commit_to):
                change_type = self._get_change_type(diff)
                file_path = diff.b_path or diff.a_path
                diff_text = self._get_diff_text(diff)
                
                diffs.append((file_path, change_type, diff_text))
        except Exception:
            pass
        
        return diffs

    def _get_change_type(self, diff: Diff) -> str:
        """Determine the type of change (added, modified, deleted)."""
        if diff.new_file:
            return "added"
        elif diff.deleted_file:
            return "deleted"
        elif diff.renamed_file:
            return "renamed"
        else:
            return "modified"

    def _get_diff_text(self, diff: Diff) -> str:
        """Extract diff text from a Diff object."""
        try:
            return diff.diff.decode("utf-8", errors="ignore")
        except Exception:
            return ""


def extract_commits(
    connection: sqlite3.Connection,
    repo_id: int,
    repo_path: Path,
    max_count: Optional[int] = None,
    since_commit: Optional[str] = None,
) -> int:
    """Extract and store commit history in the database.

    Parameters
    ----------
    connection:
        Database connection
    repo_id:
        Repository ID from repo table
    repo_path:
        Path to git repository
    max_count:
        Maximum commits to extract
    since_commit:
        Only extract commits after this SHA

    Returns
    -------
    Number of commits extracted
    """
    git_repo = GitRepo(repo_path)
    commits = git_repo.get_commits(max_count=max_count, since=since_commit)
    
    cursor = connection.cursor()
    count = 0
    
    for commit_info in commits:
        # Check if commit already exists
        existing = cursor.execute(
            "SELECT id FROM version WHERE repo_id = ? AND commit_id = ?",
            (repo_id, commit_info.commit_id),
        ).fetchone()
        
        if existing:
            continue
        
        # Insert commit metadata
        cursor.execute(
            """INSERT INTO version 
               (repo_id, commit_id, path, ts, author, message)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                repo_id,
                commit_info.commit_id,
                None,  # path is set per-file in change_event
                commit_info.timestamp.isoformat(),
                commit_info.author,
                commit_info.message,
            ),
        )
        count += 1
    
    connection.commit()
    return count


def extract_changes(
    connection: sqlite3.Connection,
    repo_id: int,
    repo_path: Path,
    from_commit: Optional[str] = None,
    to_commit: str = "HEAD",
) -> int:
    """Extract file changes between commits and store in change_event table.

    Parameters
    ----------
    connection:
        Database connection
    repo_id:
        Repository ID from repo table
    repo_path:
        Path to git repository
    from_commit:
        Starting commit (None for all history)
    to_commit:
        Ending commit (default: HEAD)

    Returns
    -------
    Number of change events extracted
    """
    git_repo = GitRepo(repo_path)
    cursor = connection.cursor()
    count = 0
    
    # Get commits in reverse chronological order
    commits = git_repo.get_commits()
    
    for commit_info in commits:
        if from_commit and commit_info.commit_id == from_commit:
            break
        
        if not commit_info.parent_commit_id:
            # Initial commit - record all files as added
            for file_path in commit_info.files_changed:
                cursor.execute(
                    """INSERT INTO change_event 
                       (repo_id, commit_id, parent_commit_id, path, kind, 
                        hunk, summary, ts)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        repo_id,
                        commit_info.commit_id,
                        None,
                        file_path,
                        "added",
                        "",
                        commit_info.message,
                        commit_info.timestamp.isoformat(),
                    ),
                )
                count += 1
            continue
        
        # Get diffs for this commit
        diffs = git_repo.get_diff(
            commit_info.parent_commit_id, commit_info.commit_id
        )
        
        for file_path, change_type, diff_text in diffs:
            # Check if this change event already exists
            existing = cursor.execute(
                """SELECT id FROM change_event 
                   WHERE repo_id = ? AND commit_id = ? AND path = ?""",
                (repo_id, commit_info.commit_id, file_path),
            ).fetchone()
            
            if existing:
                continue
            
            cursor.execute(
                """INSERT INTO change_event 
                   (repo_id, commit_id, parent_commit_id, path, kind, 
                    hunk, summary, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    repo_id,
                    commit_info.commit_id,
                    commit_info.parent_commit_id,
                    file_path,
                    change_type,
                    diff_text[:10000],  # Limit diff size
                    commit_info.message,
                    commit_info.timestamp.isoformat(),
                ),
            )
            count += 1
    
    connection.commit()
    return count




