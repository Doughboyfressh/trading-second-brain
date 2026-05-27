from pathlib import Path
from datetime import datetime


def create_vault():
    root = Path(__file__).parent / "vault"   # absolute path
    folders = [
        "00-Daily",
        "01-Assets/Stocks", "01-Assets/Options", "01-Assets/Crypto",
        "02-Strategies",
        "03-Trade-Journal",
        "04-Backtests",
        "05-News",
        "05-Agent-Profiles",
        "06-Playbooks",
        "07-Research",
        "08-Logs",
        "09-Portfolio",
        "Inbox",
        "Templates",
    ]
    for f in folders:
        (root / f).mkdir(parents=True, exist_ok=True)

    # Daily template
    tpl = root / "Templates" / "Daily.md"
    if not tpl.exists():
        tpl.write_text(
            f"# Daily Market Note - {datetime.now().strftime('%Y-%m-%d')}\n"
            "## Market Regime\n"
            "## Key Insights from Agents\n"
            "## Action Items\n"
        )

    print("Vault structure ready — open vault/ in Obsidian.")


if __name__ == "__main__":
    create_vault()
