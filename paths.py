"""Data lives outside ~/Desktop so the launchd agents can read it without a privacy prompt."""
from pathlib import Path

DATA = Path.home() / 'Library' / 'Application Support' / 'Room' / 'data'
DATA.mkdir(parents=True, exist_ok=True)
