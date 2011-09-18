# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####


import os
import struct

import bpy
import mathutils
from math import radians
from collections import defaultdict
from bpy import *
from bpy_extras.image_utils import load_image

'''
This file is a reboot of the AC3D import script that is used to import .ac format file into blender.

The original work carried out by Willian P Gerano was used to learn Python and Blender, but inherent issues and a desire to do better has prompted a reboot

Reference to the .ac format is found here:
http://www.inivis.com/ac3d/man/ac3dfileformat.html

Some noted points that are important for consideration:
 - AC3D appears to use Left Handed axes, but with Y oriented "Up". Blender uses Right Handed axes
 - AC3D supports only one texture per surface.
 - Blender's Materials can have multiple textures per material - so a material + texure in AC3D requires a distinct and unique material in blender

'''

DEBUG = True

def TRACE(message):
	if DEBUG:
		print(message)

'''
Container class for a .ac OBJECT
'''
class AcObj:
	def __init__(self, ob_type, ac_file, parent = None):
		self.type = ob_type			# Type of object
		self.ac_parent = parent		# reference to the parent object (if the object is World, then this should be None)
		self.name = ''				# name of the object
		self.data = ''				# custom data
		self.texture = ''			# texture (filepath)
		self.texrep = [1,1]			# texture repeat
		self.texoff = [0,0]			# texture offset
		self.loc = [0,0,0]			# translation location of the center relative to the parent object
		self.rot = [[1,0,0],[0,1,0],[0,0,1]]	# 3x3 rotational matrix for vertices
		self.url = ''				# url of the object (??!)
		self.crease = 30			# crease angle for smoothing
		self.vert_list = []				# list of Vector(X,Y,Z) objects
		self.surf_list = []			# list of attached surfaces
		self.face_list = []
		self.children = []

		self.bl_obj = None			# Blender object

		self.tokens =	{
						'numvert':	self.read_vertices,
						'numsurf':	self.read_surfaces,
						'name':		self.read_name,
						'data':		self.read_data,
						'kids':		self.read_children,
						'loc':		self.read_location,
						'rot':		self.read_rotation,
						'texture':	self.read_texture,
						'texrep':	self.read_texrep,
						'texoff':	self.read_texoff,
						'subdiv':	self.read_subdiv,
						'crease':	self.read_crease
						}

		self.read_ac_object(ac_file)
#		TRACE("Created object: {0} {1} {2} {3} {4} {5} {6}".format(self.type, self.name, self.data, self.texture, self.loc, self.rot, self.url))

	'''
	Read the object lines and dump them into this object, making hierarchial attachments to parents
	'''
	def read_ac_object(self, ac_file):
		bDone = False
		while not bDone:
			line = ac_file.readline()
			if line == '':
				break
			toks = line.strip().split()
			if len(toks)>0:
				if toks[0] in self.tokens.keys():
#					TRACE("\t{ln}".format(ln=line.strip()))
					bDone = self.tokens[toks[0]](ac_file,toks)
				else:
					bDone = True

	def read_vertices(self, ac_file, toks):
		vertex_count = int(toks[1])
		for n in range(vertex_count):
			line = ac_file.readline()
#			TRACE("\t\t{ln}".format(ln=line.strip()))
			line = line.strip().split()
			self.vert_list.append([float(x) for x in line])

	def read_surfaces(self, ac_file, toks):
		surf_count = int(toks[1])

		for n in range(surf_count):
			line = ac_file.readline()
			if line=='':
				break

#			TRACE("\t\t{ln}".format(ln=line.strip()))
			line = line.strip().split()
			if line[0] == 'SURF':
				self.surf_list.append(AcSurf(line[1],ac_file))

	def read_name(self, ac_file, toks):
		self.name=toks[1].strip('"')
		return False

	def read_data(self, ac_file, toks):
		line = ac_file.readline()
		self.data=line[:int(toks[1])]
		return False

	def read_location(self, ac_file, toks):
		self.loc=[0,0,0]
		return False

	def read_rotation(self, ac_file, toks):
		self.rot = Matrix([
							[float(x) for x in toks[1:4]],
							[float(x) for x in toks[4:7]],
							[float(x) for x in toks[7:9]],
							])	# 3x3 rotational matrix for vertices
		return False

	def read_texture(self, ac_file, toks):
		self.texture=toks[1].strip('"')
		return False

	def read_texrep(self, ac_file, toks):
		self.texrep=toks[1:2]
		return False

	def read_texoff(self, ac_file, toks):
		self.texoff=toks[1:2]
		return False

	def read_subdiv(self, ac_file, toks):
		self.subdiv=int(toks[1])
		return False

	def read_crease(self, ac_file, toks):
		self.crease=float(toks[1])
		return False

	def read_children(self, ac_file, toks):
		num_kids = int(toks[1])
		for n in range(num_kids):
			line = ac_file.readline()
			if line == '':
				break			
