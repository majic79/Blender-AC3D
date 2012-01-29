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

'''
This file is a complete reboot of the AC3D export script that is used to export .ac format file into blender.

Reference to the .ac format is found here:
http://www.inivis.com/ac3d/man/ac3dfileformat.html

Some noted points that are important for consideration:
 - AC3D appears to use Left Handed axes, but with Y oriented "Up". Blender uses Right Handed axes, the export does provide a rotation matrix applied to the world object that corrects this, so "Up" in the blender becomes "Up" in the .AC file - it's configurable, so you can change how it rotates...
 - AC3D supports only one texture per surface. This is a UV texture map, so only blenders texmap is exported
 - Blender's Materials can have multiple textures per material - so a material + texure in AC3D requires a distinct and unique material in blender. The export uses a comparison of material properties to see if a material is the same as another one and then uses that material index for the .ac file.

TODO: Option to only export what's currently in the scene
TODO: Option to define "DefaultWhite" material
TODO: Add ability to only export selected items
TODO: Optionally over-write existing textures
'''


import os
import shutil
import struct

import bpy
import mathutils
from math import radians
from bpy import *

DEBUG = True

def TRACE(message):
	if DEBUG:
		print(message)

class AcMat:
	'''
	Container class that defines the material properties of the .ac MATERIAL
	'''
	def __init__(self, export_config):
		self.name = 'DefaultWhite'	# string
		self.rgb = [1.0, 1.0, 1.0]			# [R,G,B]
		self.amb = [0.2, 0.2, 0.2]			# [R,G,B]
		self.emis = [0.0, 0.0, 0.0]			# [R,G,B]
		self.spec = [0.5, 0.5, 0.5]			# [R,G,B]
		self.shi = 10				# integer
		self.trans = 0				# float

		self.export_config = export_config

	def from_blender_mat(self, bl_mat):
		'''
		convert a blender material into a .ac format material
		'''
		self.name = bl_mat.name
		self.rgb = bl_mat.diffuse_color
		self.amb = [bl_mat.ambient, bl_mat.ambient, bl_mat.ambient]
		self.emis = [bl_mat.emit, bl_mat.emit, bl_mat.emit]
		self.spec = bl_mat.specular_color
		self.shi = int(bl_mat.specular_intensity * 100.0)
		self.trans = 1.0 - bl_mat.alpha

	def write_ac_material(self, ac_file):
		# MATERIAL %s rgb %f %f %f  amb %f %f %f  emis %f %f %f  spec %f %f %f  shi %d  trans %f

		ac_file.write('MATERIAL "{0}" rgb {1:.4f} {2:.4f} {3:.4f}  amb {4:.4f} {5:.4f} {6:.4f}  emis {7:.4f} {8:.4f} {9:.4f}  spec {10:.4f} {11:.4f} {12:.4f}  shi {13} trans {14:.4f}\n'.format(
							self.name,
							self.rgb[0], self.rgb[1], self.rgb[2],
							self.amb[0], self.amb[1], self.amb[2],
							self.emis[0], self.emis[1], self.emis[2],
							self.spec[0], self.spec[1], self.spec[2],
							self.shi,
							self.trans,
							))

	def same_as(self, _AcMat):
		bRet = False
		if self.rgb[0] == _AcMat.rgb[0] and \
			self.rgb[1] == _AcMat.rgb[1] and \
			self.rgb[2] == _AcMat.rgb[2] and \
			self.amb[0] == _AcMat.amb[0] and \
			self.amb[1] == _AcMat.amb[1] and \
			self.amb[2] == _AcMat.amb[2] and \
			self.emis[0] == _AcMat.emis[0] and \
			self.emis[1] == _AcMat.emis[1] and \
			self.emis[2] == _AcMat.emis[2] and \
			self.spec[0] == _AcMat.spec[0] and \
			self.spec[1] == _AcMat.spec[1] and \
			self.spec[2] == _AcMat.spec[2] and \
			self.shi == _AcMat.shi and \
			self.trans == _AcMat.trans:
			bRet = True
		return bRet

	def save_blender_texture(self, bl_mat):
		'''
		save first blender texture that has an impact on diffuse color
		'''
		pass

