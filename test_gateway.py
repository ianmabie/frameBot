import unittest,tempfile,json,threading,urllib.request,urllib.error,base64,subprocess,sys,pwd,os
from pathlib import Path
from http.server import ThreadingHTTPServer
from gateway import Store,make_handler,public_push_allowed
class GatewayTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name)
  (self.data/'config.json').write_text(json.dumps({'read_token':'read','push_token':'push','port':0}))
  self.store=Store(self.data);self.http=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.store));self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.http.server_port)
 def tearDown(self):self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
 def request(self,path,token='',payload=None):
  req=urllib.request.Request(self.url+path,data=None if payload is None else json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=3) as r:return json.load(r)
 def test_access_boundaries(self):
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/state')
  self.assertEqual(e.exception.code,401)
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/push','read',{'title':'no'})
  self.assertEqual(e.exception.code,401)
  self.assertEqual(len(self.request('/state','read')['cards']),2)
 def test_push_focus_and_persistence(self):
  self.request('/push','push',{'card':{'id':'note','title':'Hello','body':'From Hermes'},'focus':True})
  state=self.request('/state','read');self.assertEqual(state['focus_id'],'note');self.assertEqual(state['revision'],1)
  self.assertEqual(Store(self.data).state,state)
  self.request('/push','push',{'card':{'id':'note','title':'Update'},'focus':False})
  state=self.request('/state','read');self.assertEqual(len(state['cards']),3);self.assertNotIn('focus_id',state)
 def test_rejects_invalid_cards_without_mutating(self):
  before=json.dumps(self.store.state)
  for card in ({'id':'../escape'}, {'type':'executable'}, {'id':'clock','type':'html'}, {'body':'x'*16001}):
   with self.assertRaises(urllib.error.HTTPError) as e:self.request('/push','push',card)
   self.assertEqual(e.exception.code,400);self.assertEqual(json.dumps(self.store.state),before)
 def test_image_roundtrip(self):
  data=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR6sAAAAASUVORK5CYII=')
  self.request('/push','push',{'id':'photo','type':'image','image':'data:image/png;base64,'+base64.b64encode(data).decode()})
  path=self.store.state['cards'][-1]['image_path']
  req=urllib.request.Request(self.url+path,headers={'Authorization':'Bearer read'})
  with urllib.request.urlopen(req) as r:self.assertEqual(r.read(),data)
 def delete(self,ident,token='',headers=None):
  req=urllib.request.Request(self.url+'/cards/'+ident,method='DELETE',headers=headers or {'Authorization':'Bearer '+token})
  with urllib.request.urlopen(req,timeout=3) as r:return json.load(r)
 def test_delete_only_scope_and_revocation(self):
  self.store.config.update(public_push=False,delete_tokens={'shell-e':'delete-only'})
  self.request('/push','push',{'id':'remove-me','title':'Temporary'})
  for path,payload in [('/state',None),('/status',None),('/push',{'id':'no'})]:
   with self.assertRaises(urllib.error.HTTPError) as e:self.request(path,'delete-only',payload)
   self.assertEqual(e.exception.code,401)
  for token in ('','read','wrong'):
   with self.assertRaises(urllib.error.HTTPError) as e:self.delete('remove-me',token)
   self.assertEqual(e.exception.code,401)
  self.assertTrue(self.delete('remove-me','delete-only')['ok'])
  self.store.config['delete_tokens']={}
  with self.assertRaises(urllib.error.HTTPError) as e:self.delete('hermes','delete-only')
  self.assertEqual(e.exception.code,401)
  self.assertTrue(self.delete('hermes','push')['ok'])
 def test_clock_protected_but_hermes_test_card_deletable(self):
  self.store.config['delete_tokens']={'shell-e':'delete-only'}
  before=json.dumps(self.store.state)
  with self.assertRaises(urllib.error.HTTPError) as e:self.delete('clock','delete-only')
  self.assertEqual(e.exception.code,400);self.assertEqual(json.dumps(self.store.state),before)
  self.assertTrue(self.delete('hermes','delete-only')['ok'])
  self.assertEqual([c['id'] for c in self.store.state['cards']],['clock'])
  self.assertEqual(Store(self.data).state,self.store.state)
 def test_lan_cannot_delete_even_with_token_or_forwarded_header(self):
  self.store.config['delete_tokens']={'shell-e':'delete-only'}
  class Remote:
   client_address=('192.168.1.42',12345)
   headers={'Authorization':'Bearer delete-only','X-Forwarded-For':'127.0.0.1'}
   def answer(self,status,data):self.status=status
  remote=Remote()
  self.assertFalse(make_handler(self.store).auth_delete(remote))
  self.assertEqual(remote.status,403)
 def test_shared_cli_uses_invoking_profile_and_loopback_only(self):
  self.store.config['delete_tokens']={'shell-e':'delete-only'}
  profile=pwd.getpwuid(os.getuid()).pw_name
  (self.data/('delete-'+profile+'.json')).write_text(json.dumps({'delete_token':'delete-only'}))
  cli=self.data/'framectl.py'
  cli.write_text(Path(__file__).with_name('framectl.py').read_text().replace("Path('/Users/Shared/HermesFrameClient')",'Path('+repr(str(self.data))+')'))
  args=[sys.executable,'-B',str(cli),'--url',self.url,'remove','hermes']
  result=subprocess.run(args,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['ok'])
  # An explicit non-literal hostname must not receive the local credential.
  args[4]=self.url.replace('127.0.0.1','localhost')
  result=subprocess.run(args,capture_output=True,text=True)
  self.assertEqual(result.returncode,1);self.assertIn('Unauthorized',result.stderr)
  self.assertNotIn('delete-only',result.stdout+result.stderr)

class PublicPushTest(GatewayTest):
 def setUp(self):
  super().setUp()
  self.store.config.update(public_push=True,public_push_networks=['127.0.0.0/8','192.168.1.0/24'])
 def test_access_boundaries(self):
  self.assertTrue(self.request('/push',payload={'id':'from_other_profile','title':'Hello'})['ok'])
  self.assertEqual(self.request('/status')['revision'],1)
  with self.assertRaises(urllib.error.HTTPError) as e:self.request('/state')
  self.assertEqual(e.exception.code,401)
  req=urllib.request.Request(self.url+'/cards/from_other_profile',method='DELETE')
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req,timeout=3)
  self.assertEqual(e.exception.code,401)
  self.assertEqual(len(self.store.state['cards']),3)
 def test_network_scope_cannot_be_enabled_by_request_headers(self):
  self.assertTrue(public_push_allowed(self.store.config,'192.168.1.42'))
  for ip in ('192.168.2.42','8.8.8.8','not-an-ip'):
   self.assertFalse(public_push_allowed(self.store.config,ip))
  self.assertFalse(public_push_allowed({'public_push':False,'public_push_networks':['0.0.0.0/0']},'192.168.1.42'))
  self.store.config['public_push_networks']=['192.168.2.0/24']
  req=urllib.request.Request(self.url+'/push',data=b'{"title":"denied"}',headers={'X-Forwarded-For':'192.168.2.42','Content-Type':'application/json'})
  with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req,timeout=3)
  self.assertEqual(e.exception.code,401)
  self.assertEqual(self.store.state['revision'],0)

if __name__=='__main__':unittest.main()
