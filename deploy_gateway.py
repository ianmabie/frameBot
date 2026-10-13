#!/usr/bin/env python3
import os,plistlib,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
live=Path.home()/'Library/Application Support/HermesFrame'
live.mkdir(mode=0o700,parents=True,exist_ok=True)
for name in ('gateway.py','framectl.py'):shutil.copy2(root/name,live/name)
data=live/'data'
if not data.exists():shutil.copytree(root/'data',data)
data.chmod(0o700)
for f in data.rglob('*'):
 if f.is_file():f.chmod(0o600)
launch=Path.home()/'Library/LaunchAgents/com.ian.hermes-frame.plist'
launch.parent.mkdir(parents=True,exist_ok=True)
config={'Label':'com.ian.hermes-frame','ProgramArguments':['/usr/bin/python3','-B',str(live/'gateway.py')],'WorkingDirectory':str(live),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'StandardOutPath':str(live/'gateway.log'),'StandardErrorPath':str(live/'gateway-error.log')}
launch.write_bytes(plistlib.dumps(config));launch.chmod(0o600)
domain='gui/'+str(os.getuid())
service=domain+'/com.ian.hermes-frame'
loaded=subprocess.run(['launchctl','print',service],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
if loaded:subprocess.run(['launchctl','bootout',service],check=True)
subprocess.run(['launchctl','bootstrap',domain,str(launch)],check=True)
print('Installed frame gateway as a user login service')
