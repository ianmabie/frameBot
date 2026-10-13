#!/usr/bin/env python3
"""Push content from this Mac. No extra packages required."""
import argparse,base64,json,mimetypes,pwd,re,sys,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',help='Gateway URL; no config or token required when LAN push is enabled');sub=p.add_subparsers(dest='command',required=True)
text=sub.add_parser('text');text.add_argument('title');text.add_argument('body');text.add_argument('--id',default='hermes');text.add_argument('--eyebrow',default='HERMES');text.add_argument('--accent',default='#D6C3A5');text.add_argument('--no-focus',action='store_true')
image=sub.add_parser('image');image.add_argument('file');image.add_argument('--id',default='image');image.add_argument('--title',default='');image.add_argument('--no-focus',action='store_true')
raw=sub.add_parser('json');raw.add_argument('file',help='JSON card payload, or - for stdin')
sub.add_parser('status')
remove=sub.add_parser('remove');remove.add_argument('id')
a=p.parse_args()
cfg={}
if not a.url:
 try:cfg=json.loads((root/'data/config.json').read_text())
 except (FileNotFoundError,PermissionError):pass
base=a.url or 'http://127.0.0.1:'+str(cfg.get('port',8765))
from urllib.parse import urlsplit
parsed=urlsplit(base)
if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
 p.error('--url must be a plain http://HOST:PORT or https://HOST:PORT URL')
method='POST';path='/push'
if a.command=='text':data={'card':{'id':a.id,'type':'text','title':a.title,'body':a.body,'eyebrow':a.eyebrow,'accent':a.accent},'focus':not a.no_focus}
elif a.command=='image':
 f=Path(a.file);mime=mimetypes.guess_type(f.name)[0];data={'card':{'id':a.id,'type':'image','title':a.title,'image':'data:'+str(mime)+';base64,'+base64.b64encode(f.read_bytes()).decode()},'focus':not a.no_focus}
elif a.command=='json':data=json.load(sys.stdin) if a.file=='-' else json.loads(Path(a.file).read_text())
elif a.command=='status':method='GET';path='/status';data=None
else:
 if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',a.id):p.error('Invalid card id')
 method='DELETE';path='/cards/'+a.id;data=None
headers={'Content-Type':'application/json'}
if cfg.get('push_token'):headers['Authorization']='Bearer '+cfg['push_token']
elif method=='DELETE' and parsed.hostname in ('127.0.0.1','::1'):
 import os
 profile=pwd.getpwuid(os.getuid()).pw_name
 credential=Path('/Users/Shared/HermesFrameClient')/('delete-'+profile+'.json')
 try:token=json.loads(credential.read_text())['delete_token']
 except (FileNotFoundError,PermissionError):
  p.error('Deletion access has not been granted to this profile; the gateway owner can run grant_delete.py '+profile)
 if not isinstance(token,str) or not token:p.error('Invalid deletion credential')
 headers['Authorization']='Bearer '+token
req=urllib.request.Request(base.rstrip('/')+path,data=None if data is None else json.dumps(data).encode(),method=method,headers=headers)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
try:
 with opener.open(req,timeout=15) as r:print(r.read().decode())
except urllib.error.HTTPError as e:print(e.read().decode(),file=sys.stderr);sys.exit(1)
except urllib.error.URLError:print('Gateway unavailable: '+base,file=sys.stderr);sys.exit(1)
