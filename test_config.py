import json,tempfile,unittest
from pathlib import Path
from init_config import initialize

class ConfigTest(unittest.TestCase):
    def test_new_config_is_private_and_cannot_replace_existing_credentials(self):
        with tempfile.TemporaryDirectory() as temp:
            path=initialize(Path(temp)/'data','http://192.168.1.128:8765/',8765)
            before=path.read_bytes();config=json.loads(before)
            self.assertEqual(config['frame_url'],'http://192.168.1.128:8765')
            self.assertNotEqual(config['read_token'],config['push_token'])
            self.assertEqual(path.stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):initialize(path.parent,'http://different:8765',8765)
            self.assertEqual(path.read_bytes(),before)
    def test_invalid_urls_do_not_create_config(self):
        with tempfile.TemporaryDirectory() as temp:
            for url in ('https://host','http://user:pass@host','http://host/path','http://host?token=secret'):
                with self.assertRaises(ValueError):initialize(temp,url,8765)
            self.assertFalse((Path(temp)/'config.json').exists())

if __name__=='__main__':unittest.main()
