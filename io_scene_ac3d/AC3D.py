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

	def addChild( self,
								child ):
		if not isinstance(child, Object):
			raise Exception('addChild: can only add childs derived from Object')

		child.parent = self
		self.children.append(child)
		
	def _write( self, strm ):
		pass

	def write( self, strm ):
		strm.write('OBJECT {0}\nname "{1}"\n'.format(self.type, self.name))
		self._write(strm)

		if self.parent and self.bl_obj:	
			# absolute position in world coordinates
			pos_abs = self.bl_obj.matrix_world.to_translation()
			
			if self.parent.bl_obj:
				# position relative to parent
				pos_rel = pos_abs - self.parent.bl_obj.matrix_world.to_translation()
			else:
				pos_rel = pos_abs

			location = self.export_config.global_matrix * pos_rel
			strm.write('loc {0} {1} {2}\n'.format(location[0], location[1], location[2]))

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
