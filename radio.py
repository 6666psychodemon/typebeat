#!/usr/bin/env python3
"""
Legacy Streamlit radio entry — redirects to the liquid-glass local server.

Catalog remains:  streamlit run app.py
Radio (this MVP): python -m radio
                  or: python radio.py
"""

from radio.server import main

if __name__ == "__main__":
    main()
