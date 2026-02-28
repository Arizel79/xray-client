import os
from collections import defaultdict


def count_lines(content):
    return len(content.splitlines())


def read_files(root_dir, exclude_files=None, exclude_dirs=None, include_extensions=None):
    """
    Recursively read files, print their content, and count lines.

    :param root_dir: Root directory to start traversal.
    :param exclude_files: List of file names or relative paths to exclude.
    :param exclude_dirs: List of directory names to exclude.
    :param include_extensions: List of file extensions to include (e.g., ['.py', '.txt']).
                               If the list contains '*', all files are included.
    """
    lines_in_files = defaultdict(int)

    if exclude_files is None:
        exclude_files = []
    if exclude_dirs is None:
        exclude_dirs = ["venv", ".venv", ".venv1"]
    if include_extensions is None:
        include_extensions = [".py", ".html", ".txt", ".ftl"]

    # Determine if we should filter by extension
    filter_by_extension = "*" not in include_extensions

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude directories in-place
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            # Skip excluded files
            if rel_path in exclude_files or filename in exclude_files:
                continue

            # Skip files with unwanted extensions (if filtering is active)
            if filter_by_extension:
                if not any(filename.endswith(ext) for ext in include_extensions):
                    continue

            try:
                with open(full_path, "r", encoding="utf-8") as file:
                    content = file.read()
                    lines_in_files[full_path] = count_lines(content)
                    print(f"\n{'=' * 10} {rel_path} {'=' * 10}")
                    print(content)
            except Exception as e:
                print(f"\nError reading {rel_path}: {str(e)}")

    total_lines = sum(lines_in_files.values())
    sorted_lines_in_files = dict(
        sorted(lines_in_files.items(), key=lambda item: item[1])
    )
    print("\nLines in files")
    for file, n in sorted_lines_in_files.items():
        print(f"{file.rjust(70)}: {n}")
    print(f"Total lines: {total_lines}")


def main():
    directory = "."

    if not os.path.isdir(directory):
        print("Directory not found")
        return

    exclude_files = ["ra.py"]
    exclude_dirs = [".venv", ".venv1", ".git"]

    # --- Change this list to control which extensions are shown ---
    # Set file_extensions_to_show = ["*"] to include ALL files
    file_extensions_to_show = [".py"]

    read_files(
        directory,
        exclude_files=exclude_files,
        exclude_dirs=exclude_dirs,
        include_extensions=file_extensions_to_show,
    )


if __name__ == "__main__":
    main()
