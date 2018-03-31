from struct  import unpack
from os.path import split, splitext, join
from io      import BytesIO as bio

__import__('os').system('') # initialize windows color formatting
col_red   = '\x1b[38;2;%i;%i;%im' % (0xFF, 0x00, 0x00)
col_green = '\x1b[38;2;%i;%i;%im' % (0x00, 0xFF, 0x00)
col_blue  = '\x1b[38;2;%i;%i;%im' % (0x00, 0x00, 0xFF)
col_reset = '\x1b[0m'

def readnulltermstring(input,skip=False):
	if type(input) in (str, bytes): #else it's a file object
		null = '\0' if type(input)==str else b'\0'
		return input[:input.index(null)] if null in input else input
	if skip:
		while 1:
			c = input.read(1)
			if not c or c == b'\0': return
	buildstring = bytearray()
	while 1:
		c = input.read(1)
		if not c or c == b'\0': return buildstring
		buildstring += c

def open_lr2(filepath, **kwargs):
	first4 = open(filepath,'rb').read(4)
	if   first4 == b'MDL2': return open_mdl2(filepath, **kwargs)
	#elif first4 == b'MDL1': return import_mdl1(filepath)
	#elif first4 == b'MDL0': return import_mdl0(filepath)
	else: pass #print(col_green + first4.decode('ascii') + ' ' + filepath + col_reset)

VERTEX_HAS_VECTOR = 0b0001
VERTEX_HAS_NORMAL = 0b0010
VERTEX_HAS_COLOR  = 0b0100
VERTEX_HAS_UV     = 0b1000

DEFAULT_TEXBLEND = unpack('IH2B', b'\xff\xff\xff\xff\xff\xff\x0f\x03')
DEFAULT_TEXBLEND_RAW = b'\xff\xff\xff\xff\xff\xff\x0f\x03'

