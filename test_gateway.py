import unittest,tempfile,json,threading,urllib.request,urllib.error,base64
from pathlib import Path
from http.server import ThreadingHTTPServer
from gateway import Store,make_handler
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
if __name__=='__main__':unittest.main()
