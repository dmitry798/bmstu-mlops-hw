"""Weight-free local CI; process exit is never suppressed."""
import os
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
commands=[([sys.executable,'-m','compileall','-q','release.py','lab.py','service_core.py','service.py','api.py','flow.py','real_release.py','tests','integration_tests','scripts'],{}),([sys.executable,'-m','unittest','discover','-s','tests','-v'],{}),([sys.executable,'-m','unittest','discover','-s','integration_tests','-v'],{}),([sys.executable,'-m','unittest','discover','-s','integration_tests','-v'],{'SERVICE_FRAMEWORK':'fastapi'})]
for command, extra in commands:
    print('RUN', ' '.join(command),extra,flush=True)
    result=subprocess.run(command,cwd=root,env={**os.environ,**extra})
    if result.returncode: sys.exit(result.returncode)
print('LOCAL CI PASSED',flush=True)
