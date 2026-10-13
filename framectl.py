#!/usr/bin/env python3
"""Push content from this Mac. No extra packages required."""
import argparse,base64,json,mimetypes,sys,urllib.request,urllib.error
from pathlib import Path
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
text=sub.add_parser('text');text.add_argument('title');text.add_argument('body');text.add_argument('--id',default='hermes');text.add_argument('--eyebrow',default='HERMES');text.add_argument('--accent',default='#D6C3A5');text.add_argument('--no-focus',action='store_true')
image=sub.add_parser('image');image.add_argument('file');image.add_argument('--id',default='image');image.add_argument('--title',default='');image.add_argument('--no-focus',action='store_true')
raw=sub.add_parser('json');raw.add_argument('file',help='JSON card payload, or - for stdin')
sub.add_parser('status')
remove=sub.add_parser('remove');remove.add_argument('id')
a=p.parse_args();cfg=json.loads((root/'data/config.json').read_text());method='POST';path='/push'
if a.command=='text':data={'card':{'id':a.id,'type':'text','title':a.title,'body':a.body,'eyebrow':a.eyebrow,'accent':a.accent},'focus':not a.no_focus}
elif a.command=='image':
 f=Path(a.file);mime=mimetypes.guess_type(f.name)[0];data={'card':{'id':a.id,'type':'image','title':a.title,'image':'data:'+str(mime)+';base64,'+base64.b64encode(f.read_bytes()).decode()},'focus':not a.no_focus}
elif a.command=='json':data=json.load(sys.stdin) if a.file=='-' else json.loads(Path(a.file).read_text())
elif a.command=='status':method='GET';path='/status';data=None
else:method='DELETE';path='/cards/'+a.id;data=None
req=urllib.request.Request('http://127.0.0.1:'+str(cfg['port'])+path,data=None if data is None else json.dumps(data).encode(),method=method,headers={'Authorization':'Bearer '+cfg['push_token'],'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(req,timeout=15) as r:print(r.read().decode())
except urllib.error.HTTPError as e:print(e.read().decode(),file=sys.stderr);sys.exit(1)
