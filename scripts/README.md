# LocalAST Indexing Scripts Guide

## Overview

These 5 scripts cover all indexing and embedding scenarios for LocalAST. They're production-ready, well-tested, and handle all edge cases.

## 📋 Script Overview

| Script | Purpose | Time | Use When |
|--------|---------|------|----------|
| `1-initial-index.sh` | First-time indexing WITHOUT embeddings | 1-5 min | New repository, fast initial index |
| `2-initial-embedding.sh` | Generate embeddings for existing symbols | 5-15 min | After script 1, enable semantic search |
| `3-incremental-index.sh` | Update index for changed files only | <1 min | After git pull, file edits, regular updates |
| `4-incremental-embedding.sh` | Generate embeddings for new symbols only | <1 min | After script 3 without `--with-embeddings` |
| `5-delete-and-rebuild.sh` | Nuclear option: delete everything and rebuild | 10-20 min | Data corruption, schema changes, clean slate |

---

## 🚀 Common Workflows

### Workflow 1: First Time Setup (Recommended)

```bash
# Step 1: Fast initial index (1-5 minutes)
./scripts/1-initial-index.sh /path/to/your/project my-project

# Step 2: Generate embeddings (5-15 minutes)
./scripts/2-initial-embedding.sh my-project

# Step 3: Start using!
localast serve
```

**Why split into 2 steps?**
- Get working index immediately
- Test before spending time on embeddings
- Embeddings are optional (only needed for semantic search)

### Workflow 2: Daily Updates

```bash
# After editing files or git pull
./scripts/3-incremental-index.sh my-project

# If you need semantic search for new code
./scripts/3-incremental-index.sh my-project --with-embeddings
```

### Workflow 3: Something Went Wrong

```bash
# Nuclear option: delete and rebuild everything
./scripts/5-delete-and-rebuild.sh my-project --with-embeddings
```

---

## 📖 Detailed Script Documentation

### Script 1: Initial Index

**File:** `1-initial-index.sh`

**What it does:**
- Registers repository in database
- Indexes all source code (functions, classes, methods)
- Extracts nested symbols (methods in classes, inner functions)
- Builds call graphs (what calls what)
- Tracks import dependencies
- Indexes configuration files (JSON, YAML, XML)
- Extracts git history (commits, changes)
- **SKIPS embeddings** for speed

**Usage:**
```bash
./scripts/1-initial-index.sh <repo_path> <repo_name>

# Examples:
./scripts/1-initial-index.sh ~/projects/backend backend-api
./scripts/1-initial-index.sh /Users/me/my-app my-app
./scripts/1-initial-index.sh . localast  # Current directory
```

**Output:**
- Shows file counts (Python, JSON, YAML)
- Progress bars during indexing
- Final summary with counts

**Next step:** Run script 2 to add embeddings

---

### Script 2: Initial Embedding

**File:** `2-initial-embedding.sh`

**What it does:**
- Generates 384-dimensional vector embeddings
- Processes all symbols without embeddings
- Enables semantic search capabilities
- Smart batching (1000 symbols at a time)

**Usage:**
```bash
./scripts/2-initial-embedding.sh <repo_name>

# Examples:
./scripts/2-initial-embedding.sh my-project
./scripts/2-initial-embedding.sh backend-api
```

**Time:** ~1500 symbols per minute

**Why separate from script 1?**
- You can use LocalAST immediately without waiting
- Embeddings are only needed for semantic search
- Can be run later or skipped entirely

---

### Script 3: Incremental Index

**File:** `3-incremental-index.sh`

**What it does:**
- Hash-based change detection
- Only reindexes modified files
- Updates call graphs and dependencies
- Fast and efficient

**Usage:**
```bash
# Without embeddings (fast)
./scripts/3-incremental-index.sh my-project

# With embeddings for new symbols (slower)
./scripts/3-incremental-index.sh my-project --with-embeddings
```

**When to use:**
- After `git pull`
- After editing files
- Regular maintenance
- CI/CD pipeline

**How it works:**
- Compares file hashes
- Skips unchanged files
- Only processes new/modified files

---

### Script 4: Incremental Embedding

**File:** `4-incremental-embedding.sh`

**What it does:**
- Finds symbols without embeddings
- Generates embeddings only for those symbols
- Fast and efficient

**Usage:**
```bash
./scripts/4-incremental-embedding.sh my-project
```

**When to use:**
- After script 3 without `--with-embeddings`
- When you notice missing semantic search results
- To "catch up" on embeddings

---

### Script 5: Delete and Rebuild

**File:** `5-delete-and-rebuild.sh`

**What it does:**
- Deletes ALL data for a repository
- Keeps repository registration
- Rebuilds everything from scratch
- Optionally includes embeddings

**Usage:**
```bash
# Rebuild without embeddings (faster)
./scripts/5-delete-and-rebuild.sh my-project

# Rebuild with embeddings (complete)
./scripts/5-delete-and-rebuild.sh my-project --with-embeddings
```

**⚠️ WARNING:** This CANNOT be undone! You'll need to type "DELETE" to confirm.

