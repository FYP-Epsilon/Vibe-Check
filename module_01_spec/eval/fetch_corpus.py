import os
import shutil
import subprocess
from pathlib import Path

def main():
    REPO_URL = "https://github.com/IBM/flow-bench"
    # Using the latest main branch commit or a known one, we'll try to clone then checkout
    # Let's clone into a temporary directory
    repo_dir = Path("temp_flowbench")
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    print("Cloning IBM flow-bench repository...")
    subprocess.run(["git", "clone", REPO_URL, str(repo_dir)], check=True)

    # Let's pin to the current HEAD or a specific commit. 
    # For now, we will get the current HEAD commit hash.
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_dir), capture_output=True, text=True, check=True)
    pinned_sha = proc.stdout.strip()
    print(f"Pinned SHA: {pinned_sha}")

    # Target directory
    target_dir = Path("module_01_spec/eval/corpus/flowbench")
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy BPMN files
    source_dir = repo_dir / "data" / "output"
    bpmn_files = list(source_dir.glob("uid_*_output.bpmn"))
    print(f"Found {len(bpmn_files)} BPMN files. Copying to {target_dir}...")
    
    for f in bpmn_files:
        shutil.copy(f, target_dir / f.name)

    # Also copy the expected_output.sequence and conditional_ootb.yaml as they are needed for A.3
    if (repo_dir / "data" / "conditional_ootb.yaml").exists():
        shutil.copy(repo_dir / "data" / "conditional_ootb.yaml", target_dir / "conditional_ootb.yaml")
        print("Copied conditional_ootb.yaml")

    # Write PROVENANCE.md
    provenance_path = Path("module_01_spec/eval/corpus/PROVENANCE.md")
    provenance_content = f"""# Corpus Provenance

**Source:** IBM flow-bench
**Repository:** {REPO_URL}
**Pinned SHA:** {pinned_sha}
**License:** Apache-2.0

The BPMN files in the `flowbench/` directory were copied from the `data/output/` directory of the above repository.
"""
    provenance_path.write_text(provenance_content)
    print(f"Wrote {provenance_path}")

    # Cleanup
    print("Cleaning up temporary directory...")
    # On Windows, we need to handle read-only files in git repos
    def remove_readonly(func, path, excinfo):
        os.chmod(path, 0o777)
        func(path)
    shutil.rmtree(repo_dir, onerror=remove_readonly)
    
    print("Corpus fetched successfully.")

if __name__ == "__main__":
    main()
