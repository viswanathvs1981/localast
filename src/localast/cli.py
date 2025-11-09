"""Command line utilities for working with LocalAST data locally."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable

import asyncio

from .config import LocalConfig
from .docs import ingest_documents
from .git.history import GitRepo, extract_commits, extract_changes
from .indexer.pipeline import index_code_paths, index_config_files
from .storage.database import get_connection
from .storage.repo import (
    add_repository,
    get_repository_by_name,
    get_repository_stats,
    list_repositories,
    remove_repository,
    update_repository_index_time,
)
from .storage.schema import apply_schema


def _resolve_config(database: Path | None) -> LocalConfig:
    config = LocalConfig()
    if database is not None:
        config.database_path = database
    return config


def _ensure_connection(config: LocalConfig) -> sqlite3.Connection:
    connection = get_connection(config)
    apply_schema(connection)
    return connection


def _index_code(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        summary = index_code_paths(connection, args.paths, reindex=args.reindex, repo_id=None)
    finally:
        connection.close()
    print(
        f"Indexed {summary['files']} files and {summary['symbols']} symbols into"
        f" {config.resolved_database_path()}"
    )


def _index_docs(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        summary = ingest_documents(
            connection,
            args.paths,
            repo_root=args.repo_root.resolve(),
            repo_id=None,
            index_kind=args.index_kind,
        )
    finally:
        connection.close()
    print(
        f"Indexed {summary['documents']} documents into"
        f" {config.resolved_database_path()}"
    )


def _repo_info(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    try:
        cursor = connection.cursor()
        repos = cursor.execute("SELECT COUNT(*) FROM repo").fetchone()[0]
        files = cursor.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        symbols = cursor.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        documents = cursor.execute("SELECT COUNT(*) FROM blob WHERE kind = 'doc'").fetchone()[0]
        edges = cursor.execute("SELECT COUNT(*) FROM edges WHERE etype = 'DOCS'").fetchone()[0]
        commits = cursor.execute("SELECT COUNT(DISTINCT commit_id) FROM version").fetchone()[0]
    finally:
        connection.close()

    print("Repository summary:")
    print(f"  Repositories       : {repos}")
    print(f"  Files indexed      : {files}")
    print(f"  Symbols extracted  : {symbols}")
    print(f"  Documents ingested : {documents}")
    print(f"  Doc ↔ Code links   : {edges}")
    print(f"  Commits tracked    : {commits}")


def _repo_add(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    
    repo_path = args.path.resolve()
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        return
    
    try:
        # Verify it's a git repository
        git_repo = GitRepo(repo_path)
        default_branch = git_repo.default_branch
    except Exception as e:
        print(f"Error: Not a valid git repository: {e}")
        connection.close()
        return
    
    try:
        repo_id = add_repository(
            connection,
            args.name,
            repo_path,
            default_branch=default_branch,
        )
        print(f"Added repository '{args.name}' (ID: {repo_id})")
        print(f"  Path: {repo_path}")
        print(f"  Default branch: {default_branch}")
    except ValueError as e:
        print(f"Error: {e}")
    finally:
        connection.close()


def _repo_list(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    
    try:
        repos = list_repositories(connection)
        if not repos:
            print("No repositories registered.")
            return
        
        print(f"Registered repositories ({len(repos)}):")
        for repo in repos:
            print(f"\n  {repo['name']} (ID: {repo['id']})")
            print(f"    Path: {repo['path']}")
            print(f"    Branch: {repo['default_branch']}")
            print(f"    Indexed: {repo['indexed_at']}")
            if repo['last_commit']:
                print(f"    Last commit: {repo['last_commit'][:8]}")
            
            # Get stats
            stats = get_repository_stats(connection, repo['id'])
            print(f"    Files: {stats['files']}, Symbols: {stats['symbols']}, " 
                  f"Commits: {stats['commits']}")
    finally:
        connection.close()


def _repo_remove(args: argparse.Namespace) -> None:
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    
    try:
        removed = remove_repository(connection, args.name)
        if removed:
            print(f"Removed repository '{args.name}' and all associated data")
        else:
            print(f"Error: Repository '{args.name}' not found")
    finally:
        connection.close()


def _index_repo(args: argparse.Namespace) -> None:
    """Index a full repository: code, docs, and git history."""
    config = _resolve_config(args.database)
    connection = _ensure_connection(config)
    
    try:
        # Get repository info
        repo_info = get_repository_by_name(connection, args.name)
        if not repo_info:
            print(f"Error: Repository '{args.name}' not found. Add it first with 'localast repo add'")
            return
        
        repo_path = Path(repo_info['path'])
        repo_id = repo_info['id']
        
        print(f"Indexing repository: {args.name}")
        print(f"  Path: {repo_path}")
        
        # Index code
        print("\n[1/5] Indexing source code...")
        code_summary = index_code_paths(
            connection,
            [repo_path],
            repo_id=repo_id,
            reindex=args.reindex,
            embed=args.embed,
        )
        print(f"  Indexed {code_summary['files']} files, {code_summary['symbols']} symbols")
        
        # Index configuration files
        print("\n[2/5] Indexing configuration files...")
        config_summary = index_config_files(
            connection,
            [repo_path],
            repo_id=repo_id,
        )
        print(f"  Indexed {config_summary['config_files']} config files, {config_summary['config_nodes']} config nodes")
        
        # Index documentation
        print("\n[3/5] Indexing documentation...")
        doc_count = 0
        for doc_pattern in config.docs_paths:
            doc_path = repo_path / doc_pattern
            if doc_path.exists():
                doc_summary = ingest_documents(
                    connection,
                    [doc_path],
                    repo_root=repo_path,
                    repo_id=repo_id,
                    index_kind="documentation",
                )
                doc_count += doc_summary['documents']
        print(f"  Indexed {doc_count} documents")
        
        # Extract git history
        print("\n[4/5] Extracting git history...")
        try:
            since_commit = repo_info.get('last_commit')
            commit_count = extract_commits(
                connection, repo_id, repo_path, since_commit=since_commit
            )
            print(f"  Extracted {commit_count} commits")
        except Exception as e:
            print(f"  Warning: Could not extract git history: {e}")
        
        # Extract changes
        print("\n[5/5] Extracting file changes...")
        try:
            change_count = extract_changes(connection, repo_id, repo_path)
            print(f"  Extracted {change_count} change events")
        except Exception as e:
            print(f"  Warning: Could not extract changes: {e}")
        
        # Update repository index time
        git_repo = GitRepo(repo_path)
        latest_commit = git_repo.repo.head.commit.hexsha if git_repo.repo.head.is_valid() else None
        update_repository_index_time(connection, repo_id, latest_commit)
        
        print(f"\n✓ Repository '{args.name}' indexed successfully")
        
    finally:
        connection.close()


def _reindex_repo(args: argparse.Namespace) -> None:
    """Reindex a repository (incremental update)."""
    # For now, just call _index_repo with reindex flag
    args.reindex = True
    _index_repo(args)


def _serve_mcp(args: argparse.Namespace) -> None:
    """Start the MCP server."""
    config = _resolve_config(args.database)
    
    try:
        from .mcp.server import create_server
    except ImportError as e:
        print(f"Error: MCP server dependencies not available: {e}")
        print("Install with: pip install mcp")
        return
    
    print("Starting LocalAST MCP server...")
    print(f"Database: {config.resolved_database_path()}")
    print("Server running on stdio. Use Ctrl+C to stop.")
    
    try:
        server = create_server(config)
        asyncio.run(server.run())
    except KeyboardInterrupt:
        print("\nShutting down server...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        help="Path to the SQLite database (defaults to ~/.localast/localast.db)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index code or documentation")
    index_sub = index_parser.add_subparsers(dest="index_command", required=True)

    code_parser = index_sub.add_parser("code", help="Index Python source files")
    code_parser.add_argument("paths", nargs="+", type=Path, help="Files or directories")
    code_parser.add_argument(
        "--reindex",
        action="store_true",
        help="Drop existing symbols for the provided files before indexing",
    )
    code_parser.set_defaults(func=_index_code)

    docs_parser = index_sub.add_parser("docs", help="Index documentation folders")
    docs_parser.add_argument("paths", nargs="+", type=Path, help="Documentation paths")
    docs_parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root used when resolving code references",
    )
    docs_parser.add_argument(
        "--index-kind",
        default="documentation",
        help="Identifier stored alongside generated embeddings",
    )
    docs_parser.set_defaults(func=_index_docs)

    repo_parser = subparsers.add_parser("repo", help="Manage repositories")
    repo_sub = repo_parser.add_subparsers(dest="repo_command", required=True)

    # repo add
    add_parser = repo_sub.add_parser("add", help="Register a repository for indexing")
    add_parser.add_argument("path", type=Path, help="Path to git repository")
    add_parser.add_argument("--name", required=True, help="Unique name for the repository")
    add_parser.set_defaults(func=_repo_add)

    # repo list
    list_parser = repo_sub.add_parser("list", help="List all registered repositories")
    list_parser.set_defaults(func=_repo_list)

    # repo remove
    remove_parser = repo_sub.add_parser("remove", help="Remove a repository")
    remove_parser.add_argument("name", help="Repository name to remove")
    remove_parser.set_defaults(func=_repo_remove)

    # repo info
    info_parser = repo_sub.add_parser("info", help="Display aggregate statistics")
    info_parser.set_defaults(func=_repo_info)

    # index repo (new command for full repo indexing)
    index_repo_parser = index_sub.add_parser("repo", help="Index a full repository (code + docs + git)")
    index_repo_parser.add_argument("name", help="Repository name to index")
    index_repo_parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force reindexing of all files",
    )
    index_repo_parser.add_argument(
        "--embed",
        action="store_true",
        help="Generate embeddings for semantic search",
    )
    index_repo_parser.set_defaults(func=_index_repo, reindex=False, embed=False)

    # reindex command
    reindex_parser = subparsers.add_parser("reindex", help="Reindex a repository (incremental)")
    reindex_parser.add_argument("name", help="Repository name to reindex")
    reindex_parser.set_defaults(func=_reindex_repo, reindex=False)

    # serve command (MCP server)
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.set_defaults(func=_serve_mcp)

    return parser


def main(argv: Iterable[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()