def open_mdl2(filepath):
	f = open(filepath,'rb')
	offset   = 0
	bitmaps  = []
	matprops = []
	objects  = []
	while 1:
		chunk_name = f.read(4)
		if chunk_name == b'\0\0\0\0' or not chunk_name: break
		chunk_size = unpack('I', f.read(4))[0]
		chunk_base = f.tell()
		if   chunk_name == b'MDL2':
			mdl2_inertiamulti   = unpack('3f', f.read(12))
			mdl2_boundingradius,\
			mdl2_distancefades ,\
			mdl2_hasboundingbox = unpack('f2I', f.read(12)) # there is no model with no bounding box
				
			if mdl2_hasboundingbox:
				mdl2_boundingboxmin    = unpack('3f', f.read(12))
				mdl2_boundingboxmax    = unpack('3f', f.read(12))
				mdl2_boundingboxcenter = unpack('3f', f.read(12))
				mdl2_boundingboxroty   = unpack('f', f.read(4))
			
			# always 0
			# always 0
			# always 0
			# always 0
			mdl2_useuniquematerials,\
			mdl2_useuniquetextures ,\
			mdl2_usegenericgeometry,\
			mdl2_vertexbufferflags  = unpack('4I', f.read(16))
			f.seek(f.tell() + 48)
			
			# variable
			mdl2_bitmap_count = unpack('I', f.read(4))[0]
			for bitmap_id in range(mdl2_bitmap_count):
				bitmap_path  = readnulltermstring(f.read(256)).decode('utf8')
				bitmap_type  ,\
				bitmap_index = unpack('2I', f.read(8))
				bitmaps += [(bitmap_path, bitmap_type, bitmap_index)]
			
			# variable
			mdl2_matprop_count = unpack('I', f.read(4))[0]
			for matprop_id in range(mdl2_matprop_count):
				mdl2_matprop_ambient   = unpack('4f', f.read(16))
				mdl2_matprop_diffuse   = unpack('4f', f.read(16))
				mdl2_matprop_specular  = unpack('4f', f.read(16))
				mdl2_matprop_emissive  = unpack('4f', f.read(16))
				mdl2_matprop_shine     ,\
				mdl2_matprop_alpha     ,\
				mdl2_matprop_alphatype ,\
				mdl2_matprop_bitfield  = unpack('2f2I', f.read(16))
				mdl2_matprop_animname  = readnulltermstring(f.read(8))
				matprops += [(
					mdl2_matprop_ambient  ,
					mdl2_matprop_diffuse  ,
					mdl2_matprop_specular ,
					mdl2_matprop_emissive ,
					mdl2_matprop_shine    ,
					mdl2_matprop_alpha    ,
					mdl2_matprop_alphatype,
					mdl2_matprop_bitfield ,
					mdl2_matprop_animname ,
				)]
				
			#if mdl2_matprop_count != 1:
			#	print('%s %i %s%s%s' % (col_green, mdl2_matprop_count, col_red, filepath, col_reset))
			#	return
		
		elif chunk_name == b'GEO1':
			geo1_detaillevels = unpack('I', f.read(4))[0]
			detaillevel_string = 'Detail level %%0%ii' % len(str(geo1_detaillevels))
			
			for detaillevel_id in range(geo1_detaillevels):
				geo1_detaillevel_type         ,\
				geo1_detaillevel_maxedgelength,\
				geo1_rendergroups       = unpack('IfI', f.read(12))
				f.seek(f.tell() + 8)
					
				rendergroup_string = 'Rendergroup %%0%ii (Material %%0%ii)' % (len(str(geo1_rendergroups)), len(str(len(bitmaps))))
				for rendergroup_id in range(geo1_rendergroups):
					# variable
					# variable
					# variable
					# 512 in rgeffects models, else 0
					geo1_rendergroup_polygons,\
					geo1_rendergroup_vertices,\
					geo1_rendergroup_material,\
					geo1_rendergroup_effects  = unpack('4H', f.read(8))
					f.seek(f.tell() + 12)
					
					# variable as 3, 9, 17, or 513 in effects models, else 0
					# always 0
					# 2 in effects models, else always 1
					# always 0
					# 2 in flow models, else always 1
					geo1_texblend_effectmask     ,\
					geo1_texblend_renderreference,\
					geo1_texblend_effects        ,\
					geo1_texblend_custom         ,\
					geo1_texblend_coordinates     = unpack('3H2B', f.read(8))
					geo1_texblend_blends          = tuple(unpack('IH2B', f.read(8)) for x in range(4))
					#geo1_texblend_blends         = tuple(f.read(8) for x in range(4))
					# I effect         
					# H textureindex    # the bitmap used on the rendergroup
					# B coordinateindex
					# B tilinginfo      # 0x3 = tiling enabled, 0 = disabled
					
					#for texblend in geo1_texblend_blends[1:]:
					#	if texblend != DEFAULT_TEXBLEND_RAW:
					#		print('Texb @ %s' % filepath)
					#		#print('%sDiffering texblend at %s%s%s' % (col_green, col_red, filepath, col_reset))
					#		#print('\n'.join(map(str, geo1_texblend_blends)))
					#		#input()
					#		return
					
					#geo1_texblend0-3_effect         ,\
					#geo1_texblend0-3_textureindex   ,\
					#geo1_texblend0-3_coordinateindex,\
					#geo1_texblend0-3_tilinginfo      = unpack('IH2B', f.read(4+2+1*2)) # tilinginfo 0x3 = tiling enabled, 0 = disabled
					
					# always 0
					# always 12
					# variable (trash memory if not geo1_vertex_flags & VERTEX_HAS_COLOR)
					# variable on account of previous int
                    # variable on account of previous ints
					# either 1, or 2 (rare)
					# see VERTEX_HAS_VECTOR and related
					# identical to geo1_rendergroup_vertices
					# always 1
					# either 15998, 16256, or 0
					geo1_vertex_offset_vector  ,\
					geo1_vertex_offset_normal  ,\
					geo1_vertex_offset_colour  ,\
					geo1_vertex_offset_texcoord,\
					geo1_vertex_size_vertstruct,\
					geo1_vertex_num_texcoords  ,\
					geo1_vertex_flags          ,\
					geo1_vertex_vertices       ,\
					geo1_vertex_managedbuffer  ,\
					geo1_vertex_currentvertex   = unpack('4i2I4H', f.read(32))
					f.seek(f.tell() + 8)
					
					f.seek(f.tell() + geo1_vertex_size_vertstruct * geo1_vertex_vertices)
					
					# always 1
					# always 0
					# always equal to (geo1_rendergroup_polygons*3)
					geo1_fill_selectableprimblocks,\
					geo1_fill_type                ,\
					geo1_fill_indices              = unpack('3I', f.read(12))
					
					f.seek(f.tell() + geo1_fill_indices*2) # skip polygons
					
					#test_faces = []
					#for face in range(geo1_rendergroup_polygons):
					#	face = unpack('3H', f.read(6))
					#	for test_face in test_faces:
					#		if (
					#			face[0] in test_face and
					#			face[1] in test_face and
					#			face[2] in test_face
					#		):
					#			print('%sdouble face in %s%s' % (col_green, filepath, col_reset))
					#			return
					#	test_faces += [face]
		
		offset += 8 + chunk_size
		f.seek(offset)
	f.close()
	
if __name__ == '__main__':
	from sys import argv
	from os import walk
	searchdir = argv[1]
	md2files = 0
	for dir, dirs, files in walk(searchdir):
		for file in files:
			if file.lower().endswith('.md2'):
				md2files += 1
				open_lr2(join(dir, file))
	while 1:input('Done. MD2 files: %i' % md2files)