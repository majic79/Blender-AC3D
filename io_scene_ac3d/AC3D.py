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

import bpy
import os
import shutil
import re
from math import radians, degrees
from mathutils import Vector, Matrix

DEBUG = False


def TRACE(message):
    if DEBUG:
        print(message)


def _clamp01(val):
    return min(1.0, max(0.0, float(val)))


def _get_surface_shader(node_tree):
    """Find the active shader node connected to the Material Output Surface."""
    if not node_tree:
        return None

    output_node = None
    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL' and getattr(node, 'is_active_output', False):
            output_node = node
            break
    if output_node is None:
        for node in node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break

    if output_node and 'Surface' in output_node.inputs and output_node.inputs['Surface'].is_linked:
        return output_node.inputs['Surface'].links[0].from_node

    # Fallback: locate a known surface shader directly
    for node in node_tree.nodes:
        if node.type in ('BSDF_PRINCIPLED', 'EEVEE_SPECULAR', 'BSDF_DIFFUSE', 'EMISSION', 'EEVEE_EMISSION'):
            return node

    return None


def _find_linked_image_node(socket, visited=None):
    """Walk upstream from a shader input socket to find the nearest Image Texture node."""
    if not socket or not socket.is_linked:
        return None
    if visited is None:
        visited = set()

    for link in socket.links:
        node = link.from_node
        if node in visited:
            continue
        visited.add(node)
        if node.type == 'TEX_IMAGE' and node.image:
            return node
        for inp in node.inputs:
            if inp.is_linked:
                found = _find_linked_image_node(inp, visited)
                if found:
                    return found
    return None


# ------------------------------------------------------------------------------
class Object:
    """Base class for an AC3D object."""

    def __init__(self, name, ob_type, bl_obj, export_config, local_transform):
        """
        Create a AC3D object from a blender object and it's children.

        @param name             The name of the object
        @param ob_type          The type of the object
                                (world, poly, group, light)
        @param bl_obj           The according blender object
        @param export_config    Settings for export TODO move to export method?
        """
        self.export_config = export_config
        self.name = name.replace('"', '')  # quotes not allowed...
        self.type = ob_type
        self.bl_obj = bl_obj
        self.hidden = False
        self.data = ''              # custom data (eg. description)
        # custom url (use for whatever you want but never ever
        self.url = ''
        #             put spaces into it)

        if bl_obj:
            try:
                self.hidden = bl_obj.hide_get()
            except RuntimeError:
                self.hidden = bl_obj.hide_viewport
            self.matrix_world = bl_obj.matrix_world
            localMatrix = bl_obj.matrix_local
            self.location = localMatrix.to_translation()
            self.rotation = localMatrix.to_3x3()
        else:
            self.location = None
            self.rotation = None

        self.children = []
        self.parent = None

    def addChild(self, child):
        if not isinstance(child, Object):
            raise Exception(
                'addChild: can only add children derived from Object')
        child.parent = self
        self.children.append(child)

    def _parse(self, ac_mats, str_pre):
        """Override to process the mesh and add materials to ac_mats."""
        pass

    def parse(self, ac_mats, str_pre=''):
        TRACE("{0}+-({1}) {2}".format(str_pre, self.type, self.name))

        self._parse(ac_mats, str_pre)

        for child in self.children:
            child.parse(ac_mats, str_pre + ' ')

    def _write(self, strm):
        pass

    def write(self, strm):
        strm.write('OBJECT {0}\nname "{1}"\n'.format(self.type, self.name))

        if len(self.data):
            strm.write('data {0}\n'.format(len(self.data)))
            strm.write('{0}\n'.format(self.data))

        if len(self.url):
            strm.write('url {0}\n'.format(self.url))

        if self.hidden:
            strm.write('hidden\n')

        if self.location and self.export_config.export_rot:
            # position relative to parent
            location = self.location
            if any(c != 0 for c in location):
                x = '{0:.7f}'.format(location[0]).rstrip('0').rstrip('.')
                y = '{0:.7f}'.format(location[1]).rstrip('0').rstrip('.')
                z = '{0:.7f}'.format(location[2]).rstrip('0').rstrip('.')
                strm.write('loc {0:s} {1:s} {2:s}\n'.format(x, y, z))

        if self.rotation and self.export_config.export_rot:
            # rotation/scale relative to parent
            exportMatrix = self.rotation.to_3x3()
            if exportMatrix != Matrix().to_3x3():
                strm.write('rot {0:.7f} {1:.7f} {2:.7f} {3:.7f} {4:.7f} '
                           '{5:.7f} {6:.7f} {7:.7f} {8:.7f}\n'.format(
                               exportMatrix[0][0],
                               exportMatrix[1][0],
                               exportMatrix[2][0],
                               exportMatrix[0][1],
                               exportMatrix[1][1],
                               exportMatrix[2][1],
                               exportMatrix[0][2],
                               exportMatrix[1][2],
                               exportMatrix[2][2]))

        if self.type == 'world' and self.export_config.export_rot:
            exportMatrix = self.export_config.global_matrix
            if exportMatrix != Matrix().to_3x3():
                strm.write('rot {0:.7f} {1:.7f} {2:.7f} {3:.7f} {4:.7f} '
                           '{5:.7f} {6:.7f} {7:.7f} {8:.7f}\n'.format(
                               exportMatrix[0][0],
                               exportMatrix[1][0],
                               exportMatrix[2][0],
                               exportMatrix[0][1],
                               exportMatrix[1][1],
                               exportMatrix[2][1],
                               exportMatrix[0][2],
                               exportMatrix[1][2],
                               exportMatrix[2][2]))

        self._write(strm)
        strm.write('kids {0}\n'.format(len(self.children)))

        for child in self.children:
            child.write(strm)


