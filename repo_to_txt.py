import os
import argparse

# --- Configuration ---

# Directories to completely ignore for FILE CONTENTS reading
CONTENT_IGNORE_DIRS = {
    '.git', '__pycache__', '.vscode', '.idea', 'node_modules',
    'dist', 'build', 'venv', '.env', 'target', 'checkpoints',
    'data', '.venv', '.pytest_cache'
}

# Directories to PRUNE (do not descend into) while building STRUCTURE.
# They will still appear in the structure tree, but we won’t traverse inside them.
STRUCTURE_PRUNE_DIRS = {
    '.git', '__pycache__', 'node_modules', 'venv', 'dist', 'build', 'target', 'checkpoints', '.venv', '.pytest_cache'
}

# Specific files to ignore by name (for FILE CONTENTS only)
IGNORE_FILES = {
    '.gitignore', 'package-lock.json'
}

# File extensions to ignore (for FILE CONTENTS only)
IGNORE_EXTENSIONS = {
    # Compiled/binary
    '.pyc', '.pyo', '.pyd', '.o', '.so', '.dll', '.exe', '.DS_Store', '.pt',
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.ico',
    # Audio/Video
    '.mp3', '.wav', '.flac', '.mp4', '.mov', '.avi', '.mkv',
    # Archives
    '.zip', '.tar', '.gz', '.rar', '.7z',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # Databases & other
    '.sqlite3', '.db', '.lock', '.log'
}
# ---------------------


def should_include_file_content(filename: str) -> bool:
    """Return True if file content should be included (based on IGNORE_FILES/IGNORE_EXTENSIONS)."""
    if filename in IGNORE_FILES:
        return False
    ext = os.path.splitext(filename)[1]
    if ext in IGNORE_EXTENSIONS:
        return False
    return True


def insert_into_tree(tree: dict, parts: list[str], is_dir: bool):
    """Insert a path (split into parts) into a nested dict tree structure."""
    node = tree
    for i, part in enumerate(parts):
        is_last = i == len(parts) - 1
        if part not in node:
            node[part] = {"__children__": {}, "__is_dir__": True}
        if is_last:
            node[part]["__is_dir__"] = is_dir
        node = node[part]["__children__"]


def build_repo_tree(repo_path: str) -> dict:
    """
    Build a nested tree (dict) representing FULL repo structure:
    - Includes ALL folders and ALL filenames
    - Optionally prunes traversal into huge dirs (STRUCTURE_PRUNE_DIRS)
      but still shows those folders in the tree.
    """
    tree = {}

    for root, dirs, files in os.walk(repo_path, topdown=True):
        rel_dir = os.path.relpath(root, repo_path)

        # Insert current directory (except root)
        if rel_dir != ".":
            insert_into_tree(tree, rel_dir.split(os.sep), is_dir=True)

        # Insert ALL subdirectories (even if we prune traversal)
        for d in sorted(dirs):
            rel_subdir = os.path.relpath(os.path.join(root, d), repo_path)
            insert_into_tree(tree, rel_subdir.split(os.sep), is_dir=True)

        # Insert ALL files (no filtering for structure)
        for f in sorted(files):
            rel_file = os.path.relpath(os.path.join(root, f), repo_path)
            insert_into_tree(tree, rel_file.split(os.sep), is_dir=False)

        # Prune traversal into heavy directories (but they already got inserted above)
        dirs[:] = [d for d in dirs if d not in STRUCTURE_PRUNE_DIRS]

    return tree


def render_tree(tree: dict, prefix: str = "") -> list[str]:
    """Render the nested dict tree to pretty 'tree' lines."""
    entries = []
    for name, meta in tree.items():
        entries.append((name, meta.get("__is_dir__", True), meta.get("__children__", {})))

    # dirs first, then files
    entries.sort(key=lambda x: (not x[1], x[0].lower()))

    lines = []
    for idx, (name, is_dir, children) in enumerate(entries):
        is_last = idx == len(entries) - 1
        branch = "└── " if is_last else "├── "
        lines.append(f"{prefix}{branch}{name}{'/' if is_dir else ''}")

        if is_dir and children:
            extension = "    " if is_last else "│   "
            lines.extend(render_tree(children, prefix + extension))

    return lines


def create_repo_text_file(repo_path: str, output_file: str):
    """
    Writes:
      1) FULL repo structure (all folders + all filenames)
      2) Filtered file contents (based on CONTENT_IGNORE_DIRS + IGNORE_FILES + IGNORE_EXTENSIONS)
    """
    try:
        abs_repo = os.path.abspath(repo_path)
        repo_name = os.path.basename(os.path.normpath(abs_repo))

        # 1) Build full structure
        tree = build_repo_tree(repo_path)
        tree_lines = [f"{repo_name}/"] + render_tree(tree)

        with open(output_file, 'w', encoding='utf-8') as outfile:
            outfile.write(f"Repository content for: {abs_repo}\n")
            outfile.write("=" * 80 + "\n\n")

            # Structure first (FULL)
            outfile.write("REPOSITORY STRUCTURE (full)\n")
            outfile.write("-" * 80 + "\n")
            outfile.write("\n".join(tree_lines))
            outfile.write("\n\n")
            outfile.write("=" * 80 + "\n\n")

            # Contents second (FILTERED)
            outfile.write("FILE CONTENTS (filtered)\n")
            outfile.write("=" * 80 + "\n\n")

            for root, dirs, files in os.walk(repo_path, topdown=True):
                # For contents, keep your ignore rules
                dirs[:] = [d for d in sorted(dirs) if d not in CONTENT_IGNORE_DIRS]

                for filename in sorted(files):
                    if not should_include_file_content(filename):
                        continue

                    file_path = os.path.join(root, filename)
                    relative_path = os.path.relpath(file_path, repo_path)

                    try:
                        with open(file_path, 'r', encoding='utf-8') as infile:
                            content = infile.read()

                        outfile.write('-' * 80 + "\n")
                        outfile.write(f"FILE: {relative_path}\n")
                        outfile.write('-' * 80 + "\n\n")
                        outfile.write(content)
                        outfile.write("\n\n\n")

                    except UnicodeDecodeError:
                        print(f"⚠️  Skipping non-UTF-8 (likely binary) file: {relative_path}")
                    except Exception as e:
                        print(f"❌ Error reading file {relative_path}: {e}")

        print(f"✅ Success! Repository structure + contents written to '{output_file}'")

    except IOError as e:
        print(f"❌ Error writing to output file {output_file}: {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert a local repository into a single .txt file with a clear structure.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("repo_path", type=str, help="Path to the local repository you want to convert.")
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="repo_snapshot.txt",
        help="Name of the output .txt file. (default: repo_snapshot.txt)"
    )

    args = parser.parse_args()

    if not os.path.isdir(args.repo_path):
        print(f"❌ Error: The path '{args.repo_path}' is not a valid directory.")
        return

    create_repo_text_file(args.repo_path, args.output)


if __name__ == "__main__":
    main()
