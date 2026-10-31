"""Break cache identity only in a new copy; retain production source unchanged."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parents[1]
copy=Path(tempfile.mkdtemp(prefix='hw8910-negative-'))
shutil.copytree(root/'tests',copy/'tests')
source=(root/'release.py').read_text()
source=source.replace("return digest(canonical({'data_sha256': file_digest(data_path), 'config': config}))", "return '0'*64  # deliberate regression")
(copy/'release.py').write_text(source)
result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=copy)
print('Intentional broken-copy exit code:',result.returncode,flush=True)
print('Production files untouched; broken copy retained at',copy,flush=True)
sys.exit(result.returncode)
