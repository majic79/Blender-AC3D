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

__author__ = "Willian P. Germano"
__version__ = "2.48.1 2009-01-11"
__bpydoc__ = """\
This script imports AC3D models into Blender.

AC3D is a simple and affordable commercial 3d modeller also built with OpenGL.
The .ac file format is an easy to parse text format well supported,
for example, by the PLib 3d gaming library.

Supported:<br>
    UV-textured meshes with hierarchy (grouping) information.

Missing:<br>
    The url tag is irrelevant for Blender.

Known issues:<br>
    - Some objects may be imported with wrong normals due to wrong information in the model itself. This can be noticed by strange shading, like darker than expected parts in the model. To fix this, select the mesh with wrong normals, enter edit mode and tell Blender to recalculate the normals, either to make them point outside (the usual case) or inside.<br>
 
Config Options:<br>
    - display transp (toggle): if "on", objects that have materials with alpha < 1.0 are shown with translucency (transparency) in the 3D View.<br>
    - subdiv (toggle): if "on", ac3d objects meant to be subdivided receive a SUBSURF modifier in Blender.<br>
    - emis as mircol: store the emissive rgb color from AC3D as mirror color in Blender -- this is a hack to preserve the values and be able to export them using the equivalent option in the exporter.<br>
    - textures dir (string): if non blank, when imported texture paths are
wrong in the .ac file, Blender will also look for them at this dir.

Notes:<br>
   - When looking for assigned textures, Blender tries in order: the actual
paths from the .ac file, the .ac file's dir and the default textures dir path
users can configure (see config options above).
"""

# $Id: ac3d_import.py 18451 2009-01-11 16:17:41Z ianwill $
#
# --------------------------------------------------------------------------
# AC3DImport version 2.43.1 Feb 21, 2007
# Program versions: Blender 2.43 and AC3Db files (means version 0xb)
# changed: better triangulation of ngons, more fixes to support bad .ac files,
# option to display transp mats in 3d view, support "subdiv" tag (via SUBSURF modifier)
# --------------------------------------------------------------------------
# Thanks: Melchior Franz for extensive bug testing and reporting, making this
# version cope much better with old or bad .ac files, among other improvements;
# Stewart Andreason for reporting a serious crash; Francesco Brisa for the
# emis as mircol functionality (w/ patch).
# --------------------------------------------------------------------------
# ***** BEGIN GPL LICENSE BLOCK *****
#
# Copyright (C) 2004-2009: Willian P. Germano, wgermano _at_ ig.com.br
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****
# --------------------------------------------------------------------------

import os
import struct

import bpy
import mathutils
from math import radians
from bpy import *
from bpy_extras.image_utils import load_image

#from Blender import Scene, Object, Mesh, Lamp, Registry, sys as bsys, Window, Image, Material, Modifier
#from Blender.sys import dirsep
#from Blender.Mathutils import Vector, Matrix, Euler
#from Blender.Geometry import PolyFill

# Default folder for AC3D textures, to override wrong paths, change to your
# liking or leave as "":
TEXTURES_DIR = ""

DISPLAY_TRANSP = True

SUBDIV = True

EMIS_AS_MIRCOL = False
# Matrix to align ac3d's coordinate system with Blender's one,
# it's a -90 degrees rotation around the x axis:
#AC_TO_BLEND_MATRIX = Matrix([1, 0, 0], [0, 0, 1], [0, -1, 0])
#AC_TO_BLEND_MATRIX = [[1, 0, 0], [0, 0, 1], [0, -1, 0]]
#I think we can do this with an axis rotation... but I don't know how to yet...


#tooltips = {
#	'DISPLAY_TRANSP': 'Turn transparency on in the 3d View for objects using materials with alpha < 1.0.',
#	'SUBDIV': 'Apply a SUBSURF modifier to objects meant to appear subdivided.',
#	'TEXTURES_DIR': 'Additional folder to look for missing textures.',
#	'EMIS_AS_MIRCOL': 'Store emis color as mirror color in Blender.'	
#}

