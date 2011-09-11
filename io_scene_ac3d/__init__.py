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

# <pep8 compliant>

# Most of this has been copied from the __init__.py file for the io_scene__xx
# folders of the standard 2.5.9 blender package and customised to
# act as a wrapper for the conventional AC3D importer/exporter

bl_info = {
	"name": "AC3D (.ac) format",
	"description": "AC3D model importer for blender.",
	"author": "Willian P. Germano, Chris Marr",
	"version": (1,0),
	"blender" : (2,5,7),
	"api": 36079,
	"location": "File > Import-Export",
	"warning": "",
	"wiki_url": "http://wiki.blender.org/index.php/Extensions:2.5/Py/Scripts/ImportAC3D",
	"tracker_url": "",
	"category": "Import-Export"
}

# To support reload properly, try to access a package var, if it's there,
# reload everything
if "bpy" in locals():
	import imp
	if 'import_ac3d' in locals():
		imp.reload(import_ac3d)
#	if 'export_ac3d' in locals():
#		imp.reload(export_ac3d)

import time
import datetime
import bpy
import mathutils
from math import radians
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper, axis_conversion


class ImportAC3D(bpy.types.Operator, ImportHelper):
	'''Import from AC3D file format (.ac)'''
	bl_idname = 'import_mesh.import_ac3d'
	bl_label = 'Import AC3D'

	filename_ext = '.ac'
	filter_glob = StringProperty(default='*.ac', options={'HIDDEN'})

	use_image_search = BoolProperty(
							name='Image Search',
							description='Search subdirectories for any associated images',
							default=True)

	axis_forward = EnumProperty(
							name="Forward",
							items=(('X', "X Forward", ""),
								('Y', "Y Forward", ""),
								('Z', "Z Forward", ""),
								('-X', "-X Forward", ""),
								('-Y', "-Y Forward", ""),
								('-Z', "-Z Forward", ""),
							),
							default='Y',
						)

	axis_up = EnumProperty(
							name="Up",
							items=(('X', "X Up", ""),
								('Y', "Y Up", ""),
								('Z', "Z Up", ""),
								('-X', "-X Up", ""),
								('-Y', "-Y Up", ""),
								('-Z', "-Z Up", ""),
							),
							default='Z',
						)

	use_auto_smooth = BoolProperty(
							name="Auto Smooth",
							description="treats all set-smoothed faces with angles less than the specified angle as 'smooth' during render",
							default=False
						)

	auto_smooth_angle = FloatProperty(
							name="Auto Smooth Angle",
							description="Defines maximum angle between face normals that 'Auto Smooth' will operate on",
							subtype="ANGLE",
							min=radians(1),
							max=radians(80),
							default=80,
						)
	use_transparency = BoolProperty(
							name="Use Transparency",
							description="Enable transparency for rendering if material alpha < 1.0",
							default=True,
						)

	transparency_method = EnumProperty(
							name="Transparency Method",
							items=(('MASK', "Mask", ""),
								('Z_TRANSPARENCY', "Z_Transp", ""),
								('RAYTRACE', "RayTrace", ""),
							),
							default='Z_TRANSPARENCY',
						)

	transparency_shadows = BoolProperty(
							name="Transparency Shadows",
							description="Allow shadows to pass through transparency",
							default=False,
						)

	display_transparency = BoolProperty(
							name="Display Transparency",
							description="Display transparency in materials with alpha < 1.0",
							default=True,
						)


	def execute(self, context):
		from . import import_ac3d
		keywords = self.as_keywords(ignore=("axis_forward",
											"axis_up",
											"filter_glob",
											))

		global_matrix = axis_conversion(from_forward=self.axis_forward,
										from_up=self.axis_up,
										).to_4x4()

		keywords["global_matrix"] = global_matrix

		print('Importing file', self.filepath)
		t = time.mktime(datetime.datetime.now().timetuple())
		import_ac3d.read(self, context, **keywords)
		t = time.mktime(datetime.datetime.now().timetuple()) - t
		print('Finished importing in', t, 'seconds')
		return {'FINISHED'}

#class ExportAC3D(bpy.types.Operator, ExportHelper):
#	'''Export to AC3D file format (.ac)'''
#	bl_idname = 'export_mesh.AC3D'
#	bl_label = 'Export AC3D'
#
#	filename_ext = '.ac'
#
#	filter_glob = StringProperty(
#			default='*.ac',
#			options={'HIDDEN'}
#			)
#
#	use_selection = BoolProperty(
#			name="Selection Only",
#			description="Export selected objects only",
#			default=False,
#			)
#
#	def execute(self, context):
#		from . import export_ac3d
#		print('Exporting file', self.filepath)
#		return export_ac3d.save(self, context, **keywords)


def menu_func_import(self, context):
	self.layout.operator(ImportAC3D.bl_idname, text='AC3D (.ac)')


#def menu_func_export(self, context):
#	self.layout.operator(ExportAC3D.bl_idname, text='AC3D (.ac)')


def register():
	bpy.utils.register_module(__name__)
	bpy.types.INFO_MT_file_import.append(menu_func_import)
#	bpy.types.INFO_MT_file_export.append(menu_func_export)

def unregister():
	bpy.utils.unregister_module(__name__)
	bpy.types.INFO_MT_file_import.remove(menu_func_import)
#	bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
	register()
