import sys, zipfile, shutil, os

base, dex, out = sys.argv[1], sys.argv[2], sys.argv[3]
shutil.copy(base, out)
z = zipfile.ZipFile(out, 'a', zipfile.ZIP_STORED)
z.write(dex, 'classes.dex')
z.close()
print('packed ->', out, os.path.getsize(out), 'bytes')