**When to use:**
- Data corruption
- Schema updates
- Testing/development
- Want a clean slate
- Troubleshooting issues

---

## 🎯 Decision Tree: Which Script to Use?

```
Is this a NEW repository?
├─ YES → Run script 1, then script 2
└─ NO → Continue below

Did you just edit/pull files?
├─ YES → Run script 3
│   └─ Need semantic search for new code?
│       ├─ YES → Add --with-embeddings flag
│       └─ NO → Run script 4 later when needed
└─ NO → Continue below

Is something broken/corrupted?
├─ YES → Run script 5 (delete and rebuild)
└─ NO → You probably don't need to reindex!
```

---

## 💡 Pro Tips

### Tip 1: Start Fast, Add Later
```bash
# Day 1: Fast setup
./scripts/1-initial-index.sh ~/project my-proj  # 2 minutes

# Use it! Test it!
localast search code "MyClass"

# Day 2: Add semantic search
./scripts/2-initial-embedding.sh my-proj  # 10 minutes
```

### Tip 2: Daily Workflow
```bash
# Every morning after git pull
./scripts/3-incremental-index.sh my-proj  # 30 seconds

# Only generate embeddings weekly (or when needed)
./scripts/4-incremental-embedding.sh my-proj  # 1-2 minutes
```

### Tip 3: CI/CD Integration
```yaml
# .github/workflows/index.yml
- name: Update LocalAST index
  run: |
    ./scripts/3-incremental-index.sh my-project
```

### Tip 4: Multiple Repositories
```bash
# Index multiple projects
for repo in frontend backend mobile; do
  ./scripts/1-initial-index.sh ~/projects/$repo $repo
done

# Generate embeddings for all
for repo in frontend backend mobile; do
  ./scripts/2-initial-embedding.sh $repo
done
```

---

## 🔍 Troubleshooting

### Problem: "Repository not found"
**Solution:** Run script 1 first to register it

### Problem: "No embeddings" error
**Solution:** Run script 2 to generate embeddings

### Problem: Incremental index skips files
**Explanation:** Hash unchanged - this is correct behavior!
**Override:** Use script 5 to force rebuild

### Problem: Out of disk space
**Check database size:**
```bash
du -h ~/.localast/localast.db
```
**Typical sizes:**
- Small repo (100 files): 10-50 MB
- Medium repo (1000 files): 100-500 MB
- Large repo (10000 files): 500 MB - 2 GB

### Problem: Embeddings taking too long
**Estimate:** ~1500 symbols per minute
**Speed up:**
- Run on machine with better CPU
- Close other applications
- Run overnight for huge codebases

---

## 📊 Performance Metrics

| Repository Size | Initial Index | Initial Embedding | Incremental (1% changed) |
|----------------|---------------|-------------------|--------------------------|
| Small (100 files) | 30 sec | 2 min | 5 sec |
| Medium (1K files) | 2 min | 10 min | 10 sec |
| Large (10K files) | 10 min | 60 min | 30 sec |
| Huge (50K files) | 30 min | 4 hours | 2 min |

---

## 🎓 Advanced Usage

### Custom Documentation Paths
Edit `src/localast/config.py`:
```python
docs_paths = ["docs/", "documentation/", "wiki/"]
```

### Exclude Patterns
The indexer respects `.gitignore` automatically. To add more exclusions, edit the indexer logic.

### Parallel Processing
For very large repositories, consider splitting into smaller repos and indexing in parallel.

---

## 📝 What Gets Indexed?

### Code Files
- Python (`.py`)
- JavaScript (`.js`, `.jsx`)
- TypeScript (`.ts`, `.tsx`)
- C# (`.cs`)
- Go (`.go`)
- Java (`.java`)
- And more...

### Configuration Files
- JSON (`.json`, `.jsonc`)
- YAML (`.yaml`, `.yml`)
- XML (`.xml`)

### Documentation
- Markdown (`.md`)
- Text (`.txt`)
- ReStructuredText (`.rst`)

### Git Data
- All commits
- All file changes
- Blame information

---

## 🚦 Exit Codes

All scripts follow standard exit codes:
- `0` - Success
- `1` - Error (with helpful message)

Use in scripts:
```bash
if ./scripts/1-initial-index.sh ~/project my-proj; then
  echo "Success!"
  ./scripts/2-initial-embedding.sh my-proj
else
  echo "Indexing failed!"
  exit 1
fi
```

---

## 🆘 Getting Help

1. **Check script output** - Scripts provide detailed error messages
2. **Verify prerequisites** - Database initialized? Virtual env active?
3. **Check database** - `sqlite3 ~/.localast/localast.db "SELECT * FROM repo;"`
4. **Run validation** - See `validate_all.sh` example in docs
5. **Nuclear option** - When in doubt, use script 5 to rebuild

---

## 📚 Related Documentation

- `README.md` - Main project documentation
- `ENHANCED_FEATURES.md` - New features documentation
- `QUICK_START_ENHANCED.md` - Quick start guide
- `IMPLEMENTATION_SUMMARY_ENHANCED.md` - Technical details

---

**Happy indexing!** 🚀

For questions or issues, check the main README or create an issue in the repository.