#			TRACE("\t{ln}".format(ln=line.strip()))
			line = line.strip().split()
			self.children.append(AcObj(line[1].strip('"'),ac_file,self))
		# This is assumed to be the last thing in the list of things to read
		# returning True indicates to cease parsing this object
		return True

	'''
	This function does the work of creating an object in blender and configuring it correctly
	'''
	def create_blender_object(self, ac_matlist, import_config, str_pre, bLevelLinked):

		if self.type == 'world':
			self.name = import_config.ac_name
		bl_mesh = None
		if self.type == 'group' or self.type == 'world':
			# Create an empty object
			self.bl_obj = bpy.data.objects.new(self.name, None)
#			import_config.context.scene.objects.link(self.bl_obj)

		if self.type == 'light':
			bl_lamp = bpy.data.lamps.new(self.name)
			self.bl_obj = bpy.data.objects.new(self.name, bl_lamp)

		if self.type == 'poly':
			bl_mesh = bpy.data.meshes.new(self.name)
			self.bl_obj = bpy.data.objects.new(self.name, bl_mesh)

		if self.vert_list and bl_mesh:
			# make sure we have some vertices
			face_list = []
			bl_mat_dict = {}
			for surf in self.surf_list:
				face_list.append(surf.refs)
				# Material index is 1 based, the list we built is 0 based
				ac_material = ac_matlist[surf.mat_index-1]
				bl_material = ac_material.get_blender_material(import_config, self.texture)
				if bl_material == None:
					TRACE("{0}".format(len(ac_matlist)))
					TRACE("Error getting material {0} '{1}'".format(surf.mat_index, self.texture))

#				TRACE("Using Material Index {0}".format(surf.mat_index))
#				if not bl_material.name in bl_mesh.materials:
#					bl_mesh.materials.append(bl_material)
			
			bl_mesh.from_pydata(self.vert_list, [], face_list)
			self.bl_obj.show_transparent = import_config.display_transparency

		import_config.context.scene.objects.link(self.bl_obj)

		TRACE("{0}+-{1}".format(str_pre, self.name))

		# Add any children
		str_pre_new = ""
		bUseLink = True
		for obj in self.children:
			if bLevelLinked:
				str_pre_new = str_pre + "| "
			else:
				str_pre_new = str_pre + "  "

			if self.children.index(obj) == len(self.children)-1:
				bUseLink = False

			obj.create_blender_object(ac_matlist, import_config,str_pre_new, bUseLink)
			obj.bl_obj.parent = self.bl_obj

		if bl_mesh:
			bl_mesh.calc_normals()
			bl_mesh.update(calc_edges=True)
			

'''
Container class for surface definition within a parent object
'''
class AcSurf:
	def __init__(self, flags, ac_file):
		self.flags = flags			# surface flags
		self.mat_index = 0				# default material
		self.refs = []				# list of indexes into the parent objects defined vertexes with defined UV coordinates 
		self.uv_refs = []
		self.tokens =	{
						'mat':	self.read_surf_material,
						'refs':	self.read_surf_refs,
						}
		self.read_ac_surfaces(ac_file)
#		TRACE("Created surface: {0} {1} ({2})".format(self.flags, self.mat_index, len(self.refs)))

	def read_ac_surfaces(self, ac_file):
		surf_done=False
		while not surf_done:
			line = ac_file.readline()
			if line=='':
				break
			toks = line.split()
			if len(toks)>0:
				if toks[0] in self.tokens.keys():
