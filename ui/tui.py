#!/usr/bin/env python3
"""XYZ TUI Launcher"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.app import XYZApp


def main():
    """Run XYZ TUI application."""
    app = XYZApp()
    app.run()


if __name__ == "__main__":
    main()
