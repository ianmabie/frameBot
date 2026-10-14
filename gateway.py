#!/usr/bin/env python3
"""Local, persistent content gateway for the Android frame."""
import argparse,base64,hashlib,hmac,ipaddress,json,mimetypes,os,re,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from cookbook import empty_index,manifest,validate_png,asset_path,ASSET_RE,MAX_ASSET,THUMB_SIZE,DETAIL_SIZE
ROOT=Path(__file__).resolve().parent
DEFAULT={"revision":0,"focus_id":"clock","cards":[
 {"id":"clock","type":"clock","title":"Today","accent":"#BBD7B2"},
 {"id":"hermes","type":"text","title":"Room for a new thought.","eyebrow":"HERMES","body":"Your agent can send notes, images, and updates here. Swipe to explore.","accent":"#D6C3A5"}]}
class Store:
 def __init__(self,data):
  self.data=Path(data);self.data.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
  self.config=json.loads((self.data/'config.json').read_text())
  self.path=self.data/'state.json';self.media=self.data/'media';self.media.mkdir(exist_ok=True)
  self.last_poll=0;self.last_client=None
  self.state=json.loads(self.path.read_text()) if self.path.exists() else json.loads(json.dumps(DEFAULT))
  self.cookbook_path=self.data/'cookbook.json';self.cookbook_media=self.data/'cookbook-assets';self.cookbook_media.mkdir(exist_ok=True)
  self.cookbook=json.loads(self.cookbook_path.read_text()) if self.cookbook_path.exists() else empty_index()
 def upload_cookbook_asset(self,payload):
  if not isinstance(payload,dict) or set(payload)!={'image'} or not isinstance(payload['image'],str) or not payload['image'].startswith('data:image/png;base64,'):raise ValueError('Expected a cookbook PNG image')
  try:body=base64.b64decode(payload['image'].split(',',1)[1],validate=True)
  except Exception:raise ValueError('Invalid image encoding')
  validate_png(body);path=asset_path(body);target=self.cookbook_media/path.split('/')[-1]
  with self.lock:
   if not target.exists() or target.stat().st_size!=len(body) or target.read_bytes()!=body:
    tmp=target.with_suffix('.tmp')
    with tmp.open('wb') as out:out.write(body);out.flush();os.fsync(out.fileno())
    tmp.chmod(0o600);os.replace(tmp,target)
  return {'ok':True,'asset_path':path}
 def import_cookbook(self,payload):
  clean=manifest(payload)
  with self.lock:
   # Validate every referenced file before touching the authoritative index.
   for recipe in clean['recipes']:
    for key,size in [('thumbnail_path',THUMB_SIZE),('detail_path',DETAIL_SIZE)]:
     path=recipe[key];target=self.cookbook_media/path.split('/')[-1]
     if not target.is_file():raise ValueError('Missing cookbook asset: '+path)
     body=target.read_bytes();validate_png(body,size)
     if asset_path(body)!=path:raise ValueError('Cookbook asset hash mismatch')
   if clean['revision']!=self.cookbook['revision']:
    tmp=self.cookbook_path.with_suffix('.tmp')
    with tmp.open('w') as out:json.dump(clean,out);out.flush();os.fsync(out.fileno())
    tmp.chmod(0o600);os.replace(tmp,self.cookbook_path);self.cookbook=clean
   return {'ok':True,'revision':self.cookbook['revision'],'recipes':len(clean['recipes'])}
 def save(self):
  tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.state));tmp.chmod(0o600);os.replace(tmp,self.path)
 def push(self,payload):
  if not isinstance(payload,dict):raise ValueError('Expected a JSON object')
  card=payload.get('card',payload)
  if not isinstance(card,dict):raise ValueError('Expected a card object')
  ident=card.get('id','hermes')
  if not isinstance(ident,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',ident):raise ValueError('Invalid card id')
  kind=card.get('type','text')
  if kind not in ('clock','text','image','html'):raise ValueError('Unsupported card type')
  clean={'id':ident,'type':kind}
  for key,limit in [('title',200),('body',16000),('eyebrow',80),('html',100000)]:
   value=card.get(key,'')
   if not isinstance(value,str) or len(value)>limit:raise ValueError('Invalid '+key)
   clean[key]=value
  accent=card.get('accent','#BBD7B2')
  if not isinstance(accent,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',accent):raise ValueError('Invalid accent')
  clean['accent']=accent
  image=None
  if kind=='image':
   uri=card.get('image','')
   if not isinstance(uri,str) or not re.match(r'^data:image/(png|jpeg|webp);base64,',uri):raise ValueError('Image must be a PNG, JPEG, or WebP data URI')
   head,b64=uri.split(',',1)
   try:image=base64.b64decode(b64,validate=True)
   except Exception:raise ValueError('Invalid image encoding')
   if not 0<len(image)<=8*1024*1024:raise ValueError('Image exceeds 8 MiB')
   ext={'image/png':'png','image/jpeg':'jpg','image/webp':'webp'}[head[5:].split(';')[0]]
   valid=(ext=='png' and image.startswith(b'\x89PNG\r\n\x1a\n')) or (ext=='jpg' and image.startswith(b'\xff\xd8\xff')) or (ext=='webp' and image.startswith(b'RIFF') and image[8:12]==b'WEBP')
   if not valid:raise ValueError('Image type does not match its bytes')
   clean['image_path']='/media/'+hashlib.sha256(image).hexdigest()+'.'+ext
  with self.lock:
   if ident=='clock' and kind!='clock':raise ValueError('The default clock must remain a clock')
   existing=next((i for i,c in enumerate(self.state['cards']) if c['id']==ident),None)
   if existing is None and len(self.state['cards'])>=20:raise ValueError('Maximum 20 cards')
   if image is not None:(self.media/clean['image_path'].split('/')[-1]).write_bytes(image)
   if existing is None:self.state['cards'].append(clean)
   else:self.state['cards'][existing]=clean
   self.state['revision']+=1
   if payload.get('focus',True):self.state['focus_id']=ident
   else:self.state.pop('focus_id',None)
   self.save();return {'ok':True,'revision':self.state['revision'],'card_id':ident}
 def remove(self,ident):
  if ident=='clock':raise ValueError('The default clock cannot be removed')
  with self.lock:
   if not any(c['id']==ident for c in self.state['cards']):raise ValueError('Card not found')
   self.state['cards']=[c for c in self.state['cards'] if c['id']!=ident];self.state['revision']+=1;self.state.pop('focus_id',None);self.save()
   return {'ok':True,'revision':self.state['revision']}
def public_push_allowed(config,client_ip):
 if config.get('public_push') is not True:return False
 try:
  address=ipaddress.ip_address(client_ip)
  return any(address in ipaddress.ip_network(net) for net in config.get('public_push_networks',[]))
 except (ValueError,TypeError):return False

def make_handler(store):
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*args):pass
  def answer(self,status,data):
   body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  def auth(self,push=False,allow_public=False):
   if allow_public and public_push_allowed(store.config,self.client_address[0]):return True
   expected=store.config['push_token' if push else 'read_token']
   supplied=self.headers.get('Authorization','')
   if push and self.client_address[0] not in ('127.0.0.1','::1'):self.answer(403,{'error':'Push requests must originate on this Mac'});return False
   if not hmac.compare_digest(supplied,'Bearer '+expected):self.answer(401,{'error':'Unauthorized'});return False
   return True
  def do_GET(self):
   if self.path=='/health':self.answer(200,{'ok':True});return
   if self.path=='/status':
    if not self.auth(True,allow_public=True):return
    self.answer(200,{'last_poll':store.last_poll,'client':store.last_client,'revision':store.state['revision'],'cookbook_revision':store.cookbook['revision'],'recently_connected':time.time()-store.last_poll<15});return
   if not self.auth():return
   if self.path=='/state':
    with store.lock:
     store.last_poll=time.time();store.last_client=self.client_address[0];self.answer(200,store.state)
   elif self.path=='/cookbook':
    with store.lock:self.answer(200,store.cookbook)
   elif re.fullmatch(r'/media/[a-f0-9]{64}\.(png|jpg|webp)',self.path) or re.fullmatch(ASSET_RE,self.path):
    p=(store.cookbook_media if self.path.startswith('/cookbook/') else store.media)/self.path.split('/')[-1]
    if not p.is_file():self.answer(404,{'error':'Not found'});return
    body=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(p.name)[0]);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   else:self.answer(404,{'error':'Not found'})
  def do_POST(self):
   if self.path not in ('/push','/cookbook/assets','/cookbook/import'):self.answer(404,{'error':'Not found'});return
   if not self.auth(True,allow_public=True):return
   try:
    n=int(self.headers.get('Content-Length','0'))
    limit=512*1024 if self.path=='/cookbook/import' else (2*1024*1024+1024 if self.path=='/cookbook/assets' else 12*1024*1024)
    if not 0<n<=limit:self.answer(413,{'error':'Payload size exceeds endpoint limit'});return
    self.connection.settimeout(10)
    payload=json.loads(self.rfile.read(n))
    operation={'/push':store.push,'/cookbook/assets':store.upload_cookbook_asset,'/cookbook/import':store.import_cookbook}[self.path]
    self.answer(200,operation(payload))
   except (ValueError,TypeError,KeyError) as e:self.answer(400,{'error':str(e)})
   except OSError:self.answer(500,{'error':'Storage unavailable; inspect deck state before retrying' if self.path=='/push' else 'Storage unavailable; cookbook index was not replaced'})
  def auth_delete(self):
   if self.client_address[0] not in ('127.0.0.1','::1'):
    self.answer(403,{'error':'Delete requests must originate on this Mac'});return False
   supplied=self.headers.get('Authorization','')
   tokens=[store.config['push_token']]+list(store.config.get('delete_tokens',{}).values())
   if not any(isinstance(token,str) and token and hmac.compare_digest(supplied,'Bearer '+token) for token in tokens):
    self.answer(401,{'error':'Unauthorized'});return False
   return True
  def do_DELETE(self):
   if not self.auth_delete():return
   if not re.fullmatch(r'/cards/[a-zA-Z0-9_-]{1,64}',self.path):self.answer(404,{'error':'Not found'});return
   try:self.answer(200,store.remove(self.path.split('/')[-1]))
   except ValueError as e:self.answer(400,{'error':str(e)})
 return Handler
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--data',default=str(ROOT/'data'));parser.add_argument('--port',type=int);args=parser.parse_args()
 store=Store(args.data);port=args.port or store.config['port']
 server=ThreadingHTTPServer(('0.0.0.0',port),make_handler(store));server.daemon_threads=True
 print('Frame content gateway listening on port '+str(port),flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
