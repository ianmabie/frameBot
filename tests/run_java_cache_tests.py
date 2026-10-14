#!/usr/bin/env python3
"""Compile real production Android sources; run cache regressions with host framework shims."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--work-dir', type=Path, required=True, help='Authorized temporary test directory')
p.add_argument('--jdk', type=Path, default=Path('/opt/homebrew/Cellar/openjdk@17/17.0.20.1/libexec/openjdk.jdk/Contents/Home'))
p.add_argument('--android-jar', type=Path, default=Path('/Users/hermy/.hermes/cache/scratch/framebot-sdk/platforms/android-23/android.jar'))
a = p.parse_args()
work = a.work_dir.resolve()
production = work/'production'; host = work/'host'; fixtures = work/'fixtures'
for directory in (production, host, fixtures): directory.mkdir(parents=True, exist_ok=True)
build_config = ROOT/'tests/java/com/ian/frame/BuildConfig.java'
javac = a.jdk/'bin/javac'; java = a.jdk/'bin/java'
def run(args): subprocess.run([str(x) for x in args], cwd=ROOT, check=True)
run([javac, '-source', '8', '-target', '8', '-classpath', a.android_jar, '-d', production,
     *sorted((ROOT/'android/src').rglob('*.java')), build_config])
run([javac, '-source', '8', '-target', '8', '-classpath', os.pathsep.join(map(str, (production, a.android_jar))),
     '-d', host, *sorted((ROOT/'tests/java').rglob('*.java'))])
classpath = os.pathsep.join(map(str, (host, production, a.android_jar)))
run([java, '-Djava.awt.headless=true', '-Djava.io.tmpdir=' + str(fixtures), '-classpath', classpath,
     'com.ian.frame.CookbookLogicTest'])
run([java, '-Djava.awt.headless=true', '-Djava.io.tmpdir=' + str(fixtures), '-classpath', classpath,
     'com.ian.frame.MainActivityCacheTest', fixtures])