#					TRACE("\t\t{ln}".format(ln=line.strip()))
					surf_done = self.tokens[toks[0]](ac_file,toks)
				else:
					surf_done = True
			
	def read_surf_material(self, ac_file, tokens):
		self.mat_index = int(tokens[1])
		return False
	
	def read_surf_refs(self, ac_file, tokens):
		num_refs = int(tokens[1])
		for n in range(num_refs):
			line = ac_file.readline()
#			TRACE("\t\t\t{ln}".format(ln=line.strip()))
			line = line.strip().split()
		
			self.refs.append(int(line[0]))
			self.uv_refs.append([float(x) for x in line[1:3]])
		return True

class AcMat:
	'''
	Container class that defines the material properties of the .ac MATERIAL
	'''
	def __init__(self, name, rgb, amb, emis, spec, shi, trans):
		if name == "":
			name = "Default"
		self.name = name			# string
		self.rgb = rgb				# [R,G,B]
		self.amb = amb				# [R,G,B]
		self.emis = emis			# [R,G,B]
		self.spec = spec			# [R,G,B]
		self.shi = shi				# integer
		self.trans = trans			# float

		self.bmat_keys = {}			# dictionary list of blender materials
		self.bmat_keys.setdefault(None)
		self.bl_material = None		# untextured material

#		TRACE("Created material: {0} {1} {2} {3} {4} {5} {6}".format(self.name, self.rgb, self.amb, self.emis, self.spec, self.shi, self.trans))

	def make_blender_mat(self, bl_mat, import_config):
		bl_mat.diffuse_color = self.rgb
		bl_mat.ambient = (self.amb[0] + self.amb[1] + self.amb[2]) / 3.0
		bl_mat.emit = (self.emis[0] + self.emis[1] + self.emis[2]) / 3.0
		bl_mat.specular_color = self.spec
		bl_mat.specular_intensity = float(self.shi) / 100
		bl_mat.alpha = (1.0 - self.trans)
		if bl_mat.alpha < 1.0:
			bl_mat.use_transparency = import_config.use_transparency
			bl_mat.transparency_method = import_config.transparency_method
		return bl_mat

	'''
	looks for a matching blender material (optionally with a texture), adds it if it doesn't exist
	'''
	def get_blender_material(self, import_config, tex_name=''):
		bl_mat = None
		tex_slot = None
		if tex_name == '':
			bl_mat = self.bl_material
			if bl_mat == None:
				bl_mat = bpy.data.materials.new(self.name)
				bl_mat = self.make_blender_mat(bl_mat, import_config)

				self.bl_material = bl_mat
		else:
			if tex_name in self.bmat_keys:
				bl_mat = self.bmat_keys[tex_name]
			else:
				bl_mat = bpy.data.materials.new(self.name)
				bl_mat = self.make_blender_mat(bl_mat, import_config)
				
				tex_slot = bl_mat.texture_slots.add()
				tex_slot.texture = self.get_blender_texture(import_config, tex_name)

				self.bmat_keys[tex_name] = bl_mat
		return bl_mat

	'''
	looks for the image in blender, adds it if it doesn't exist, returns the image to the callee
	'''
	def get_blender_image(self, import_config, tex_name):
		bl_image = None
		if tex_name in bpy.data.images:
			bl_image = bpy.data.images[texture]
		else:
			texture_path = None
			if os.path.exists(tex_name):
				texture_path = texture
			elif os.path.exists(os.path.join(import_config.importdir, tex_name)):
				texture_path = os.path.join(import_config.importdir, tex_name)
		
			if texture_path:
#				TRACE("Loading texture: {0}".format(texture_path))
				try:
					bl_image = bpy.data.images.load(texture_path)
				except:
					TRACE("Failed to load texture: {0}".format(tex_name))

		return bl_image

	'''
	looks for the blender texture, adds it if it doesn't exist
	'''
	def get_blender_texture(self, import_config, tex_name):
		bl_tex = None
		if tex_name in bpy.data.textures:
			bl_tex = bpy.data.textures[tex_name]
		else:
			bl_tex = bpy.data.textures.new(tex_name, 'IMAGE')
			bl_tex.image = self.get_blender_image(import_config, tex_name)
			bl_tex.use_preview_alpha = True

		return bl_tex

