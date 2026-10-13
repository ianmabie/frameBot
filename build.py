#!/usr/bin/env python3
import os,subprocess,zipfile,json
from pathlib import Path
root=Path(__file__).resolve().parent
sdk=Path(os.environ.get('FRAME_SDK_ROOT','/private/tmp/frame-wireless/build-tools')).expanduser()
try:
 javac=Path(os.environ['JAVA_HOME'])/'bin/javac' if os.environ.get('JAVA_HOME') else next(sdk.rglob('bin/javac'))
 jdk=javac.parent.parent
 platforms=sdk/'platforms' if (sdk/'platforms').exists() else sdk/'android-platform'
 tools=sdk/'build-tools' if (sdk/'build-tools').exists() else sdk/'android-tools'
 jar=next(platforms.rglob('android.jar'))
 aapt=next(tools.rglob('aapt2'));bt=aapt.parent
 if not javac.is_file():raise FileNotFoundError('javac')
except (StopIteration,FileNotFoundError):
 raise SystemExit('Build tools missing. Set FRAME_SDK_ROOT to an Android SDK containing platforms and build-tools, and JAVA_HOME to a JDK 17. See README.md.')
app=root/'android';out=app/'build';out.mkdir(exist_ok=True)
(out/'classes').mkdir(exist_ok=True)
generated=out/'generated/com/ian/frame';generated.mkdir(parents=True,exist_ok=True)
cfg=json.loads((root/'data/config.json').read_text())
(generated/'BuildConfig.java').write_text('package com.ian.frame; final class BuildConfig { static final String FRAME_URL='+json.dumps(cfg['frame_url'])+'; static final String READ_TOKEN='+json.dumps(cfg['read_token'])+'; }')
env=os.environ.copy();env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+':'+env.get('PATH','')
def run(args):subprocess.run([str(x) for x in args],check=True,env=env,cwd=app)
run([aapt,'compile','--dir',app/'res','-o',out/'resources.zip'])
run([aapt,'link','-o',out/'base.apk','-I',jar,'--manifest',app/'AndroidManifest.xml',out/'resources.zip','--min-sdk-version','23','--target-sdk-version','23'])
run([javac,'-nowarn','-source','8','-target','8','-classpath',jar,'-d',out/'classes',*list((app/'src').rglob('*.java')),*list((out/'generated').rglob('*.java'))])
run([bt/'d8','--min-api','23','--lib',jar,'--output',out,*list((out/'classes').rglob('*.class'))])
with zipfile.ZipFile(out/'base.apk','a',zipfile.ZIP_DEFLATED) as z:z.write(out/'classes.dex','classes.dex')
run([bt/'zipalign','-f','4',out/'base.apk',out/'aligned.apk'])
key=out/'frame.keystore'
if not key.exists():run([jdk/'bin/keytool','-genkeypair','-keystore',key,'-storepass','android','-keypass','android','-alias','frame','-keyalg','RSA','-keysize','2048','-validity','10000','-dname','CN=Frame Development'])
run([bt/'apksigner','sign','--ks',key,'--ks-pass','pass:android','--out',out/'frame.apk',out/'aligned.apk'])
run([bt/'apksigner','verify',out/'frame.apk'])
print('Built and verified:',out/'frame.apk')
