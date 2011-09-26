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
		self.name = "DefaultWhite"	# string
		self.rgb = [1,1,1]			# [R,G,B]
		self.amb = [0,0,0]			# [R,G,B]
		self.emis = [0,0,0]			# [R,G,B]
		self.spec = [0,0,0]			# [R,G,B]
		self.shi = 0				# integer
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

		ac_file.write('MATERIAL "{0}" rgb {1} {2} {3}  amb {4} {5} {6}  emis {7} {8} {9}  spec {10} {11} {12}  shi {13} trans {14}\n'.format(
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

class AcObj:
	def __init__(
			self,
			export_config,
			bl_obj,
			):
		self.ac_mats = []
		self.name = bl_obj.name
		self.export_config = export_config


class ExportConf:
	def __init__(
			self,
			operator,
			context,
			filepath,
			global_matrix,
			use_selection,
			skip_data,
			global_coords,
			mircol_as_emis,
			mircol_as_amb,
			no_split,
			):
		# Stuff that needs to be available to the working classes (ha!)
		self.operator = operator
		self.context = context
		self.global_matrix = global_matrix
		self.use_selection = use_selection
		self.skip_data = skip_data
		self.global_coords = global_coords
		self.mircol_as_emis = mircol_as_emis
		self.mircol_as_amb = mircol_as_amb

		# used to determine relative file paths
		self.importdir = os.path.dirname(filepath)
		self.ac_name = os.path.split(filepath)[1]
		TRACE("Exporting to {0}".format(self.ac_name))

class ExportAC3D:
	def __init__(
			self,
			operator,
			context,
			filepath="",
			global_matrix=None,
			use_selection=False,
			skip_data=False,
			global_coords=False,
			mircol_as_emis=True,
			mircol_as_amb=False,
			no_split=True,
			):

			self.export_conf = ExportConf(
										operator,
										context,
										filepath,
										global_matrix,
										use_selection,
										skip_data,
										global_coords,
										mircol_as_emis,
										mircol_as_amb,
										no_split,
										)

			self.ac_mats = []
			self.ac_objects = []

			# traverse the material and object trees to compile the initial list
			for bl_obj in self.export_conf.context.scene.objects:
				ac_obj = AcObj(self.export_conf, bl_obj)
				for bl_mat in bl_obj.material_slots:
					ac_mat = AcMat(self.export_conf)
					ac_mat.from_blender_mat(bl_mat.material)

					bUniqueMaterial = True
					for mat in self.ac_mats:
						if mat.same_as(ac_mat):
							ac_mat = mat
							bUniqueMaterial = False
							continue

					if bUniqueMaterial:
						self.ac_mats.append(ac_mat)
					if not ac_mat in ac_obj.ac_mats:
						ac_obj.ac_mats.append(ac_mat)

			# dump the contents of the lists to file
			ac_file = open(filepath, 'w')
			ac_file.write("AC3Db\n")
			for ac_mat in self.ac_mats:
				ac_mat.write_ac_material(ac_file)

			ac_file.close()