class ImportConf:
	def __init__(
			self,
			operator,
			context,
			filepath,
			use_image_search,
			global_matrix,
			use_auto_smooth,
			show_double_sided,
			use_transparency,
			transparency_method,
			transparency_shadows,
			display_transparency,
			use_emis_as_mircol,
			use_subsurf,
			):
		# Stuff that needs to be available to the working classes (ha!)
		self.operator = operator
		self.context = context
		self.global_matrix = global_matrix
		self.use_image_search = use_image_search
		self.use_auto_smooth = use_auto_smooth
		self.show_double_sided = show_double_sided
		self.use_transparency = use_transparency
		self.transparency_method = transparency_method
		self.transparency_shadows = transparency_shadows
		self.display_transparency = display_transparency
		self.use_emis_as_mircol = use_emis_as_mircol

		# used to determine relative file paths
		self.importdir = os.path.dirname(filepath)
		self.ac_name = os.path.split(filepath)[1]
		TRACE("Importing {0}".format(self.ac_name))
	
class ImportAC3D:
	def __init__(
			self,
			operator,
			context,
			filepath="",
			use_image_search=False,
			global_matrix=None,
			use_auto_smooth=False,	
			show_double_sided=True,
			use_transparency=True,
			transparency_method='Z_TRANSPARENCY',
			transparency_shadows=False,
			display_transparency=True,
			use_emis_as_mircol=True,
			use_subsurf=True,
			):

		self.import_config = ImportConf(
										operator,
										context,
										filepath,
										use_image_search,
										global_matrix,
										use_auto_smooth,
										show_double_sided,
										use_transparency,
										transparency_method,
										transparency_shadows,
										display_transparency,
										use_emis_as_mircol,
										use_subsurf,
										)


		self.tokens = 	{
						'MATERIAL':		self.read_material,
						'OBJECT':		self.read_object,
						}
		self.oblist = []
		self.matlist = []

		operator.report('INFO', "Attempting import: {file}".format(file=filepath))

		# Check to make sure we're working with a valid AC3D file
		ac_file = open(filepath, 'r')
		self.header = ac_file.readline().strip()
		if len(self.header) != 5:
			# have blender report an error (using an indexed argument)
			operator.report('ERROR',"Invalid file header length: {0}".format(self.header))
			ac_file.close()
			return None

		#pull out the AC3D file header
		AC3D_header = self.header[:4]
		AC3D_ver = self.header[4:5]
		if AC3D_header != 'AC3D':
			operator.report('ERROR',"Invalid file header: {0}".format(self.header))
			ac_file.close()
			return None

		self.read_ac_file(ac_file)

		ac_file.close()

		self.create_blender_data()

		return None

	'''
	Simplifies the reporting of errors to the user
	'''
	def report_error(self, message):
		self.operator.report('ERROR',message)

	'''
	read our validated .ac file
	'''
	def read_ac_file(self, ac_file):
		line = ac_file.readline()
		while line != '':
			toks = line.strip().split()
			# See if this is a valid token and pass the file handle and the current line to our function
			if len(toks) > 0:
				if toks[0] in self.tokens.keys():
#					TRACE("*\t{ln}".format(ln=line.strip()))
					self.tokens[toks[0]](ac_file,toks)
				else:
					self.report_error("invalid token: {tok} ({ln})".format(tok=toks[0], ln=line.strip()))

			line = ac_file.readline()

	'''
	Take the passed in line and interpret as a .ac material
	'''
	def read_material(self, ac_file, line):

		# MATERIAL %s rgb %f %f %f  amb %f %f %f  emis %f %f %f  spec %f %f %f  shi %d  trans %f

		self.matlist.append(AcMat(line[1].strip('"'),
						[float(x) for x in line[3:6]],
						[float(x) for x in line[7:10]],
						[float(x) for x in line[11:14]],
						[float(x) for x in line[15:18]],
						int(line[19]),
						float(line[21])
						))

	'''
	Read the Object definition (including child objects)
	'''
	def read_object(self, ac_file, line):
		# OBJECT %s
		self.oblist.append(AcObj(line[1].strip('"'), ac_file))

	'''
	Reads the data imported from the file and creates blender data
	'''
	def create_blender_data(self):

		# go through the list of objects
		bUseLink = True
		for obj in self.oblist:
			if self.oblist.index(obj) == len(self.oblist)-1:
				bUseLink = False
			obj.create_blender_object(self.matlist, self.import_config, "", bUseLink)