# ------------------------------------------------------------------------------
class World(Object):
    """Normally the root element is a world object."""

    def __init__(self,
                 name,
                 export_config,
                 local_transform=Matrix()):
        Object.__init__(self, name, 'world', None,
                        export_config, local_transform)


# ------------------------------------------------------------------------------
class Poly(Object):
    """A polygon mesh."""

    def __init__(self, name, bl_obj, export_config, local_transform=Matrix()):
        Object.__init__(self, name, "poly", bl_obj,
                        export_config, local_transform)

        self.crease = None
        self.subdiv = 0
        self.vertices = []
        self.surfaces = []
        self.tex_name = ''     # texture name (filename of texture)
        self.tex_rep = [1, 1]  # texture repeat
        self.ac_mats = {}      # Blender to AC3d index cross-reference

    def _parse(self, ac_mats, str_pre):
        if self.bl_obj:
            TRACE('{0}  ~ ({1}) {2}'.format(str_pre,
                                            self.bl_obj.type,
                                            self.bl_obj.data.name))
            self._parseMesh(ac_mats)

    def _parseMesh(self, ac_mats):
        # We work on a copy of the object and apply all modifiers except EDGE_SPLIT and SUBSURF:
        useCopy = False

        apply_list = []
        remove_list = []
        number_of_subdivs = 0
        for mod in self.bl_obj.modifiers:

            if mod.type == 'EDGE_SPLIT':
                self.crease = 180
                apply_list.append(mod.name)
                useCopy = True
            elif mod.type == 'SUBSURF':
                self.subdiv = mod.levels
                remove_list.append(mod.name)
                number_of_subdivs += 1
            else:
                apply_list.append(mod.name)
                useCopy = True

        if (self.crease and self.subdiv > 0) or number_of_subdivs > 1:
            self.subdiv = 0
            remove_list = []

        self.bl_obj_copy = self.bl_obj
        mesh = None
        col = None
        mesh_copy = None
        if useCopy:
            self.bl_obj_copy = self.bl_obj.copy()
            mesh_copy = self.bl_obj_copy.data.copy()
            self.bl_obj_copy.data = mesh_copy

            prev_selected = []
            old_active = None
            view_layer = bpy.context.view_layer
            if bpy.context.active_object:
                old_active = view_layer.objects.active
            for objekt in view_layer.objects:
                if objekt.select_get():
                    prev_selected.append(objekt)

            col = bpy.data.collections.new("export_ac3d_temp")
            bpy.context.scene.collection.children.link(col)
            col.objects.link(self.bl_obj_copy)

            # Ensure copy is visible so select_set/convert succeed
            self.bl_obj_copy.hide_viewport = False
            self.bl_obj_copy.hide_set(False)

            bpy.ops.object.select_all(action='DESELECT')
            self.bl_obj_copy.select_set(True)
            view_layer.objects.active = self.bl_obj_copy
            for modname in remove_list:
                bpy.ops.object.modifier_remove(modifier=modname)
            bpy.ops.object.convert(target='MESH')
            mesh_copy = self.bl_obj_copy.data

            depsgraph = self.export_config.context.evaluated_depsgraph_get()
            mesh = self.bl_obj_copy.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

            self.bl_obj_copy.select_set(False)
            for objekt in prev_selected:
                objekt.select_set(True)
            if old_active:
                view_layer.objects.active = old_active
        else:
            depsgraph = self.export_config.context.evaluated_depsgraph_get()
            mesh = self.bl_obj_copy.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)

        orig_mesh = self.bl_obj.data
        if orig_mesh:
            if orig_mesh.name:
                self.data = orig_mesh.name.replace('"', '')

        self._parseMaterials(mesh, ac_mats)
        self._parseVertices(mesh)
        self._parseFaces(mesh)

        if not self.crease:
            if getattr(mesh, 'use_auto_smooth', False):
                self.crease = round(degrees(mesh.auto_smooth_angle), 3)
            else:
                self.crease = round(
                    degrees(self.export_config.crease_angle), 3)

        mesh = None
        self.bl_obj_copy.to_mesh_clear()

        if useCopy:
            bpy.data.objects.remove(self.bl_obj_copy, do_unlink=True, do_id_user=True, do_ui_user=True)
            bpy.data.collections.remove(col, do_unlink=True, do_id_user=True, do_ui_user=True)
            bpy.data.meshes.remove(mesh_copy, do_unlink=True, do_id_user=True, do_ui_user=True)
        self.bl_obj_copy = None

    def _parseMaterials(self, mesh, ac_mats):
        """
        Material parser and global mapping.

        Extract the materials from a blender mesh and create an id mapping from
        object material index to global AC3D material index.
        """
        mat_index = 0  # local material index
        for bl_mat in mesh.materials:
            if not bl_mat:
                continue

            ac_mat = Material(bl_mat.name, bl_mat, self.export_config)

            mat_exists = False
            for mat in ac_mats:
                if mat.same_as(ac_mat):
                    ac_mat = mat
                    mat_exists = True
                    break

            if not mat_exists:
                ac_mats.append(ac_mat)

            if not len(self.tex_name):
                if bl_mat.node_tree:
                    doSearch = False
                    try:
                        shader = _get_surface_shader(bl_mat.node_tree)
                        base_socket = None
                        if shader:
                            if 'Base Color' in shader.inputs:
                                base_socket = shader.inputs['Base Color']
                            elif 'Color' in shader.inputs:
                                base_socket = shader.inputs['Color']
                        tex_node = _find_linked_image_node(base_socket)
                        if tex_node and tex_node.image:
                            self._processTexture(tex_node.image, bl_mat)
                        else:
                            doSearch = True
                    except Exception:
                        doSearch = True

                    if doSearch:
                        textures = [x for x in bl_mat.node_tree.nodes if x.type == 'TEX_IMAGE']
                        for bl_tex in textures:
                            bl_im = bl_tex.image

                            if bl_im is None:
                                print("Texture has no image data (skipping): "
                                      "Tex name=" + bl_tex.name +
                                      " Mat name=" + bl_mat.name)
                                self.export_config.operator.report(
                                    {'WARNING'},
                                    'AC3D Exporter: Texture "' + bl_tex.name +
                                    '" in material: "' + bl_mat.name + '" contains'
                                    ' no image data and was not exported.')
                                continue

                            self._processTexture(bl_im, bl_mat)
                            break

            self.ac_mats[mat_index] = ac_mats.index(ac_mat)
            mat_index = mat_index + 1

    def _processTexture(self, image, bl_mat):
        full_path = bpy.path.abspath(image.filepath, library=image.library)
        norm_path = os.path.normpath(full_path)

        tex_name = bpy.path.basename(norm_path)
        export_tex = os.path.join(
            self.export_config.exportdir, tex_name)

        if image.packed_file:
            splt = export_tex.rsplit('.', 1)[0]
            export_tex = splt + '.png'
            tex_name = bpy.path.basename(export_tex)

        if image.has_data:
            if not os.path.exists(export_tex):
                if image.packed_file:
                    old_file_format = image.file_format
                    image.file_format = 'PNG'
                    orig_file_path = image.filepath
                    image.filepath_raw = export_tex
                    image.save()
                    image.filepath_raw = orig_file_path
                    image.file_format = old_file_format
                else:
                    abs_path = bpy.path.abspath(image.filepath)
                    if not os.path.exists(abs_path):
                        TRACE('Warning: Texture doesn\'t '
                              'exists: {0}'.format(
                                  image.filepath))
                    else:
                        if not image.is_dirty:
                            shutil.copy(abs_path, export_tex)
                        else:
                            orig_file_path = image.filepath
                            image.filepath_raw = export_tex
                            image.save()
                            image.filepath_raw = orig_file_path
        else:
            self.export_config.operator.report(
                {'WARNING'},
                'AC3D Exporter: Texture "' + image.name +
                '" (' + tex_name + ')' + ' in material: "' +
                bl_mat.name + '" contains no image and was '
                'not exported alongside model. (The .ac '
                'texture reference was exported though)')

        self.tex_name = tex_name
        self.tex_rep = [1, 1]

    def _parseVertices(self, mesh):
        """Extract the vertices from a blender mesh."""
        transform = Matrix().to_4x4()
        transform.identity()
        if not self.export_config.export_rot:
            transform = \
                self.export_config.global_matrix.to_4x4() @ self.matrix_world
        self.vertices = [transform @ v.co for v in mesh.vertices]

    def _parseFaces(self, mesh):
        """Extract the faces from a blender mesh."""
        uv_layer = None
        if len(mesh.uv_layers):
            uv_layers = mesh.uv_layers
            for uv_l in uv_layers:
                if uv_l.active:
                    uv_layer = uv_l

        is_flipped = (
            self.bl_obj.scale[0] *
            self.bl_obj.scale[1] *
            self.bl_obj.scale[2] < 0
        )

        for face_idx in range(len(mesh.polygons)):
            poly = mesh.polygons[face_idx]

            uv_coords = []
            no_uv = False
            if uv_layer:
                for loop_index in range(poly.loop_start,
                                        poly.loop_start + poly.loop_total):
                    uv_coords.append([uv_layer.data[loop_index].uv[0], uv_layer.data[loop_index].uv[1]])
                    if not uv_layer.data[loop_index].uv:
                        no_uv = True
            else:
                no_uv = True

            if no_uv:
                uv_coords = None

            surf = self.Surface(self.export_config, poly, self.ac_mats,
                                self.export_config.global_doublesided, is_flipped,
                                uv_coords, 0)
            self.surfaces.append(surf)

        if self.export_config.export_lines:
            faceEdgeKeys = set([])
            for poly in mesh.polygons:
                for key in poly.edge_keys:
                    faceEdgeKeys.add(key)

            allEdgeKeys = set(mesh.edge_keys)
            freeEdgeKeys = allEdgeKeys.difference(faceEdgeKeys)

            freeEdges = set([])
            for f_edge in freeEdgeKeys:
                for b_edge in mesh.edges:
                    if b_edge.key == f_edge:
                        freeEdges.add(b_edge)

            for bl_edge in freeEdges:
                ac_edge = self.Surface(
                    self.export_config,
                    bl_edge,
                    self.ac_mats,
                    self.export_config.global_doublesided,
                    is_flipped,
                    None,
                    2)
                self.surfaces.append(ac_edge)

    def _write(self, strm):

        strm.write('crease {0}\n'.format(self.crease))

        if self.subdiv > 0:
            strm.write('subdiv {0}\n'.format(self.subdiv))

        if len(self.tex_name) > 0:
            strm.write('texture "{0}"\n'.format(self.tex_name))
            if self.tex_rep[0] != 1 and self.tex_rep[1] != 1:
                strm.write('texrep {0} {1}\n'.format(
                    self.tex_rep[0], self.tex_rep[1]))

        if len(self.vertices):
            strm.write('numvert {0}\n'.format(len(self.vertices)))
            for vert in self.vertices:
                x = '{0:.5f}'.format(round(vert[0], 5)).rstrip('0').rstrip('.')
                y = '{0:.5f}'.format(round(vert[1], 5)).rstrip('0').rstrip('.')
                z = '{0:.5f}'.format(round(vert[2], 5)).rstrip('0').rstrip('.')
                strm.write('{0:s} {1:s} {2:s}\n'.format(x, y, z))

        if len(self.surfaces):
            strm.write('numsurf {0}\n'.format(len(self.surfaces)))
            for surf in self.surfaces:
                surf.write(strm)

    # ------------------------------
    class Surface:
        def __init__(self,
                     export_config,
                     bl_face,
                     ac_mats,
                     is_two_sided,
                     is_flipped,
                     uv_coords,
                     surf_type):
            self.export_config = export_config
            self.mat = 0        # material index for this surface
            self.bl_face_vertices = None
            self.surf_ref = None
            self.uv_coords = uv_coords
            self.is_two_sided = is_two_sided
            self.is_flipped = is_flipped
            self.ac_surf_flags = self.SurfaceFlags(surf_type, False, True)

            self.parse_blender_face(bl_face, ac_mats)

        def write(self, ac_file):
            surf_flags = self.ac_surf_flags.getFlags()
            ac_file.write('SURF {0:#X}\n'.format(surf_flags))
            ac_file.write('mat {0}\n'.format(
                self.mat - self.export_config.mat_offset))
            ac_file.write('refs {0}\n'.format(self.bl_face_vertices))

            r = range(self.bl_face_vertices)
            # This is to fix normals when scaled negative
            if self.is_flipped:
                r = reversed(r)

            if self.uv_coords:
                for n in r:
                    surf_ref = self.surf_ref[n]
                    uv_ref = self.uv_coords[n]
                    u = '{0:.6f}'.format(
                        round(uv_ref[0], 6)).rstrip('0').rstrip('.')
                    v = '{0:.6f}'.format(
                        round(uv_ref[1], 6)).rstrip('0').rstrip('.')
                    ac_file.write('{0} {1:s} {2:s}\n'.format(surf_ref, u, v))
            else:
                for n in r:
                    surf_ref = self.surf_ref[n]
                    ac_file.write('{0} 0 0\n'.format(surf_ref))

        def parse_blender_face(self, bl_face, ac_mats):
            self.ac_surf_flags.twosided = self.is_two_sided

            try:
                if bl_face.material_index in ac_mats:
                    self.mat = ac_mats[bl_face.material_index]
            except Exception:
                # is edge
                self.mat = 0
                if len(ac_mats) == 1:
                    for val in ac_mats.values():
                        self.mat = val

            try:
                self.ac_surf_flags.smooth_shaded = bl_face.use_smooth
            except Exception:
                # is edge
                self.ac_surf_flags.smooth_shaded = True

            if self.mat == 0:
                self.export_config.mat_offset = 0

            self.bl_face_vertices = len(bl_face.vertices)
            r = range(self.bl_face_vertices)

            self.surf_ref = []
            for n in r:
                self.surf_ref.append(bl_face.vertices[n])

        class SurfaceFlags:
            def __init__(self, surf_type, is_smooth, is_twosided):
                self.surf_type = surf_type
                self.smooth_shaded = is_smooth
                self.twosided = is_twosided

            def getFlags(self):
                n = self.surf_type & 0x0F
                if self.smooth_shaded:
                    n = n | 0x10
                if self.twosided:
                    n = n | 0x20
                return n


