import bpy
from math import radians, degrees
from mathutils import Vector, Matrix

DEBUG = True

def TRACE(message):
	if DEBUG:
		print(message)

# ------------------------------------------------------------------------------
class Object:
	'''
	Base class for an AC3D object.
	'''

	def __init__(	self,
								name,
								ob_type,
								bl_obj,
								export_config ):
		'''
		Create a AC3D object from a blender object and it's children
		
		@param name			The name of the object
		@param ob_type	The type of the object (world, poly, group)
		@param bl_obj	The according blender object
		@param export_config	Settings for export TODO move to export method?
		'''

		self.export_config = export_config
		self.name = name.replace('"','') # quotes not allowed...
		self.type = ob_type
		self.bl_obj = bl_obj
		self.children = []
		self.parent = None
		# absolute position in world coordinates
		self.pos_abs = bl_obj.matrix_world.to_translation() if bl_obj else None

	def addChild( self,
								child ):
		if not isinstance(child, Object):
			raise Exception('addChild: can only add childs derived from Object')

		child.parent = self
		self.children.append(child)
		
	def _parse( self, ac_mats, str_pre ):
		'''
		Override to process the blender mesh and add materials to ac_mats if
		needed
		'''
		pass
	
	def parse( self, ac_mats, str_pre = '' ):
		TRACE("{0}+-({1}) {2}".format(str_pre, self.type, self.name))
		
		self._parse(ac_mats, str_pre)
		
		for child in self.children:
			child.parse(ac_mats, str_pre + ' ')

	def _write( self, strm ):
		pass

	def write( self, strm ):
		strm.write('OBJECT {0}\nname "{1}"\n'.format(self.type, self.name))

		if self.parent and self.bl_obj:	
			if self.parent.bl_obj:
				# position relative to parent
				pos_rel = self.pos_abs - self.parent.bl_obj.matrix_world.to_translation()
			else:
				pos_rel = self.pos_abs

			location = self.export_config.global_matrix * pos_rel
			strm.write('loc {0} {1} {2}\n'.format(location[0], location[1], location[2]))

		self._write(strm)
		strm.write('kids {0}\n'.format(len(self.children)))
				
		for child in self.children:
			child.write(strm)

# ------------------------------------------------------------------------------
class World (Object):
	'''
	Normally the root element is a world object
	'''
	def __init__( self,
								name,
								export_config ):
		Object.__init__(self, name, 'world', None, export_config)

# ------------------------------------------------------------------------------
class Poly (Object):
	'''
	A polygon mesh
	'''
	def __init__( self,
								name,
								bl_obj,
								export_config ):
		Object.__init__(self, name, 'poly', bl_obj, export_config)
		
		self.crease = None
		self.vertices = []
		
	def _parse( self, ac_mats, str_pre ):

		if self.bl_obj:
			TRACE('{0}  ~ ({1}) {2}'.format( str_pre,
																			 self.bl_obj.type,
																			 self.bl_obj.data.name ))
			if self.bl_obj.type == 'MESH':
				self._parseMesh(ac_mats)
	
	def _parseMesh( self, ac_mats ):
		mesh = self.bl_obj.to_mesh(self.export_config.context.scene, True, 'PREVIEW')
		
		transform = self.export_config.global_matrix\
							* Matrix.Translation(-self.pos_abs)\
							* self.bl_obj.matrix_world
		self.vertices = [transform * v.co for v in mesh.vertices]
		
		for mod in self.bl_obj.modifiers:
			if mod.type=='EDGE_SPLIT':
				self.crease = degrees(mod.split_angle)
				break

		if not self.crease:
			if mesh.use_auto_smooth:
				self.crease = degrees(mesh.auto_smooth_angle)
			else:
				self.crease = self.export_config.crease_angle

		bpy.data.meshes.remove(mesh)
		
	def _write( self, strm ):

		if( len(self.vertices) ):
			strm.write('numvert {0}\n'.format(len(self.vertices)))
			for vert in self.vertices:
				strm.write('{0:.8f} {1:.8f} {2:.8f}\n'.format( vert[0],
																											 vert[1],
																											 vert[2] ))

# ------------------------------------------------------------------------------
class Group (Object):
	'''
	An object group
	
	TODO maybe add an option to prevent exporting empty groups
	'''
	def __init__( self,
								name,
								bl_obj,
								export_config ):
		Object.__init__(self, name, 'group', bl_obj, export_config)
