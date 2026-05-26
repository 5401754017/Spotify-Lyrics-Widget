import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.shortcuts import create_shortcuts


def main():
    locations = create_shortcuts()
    print(f"Created: {locations.desktop}")
    print(f"Created: {locations.start_menu}")


if __name__ == "__main__":
    main()