#def update_registry():
#	global TEXTURES_DIR, DISPLAY_TRANSP, EMIS_AS_MIRCOL
#	rd = dict([('tooltips', tooltips), ('TEXTURES_DIR', TEXTURES_DIR), ('DISPLAY_TRANSP', DISPLAY_TRANSP), ('SUBDIV', SUBDIV), ('EMIS_AS_MIRCOL', EMIS_AS_MIRCOL)])
#	Registry.SetKey('ac3d_import', rd, True)
#
#rd = Registry.GetKey('ac3d_import', True)
#
#if rd:
#	if 'GROUP' in rd:
#		update_registry()
#	try:
#		TEXTURES_DIR = rd['TEXTURES_DIR']
#		DISPLAY_TRANSP = rd['DISPLAY_TRANSP']
#		SUBDIV = rd['SUBDIV']
#		EMIS_AS_MIRCOL = rd['EMIS_AS_MIRCOL']
#	except:
#		update_registry()
#else: update_registry()
#
#if TEXTURES_DIR:
#	oldtexdir = TEXTURES_DIR
#	if dirsep == '/': TEXTURES_DIR = TEXTURES_DIR.replace('\\', '/')
#	if TEXTURES_DIR[-1] != dirsep: TEXTURES_DIR = "%s%s" % (TEXTURES_DIR, dirsep)
#	if oldtexdir != TEXTURES_DIR: update_registry()
#

VERBOSE = True
#rd = Registry.GetKey('General', True)
#if rd:
#	if rd.has_key('verbose'):
#		VERBOSE = rd['verbose']

	
errmsg = ""

AC_WORLD = 0
AC_GROUP = 1
AC_POLY = 2
AC_LIGHT = 3
AC_OB_TYPES = {
	'world': AC_WORLD,
	'group': AC_GROUP,
	'poly':  AC_POLY,
	'light':  AC_LIGHT
	}

AC_OB_BAD_TYPES_LIST = [] # to hold references to unknown (wrong) ob types

def inform(msg):
	global VERBOSE
	if VERBOSE: print(msg)

def euler_in_radians(eul):
#	"Used while there's a bug in the BPY API"
	eul.x = radians(eul.x)
	eul.y = radians(eul.y)
	eul.z = radians(eul.z)
	return eul

class Obj:
	
	def __init__(self, type):
		self.type = type
		self.dad = None
		self.name = ''
		self.data = ''
		self.tex = ''
		self.texrep = [1,1]
		self.texoff = None
		self.loc = []
		self.rot = []
		self.size = []
		self.crease = 30
		self.subdiv = 0
		self.vlist = []
		self.flist_cfg = []
		self.flist_v = []
		self.flist_uv = []
		self.elist = []
		self.matlist = []
		self.kids = 0

		self.bl_obj = None # the actual Blender object created from this data

