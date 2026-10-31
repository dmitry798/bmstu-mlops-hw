"""Export original source via git show (read-only), run unchanged public tests."""
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parents[1]
snapshot=Path(tempfile.mkdtemp(prefix='hw8910-original-'))
(snapshot/'tests').mkdir()
for name in ['release.py','lab.py','service.py','tests/test_release.py']:
    data=subprocess.check_output(['git','show','867cb8f:hw8910-broken/'+name],cwd=root)
    (snapshot/name).write_bytes(data)
result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=snapshot,capture_output=True,text=True)
(root/'docs/evidence/contracts-before.log').write_text(result.stdout+result.stderr+f'\nEXIT_CODE={result.returncode}\n')
print('Original public tests exit:',result.returncode)
# Additional crash test was added after original red capture and needs no red claim.
print('Original sources retained at',snapshot)
