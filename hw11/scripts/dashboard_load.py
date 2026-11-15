"""Low-rate real traffic solely for the live screen demonstration."""
import experiments as e
import time
e.ports[:]=[19200+i for i in range(4)]
processes=e.launch_clients()
try:e.collect(e.begin('video-dashboard-'+str(int(time.time())),'other',e.schedule(480,1)))
finally:
 for process in processes:process.terminate()