class AC3DImport:

	def __init__(
			self,
			context,
			filepath="",
			use_image_search=False,
			global_matrix=None,
			use_auto_smooth=False,	
			auto_smooth_angle=radians(80),
			show_double_sided=True,
			use_transparency=True,
			transparency_method='Z_TRANSPARENCY',
			transparency_shadows=False,
			display_transparency=True,
			):

		global errmsg

		self.scene = context.scene
		self.global_matrix = global_matrix
		self.use_image_search = use_image_search
		self.use_auto_smooth = use_auto_smooth
		self.auto_smooth_angle = auto_smooth_angle
		self.show_double_sided = show_double_sided
		self.use_transparency = use_transparency
		self.transparency_method = transparency_method
		self.transparency_shadows = transparency_shadows
		self.display_transparency = display_transparency
		self.i = 0
		errmsg = ''
		self.importdir = os.path.dirname(filepath)

		import_file = open(filepath, 'r')

		header = import_file.read(5)
		header, version = header[:4], header[-1]
		if header != 'AC3D':
			import_file.close()
			errmsg = 'AC3D header not found (invalid file)'
			Blender.Draw.PupMenu('ERROR: %s' % errmsg)
			inform(errmsg)
			return None
		elif version != 'b':
			inform('AC3D file version 0x%s.' % version)
			inform('This importer is for version 0xb, so it may fail.')

		self.token = {'OBJECT':		self.parse_obj,
					  'numvert':	self.parse_vert,
					  'numsurf':	self.parse_surf,
					  'name':		self.parse_name,
					  'data':		self.parse_data,
					  'kids':		self.parse_kids,
					  'loc':		self.parse_loc,
					  'rot':		self.parse_rot,
					  'MATERIAL':	self.parse_mat,
					  'texture':	self.parse_tex,
					  'texrep':		self.parse_texrep,
					  'texoff':		self.parse_texoff,
					  'subdiv':		self.parse_subdiv,
					  'crease':		self.parse_crease}

		self.objlist = []
		self.mlist = []
		self.kidsnumlist = []
		self.dad = None

		self.lines = import_file.readlines()
		self.lines.append('')
		self.parse_file()
		import_file.close()
		
		self.testAC3DImport()
				
	def parse_obj(self, value):
		kidsnumlist = self.kidsnumlist
		if kidsnumlist:
			while not kidsnumlist[-1]:
				kidsnumlist.pop()
				if kidsnumlist:
					self.dad = self.dad.dad
				else:
					inform('Ignoring unexpected data at end of file.')
					return -1 # bad file with more objects than reported
			kidsnumlist[-1] -= 1
		if value in AC_OB_TYPES:
			new = Obj(AC_OB_TYPES[value])
		else:
			if value not in AC_OB_BAD_TYPES_LIST:
				AC_OB_BAD_TYPES_LIST.append(value)
				inform('Unexpected object type keyword: "%s". Assuming it is of type: "poly".' % value)
			new = Obj(AC_OB_TYPES['poly'])
		new.dad = self.dad
		new.name = value
		self.objlist.append(new)

	def parse_name(self, value):
		name = value.split('"')[1]
		self.objlist[-1].name = name

	def parse_data(self, value):
		data = self.lines[self.i].strip()
		self.objlist[-1].data = data

	def parse_tex(self, value):
		line = self.lines[self.i - 1] # parse again to properly get paths with spaces
		texture = line.split('"')[1]
		self.objlist[-1].tex = texture

	def parse_texrep(self, trash):
		trep = self.lines[self.i - 1]
		trep = trep.split()
		trep = [float(trep[1]), float(trep[2])]
		self.objlist[-1].texrep = trep
		self.objlist[-1].texoff = [0, 0]

	def parse_texoff(self, trash):
		toff = self.lines[self.i - 1]
		toff = toff.split()
		toff = [float(toff[1]), float(toff[2])]
		self.objlist[-1].texoff = toff
		
	def parse_mat(self, value):
		i = self.i - 1
		lines = self.lines
		line = lines[i].split()
		mat_name = ''
		mat_col = mat_amb = mat_emit = mat_spec_col = mat_mir_col = [0,0,0]
		mat_alpha = 1
		mat_spec = 1.0

		while line[0] == 'MATERIAL':
			mat_name = line[1].split('"')[1]
			mat_col = list(map(float,[line[3],line[4],line[5]]))
			v = list(map(float,[line[7],line[8],line[9]]))
			mat_amb = (v[0]+v[1]+v[2]) / 3.0
			v = list(map(float,[line[11],line[12],line[13]]))
			mat_emit = (v[0]+v[1]+v[2]) / 3.0
			if EMIS_AS_MIRCOL:
				mat_emit = 0
				mat_mir_col = list(map(float,[line[11],line[12],line[13]]))

			mat_spec_col = list(map(float,[line[15],line[16],line[17]]))
			mat_spec = float(line[19]) / 64.0
			mat_alpha = float(line[-1])
			mat_alpha = 1 - mat_alpha
			self.mlist.append([mat_name, mat_col, mat_amb, mat_emit, mat_spec_col, mat_spec, mat_mir_col, mat_alpha])
			i += 1
			line = lines[i].split()

		self.i = i

	def parse_rot(self, trash):
		i = self.i - 1
		ob = self.objlist[-1]
		rot = self.lines[i].split(' ', 1)[1]
		rot = list(map(float, rot.split()))
		matrix = Matrix(rot[:3], rot[3:6], rot[6:])
		ob.rot = matrix
		size = matrix.scalePart() # vector
		ob.size = size

	def parse_loc(self, trash):
		i = self.i - 1
		loc = self.lines[i].split(' ', 1)[1]
		loc = list(map(float, loc.split()))
		self.objlist[-1].loc = mathutils.Vector(loc)

	def parse_crease(self, value):
		# AC3D: range is [0.0, 180.0]; Blender: [1, 80]
		value = float(value)
		self.objlist[-1].crease = int(value)

	def parse_subdiv(self, value):
		self.objlist[-1].subdiv = int(value)

	def parse_vert(self, value):
		i = self.i
		lines = self.lines
		obj = self.objlist[-1]
		vlist = obj.vlist
		n = int(value)

		while n:
			line = lines[i].split()
			line = list(map(float, line))
			vlist.append(line)
			n -= 1
			i += 1

		self.i = i

	def parse_surf(self, value):
		i = self.i
		is_smooth = 0
		double_sided = 0
		lines = self.lines
		obj = self.objlist[-1]
		vlist = obj.vlist
		matlist = obj.matlist
		numsurf = int(value)
		NUMSURF = numsurf

		badface_notpoly = badface_multirefs = 0

		while numsurf:
			flags = lines[i].split()[1][2:]
			if len(flags) > 1:
				flaghigh = int(flags[0])
				flaglow = int(flags[1])
			else:
				flaghigh = 0
				flaglow = int(flags[0])

			is_smooth = flaghigh & 1
			twoside = flaghigh & 2
			nextline = lines[i+1].split()
			if nextline[0] != 'mat': # the "mat" line may be missing (found in one buggy .ac file)
				matid = 0
				if not matid in matlist: matlist.append(matid)
				i += 2
			else:
				matid = int(nextline[1])
				if not matid in matlist: matlist.append(matid)
				nextline = lines[i+2].split()
				i += 3
			refs = int(nextline[1])
			face = []
			faces = []
			edges = []
			fuv = []
			fuvs = []
			rfs = refs

			while rfs:
				line = lines[i].split()
				v = int(line[0])
				uv = [float(line[1]), float(line[2])]
				face.append(v)
				fuv.append(mathutils.Vector(uv))
				rfs -= 1
				i += 1

			if flaglow: # it's a line or closed line, not a polygon
				while len(face) >= 2:
					cut = face[:2]
					edges.append(cut)
					face = face[1:]

				if flaglow == 1 and edges: # closed line
					face = [edges[-1][-1], edges[0][0]]
					edges.append(face)

			else: # polygon

				# check for bad face, that references same vertex more than once
				lenface = len(face)
				if lenface < 3:
					# less than 3 vertices, not a face
					badface_notpoly += 1
				elif sum(map(face.count, face)) != lenface:
					# multiple references to the same vertex
					badface_multirefs += 1
				else: # ok, seems fine
					# anything with more than 3 edges is triangulated
					if len(face) > 4: # ngon, triangulate it
						polyline = []
						for vi in face:
							polyline.append(mathutils.Vector(vlist[vi]))
						tris = PolyFill([polyline])
						for t in tris:
							tri = [face[t[0]], face[t[1]], face[t[2]]]
							triuvs = [fuv[t[0]], fuv[t[1]], fuv[t[2]]]
							faces.append(tri)
							fuvs.append(triuvs)
					else: # tri or quad
						faces.append(face)
						fuvs.append(fuv)

			obj.flist_cfg.extend([[matid, is_smooth, twoside]] * len(faces))
			obj.flist_v.extend(faces)
			obj.flist_uv.extend(fuvs)
			obj.elist.extend(edges) # loose edges

			numsurf -= 1	  

		if badface_notpoly or badface_multirefs:
			inform('Object "%s" - ignoring bad faces:' % obj.name)
			if badface_notpoly:
				inform('\t%d face(s) with less than 3 vertices.' % badface_notpoly)
			if badface_multirefs:
				inform('\t%d face(s) with multiple references to a same vertex.' % badface_multirefs)

		self.i = i

	def parse_file(self):
		i = 1
		lines = self.lines
		line = lines[i].split()

		while line:
			kw = ''
			for k in self.token.keys():
				if line[0] == k:
					kw = k
					break
			i += 1
			if kw:
				self.i = i
				result = self.token[kw](line[1])
				if result:
					break # bad .ac file, stop parsing
				i = self.i
			line = lines[i].split()

	def parse_kids(self, value):
		kids = int(value)
		if kids:
			self.kidsnumlist.append(kids)
			self.dad = self.objlist[-1]
		self.objlist[-1].kids = kids

	# for each group of meshes we try to find one that can be used as
	# parent of the group in Blender.
	# If not found, we can use an Empty as parent.
	def found_parent(self, groupname, olist):
		l = [o for o in olist if o.type == AC_POLY \
				and not o.kids and not o.rot and not o.loc]
		if l:
			for o in l:
				if o.name == groupname:
					return o
				#return l[0]
		return None

	def build_hierarchy(self):
