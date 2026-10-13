#!/usr/bin/env python3
"""Grant a local Mac profile delete-only frame access. Run as the gateway owner."""
import argparse,json,os,pwd,re,secrets,subprocess
from pathlib import Path


def private_write(path,content):
 if path.is_symlink():raise ValueError('Refusing a symlink: '+str(path))
 temp=path.with_name('.'+path.name+'.'+secrets.token_hex(8))
 try:
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as out:out.write(json.dumps(content))
  os.replace(temp,path)
 finally:
  if temp.exists():temp.unlink()


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('profile');p.add_argument('--revoke',action='store_true')
 a=p.parse_args()
 if not re.fullmatch(r'[a-zA-Z0-9_-]+',a.profile):p.error('Invalid profile name')
 pwd.getpwnam(a.profile)  # Must be an existing local account.
 live=Path.home()/'Library/Application Support/HermesFrame'
 config=live/'data/config.json';shared=Path('/Users/Shared/HermesFrameClient')
 for path in (live,config.parent,config,shared):
  if path.is_symlink() or path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o022:
   p.error('Gateway and client paths must belong to this user and not be writable by others')
 cfg=json.loads(config.read_text());tokens=cfg.setdefault('delete_tokens',{})
 credential=shared/('delete-'+a.profile+'.json')
 if credential.is_symlink():p.error('Credential must not be a symlink')
 if a.revoke:
  tokens.pop(a.profile,None)
  if credential.exists():credential.unlink()
 else:
  token=secrets.token_urlsafe(32)
  private_write(credential,{'delete_token':token})
  try:
   subprocess.run(['/bin/chmod','+a','user:'+a.profile+' allow read',str(credential)],check=True)
  except Exception:
   credential.unlink();raise
  tokens[a.profile]=token
 private_write(config,cfg)
 print(('Revoked' if a.revoke else 'Granted')+' delete-only access for '+a.profile+'. Restart or redeploy the gateway to apply.')


if __name__=='__main__':main()