class AcSurf:
	class AcSurfFlags:
		def __init__(
				self,
				surf_type,
				is_smooth,
				is_twosided,
				):
			self.surf_type = surf_type
			self.smooth_shaded = is_smooth
			self.twosided = is_twosided

		def get_flags(self):
			n = self.surf_type & 0x0f
			if self.smooth_shaded:
				n = n | 0x10
			if self.twosided:
				n = n | 0x20
			return n

	def __init__(
			self,
			export_config,
			bl_face,
			bl_mats,
			is_two_sided,
			uv_tex_face,
			ac_obj,
			):
		self.export_config = export_config
		self.mat = 0		# material index for this surface
		self.refs = []		# list of vertex references from the parent mesh
		self.uv_refs = []	# list of UV referense for texture mapping
		self.bl_mats = bl_mats	# Sometimes a face/surface has no material to it .. so the material index is null...
		self.uv_face = uv_tex_face
		self.is_two_sided = is_two_sided
		self.ac_surf_flags = self.AcSurfFlags(0, False, True)

		self.parse_blender_face(bl_face, ac_obj)

	def write_ac_surface(self, ac_file):
		surf_flags = self.ac_surf_flags.get_flags()
		ac_file.write('SURF {0:#X}\n'.format(surf_flags))
		ac_file.write('mat {0}\n'.format(self.mat))
		ac_file.write('refs {0}\n'.format(len(self.refs)))
		for n in range(len(self.refs)):
			surf_ref = self.refs[n]
			uv_ref = self.uv_refs[n]
			ac_file.write('{0} {1:.6f} {2:.6f}\n'.format(surf_ref, uv_ref[0], uv_ref[1]))

	def parse_blender_face(self, bl_face, ac_obj):
		# Create basic vertex reference list
		self.refs.append(bl_face.vertices_raw[0])
		self.refs.append(bl_face.vertices_raw[1])
		self.refs.append(bl_face.vertices_raw[2])

		if self.uv_face:
			self.uv_refs.append(self.uv_face.uv1)
			self.uv_refs.append(self.uv_face.uv2)
			self.uv_refs.append(self.uv_face.uv3)
		else:			
			self.uv_refs.append([0,0])
			self.uv_refs.append([0,0])
			self.uv_refs.append([0,0])
		# working on the basis that vertices are listed in ascending order - if the last vertex is less than the previous, it's a null vertex (so three sided poly)
		if bl_face.vertices_raw[3] != 0:
			self.refs.append(bl_face.vertices_raw[3])
			if self.uv_face:
				self.uv_refs.append(self.uv_face.uv4)
			else:
				self.uv_refs.append([0,0])

		# TRACE('Material index {0}'.format(bl_face.material_index))
		if len(self.bl_mats) > 0:
			self.mat = ac_obj.ac_mats[bl_face.material_index]
	
		self.ac_surf_flags.smooth_shaded = bl_face.use_smooth
		self.ac_surf_flags.twosided = self.is_two_sided
		
