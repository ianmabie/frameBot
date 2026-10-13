#!/usr/bin/env python3
"""Create fresh local credentials; never replace an existing frame's credentials."""
import argparse,json,os,secrets
from pathlib import Path
from urllib.parse import urlsplit

def initialize(directory,frame_url,port):
    parsed=urlsplit(frame_url)
    if parsed.scheme!='http' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Use a plain http://HOST:PORT gateway URL')
    if not 1<=port<=65535:raise ValueError('Port must be 1..65535')
    directory=Path(directory);directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=directory/'config.json'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump({'port':port,'frame_url':frame_url.rstrip('/'),'read_token':secrets.token_urlsafe(32),'push_token':secrets.token_urlsafe(32)},stream,indent=2)
    return path

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frame-url',required=True)
    p.add_argument('--port',type=int,default=8765)
    p.add_argument('--data',default=str(Path(__file__).resolve().parent/'data'))
    a=p.parse_args()
    try:result=initialize(a.data,a.frame_url,a.port)
    except FileExistsError:raise SystemExit('Config already exists. Keep it to preserve the installed app connection.')
    except ValueError as e:raise SystemExit(str(e))
    print('Created private config:',result)
