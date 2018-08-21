from sys import argv
from struct import unpack
from os import walk
from os.path import isdir, isfile, join, split, splitext

if isfile(argv[1]):
	f = open(argv[1], 'rb')
	while 1:
		cn = f.read(4)
		if cn == b'\0\0\0\0' or len(cn) < 4: break
		cl = unpack('I', f.read(4))[0]
		print('%08x %s %08x' % (f.tell() - 8, cn.decode('utf8'), cl))
		f.seek(cl, 1)
else:
	chunks = {}
	for dir, dirs, files in walk(argv[1]):
		for file in files:
			if file.lower().endswith('.md2'):
				f = open(join(dir, file), 'rb')
				while 1:
					cn = f.read(4)
					if cn == b'MDL0' or cn == b'\0\0\0\0' or len(cn) < 4: break
					cl = unpack('I', f.read(4))[0]
					if not cn in chunks: chunks[cn] = 1
					else: chunks[cn] += 1
					f.seek(cl, 1)
	for key in chunks: print(key, chunks[key])
input('Done')