# majic79: not using AC_TO_BLEND_MATRIX, instead we convert by using the axis_conversion routines within blender
#		blmatrix = AC_TO_BLEND_MATRIX

		olist = self.objlist[1:]
		olist.reverse()

		scene = self.scene

		newlist = []

		for o in olist:
			kids = o.kids
			if kids:
				children = newlist[-kids:]
				newlist = newlist[:-kids]
				if o.type == AC_GROUP:
					parent = self.found_parent(o.name, children)
					if parent:
						children.remove(parent)
						o.bl_obj = parent.bl_obj
					else: # not found, use an empty
						empty = bpy.data.objects.new(o.name,None)
						o.bl_obj = empty

				bl_children = [c.bl_obj for c in children if c.bl_obj != None]
				for c in bl_children:
					c.parent = o.bl_obj
				
				for child in children:
					blob = child.bl_obj
					if not blob: continue
					if child.rot:
						eul = child.rot.toEuler()
						blob.rotation_euler = eul
					if child.size:
						blob.size = child.size
					if not child.loc:
						child.loc = mathutils.Vector([0.0, 0.0, 0.0])
					blob.location = child.loc

			newlist.append(o)

		for o in newlist: # newlist now only has objs w/o parents
			blob = o.bl_obj
			if not blob:
				continue
			if self.global_matrix:
				blob.matrix_world = blob.matrix_world * self.global_matrix

			if o.size:
				o.bl_obj.size = o.size
			if o.rot:
				blob.rotation_euler = o.rot.toEuler()

			if not o.loc:
				o.loc = mathutils.Vector([0.0, 0.0, 0.0])
			# forces DAG update, so we do it even for 0, 0, 0
			blob.location = o.loc

