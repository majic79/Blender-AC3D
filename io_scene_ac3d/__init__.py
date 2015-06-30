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
# folders of the standard 2.59 blender package and customised to
# act as a wrapper for the conventional AC3D importer/exporter

import time
import datetime
import bpy
import mathutils
from math import radians
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper, axis_conversion

bl_info = {
	"name": "AC3D (.ac) format",
	"description": "AC3D model exporter for blender.",
	"author": "Chris Marr",
	"version": (2,0),
	"blender" : (2,6,0),
	"api": 41098,
	"location": "File > Import-Export",
	"warning": "",
	"wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/Blender-AC3D",
	"tracker_url": "http://projects.blender.org/tracker/index.php?func=detail&aid=29007&group_id=153&atid=468",
	"category": "Import-Export"
}

# To support reload properly, try to access a package var, if it's there,
# reload everything
if "bpy" in locals():
	import imp
	if 'import_ac3d' in locals():
		imp.reload(import_ac3d)
	if 'export_ac3d' in locals():
		imp.reload(export_ac3d)

def menu_func_import(self, context):
	self.layout.operator(ImportAC3D.bl_idname, text='AC3D (.ac)')


def menu_func_export(self, context):
	self.layout.operator(ExportAC3D.bl_idname, text='AC3D (.ac)')


def register():
	bpy.utils.register_module(__name__)
	bpy.types.INFO_MT_file_import.append(menu_func_import)
	bpy.types.INFO_MT_file_export.append(menu_func_export)

def unregister():
	bpy.utils.unregister_module(__name__)
	bpy.types.INFO_MT_file_import.remove(menu_func_import)
	bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
	register()

class ImportAC3D(bpy.types.Operator, ImportHelper):
	'''Import from AC3D file format (.ac)'''
	bl_idname = 'import_scene.import_ac3d'
	bl_label = 'Import AC3D'
	bl_options = {'PRESET'}	

	filename_ext = '.ac'
	filter_glob = StringProperty(default='*.ac', options={'HIDDEN'})

	axis_forward = EnumProperty(
							name="Forward",
							items=(('X', "X Forward", ""),
								('Y', "Y Forward", ""),
								('Z', "Z Forward", ""),
								('-X', "-X Forward", ""),
								('-Y', "-Y Forward", ""),
								('-Z', "-Z Forward", ""),
							),
							default='-Z',
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
							default='Y',
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

	use_auto_smooth = BoolProperty(
							name="Auto Smooth",
							description="Use object auto smooth if normal angles are beneath Crease angle",
							default=True,
						)
	use_emis_as_mircol = BoolProperty(
							name="Use Emis as Mirror colour",
							description="Use Emission colour as Mirror colour",
							default=True,
						)

	use_amb_as_mircol = BoolProperty(
							name="Use Amb as Mirror colour",
							description="Use Ambient colour as Mirror colour",
							default=False,
						)
	display_transparency = BoolProperty(
							name="Display Transparency",
							description="Display transparency in main display",
							default=True,
						)
	display_textured_solid = BoolProperty(
							name="Display textured solid",
							description="Show main window with textures applied (transparency works in only in normal direction)",
							default=False,
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

		t = time.mktime(datetime.datetime.now().timetuple())
		import_ac3d.ImportAC3D(self, context, **keywords)
		t = time.mktime(datetime.datetime.now().timetuple()) - t
		print('Finished importing in', t, 'seconds')

		return {'FINISHED'}

class ExportAC3D(bpy.types.Operator, ExportHelper):
	'''Export to AC3D file format (.ac)'''
	bl_idname = 'export_scene.export_ac3d'
	bl_label = 'Export AC3D'
	bl_options = {'PRESET'}

	filename_ext = '.ac'

	filter_glob = StringProperty(
							default='*.ac',
							options={'HIDDEN'}
							)

	axis_forward = EnumProperty(
								name="Forward",
								items=(('X', "X Forward", ""),
									('Y', "Y Forward", ""),
									('Z', "Z Forward", ""),
									('-X', "-X Forward", ""),
									('-Y', "-Y Forward", ""),
									('-Z', "-Z Forward", ""),
									),
								default='-Z',
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
							default='Y',
							)
	use_render_layers = BoolProperty(
							name="Only Render Layers",
							description="Only export from selected render layers",
							default=True,
							)
	use_selection = BoolProperty(
							name="Selection Only",
							description="Export selected objects only",
							default=False,
							)
#	skip_data = BoolProperty(
#							name="Skip Data",
#							description="don't export mesh names as data fields",
#							default=False,
#							)
#	global_coords = BoolProperty(
#							name="Global Co-ordinates",
#							description="Transform all vertices of all meshes to global coordinates",
#							default=False,
#							)
	mircol_as_emis = BoolProperty(
							name="Mirror col as Emis",
							description="export mirror colour as emissive colour",
							default=True,
							)
	mircol_as_amb = BoolProperty(
							name="Mirror col as Amb",
							description="export mirror colour as ambient colour",
							default=False,
							)
	crease_angle = FloatProperty(
							name="Default Crease Angle",
							description="Default crease angle for exported .ac faces",
							default=radians(35.0),
							options={"ANIMATABLE"},
							unit="ROTATION",
							subtype="ANGLE",
							)
# This behaviour from the original exporter - not applicable?
#	no_split = BoolProperty(
#							name="No Split",
#							description="don't split meshes with multiple textures (or both textured and non-textured polygons)",
#							default=True,
#							)
	def execute(self, context):
		from . import export_ac3d
		keywords = self.as_keywords(ignore=("axis_forward",
											"axis_up",
											"filter_glob",
											"check_existing",
											))

		global_matrix = axis_conversion(to_forward=self.axis_forward,
										to_up=self.axis_up,
										).to_4x4()

		keywords["global_matrix"] = global_matrix
		t = time.mktime(datetime.datetime.now().timetuple())
		export_ac3d.ExportAC3D(self, context, **keywords)
		t = time.mktime(datetime.datetime.now().timetuple()) - t
		print('Finished exporting in', t, 'seconds')

		return {'FINISHED'}

