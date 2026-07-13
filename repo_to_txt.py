import os
import argparse

def generate_snapshot(root_dir, output_file):
    exclude_dirs = {'venv', '.pytest_cache', 'build', '__pycache__', '.git', '.vscode'}
    exclude_files = {output_file, 'repo_to_txt.py'}
    
    with open(output_file, 'w', encoding='utf-8') as out:
        out.write(f"Repository content for: {os.path.abspath(root_dir)}\n")
        out.write("="*80 + "\n\n")
        out.write("REPOSITORY STRUCTURE\n")
        out.write("-"*80 + "\n")
        
        # 1. Generate Tree Structure
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            level = root.replace(root_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            sub_dir = os.path.basename(root)
            if sub_dir:
                out.write(f"{indent}{sub_dir}/\n")
            for f in sorted(files):
                if f not in exclude_files and not f.endswith(('.pyc', '.png', '.jpg', '.jpeg', '.pdf')):
                    out.write(f"{indent}    {f}\n")
        
        out.write("\n" + "="*80 + "\n\n")
        out.write("FILE CONTENTS\n")
        out.write("-"*80 + "\n")
        
        # 2. Append File Contents
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in sorted(files):
                if f not in exclude_files and not f.endswith(('.pyc', '.png', '.jpg', '.jpeg', '.pdf', '.zip', '.tar.gz')):
                    file_path = os.path.join(root, f)
                    rel_path = os.path.relpath(file_path, root_dir)
                    out.write(f"\n{'='*40}\nFILE: {rel_path}\n{'='*40}\n")
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='replace') as code_file:
                            out.write(code_file.read())
                    except Exception as e:
                        out.write(f"[Could not read file: {e}]\n")
                    out.write("\n")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', nargs='?', default='.')
    parser.add_argument('-o', '--output', default='project_snapshot.txt')
    args = parser.parse_args()
    generate_snapshot(args.dir, args.output)
    print(f"Snapshot successfully saved to {args.output}")