class AcObj:
	def __init__(
			self,
			export_config,
			bl_obj,
			):
		self.ac_mats = {}
		self.name = ''
		self.export_config = export_config
		self.bl_obj = bl_obj
		self.bl_export_flag = False
		self.type = 'world'			# Type of object
		self.name = ''				# name of the object
		self.data = ''				# custom data (mesh name)
		self.tex_name = ''			# texture name (filename of texture)
		self.texrep = [1,1]			# texture repeat
		if bl_obj:
			self.location = export_config.global_matrix * bl_obj.location
			rotation = bl_obj.rotation_euler.to_matrix()
			#TRACE("Object: {0}".format(rotation))
			
			self.rotation = rotation
		else:
			self.location = None		# translation location of the center relative to the parent object
			self.rotation = None		# 3x3 rotational matrix for vertices
		self.url = ''				# url of the object (??!)
		self.crease = 30			# crease angle for smoothing
		self.vert_list = []			# list of Vector(X,Y,Z) objects
		self.surf_list = []			# list of attached surfaces
		self.face_list = []			# flattened surface list
		self.edge_list = []			# spare edge list (handles poly lines etc)
		self.children = []			# child objects
	
		self.export_conf = export_config

	def write_ac_output(self, ac_file):
		ac_file.write('OBJECT {0}\n'.format(self.type))
		if len(self.name) > 0:
			ac_file.write('name "{0}"\n'.format(self.name))

		if len(self.data) > 0:
			ac_file.write('data {0}\n'.format(len(self.data)))
			ac_file.write('{0}\n'.format(self.data))

		if len(self.tex_name) > 0:
			ac_file.write('texture "{0}"\n'.format(self.tex_name))
			ac_file.write('texrep {0} {1}\n'.format(self.texrep[0], self.texrep[1]))

		if self.location:
			ac_file.write('loc {0} {1} {2}\n'.format(self.location[0],self.location[1],self.location[2]))

		if self.rotation:
			rot = self.rotation
			ac_file.write('rot {0} {1} {2}  {3} {4} {5}  {6} {7} {8}\n'.format(rot[0][0],rot[0][1],rot[0][2],rot[1][0],rot[1][1],rot[1][2],rot[2][0],rot[2][1],rot[2][2]))

		if len(self.vert_list) > 0:
			ac_file.write('numvert {0}\n'.format(len(self.vert_list)))
			for vert in self.vert_list:
				ac_file.write('{0:.8f} {1:.8f} {2:.8f}\n'.format(vert[0],vert[1],vert[2]))

		if len(self.surf_list) > 0:
			ac_file.write('numsurf {0}\n'.format(len(self.surf_list)))
			for ac_surf in self.surf_list:
				ac_surf.write_ac_surface(ac_file)

		ac_file.write('kids {0}\n'.format(len(self.children)))
		for kid in self.children:
			kid.write_ac_output(ac_file)

	def parse_blender_object(self, ac_mats, str_pre):
		sSubType = ''
		if self.bl_obj != None:		
			self.name = self.bl_obj.name
			if self.bl_obj.type == 'LAMP':
				self.type = 'lamp'
				self.bl_export_flag = self.export_config.export_lamps
			elif self.bl_obj.type in ['MESH', 'LATTICE', 'CURVE', 'SURFACE']:
				self.type = 'poly'
				self.bl_export_flag = True
				if self.bl_obj.type == 'CURVE':
					sSubType = 'Polyline'
				elif self.bl_obj.type == 'SURFACE':
					sSubType = 'closedPolyline'
			elif self.bl_obj.type == 'EMPTY':
				self.type = 'group'
				self.bl_export_flag = True

			# Add any children

			if self.bl_export_flag:
				if self.type == 'poly':
					self.parse_blender_mesh(ac_mats, str_pre)

				if self.type == 'group':
					self.parse_sub_objects(ac_mats, str_pre)

				if self.type == 'lamp':
					self.parse_lamp()

	def parse_lamp(self):
		# Create Lamp information - I don't think AC3D does lamps...
		self.bl_export_flag = False

	def parse_sub_objects(self, ac_mats, str_pre):
		# Read the child objects and those who's parents are this object, we make child objects
		if self.export_conf.use_selection:
			bl_obj_list = [_obj for _obj in bpy.data.objects if _obj.parent == self.bl_obj and _obj.select == True]
		else:
			bl_obj_list = [_obj for _obj in bpy.data.objects if _obj.parent == self.bl_obj]
		
		bpy.data.scenes
