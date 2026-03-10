"""Entry point for the Engagement Simulator."""

import sys
import os

# Ensure the package root is on the path so 'app' imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ui.main_window import MainWindow


def main():
    window = MainWindow()
    window.run()


if __name__ == "__main__":
    main()
