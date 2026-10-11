"""ITTKI Nazorat — launcher (also the PyInstaller entry script)."""
import sys

from ittki.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
