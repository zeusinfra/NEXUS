import os
import shutil
import tempfile
from pathlib import Path
from zeus_core.integrations.filesystem_mirror import FilesystemMirror

def test_filesystem_mirror_basic():
    # Setup temporary directory structure
    # We use a subfolder in the project to avoid the /tmp ignore filter
    test_root = Path("test_mirror_temp").resolve()
    test_root.mkdir(parents=True, exist_ok=True)
    
    try:
        (test_root / "folder1").mkdir(exist_ok=True)
        (test_root / "folder1" / "file1.txt").write_text("Hello")
        (test_root / "folder2").mkdir(exist_ok=True)
        (test_root / "file2.py").write_text("print('test')")
        
        # Setup temporary vault
        vault_dir = test_root / "vault"
        vault_dir.mkdir(parents=True, exist_ok=True)
        
        os.environ["ZEUS_VAULT_PATH"] = str(vault_dir)
        mirror = FilesystemMirror()
        
        # Run mirror
        result = mirror.mirror_path(str(test_root), max_depth=2)
        print(result)
        
        # Check if mirror files exist in a structured way
        mirror_root = vault_dir / "OS_Mirror"
        assert mirror_root.exists()
        
        # Calculate relative path as used in the mirror
        rel_path = str(test_root).lstrip("/")
        base_mirror = mirror_root / rel_path
        
        # Check for folder1
        assert (base_mirror / "folder1" / "folder1.md").exists()
        assert (base_mirror / "folder2" / "folder2.md").exists()
        assert (base_mirror / "file2.py.md").exists()
        assert (base_mirror / "folder1" / "file1.txt.md").exists()
        
        print("Structure check passed!")
        
    finally:
        # Cleanup
        if test_root.exists():
            shutil.rmtree(test_root)


if __name__ == "__main__":
    try:
        test_filesystem_mirror_basic()
        print("Test passed!")
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
