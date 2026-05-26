from pathlib import Path
from datetime import datetime
import os
from config import VAULT_PATH

class VaultManager:
    def __init__(self):
        self.root = Path(VAULT_PATH)
    
    def write_note(self, folder: str, filename: str, content: str, append: bool = False):
        path = self.root / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        prefix = f"### {datetime.now().isoformat()}\n" if append else ""
        with open(path, mode, encoding="utf-8") as f:
            f.write(prefix + content + "\n\n")
        print(f"✅ Vault updated: {path}")
    
    def read_note(self, folder: str, filename: str) -> str:
        path = self.root / folder / filename
        return path.read_text(encoding="utf-8") if path.exists() else ""
    
    def list_notes(self, folder: str):
        path = self.root / folder
        return [f.name for f in path.glob("*.md")] if path.exists() else []