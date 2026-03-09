import sys
import subprocess

subprocess.check_call([sys.executable, "-m", "pip", "install", "edge-tts==7.2.7"])
import edge_tts
sub = edge_tts.SubMaker()
print(dir(sub))
print(vars(sub))
