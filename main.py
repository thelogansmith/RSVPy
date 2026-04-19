"""
RSVPy entry point.

Creates the Tk root and hands off to the main window. All interesting
work lives in the ui, core, importers, and storage packages; this
module exists so `python main.py` is the one obvious way to launch the
app.
"""

from ui.main_window import launch


if __name__ == "__main__":
    launch()
