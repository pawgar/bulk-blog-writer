"""Bulk Blog Writer — SemTree
Punkt wejścia aplikacji.
"""

import sys
from pathlib import Path

# Dodaj katalog aplikacji do sys.path (na wypadek uruchomienia z innego katalogu)
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ui.main_window import MainWindow


def main():
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
