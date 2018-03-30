from struct  import unpack
from sys     import argv
from os.path import split, splitext, join
from io      import BytesIO as bio
import bpy, bmesh

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

# .md2 chunks:
# b'MDL2', # header, texture info
# b'MDL1', # old model version, rare
# b'MDL0', # old model version with no chunk system, rare
# b'P2G0', # unknown
# b'GEO1', # GEOmetry, mesh data
# b'COLD', # COLlision Data
# b'SHA0', # unknown
# b'SKN0', # weights?

def open_lr2(filepath, **kwargs):
	first4 = open(filepath,'rb').read(4)
	if   first4 == b'MDL2': return open_mdl2(filepath, **kwargs)
	#elif first4 == b'MDL1': return import_mdl1(filepath)
	#elif first4 == b'MDL0': return import_mdl0(filepath)
	else: raise AssertionError('Input file is not a MODEL2 file.')

VERTEX_HAS_VECTOR = 0b0001
VERTEX_HAS_NORMAL = 0b0010
VERTEX_HAS_COLOR  = 0b0100
VERTEX_HAS_UV     = 0b1000
def open_mdl2(filepath, open_bitmaps = True):
	f = open(filepath,'rb')
	
	open_bitmaps_successful = True
	if open_bitmaps:
		try: rootpath = filepath[:filepath.lower().index('game data')]
		except ValueError:
			open_bitmaps_successful = False
			print('Could not trace back to root directory "GAME DATA".')
		
	bpy.ops.object.empty_add()
	obj_root = bpy.context.scene.objects[0]
	obj_root.name = splitext(split(filepath)[1])[0]
	
	offset   = 0
	bitmaps  = []
	matprops = []
	objects  = []
	while 1:
		chunk_name = f.read(4)
		if chunk_name == b'\0\0\0\0' or not chunk_name: break
		chunk_size = unpack('I', f.read(4))[0]
		chunk_base = f.tell()
		
		print('%s: %s' % (chunk_name.decode('ascii'), hex(chunk_size)))
		
		if   chunk_name == b'MDL2':
			mdl2_inertiamulti   = unpack('3f', f.read(12))
			mdl2_boundingradius = unpack('f', f.read(4))
			mdl2_distancefades  = unpack('I', f.read(4))
			mdl2_hasboundingbox = unpack('I', f.read(4))
			if mdl2_hasboundingbox:
				mdl2_boundingboxmin    = unpack('3f', f.read(12))
				mdl2_boundingboxmax    = unpack('3f', f.read(12))
				mdl2_boundingboxcenter = unpack('3f', f.read(12))
				mdl2_boundingboxroty   = unpack('f', f.read(4))
			mdl2_useuniquematerials = unpack('I', f.read(4))
			mdl2_useuniquetextures  = unpack('I', f.read(4))
			mdl2_usegenericgeometry = unpack('I', f.read(4))
			mdl2_vertexbufferflags  = unpack('I', f.read(4))
			f.seek(f.tell() + 48) # padding
			
			mdl2_bitmap_count = unpack('I', f.read(4))[0]
			print('	Textures:', mdl2_bitmap_count)
			for bitmap_id in range(mdl2_bitmap_count):
				bitmap_path  = readnulltermstring(f.read(256)).decode('utf8')
				bitmap_type  ,\
				bitmap_index = unpack('2I', f.read(8))
				print('		' + bitmap_path)
				bitmaps += [(bitmap_path, bitmap_type, bitmap_index)]
			materials = [bpy.data.materials.new(x[0]) for x in bitmaps]
			
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
			print('End of MDL2:', hex(f.tell()))
			
		elif chunk_name == b'GEO1':
			geo1_detaillevels = unpack('I', f.read(4))[0]
			detaillevel_string = 'Detail level %%0%ii' % len(str(geo1_detaillevels))
			print('Detail levels: %i' % geo1_detaillevels)
			
			for detaillevel_id in range(geo1_detaillevels):
				print('Detail level %i:' % detaillevel_id)
				bpy.ops.object.empty_add()
				dl_root = bpy.context.scene.objects[0]
				dl_root.name = detaillevel_string % detaillevel_id
				dl_root.parent = obj_root
				
				geo1_detaillevel_type         ,\
				geo1_detaillevel_maxedgelength,\
				geo1_rendergroups       = unpack('IfI', f.read(12))
				f.seek(f.tell() + 8) # padding
				print(' Detail level type: %i'            % geo1_detaillevel_type)
				print(' Detail level max edge length: %f' % geo1_detaillevel_maxedgelength)
				print(' Render groups: %i'                % geo1_rendergroups)
				
				rendergroup_string = 'Rendergroup %%0%ii (Material %%0%ii)' % (len(str(geo1_rendergroups)), len(str(len(bitmaps))))
				for rendergroup_id in range(geo1_rendergroups):
					work_bmesh = bmesh.new()
					geo1_rendergroup_polygons,\
					geo1_rendergroup_vertices,\
					geo1_rendergroup_material,\
					geo1_rendergroup_effects  = unpack('4H', f.read(8))
					f.seek(f.tell() + 12) # padding
					print('  Render group polygons: %i' % geo1_rendergroup_polygons)
					print('  Render group vertices: %i' % geo1_rendergroup_vertices)
					print('  Render group material: %i' % geo1_rendergroup_material)
					print('  Render group effects: %i'  % geo1_rendergroup_effects)
					geo1_texblend_effectmask     ,\
					geo1_texblend_renderreference,\
					geo1_texblend_effects        ,\
					geo1_texblend_custom         ,\
					geo1_texblend_coordinates     = unpack('3H2B', f.read(8))
					geo1_texblend_blends          = tuple(unpack('IH2B', f.read(8)) for x in range(4))
					#geo1_texblend0-3_effect          ,\
					#geo1_texblend0-3_textureindex    ,\
					#geo1_texblend0-3_coordinateindex ,\
					#geo1_texblend0-3_tilinginfo      = unpack('IH2B', f.read(4+2+1*2)) # tilinginfo 0x3 = tiling enabled, 0 = disabled
					print('  Texture blend effect mask: %i'      % geo1_texblend_effectmask)
					print('  Texture blend render reference: %i' % geo1_texblend_renderreference)
					print('  Texture blend effects: %i'          % geo1_texblend_effects)
					print('  Texture blend custom: %i'           % geo1_texblend_custom)
					print('  Texture blend coordinates: %i'      % geo1_texblend_coordinates)
					print('  Texture blend blends: %i'           % len(geo1_texblend_blends))
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
					f.seek(f.tell() + 8) # padding
					print('  Vertex vector offset: %i'       % geo1_vertex_offset_vector)
					print('  Vertex normal offset: %i'       % geo1_vertex_offset_normal)
					print('  Vertex colour offset: %i'       % geo1_vertex_offset_colour)
					print('  Vertex uv offset: %i'           % geo1_vertex_offset_texcoord)
					print('  Vertex struct size: %i'         % geo1_vertex_size_vertstruct)
					print('  Vertex texture coordinates: %i' % geo1_vertex_num_texcoords)
					print('  Vertex flags: %s'               % format(geo1_vertex_flags, '08b'))
					print('  Vertex vertices: %i'            % geo1_vertex_vertices)
					print('  Vertex managed buffer: %i'      % geo1_vertex_managedbuffer)
					print('  Vertex current: %i'             % geo1_vertex_currentvertex)
					
					for vertex in range(geo1_vertex_vertices): work_bmesh.verts.new()
					work_bmesh.verts.ensure_lookup_table()
					
					uvs = []
					normals = []
					assert geo1_vertex_flags & VERTEX_HAS_VECTOR, 'Vertex struct has no vertices.'
					for vertex in range(geo1_vertex_vertices):
						# this dumb code works, but there is probably a model or two it doesn't work on. wip
						vertex_struct = bio(f.read(geo1_vertex_size_vertstruct))
						vertex_xyz    = unpack('3f', vertex_struct.read(12))[::-1]
						if geo1_vertex_size_vertstruct == 0x20: pass
						elif geo1_vertex_size_vertstruct == 0x24: vertex_struct.read(4)
						elif geo1_vertex_size_vertstruct == 0x28: vertex_struct.read(8)
						else: raise AssertionError('Unexpected vertex struct size (%s).' % hex(geo1_vertex_size_vertstruct))
						vertex_normal = unpack('3f', vertex_struct.read(12))[::-1]
						vertex_uv     = unpack('2f', vertex_struct.read(8))
						work_bmesh.verts[vertex].co = vertex_xyz
						normals += [vertex_normal]
						uvs += [vertex_uv]
					
					geo1_fill_selectableprimblocks,\
					geo1_fill_type                ,\
					geo1_fill_indices              = unpack('3I', f.read(12))
					
					for polygon in range(geo1_fill_indices // 3):
						work_bmesh.faces.new((work_bmesh.verts[x] for x in unpack('3H', f.read(6))))#.material_index = geo1_texblend_blends[0][1]
					
					### uv
					work_bmesh.faces.ensure_lookup_table()
					work_bmesh.verts.index_update()
					uv_layer = work_bmesh.loops.layers.uv.new()
					for face in work_bmesh.faces:
						for loop in face.loops: loop[uv_layer].uv = uvs[loop.vert.index]
					### uv
					
					work_mesh = bpy.data.meshes.new(rendergroup_string % (rendergroup_id, geo1_texblend_blends[0][1]))
					work_bmesh.to_mesh(work_mesh)
					
					#### uv test
					work_mesh.normals_split_custom_set_from_vertices(normals)
					work_mesh.use_auto_smooth = True
					#### uv test
					
					work_obj = bpy.data.objects.new(rendergroup_string % (rendergroup_id, geo1_texblend_blends[0][1]), work_mesh)
					work_obj.data.materials.append(materials[geo1_texblend_blends[0][1]])
					work_obj.parent = dl_root
					bpy.context.scene.objects.link(work_obj)
		
		offset += 8 + chunk_size
		f.seek(offset)
	f.close()
	
	obj_root.rotation_euler = (__import__('math').pi / 2, 0, 0)
	
	if open_bitmaps and open_bitmaps_successful:
		for bitmap in bitmaps:
			bpy.ops.image.open(filepath = join(rootpath, splitext(bitmap[0])[0] + '.mip'))