# majic79: Not sure if this is still relevant - someone can test if this is still required?
#		# XXX important: until we fix the BPy API so it doesn't increase user count
#		# when wrapping a Blender object, this piece of code is needed for proper
#		# object (+ obdata) deletion in Blender:
#		for o in self.objlist:
#			if o.bl_obj:
#				o.bl_obj = None

	def testAC3DImport(self):

# majic79: Couldn't see how this is implemented in the new model - left as commented code for the moment
#		FACE_TEX = Mesh.FaceModes['TEX']

		scene = self.scene

		bl_images = {} # loaded texture images
		missing_textures = [] # textures we couldn't find

		objlist = self.objlist[1:] # skip 'world'

		bmat = []
		for mat in self.mlist:
			name = mat[0]
			m = bpy.data.materials.new(name)
			m.diffuse_color = (mat[1][0], mat[1][1], mat[1][2])
			m.ambient = mat[2]
			m.emit = mat[3]
			m.specular_color = (mat[4][0], mat[4][1], mat[4][2])
			m.specular_intensity = mat[5]
			m.mirror_color = (mat[4][0], mat[4][1], mat[4][2])
			m.alpha = mat[7]
			bmat.append(m)

		obj_idx = 0 # index of current obj in loop
		for obj in objlist:
			if obj.type == AC_GROUP:
				continue
			elif obj.type == AC_LIGHT:
				light = Lamp.New('Lamp')
				object = scene.objects.new(light, obj.name)
				#object.select(True)
				obj.bl_obj = object
				if obj.data:
					light.name = obj.data
				continue

			# type AC_POLY:

			# old .ac files used empty meshes as groups, convert to a real ac group
			if not obj.vlist and obj.kids:
				obj.type = AC_GROUP
				continue


			mesh = bpy.data.meshes.new(obj.name)
			object = bpy.data.objects.new(obj.name,mesh)
			obj.bl_obj = object
			if obj.data: mesh.name = obj.data
			# will auto clamp to [1, 80] (majic79: Will it? maybe it did in 2.4, no idea what it does in 2.5)
			mesh.auto_smooth_angle = obj.crease

			if not obj.vlist: # no vertices? nothing more to do
				continue

			mesh.from_pydata(obj.vlist, [], obj.flist_v)

			objmat_indices = []
			for mat in bmat:
				if bmat.index(mat) in obj.matlist:
					objmat_indices.append(bmat.index(mat))
					mesh.materials.append(mat)

					if mat.alpha < 1.0:
						mat.use_transparency=self.use_transparency
						mat.transparency_method=self.transparency_method
						object.show_transparent = self.display_transparency

			scene.objects.link(object)
			# shouldn't happen, of course
			facesnum = len(mesh.faces)
			if facesnum == 0: 
				continue

			# checking if the .ac file had duplicate faces (Blender ignores them)
			if facesnum != len(obj.flist_v):
				# it has, ugh. Let's clean the uv list:
				lenfl = len(obj.flist_v)
				flist = obj.flist_v
				uvlist = obj.flist_uv
				cfglist = obj.flist_cfg
				for f in flist:
					f.sort()
				fi = lenfl
				while fi > 0: # remove data related to duplicates
					fi -= 1
					if flist[fi] in flist[:fi]:
						uvlist.pop(fi)
						cfglist.pop(fi)

			img = None
			if obj.tex != '':
				if obj.tex in bl_images.keys():
					img = bl_images[obj.tex]
				elif obj.tex not in missing_textures:
					texfname = None
					objtex = obj.tex
					baseimgname = os.path.basename(objtex)
					if os.path.exists(objtex) == 1:
						texfname = objtex
					elif os.path.exists(os.path.join(self.importdir, objtex)):
						texfname = os.path.join(self.importdir, objtex)
					else:
						if baseimgname.find('\\') > 0:
							baseimgname = bpy.path.basename(objtex.replace('\\','/'))
						objtex = os.path.join(self.importdir, baseimgname)
						if os.path.exists(objtex) == 1:
							texfname = objtex
						else:
							objtex = os.path.join(TEXTURES_DIR, baseimgname)
							if os.path.exists(objtex):
								texfname = objtex
					if texfname:
						inform("Loading texture: %s" % texfname)
						try:
							img = bpy.data.images.load(texfname)
							if img:
								bl_images[obj.tex] = img
						except:
							inform("Couldn't load texture: %s" % baseimgname)
					else:
						missing_textures.append(obj.tex)
						inform("Couldn't find texture: %s" % baseimgname)

			uv_faces = []
			if img:
				uv_tex = mesh.uv_textures.new(obj.tex)
				uv_tex.active = True
				uv_faces = uv_tex.data[:]
				
