"""Freeze installed distributions without modifying an environment."""
from importlib.metadata import distributions
for name, version in sorted({(d.metadata['Name'].lower(), d.version) for d in distributions()}):
    print(f'{name}=={version}')