# TODO: Option to only export from active layer
		TRACE("{0}+-{1}".format(str_pre, self.name))
		str_pre = str_pre + " "

		for bl_obj in bl_obj_list:
			ac_obj = AcObj(self.export_conf, bl_obj)
			ac_obj.parse_blender_object(ac_mats, str_pre)
			if ac_obj.bl_export_flag:
				self.children.append(ac_obj)
		
		del bl_obj_list

	def parse_blender_mesh(self, ac_mats, str_pre):
		# Export materials out first
		self.data = self.bl_obj.data.name
		TRACE("{0}+-{1} ({2})".format(str_pre, self.name, self.data))
		self.parse_blender_materials(self.bl_obj.material_slots, ac_mats)
		self.parse_vertices()
		self.parse_faces(self.bl_obj.data.show_double_sided)

	def parse_faces(self, bl_two_sided):

		uv_tex = None

		if len(self.bl_obj.data.uv_textures):
			uv_tex = self.bl_obj.data.uv_textures[0]

		for face_idx in range(len(self.bl_obj.data.faces)):
			bl_face = self.bl_obj.data.faces[face_idx]
			tex_face = None
			if uv_tex:
				tex_face = uv_tex.data[face_idx]

			ac_surf = AcSurf(self.export_conf, bl_face, self.bl_obj.data.materials, bl_two_sided, tex_face, self)
			self.surf_list.append(ac_surf)
		
	def parse_vertices(self):
		for vtex in self.bl_obj.data.vertices:
			self.vert_list.append((self.export_conf.global_matrix * vtex.co))
		
	def parse_blender_materials(self, material_slots, ac_mats):
		mat_index = 0
		for bl_mat_sl in material_slots:
			ac_mat = AcMat(self.export_conf)
			bl_mat = bl_mat_sl.material
			ac_mat.from_blender_mat(bl_mat)

			bUniqueMaterial = True
			for mat in ac_mats:
				if mat.same_as(ac_mat):
					ac_mat = mat
					bUniqueMaterial = False
					continue

			if bUniqueMaterial:
				ac_mats.append(ac_mat)

			# Check to see if there's a texture...
			if self.tex_name=='':
				# export it
				
				for tex_slot in bl_mat.texture_slots:
					if tex_slot and tex_slot.texture_coords == 'UV':
						bl_tex = tex_slot.texture
						bl_im = bl_tex.image
						tex_path = os.path.split(bl_im.filepath)
						tex_name=tex_path[1]
						export_tex = os.path.join(self.export_conf.exportdir, tex_name)
						# TRACE('Exporting texture "{0}" to "{1}"'.format(bl_im.filepath, export_tex))
# TODO: Optionally over-write existing textures
						if not os.path.exists(export_tex):
							if bl_im.packed_file:
								bl_im.file_format = 'PNG'
								bl_im.filepath = export_tex
								bl_im.unpack('WRITE_LOCAL')
							else:
								shutil.copy(bl_im.filepath, export_tex)
						# else:
							# TRACE('File already exists "{0}"- not overwriting!'.format(tex_name))
						
						self.tex_name = tex_name

			# Blender to AC3d index cross-reference
			# TRACE('Created Material {0} at index {1}'.format(ac_mats.index(ac_mat), mat_index))
			self.ac_mats[mat_index] = ac_mats.index(ac_mat)
			mat_index = mat_index + 1
	
	
class ExportConf:
	def __init__(
			self,
			operator,
			context,
			filepath,
			global_matrix,
			use_selection,
			use_render_layers,
			skip_data,
			global_coords,
			mircol_as_emis,
			mircol_as_amb,
			export_lamps,
			):
		# Stuff that needs to be available to the working classes (ha!)
		self.operator = operator
		self.context = context
		self.global_matrix = global_matrix
		self.use_selection = use_selection
		self.use_render_layers = use_render_layers
		self.skip_data = skip_data
		self.global_coords = global_coords
		self.mircol_as_emis = mircol_as_emis
		self.mircol_as_amb = mircol_as_amb
		self.export_lamps = export_lamps

		# used to determine relative file paths
		self.exportdir = os.path.dirname(filepath)
		self.ac_name = os.path.split(filepath)[1]
		TRACE('Exporting to {0}'.format(self.ac_name))

class ExportAC3D:
	def __init__(
			self,
			operator,
			context,
			filepath='',
			global_matrix=None,
			use_selection=False,
			use_render_layers=True,
			skip_data=False,
			global_coords=False,
			mircol_as_emis=True,
			mircol_as_amb=False,
			export_lamps=False,
			):

			self.export_conf = ExportConf(
										operator,
										context,
										filepath,
										global_matrix,
										use_selection,
										use_render_layers,
										skip_data,
										global_coords,
										mircol_as_emis,
										mircol_as_amb,
										export_lamps,
										)

			#TRACE("Global: {0}".format(global_matrix))

			self.ac_mats = []
			self.ac_world = None

			self.ac_world = AcObj(self.export_conf, None)

			self.ac_world.parse_sub_objects(self.ac_mats, "")

			# dump the contents of the lists to file
			ac_file = open(filepath, 'w')
			ac_file.write('AC3Db\n')
			for ac_mat in self.ac_mats:
				ac_mat.write_ac_material(ac_file)

			self.ac_world.write_ac_output(ac_file)

			ac_file.close()
