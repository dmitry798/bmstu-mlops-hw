"""Append the report's cold-start explanation, then stop the actual OBS output."""
from pathlib import Path
import time,json,subprocess
from browser_control import Browser
from obs_control import OBS
ROOT=Path(__file__).resolve().parents[1]
while not (ROOT/'results/demo-finished.json').exists():time.sleep(1)
b=Browser();b.navigate((ROOT/'report.html').as_uri());time.sleep(2);b.js('document.body.style.fontSize="22px"');b.js('Array.from(document.querySelectorAll("h2")).find(x=>x.textContent.startsWith("A.")).scrollIntoView()');subprocess.run(['wmctrl','-a','Google Chrome']);time.sleep(20)
b.js('Array.from(document.querySelectorAll("p")).find(x=>x.textContent.startsWith("Первый диагностический rollout")).scrollIntoView()');time.sleep(20)
o=OBS();output=o.call('StopRecord');(ROOT/'results/record-output.json').write_text(json.dumps({'wall_time':time.time(),**output},indent=2));print(output,flush=True)
