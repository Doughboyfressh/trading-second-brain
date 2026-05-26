from pathlib import Path
from datetime import datetime

def create_vault():
    root = Path("vault")
    folders = [
        "00-Daily", "01-Assets/Stocks", "01-Assets/Options", "01-Assets/Crypto",
        "02-Strategies", "03-Trade-Journal", "04-Backtests", "05-Agent-Profiles",
        "06-Playbooks", "07-Research", "08-Logs", "Inbox", "Templates"
    ]
    for f in folders:
        (root / f).mkdir(parents=True, exist_ok=True)
    
    # Create a quick daily template
    with open(root / "Templates" / "Daily.md", "w") as f:
        f.write(f"""# Daily Market Note - {datetime.now().strftime("%Y-%m-%d")}
## Market Regime
## Key Insights from Agents
## Action Items
""")
    print("✅ Vault structure created! Open 'vault/' in Obsidian.")

if __name__ == "__main__":
    create_vault()