#				uv_faces = mesh.uv_textures.active.data[:]

			for i in range(facesnum):
				f = obj.flist_cfg[i]
				fmat = f[0]
				is_smooth = f[1]
				twoside = f[2]
				bface = mesh.faces[i]

				bface.use_smooth = is_smooth
				mesh.show_double_sided = self.show_double_sided

				bface.material_index = objmat_indices.index(fmat)

				fuv = obj.flist_uv[i]
				if obj.texoff:
					uoff = obj.texoff[0]
					voff = obj.texoff[1]
					urep = obj.texrep[0]
					vrep = obj.texrep[1]
					for uv in fuv:
						uv[0] *= urep
						uv[1] *= vrep
						uv[0] += uoff
						uv[1] += voff

				if uv_faces and img:
					uf = uv_faces[i]
					uf.image = img
					uf.use_image = True
# majic79: Couldn't see how to implement this in the new model (yet) - left as commented code for the moment
#				if img:
#					bface.mode |= FACE_TEX
#					bface.image = img
				
# majic79: Couldn't see how to implement this in the new model (yet) - left as commented code for the moment
#				mesh.faces[i].uv = fuv
#				muv = mesh.uv_textures.new()
			
#				muv.active = True
#				muv.data.uv = fuv

			mesh.calc_normals()

			mesh.use_auto_smooth = self.use_auto_smooth
			mesh.auto_smooth_angle = self.auto_smooth_angle

			# subdiv: create SUBSURF modifier in Blender
			if SUBDIV and obj.subdiv > 0:
				subdiv = obj.subdiv
				subdiv_render = subdiv
				# just to be safe:
				if subdiv_render > 6: subdiv_render = 6
				if subdiv > 3: subdiv = 3
				modif = object.modifiers.append(Modifier.Types.SUBSURF)
				modif[Modifier.Settings.LEVELS] = subdiv
				modif[Modifier.Settings.RENDLEVELS] = subdiv_render

			obj_idx += 1

		self.build_hierarchy()
		scene.update()

# End of class AC3DImport

def read(operator,
		context,
		filepath="",
		use_image_search = True,
		global_matrix = None,
		use_auto_smooth = False,
		auto_smooth_angle = radians(80),
		show_double_sided = True,
		use_transparency = True,
		transparency_method = 'Z_TRANSPARENCY',
		transparency_shadows = False,
		display_transparency = True,
		):
    inform("\nTrying to import AC3D model(s) from:\n%s ..." % filepath)
    AC3DImport(
		context,
		filepath,
		use_image_search,	
		global_matrix,
		use_auto_smooth,
		auto_smooth_angle,
		show_double_sided,
		use_transparency,
		transparency_method,
		transparency_shadows,
		display_transparency,
		)
