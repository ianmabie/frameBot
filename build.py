#!/usr/bin/env python3
import argparse,os,subprocess,zipfile,json,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description='Build API 23 frame APK; never creates a signing key')
p.add_argument('--unsigned',action='store_true',help='Build aligned unsigned APK for source review only')
p.add_argument('--config',type=Path,default=root/'data/config.json',help='Existing private build configuration')
p.add_argument('--keystore',type=Path,default=root/'android/build/frame.keystore',help='Existing owner signing key')
a=p.parse_args()
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
if not a.unsigned and not a.keystore.is_file():
 raise SystemExit('Existing signing key missing. Owner must use --keystore with the original key. No new key was generated. Use --unsigned for a non-installable review build.')
if not a.config.is_file():raise SystemExit('Existing build config missing. Owner must supply --config; do not regenerate live tokens.')
if (out/'classes').exists():shutil.rmtree(out/'classes')
(out/'classes').mkdir(exist_ok=True)
generated=out/'generated/com/ian/frame';generated.mkdir(parents=True,exist_ok=True)
cfg=json.loads(a.config.read_text())
(generated/'BuildConfig.java').write_text('package com.ian.frame; final class BuildConfig { static final String FRAME_URL='+json.dumps(cfg['frame_url'])+'; static final String READ_TOKEN='+json.dumps(cfg['read_token'])+'; }')
env=os.environ.copy();env['JAVA_HOME']=str(jdk);env['PATH']=str(jdk/'bin')+':'+env.get('PATH','')
def run(args):subprocess.run([str(x) for x in args],check=True,env=env,cwd=app)
run([aapt,'compile','--dir',app/'res','-o',out/'resources.zip'])
run([aapt,'link','-o',out/'base.apk','-I',jar,'--manifest',app/'AndroidManifest.xml',out/'resources.zip','--min-sdk-version','23','--target-sdk-version','23'])
run([javac,'-nowarn','-source','8','-target','8','-classpath',jar,'-d',out/'classes',*list((app/'src').rglob('*.java')),*list((out/'generated').rglob('*.java'))])
run([bt/'d8','--min-api','23','--lib',jar,'--output',out,*list((out/'classes').rglob('*.class'))])
with zipfile.ZipFile(out/'base.apk','a',zipfile.ZIP_DEFLATED) as z:z.write(out/'classes.dex','classes.dex')
run([bt/'zipalign','-f','4',out/'base.apk',out/'aligned.apk'])
if a.unsigned:
 print('Built unsigned review APK (do not install on existing frame):',out/'aligned.apk')
else:
 run([bt/'apksigner','sign','--ks',a.keystore.resolve(),'--ks-pass','pass:android','--out',out/'frame.apk',out/'aligned.apk'])
 run([bt/'apksigner','verify','--verbose','--print-certs',out/'frame.apk'])
 print('Built and signature verified; compare certificate digest to installed package before install:',out/'frame.apk')