# ------------------------------------------------------------------------------
class Group(Object):
    """
    An object group.

    TODO maybe add an option to prevent exporting empty groups
    """

    def __init__(self, name, bl_obj, export_config, local_transform=Matrix()):
        Object.__init__(self, name, "group", bl_obj,
                        export_config, local_transform)


# ------------------------------------------------------------------------------
class Light(Object):
    """An light group."""

    def __init__(self,
                 name,
                 bl_obj,
                 export_config,
                 local_transform=Matrix()):
        Object.__init__(self, name, 'light', bl_obj,
                        export_config, local_transform)
        if bl_obj.data:
            self.data = bl_obj.data.type


# ------------------------------------------------------------------------------
class Material:
    """Container class that defines the material properties."""

    def __init__(self,
                 name='DefaultWhite',
                 bl_mat=None,
                 export_config=None):
        self.name = name                    # string
        self.rgb = [1.0, 1.0, 1.0]          # [R,G,B]
        self.amb = [0.8, 0.8, 0.8]          # [R,G,B]
        self.emis = [0.0, 0.0, 0.0]         # [R,G,B]
        self.spec = [0.5, 0.5, 0.5]         # [R,G,B]
        self.shi = 64                       # integer
        self.trans = 0                      # float
        self.merge = False
        self.default = True
        self.export_config = export_config

        if bl_mat:
            self.default = False
            # remove any " from the name.
            self.name = re.sub('["]', '', bl_mat.name)
            self.merge = export_config.merge_materials

            rough = 0.5
            try:
                curr_shader = _get_surface_shader(bl_mat.node_tree)

                if curr_shader and curr_shader.type == 'BSDF_PRINCIPLED':
                    principled = curr_shader

                    # Emission: Blender 4.0+ uses 'Emission Color' + 'Emission Strength'
                    if 'Emission Color' in principled.inputs:
                        emis_col = principled.inputs['Emission Color'].default_value
                    elif 'Emission' in principled.inputs:
                        emis_col = principled.inputs['Emission'].default_value
                    else:
                        emis_col = (0.0, 0.0, 0.0, 1.0)

                    if 'Emission Strength' in principled.inputs:
                        emis_str = principled.inputs['Emission Strength'].default_value
                    else:
                        emis_str = 1.0

                    self.emis = [
                        _clamp01(emis_col[0] * emis_str),
                        _clamp01(emis_col[1] * emis_str),
                        _clamp01(emis_col[2] * emis_str),
                    ]

                    # Alpha -> Transparency
                    if 'Alpha' in principled.inputs:
                        self.trans = _clamp01(1.0 - principled.inputs['Alpha'].default_value)
                    else:
                        self.trans = 0.0

                    # Roughness -> Shininess
                    if 'Roughness' in principled.inputs:
                        rough = _clamp01(1.0 - principled.inputs['Roughness'].default_value)

                    # Base Color (only when no image/node texture drives it)
                    if 'Base Color' in principled.inputs:
                        base = principled.inputs['Base Color']
                        if not base.is_linked:
                            self.rgb = [
                                _clamp01(base.default_value[0]),
                                _clamp01(base.default_value[1]),
                                _clamp01(base.default_value[2]),
                            ]

                    # Specular: Blender 4.0+ uses 'Specular IOR Level' and RGBA 'Specular Tint'
                    if 'Specular IOR Level' in principled.inputs:
                        spec_val = principled.inputs['Specular IOR Level'].default_value
                    elif 'Specular' in principled.inputs:
                        spec_val = principled.inputs['Specular'].default_value
                    else:
                        spec_val = 0.5

                    if ('Specular Tint' in principled.inputs and
                            hasattr(principled.inputs['Specular Tint'].default_value, '__len__')):
                        spec_tint = principled.inputs['Specular Tint'].default_value
                        self.spec = [
                            _clamp01(spec_val * spec_tint[0]),
                            _clamp01(spec_val * spec_tint[1]),
                            _clamp01(spec_val * spec_tint[2]),
                        ]
                    else:
                        spec_c = _clamp01(spec_val)
                        self.spec = [spec_c, spec_c, spec_c]

                elif curr_shader and curr_shader.type == 'BSDF_DIFFUSE':
                    diffuse = curr_shader
                    if 'Roughness' in diffuse.inputs:
                        rough = _clamp01(1.0 - diffuse.inputs['Roughness'].default_value)
                    if 'Color' in diffuse.inputs:
                        base = diffuse.inputs['Color']
                        if not base.is_linked:
                            self.rgb = [
                                _clamp01(base.default_value[0]),
                                _clamp01(base.default_value[1]),
                                _clamp01(base.default_value[2]),
                            ]

                elif curr_shader and curr_shader.type in ('EMISSION', 'EEVEE_EMISSION'):
                    emission = curr_shader
                    emis_str = emission.inputs['Strength'].default_value if 'Strength' in emission.inputs else 1.0
                    base_col = emission.inputs['Color'].default_value if 'Color' in emission.inputs else (1.0, 1.0, 1.0, 1.0)
                    self.emis = [
                        _clamp01(emis_str * base_col[0]),
                        _clamp01(emis_str * base_col[1]),
                        _clamp01(emis_str * base_col[2]),
                    ]
                    self.rgb = [0.0, 0.0, 0.0]
                    self.amb = [0.0, 0.0, 0.0]
                    self.spec = [0.0, 0.0, 0.0]
                    rough = 0.5
                    self.trans = 0.0

                elif curr_shader and curr_shader.type == 'EEVEE_SPECULAR':
                    specular = curr_shader
                    if 'Emissive Color' in specular.inputs:
                        ec = specular.inputs['Emissive Color'].default_value
                        self.emis = [_clamp01(ec[0]), _clamp01(ec[1]), _clamp01(ec[2])]
                    if 'Transparency' in specular.inputs:
                        self.trans = _clamp01(specular.inputs['Transparency'].default_value)
                    if 'Roughness' in specular.inputs:
                        rough = _clamp01(1.0 - specular.inputs['Roughness'].default_value)
                    if 'Base Color' in specular.inputs:
                        base = specular.inputs['Base Color']
                        if not base.is_linked:
                            self.rgb = [
                                _clamp01(base.default_value[0]),
                                _clamp01(base.default_value[1]),
                                _clamp01(base.default_value[2]),
                            ]
                    if 'Specular' in specular.inputs:
                        sc = specular.inputs['Specular'].default_value
                        self.spec = [_clamp01(sc[0]), _clamp01(sc[1]), _clamp01(sc[2])]

                else:
                    self.spec = [
                        _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[0]),
                        _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[1]),
                        _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[2]),
                    ]
                    rough = _clamp01(1.0 - bl_mat.roughness)
                    self.rgb = [
                        _clamp01(bl_mat.diffuse_color[0]),
                        _clamp01(bl_mat.diffuse_color[1]),
                        _clamp01(bl_mat.diffuse_color[2]),
                    ]
                    self.trans = _clamp01(1.0 - bl_mat.diffuse_color[3])
                    print('Material ' + bl_mat.name + ' is not Principled BSDF or Specular using nodes, Emission not exported')
            except Exception as e:
                self.spec = [
                    _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[0]),
                    _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[1]),
                    _clamp01(bl_mat.specular_intensity * bl_mat.specular_color[2]),
                ]
                rough = _clamp01(1.0 - bl_mat.roughness)
                self.rgb = [
                    _clamp01(bl_mat.diffuse_color[0]),
                    _clamp01(bl_mat.diffuse_color[1]),
                    _clamp01(bl_mat.diffuse_color[2]),
                ]
                self.trans = _clamp01(1.0 - bl_mat.diffuse_color[3])
                print('Material ' + bl_mat.name + ' fallback to viewport display (' + str(e) + ')')

            if export_config.amb_as_diff:
                self.amb = list(self.rgb)

            acMin = 0.0
            acMax = 128.0
            blMin = 0.0
            blMax = 1.0
            acRange = (acMax - acMin)
            blRange = (blMax - blMin)
            self.shi = int(round(
                (((float(rough) - blMin) * acRange) /
                 blRange) + acMin, 0))

    def write(self, strm):
        if not (self.default and self.export_config.mat_offset == 1):
            strm.write(
                'MATERIAL "{0}" rgb {1:.3f} {2:.3f} {3:.3f} '
                ' amb {4:.3f} {5:.3f} {6:.3f} '
                ' emis {7:.3f} {8:.3f} {9:.3f} '
                ' spec {10:.3f} {11:.3f} {12:.3f} '
                ' shi {13} trans {14:.3f}\n'.format(
                    self.name,
                    round(self.rgb[0], 3),
                    round(self.rgb[1], 3),
                    round(self.rgb[2], 3),
                    round(self.amb[0], 3),
                    round(self.amb[1], 3),
                    round(self.amb[2], 3),
                    round(self.emis[0], 3),
                    round(self.emis[1], 3),
                    round(self.emis[2], 3),
                    round(self.spec[0], 3),
                    round(self.spec[1], 3),
                    round(self.spec[2], 3),
                    self.shi,
                    round(self.trans, 3)))

    def same_as(self, rhs):
        if self.default or rhs.default:
            return False

        if self.merge:
            return (
                self._feq(self.rgb[0], rhs.rgb[0]) and
                self._feq(self.rgb[1], rhs.rgb[1]) and
                self._feq(self.rgb[2], rhs.rgb[2]) and
                self._feq(self.amb[0], rhs.amb[0]) and
                self._feq(self.amb[1], rhs.amb[1]) and
                self._feq(self.amb[2], rhs.amb[2]) and
                self._feq(self.emis[0], rhs.emis[0]) and
                self._feq(self.emis[1], rhs.emis[1]) and
                self._feq(self.emis[2], rhs.emis[2]) and
                self._feq(self.spec[0], rhs.spec[0]) and
                self._feq(self.spec[1], rhs.spec[1]) and
                self._feq(self.spec[2], rhs.spec[2]) and
                self._feq(self.shi, rhs.shi) and
                self._feq(self.trans, rhs.trans))

        return (
            self._feq(self.rgb[0], rhs.rgb[0]) and
            self._feq(self.rgb[1], rhs.rgb[1]) and
            self._feq(self.rgb[2], rhs.rgb[2]) and
            self._feq(self.amb[0], rhs.amb[0]) and
            self._feq(self.amb[1], rhs.amb[1]) and
            self._feq(self.amb[2], rhs.amb[2]) and
            self._feq(self.emis[0], rhs.emis[0]) and
            self._feq(self.emis[1], rhs.emis[1]) and
            self._feq(self.emis[2], rhs.emis[2]) and
            self._feq(self.spec[0], rhs.spec[0]) and
            self._feq(self.spec[1], rhs.spec[1]) and
            self._feq(self.spec[2], rhs.spec[2]) and
            self._feq(self.shi, rhs.shi) and
            self._feq(self.trans, rhs.trans) and
            self.name == rhs.name)

    def _feq(self, lhs, rhs):
        return abs(rhs - lhs) < 0.0001
