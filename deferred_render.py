from __future__ import print_function
import sys
import math
from direct.showbase.DirectObject import DirectObject
from panda3d.core import *
if sys.version_info >= (3, 0):
    import builtins
    basestring = str
else:
    import __builtin__ as builtins

__author__ = "wezu"
__copyright__ = "Copyright 2017"
__license__ = "ISC"
__version__ = "0.1"
__email__ = "wezu.dev@gmail.com"
__all__ = ['SphereLight', 'ConeLight', 'SceneLight', 'DeferredRenderer']


class DeferredRenderer(DirectObject):
    """
    DeferredRenderer is a singelton class that takes care of rendering
    It installs itself in the buildins,
    it also creates a deferred_render and forward_render nodes.
    """

    def __init__(self, preset='medium', filter_setup=None, shading_setup=None, scene_mask=1, light_mask=2):
        # check if there are other DeferredRenderer in buildins
        if hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('There can only be one DeferredRenderer')

        builtins.deferred_renderer = self
        # template to load the shaders by name, without the directory and
        # extension
        self.f = 'shaders/{}_f.glsl'
        self.v = 'shaders/{}_v.glsl'
        # last known window size, needed to test on window events if the window
        # size changed
        self.last_window_size = (base.win.getXSize(), base.win.getYSize())

        # install a wrapped version of the loader in the builtins
        builtins.loader = WrappedLoader(builtins.loader)
        loader.texture_shader_inputs = [{'input_name': 'tex_diffuse',
                                         'stage_modes': (TextureStage.M_modulate, TextureStage.M_modulate_glow, TextureStage.M_modulate_gloss),
                                         'default_texture': loader.loadTexture('data/def_diffuse.png')},
                                        {'input_name': 'tex_normal',
                                         'stage_modes': (TextureStage.M_normal, TextureStage.M_normal_height, TextureStage.M_normal_gloss),
                                         'default_texture': loader.loadTexture('data/def_normal.png')},
                                        {'input_name': 'tex_shga',  # Shine Height Alpha Glow
                                         # something different
                                         'stage_modes': (TextureStage.M_selector,),
                                         'default_texture': loader.loadTexture('data/def_shga.png')}]

        self.shading_preset = {'full': {},
                               'medium': {'DISABLE_POM': 1},
                               'minimal': {'DISABLE_POM': 1, 'DISABLE_SHADOWS': 1, 'DISABLE_NORMALMAP': 1}
                               }
        # set up the deferred rendering buffers
        if shading_setup:
            self.shading_setup = shading_setup
        else:
            self.shading_setup = self.shading_preset[preset]

        self._setup_g_buffer(self.shading_setup)

        self.preset = {'full': [{'shader_name': 'ao',
                                 'inputs': {'random_tex': 'data/random.png',
                                            'random_size': 64.0,
                                            'sample_rad': 0.4,
                                            'intensity': 10.0,
                                            'scale': 0.9,
                                            'bias': 0.4,
                                            'fade_distance': 80.0}},
                                {'name': 'final_light', 'shader_name': 'dir_light',
                                 'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                {'shader_name': 'fog',
                                 'inputs': {'fog_color': Vec4(0.1, 0.1, 0.1, 0.0),
                                            # start, stop, power, mix
                                            'fog_config': Vec4(10.0, 100.0, 2.0, 1.0),
                                            'dof_near': 0.5,  # 0.0..1.0 not distance!
                                            'dof_far': 60.0}},  # distance in units to full blur
                                {'shader_name': 'ssr', 'inputs': {}},
                                {'shader_name': 'bloom',
                                 'size_factor': 0.5,
                                 'inputs': {'glow_power': 5.0}},
                                {'name': 'bloom_blur', 'shader_name': 'blur',
                                 'inputs': {'blur': 3.0},
                                 'size_factor': 0.5},
                                {'name': 'compose', 'shader_name': 'mix',
                                 'translate_tex_name': {'fog': 'final_color'},
                                 'inputs': {'lut_tex': 'data/lut_v1.png',
                                            'noise_tex': 'data/noise.png'}},
                                {'name': 'pre_aa', 'shader_name': 'dof',
                                 'inputs': {'blur': 6.0}},
                                {'shader_name': 'fxaa',
                                 'inputs': {'FXAA_SPAN_MAX': 2.0,
                                            'FXAA_REDUCE_MUL': float(1.0 / 16.0),
                                            'FXAA_SUBPIX_SHIFT': float(1.0 / 8.0)}}
                                ],
                       'minimal': [{'name': 'final_light', 'shader_name': 'dir_light',
                                    'define': {'HALFLAMBERT': 2.0},
                                    'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                   {'name': 'compose', 'shader_name': 'mix',
                                    'translate_tex_name': {'final_light': 'final_color'},
                                    'define': {'DISABLE_SSR': 1,
                                               'DISABLE_AO': 1,
                                               'DISABLE_BLOOM': 1,
                                               'DISABLE_LUT': 1,
                                               'DISABLE_DITHERING': 1},
                                    'inputs': {'lut_tex': 'data/lut_v1.png',
                                               'noise_tex': 'data/noise.png'}},
                                   {'shader_name': 'fxaa',
                                    'translate_tex_name': {'compose': 'pre_aa'},
                                    'inputs': {'FXAA_SPAN_MAX': 2.0,
                                               'FXAA_REDUCE_MUL': float(1.0 / 16.0),
                                               'FXAA_SUBPIX_SHIFT': float(1.0 / 8.0)}}
                                   ],
                       'medium': [{'shader_name': 'ao', 'size_factor': 0.5,
                                   'inputs': {'random_tex': 'data/random.png',
                                              'random_size': 64.0,
                                              'sample_rad': 0.4,
                                              'intensity': 10.0,
                                              'scale': 0.9,
                                              'bias': 0.4,
                                              'fade_distance': 80.0}},
                                  {'name': 'final_light', 'shader_name': 'dir_light',
                                   'define': {'HALFLAMBERT': 2.0},
                                   'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                  {'shader_name': 'fog',
                                   'inputs': {'fog_color': Vec4(0.1, 0.1, 0.1, 0.0),
                                              # start, stop, power, mix
                                              'fog_config': Vec4(1.0, 100.0, 2.0, 1.0),
                                              'dof_near': 0.5,  # 0.0..1.0 not distance!
                                              'dof_far': 60.0}},  # distance in units to full blur
                                  {'shader_name': 'bloom',
                                   'size_factor': 0.5,
                                   'inputs': {'glow_power': 5.0}},
                                  {'name': 'bloom_blur', 'shader_name': 'blur',
                                   'inputs': {'blur': 3.0},
                                   'size_factor': 0.5},
                                  {'name': 'compose', 'shader_name': 'mix',
                                   'translate_tex_name': {'fog': 'final_color'},
                                   'define': {'DISABLE_SSR': 1},
                                   'inputs': {'lut_tex': 'data/lut_v1.png',
                                              'noise_tex': 'data/noise.png'}},
                                  {'shader_name': 'fxaa',
                                   'translate_tex_name': {'compose': 'pre_aa'},
                                   'inputs': {'FXAA_SPAN_MAX': 2.0,
                                              'FXAA_REDUCE_MUL': float(1.0 / 16.0),
                                              'FXAA_SUBPIX_SHIFT': float(1.0 / 8.0)}}
                                  ]
                       }

        # post process
        self.filter_buff = {}
        self.filter_quad = {}
        self.filter_tex = {}
        self.filter_cam = {}
        self.common_inputs = {'render': render,
                              'camera': base.cam,
                              'depth_tex': self.depth,
                              'normal_tex': self.normal,
                              'albedo_tex': self.albedo,
                              'lit_tex': self.lit_tex,
                              'forward_tex': self.plain_tex}
        if filter_setup:
            self.filter_stages = filter_setup
        else:
            self.filter_stages = self.preset[preset]

        for stage in self.filter_stages[:-1]:
            self.add_filter(**stage)
        for name, tex in self.filter_tex.items():
            self.common_inputs[name] = tex
        for name, value in self.common_inputs.items():
            for filter_name, quad in self.filter_quad.items():
                quad.setShaderInput(name, value)

        # stick the last stage quad to render2d
        # this is a bit ugly...
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader_name']
        self.filter_quad[last_stage] = self.lightbuffer.getTextureCard()
        self.reload_filter(last_stage)
        self.filter_quad[last_stage].reparentTo(render2d)

        # listen to window events so that buffers can be resized with the
        # window
        self.accept("window-event", self._on_window_event)
        # update task
        taskMgr.add(self._update, '_update_tsk')

    def reset_filters(self, filter_setup):
        """
        Remove all filters and creates a new filter list using the given filter_setup (dict)
        """
        # special case - get the inputs for the directionl light(s)
        dir_light_num_lights = self.get_filter_define(
            'final_light', 'NUM_LIGHTS')
        dir_light_color = self.get_filter_input('final_light', 'light_color')
        dir_light_dir = self.get_filter_input('final_light', 'direction')

        # remove buffers
        for buff in self.filter_buff.values():
            buff.clearRenderTextures()
            base.win.getGsg().getEngine().removeWindow(buff)
        # remove quads, but keep the last one (detach it)
        # the last one should also be self.lightbuffer.getTextureCard()
        # so we don't need to keep a reference to it
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader_name']
        for name, quad in self.filter_quad.items():
            if name != last_stage:
                quad.removeNode()
            else:
                quad.detachNode()
        for cam in self.filter_cam.values():
            cam.removeNode()
        # load the new values
        self.filter_buff = {}
        self.filter_quad = {}
        self.filter_tex = {}
        self.filter_cam = {}
        self.filter_stages = filter_setup
        for stage in self.filter_stages[:-1]:
            self.add_filter(**stage)
        for name, tex in self.filter_tex.items():
            self.common_inputs[name] = tex
        for name, value in self.common_inputs.items():
            for filter_name, quad in self.filter_quad.items():
                quad.setShaderInput(name, value)
        # stick the last stage quad to render2d
        # this is a bit ugly...
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader_name']
        self.filter_quad[last_stage] = self.lightbuffer.getTextureCard()
        self.reload_filter(last_stage)
        self.filter_quad[last_stage].reparentTo(render2d)

        # reapply the directional lights
        self.set_filter_define(
            'final_light', 'NUM_LIGHTS', dir_light_num_lights)
        if dir_light_color:
            self.set_filter_input('final_light', None, dir_light_color)
            self.set_filter_input('final_light', None, dir_light_dir)

    def reload_filter(self, stage_name):
        """
        Reloads the shader and inputs of a given filter stage
        """
        id = self._get_filter_stage_index(stage_name)
        shader_name = self.filter_stages[id]['shader_name']
        inputs = {}
        if 'inputs' in self.filter_stages[id]:
            inputs = self.filter_stages[id]['inputs']
        define = None
        if 'define' in self.filter_stages[id]:
            define = self.filter_stages[id]['define']
        self.filter_quad[stage_name].setShader(loader.loadShaderGLSL(
            self.v.format(shader_name), self.f.format(shader_name), define))
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value = loader.loadTexture(value)
            self.filter_quad[stage_name].setShaderInput(str(name), value)
        for name, value in self.common_inputs.items():
            self.filter_quad[stage_name].setShaderInput(name, value)
        if 'translate_tex_name' in self.filter_stages[id]:
            for old_name, new_name in self.filter_stages[id]['translate_tex_name'].items():
                value = self.filter_tex[old_name]
                self.filter_quad[stage_name].setShaderInput(
                    str(new_name), value)

    def get_filter_define(self, stage_name, name):
        """
        Returns the current value of a shader pre-processor define for a given filter stage
        """
        if stage_name in self.filter_quad:
            id = self._get_filter_stage_index(stage_name)
            if 'define' in self.filter_stages[id]:
                if name in self.filter_stages[id]['define']:
                    return self.filter_stages[id]['define'][name]
        return None

    def set_filter_define(self, stage_name, name, value):
        """
        Sets a define value for the shader pre-processor for a given filter stage,
        The shader for that filter stage gets reloaded, so no need to call reload_filter()
        """
        if stage_name in self.filter_quad:
            id = self._get_filter_stage_index(stage_name)
            if 'define' in self.filter_stages[id]:
                if value is None:
                    if name in self.filter_stages[id]['define']:
                        del self.filter_stages[id]['define'][name]
                else:
                    self.filter_stages[id]['define'][name] = value
            elif value is not None:
                self.filter_stages[id]['define'] = {name: value}
            # reload the shader
            self.reload_filter(stage_name)

    def _get_filter_stage_index(self, name):
        """
        Returns the index of a filter stage
        """
        for index, stage in enumerate(self.filter_stages):
            if 'name' in stage:
                if stage['name'] == name:
                    return index
            elif stage['shader_name'] == name:
                return index
        raise IndexError('No stage named ' + name)

    def get_filter_input(self, stage_name, name):
        """
        Returns the shader input from a given stage
        """
        if stage_name in self.filter_quad:
            id = self._get_filter_stage_index(stage_name)
            value = self.filter_quad[stage_name].getShaderInput(str(name))
            return value
            '''
            value_type=value.getValueType()
            print(name, value_type)

            if value_type==ShaderInput.M_texture:
                return value.getTexture()
            elif value_type==ShaderInput.M_nodepath:
                return value.getNodepath()
            elif value_type==ShaderInput.M_vector:
                return value.getVector()
            elif value_type==ShaderInput.M_texture_sampler :
                return value.getSampler()
            elif value_type==ShaderInput.M_numeric:
                return self.filter_quad[stage_name].getShaderInput(str(name))
            '''
        return None

    def set_filter_input(self, stage_name, name, value, modify_using=None):
        """
        Sets a shader input for a given filter stage.
        modify_using - should be an operator, like operator.add if you want to
                       change the value of an input based on the current value
        """
        if stage_name in self.filter_quad:
            id = self._get_filter_stage_index(stage_name)
            if name is None:
                self.filter_quad[stage_name].setShaderInput(value)
                return
            if modify_using is not None:
                value = modify_using(self.filter_stages[id][
                                     'inputs'][name], value)
                self.filter_stages[id]['inputs'][name] = value
            if isinstance(value, basestring):
                value = loader.loadTexture(value)
            self.filter_quad[stage_name].setShaderInput(str(name), value)
            # print(stage_name, name, value)

    def _setup_g_buffer(self, define=None):
        """
        Creates all the needed buffers, nodes and attributes for a geometry buffer
        """
        self.modelbuffer = self._make_FBO("model buffer", 1)
        self.lightbuffer = self._make_FBO("light buffer", 0)

        # Create four render textures: depth, normal, albedo, and final.
        # attach them to the various bitplanes of the offscreen buffers.
        self.depth = Texture()
        self.depth.setWrapU(Texture.WM_clamp)
        self.depth.setWrapV(Texture.WM_clamp)
        self.depth.setFormat(Texture.F_depth_component32)
        self.depth.setComponentType(Texture.T_float)
        self.albedo = Texture()
        self.normal = Texture()
        self.normal.setFormat(Texture.F_rgba16)
        self.normal.setComponentType(Texture.T_float)
        self.lit_tex = Texture()
        self.lit_tex.setWrapU(Texture.WM_clamp)
        self.lit_tex.setWrapV(Texture.WM_clamp)

        self.modelbuffer.addRenderTexture(tex=self.depth,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPDepth)
        self.modelbuffer.addRenderTexture(tex=self.albedo,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPColor)
        self.modelbuffer.addRenderTexture(tex=self.normal,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPAuxRgba0)
        self.lightbuffer.addRenderTexture(tex=self.lit_tex,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPColor)
        # Set the near and far clipping planes.
        base.cam.node().getLens().setNearFar(1.0, 500.0)
        lens = base.cam.node().getLens()

        # This algorithm uses three cameras: one to render the models into the
        # model buffer, one to render the lights into the light buffer, and
        # one to render "plain" stuff (non-deferred shaded) stuff into the
        # light buffer.  Each camera has a bitmask to identify it.
        self.modelMask = 1
        self.lightMask = 2

        self.modelcam = base.makeCamera(win=self.modelbuffer,
                                        lens=lens,
                                        scene=render,
                                        mask=self.modelMask)
        self.lightcam = base.makeCamera(win=self.lightbuffer,
                                        lens=lens,
                                        scene=render,
                                        mask=self.lightMask)

        # Panda's main camera is not used.
        base.cam.node().setActive(0)

        # Take explicit control over the order in which the three
        # buffers are rendered.
        self.modelbuffer.setSort(1)
        self.lightbuffer.setSort(2)
        base.win.setSort(3)

        # Within the light buffer, control the order of the two cams.
        self.lightcam.node().getDisplayRegion(0).setSort(1)

        # By default, panda usually clears the screen before every
        # camera and before every window.  Tell it not to do that.
        # Then, tell it specifically when to clear and what to clear.
        self.modelcam.node().getDisplayRegion(0).disableClears()
        self.lightcam.node().getDisplayRegion(0).disableClears()
        base.cam.node().getDisplayRegion(0).disableClears()
        base.cam2d.node().getDisplayRegion(0).disableClears()
        self.modelbuffer.disableClears()
        base.win.disableClears()

        self.modelbuffer.setClearColorActive(1)
        self.modelbuffer.setClearDepthActive(1)
        self.lightbuffer.setClearColorActive(1)
        self.lightbuffer.setClearColor((0, 0, 0, 0))
        self.modelbuffer.setClearColor((0, 0, 0, 0))
        self.modelbuffer.setClearActive(GraphicsOutput.RTPAuxRgba0, True)

        render.setState(RenderState.makeEmpty())

        # Create two subroots, to help speed cull traversal.
        # root node and a list for the lights
        self.light_root = render.attachNewNode('light_root')
        self.light_root.setShader(loader.loadShaderGLSL(
            self.v.format('light'), self.f.format('light'), define))
        self.light_root.setShaderInput("albedo_tex", self.albedo)
        self.light_root.setShaderInput("depth_tex", self.depth)
        self.light_root.setShaderInput("normal_tex", self.normal)
        self.light_root.setShaderInput('win_size', Vec2(
            base.win.getXSize(), base.win.getYSize()))
        self.light_root.hide(BitMask32(self.modelMask))
        self.light_root.setShaderInput('camera', base.cam)
        self.light_root.setShaderInput('render', render)
        # self.light_root.hide(BitMask32(self.plainMask))

        self.geometry_root = render.attachNewNode('geometry_root')
        self.geometry_root.setShader(loader.loadShaderGLSL(
            self.v.format('geometry'), self.f.format('geometry'), define))
        self.geometry_root.hide(BitMask32(self.lightMask))
        # self.geometry_root.hide(BitMask32(self.plainMask))

        self.plain_root, self.plain_tex, self.plain_cam, self.plain_buff = self._make_forward_stage()
        self.plain_root.setShader(loader.loadShaderGLSL(
            self.v.format('forward'), self.f.format('forward'), define))
        self.plain_root.setShaderInput("depth_tex", self.depth)
        self.plain_root.setShaderInput('win_size', Vec2(
            base.win.getXSize(), base.win.getYSize()))
        self.plain_root.hide(BitMask32(self.lightMask))
        self.plain_root.hide(BitMask32(self.modelMask))

        # instal into buildins
        builtins.defered_render = self.geometry_root
        builtins.forward_render = self.plain_root

    def _on_window_event(self, window):
        """
        Function called when something hapens to the main window
        Currently it's only function is to resize all the buffers to fit
        the new size of the window if the size of the window changed
        """
        if window is not None:
            window_size = (base.win.getXSize(), base.win.getYSize())
            if self.last_window_size != window_size:
                self.modelbuffer.setSize(window_size[0], window_size[1])
                self.lightbuffer.setSize(window_size[0], window_size[1])
                self.plain_buff.setSize(window_size[0], window_size[1])
                for buff in self.filter_buff.values():
                    old_size = buff.getFbSize()
                    x_factor = float(old_size[0]) / \
                        float(self.last_window_size[0])
                    y_factor = float(old_size[1]) / \
                        float(self.last_window_size[1])
                    buff.setSize(
                        int(window_size[0] * x_factor), int(window_size[1] * y_factor))
                self.last_window_size = window_size

    def add_filter(self, shader_name, inputs,
                   name=None, size_factor=1.0,
                   clear_color=None, translate_tex_name=None,
                   define=None):
        """
        Creates and adds filter stage to the filter stage dicts:
        the created buffer is put in self.filter_buff[name]
        the created fullscreen quad is put in self.filter_quad[name]
        the created fullscreen texture is put in self.filter_tex[name]
        """
        if name is None:
            name = shader_name
        index = len(self.filter_buff)
        quad, tex, buff, cam = self._make_filter_stage(
            sort=index, size=size_factor, clear_color=clear_color)
        self.filter_buff[name] = buff
        self.filter_quad[name] = quad
        self.filter_tex[name] = tex
        self.filter_cam[name] = cam

        quad.setShader(loader.loadShaderGLSL(self.v.format(
            shader_name), self.f.format(shader_name), define))
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value = loader.loadTexture(value)
            quad.setShaderInput(str(name), value)
        if translate_tex_name:
            for old_name, new_name in translate_tex_name.items():
                value = self.filter_tex[old_name]
                quad.setShaderInput(str(new_name), value)

    def _make_filter_stage(self, sort=0, size=1.0, clear_color=None):
        """
        Creates a buffer, quad, camera and texture needed for a filter stage
        Use add_filter() not this function
        """
        # make a root for the buffer
        root = NodePath("filterBufferRoot")
        tex = Texture()
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        buff_size_x = int(base.win.getXSize() * size)
        buff_size_y = int(base.win.getYSize() * size)
        # buff=base.win.makeTextureBuffer("buff", buff_size_x, buff_size_y, tex)
        winprops = WindowProperties()
        winprops.setSize(buff_size_x, buff_size_y)
        props = FrameBufferProperties()
        props.setRgbColor(True)
        props.setRgbaBits(8, 8, 8, 8)
        props.setDepthBits(0)
        buff = base.graphicsEngine.makeOutput(
            base.pipe, 'filter_stage', sort,
            props, winprops,
            GraphicsPipe.BF_resizeable,
            base.win.getGsg(), base.win)
        buff.addRenderTexture(
            tex=tex, mode=GraphicsOutput.RTMBindOrCopy, bitplane=GraphicsOutput.RTPColor)
        # buff.setSort(sort)
        # buff.setSort(0)
        if clear_color:
            buff.setClearColor(clear_color)
            buff.setClearActive(GraphicsOutput.RTPColor, True)
        cam = base.makeCamera(win=buff)
        cam.reparentTo(root)
        cam.set_pos(buff_size_x * 0.5, buff_size_y * 0.5, 100)
        cam.setP(-90)
        lens = OrthographicLens()
        lens.setFilmSize(buff_size_x, buff_size_y)
        cam.node().setLens(lens)
        # plane with the texture, a blank texture for now
        cm = CardMaker("plane")
        cm.setFrame(0, buff_size_x, 0, buff_size_y)
        quad = root.attachNewNode(cm.generate())
        quad.lookAt(0, 0, -1)
        quad.setLightOff()
        return quad, tex, buff, cam

    def _make_forward_stage(self):
        """
        Creates nodes, buffers and whatnot needed for forward rendering
        """
        root = NodePath("forwardRoot")
        tex = Texture()
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        buff_size_x = int(base.win.getXSize())
        buff_size_y = int(base.win.getYSize())
        buff = base.win.makeTextureBuffer(
            "buff", buff_size_x, buff_size_y, tex)
        buff.setSort(2)
        buff.setClearColor((0, 0, 0, 0))
        cam = base.makeCamera(win=buff)
        cam.reparentTo(root)
        lens = base.cam.node().getLens()
        cam.node().setLens(lens)
        mask = BitMask32.bit(self.modelMask)
        mask.setBit(self.lightMask)
        cam.node().setCameraMask(mask)
        return root, tex, cam, buff

    def set_directional_light(self, color, direction, shadow_size=0):
        """
        Sets value for a directional light,
        use the SceneLight class to set the lights!
        """
        self.filter_quad['final_light'].setShaderInput('light_color', color)
        self.filter_quad['final_light'].setShaderInput('direction', direction)

    def add_cone_light(self, color, pos=(0, 0, 0), hpr=(0, 0, 0), radius=1.0, fov=45.0, shadow_size=0.0):
        """
        Creates a spotlight,
        use the ConeLight class, not this function!
        """
        if fov > 179.0:
            fov = 179.0
        xy_scale = math.tan(deg2Rad(fov * 0.5))
        model = loader.loadModel("volume/cone")
        # temp=model.copyTo(self.plain_root)
        # self.lights.append(model)
        model.reparentTo(self.light_root)
        model.setScale(xy_scale, 1.0, xy_scale)
        model.flattenStrong()
        model.setScale(radius)
        model.set_pos(pos)
        model.setHpr(hpr)
        # debug=self.lights[-1].copyTo(self.plain_root)
        model.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.setAttrib(CullFaceAttrib.make(
            CullFaceAttrib.MCullCounterClockwise))
        model.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))

        model.setShader(loader.loadShaderGLSL(self.v.format(
            'spot_light'), self.f.format('spot_light'), self.shading_setup))
        model.setShaderInput("light_radius", float(radius))
        model.setShaderInput("light_pos", Vec4(pos, 1.0))
        model.setShaderInput("light_fov", deg2Rad(fov))
        model.setShaderInput("light_pos", Vec4(pos, 1.0))
        p3d_light = render.attachNewNode(Spotlight("Spotlight"))
        p3d_light.set_pos(render, pos)
        p3d_light.setHpr(render, hpr)
        p3d_light.node().setExponent(20)
        if shadow_size > 0.0:
            p3d_light.node().set_shadow_caster(True, 256, 256)
        # p3d_light.node().setCameraMask(self.modelMask)
        model.setShaderInput("spot", p3d_light)
        # p3d_light.node().showFrustum()
        p3d_light.node().getLens().set_fov(fov)
        p3d_light.node().getLens().setFar(radius)
        p3d_light.node().getLens().setNear(1.0)
        return model, p3d_light

    def add_point_light(self, color, model="volume/sphere", pos=(0, 0, 0), radius=1.0, shadow_size=0):
        """
        Creates a omni (point) light,
        Use the SphereLight class to create lights!!!
        """
        # light geometry
        # if we got a NodePath we use it as the geom for the light
        if not isinstance(model, NodePath):
            model = loader.loadModel(model)
        # self.lights.append(model)
        model.reparentTo(self.light_root)
        model.set_pos(pos)
        model.setScale(radius)
        model.setShader(loader.loadShaderGLSL(self.v.format(
            'light'), self.f.format('light'), self.shading_setup))
        model.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.setAttrib(CullFaceAttrib.make(
            CullFaceAttrib.MCullCounterClockwise))
        model.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        # shader inpts
        model.setShaderInput("light", Vec4(color, radius * radius))
        model.setShaderInput("light_pos", Vec4(pos, 1.0))
        if shadow_size > 0:
            model.setShader(loader.loadShaderGLSL(self.v.format(
                'light_shadow'), self.f.format('light_shadow'), self.shading_setup))
            p3d_light = render.attachNewNode(PointLight("PointLight"))
            p3d_light.set_pos(render, pos)
            p3d_light.node().set_shadow_caster(True, shadow_size, shadow_size)
            p3d_light.node().setCameraMask(self.modelMask)
            # p3d_light.node().showFrustum()
            for i in range(6):
                p3d_light.node().getLens(i).setNearFar(0.1, radius)
            model.setShaderInput("shadowcaster", p3d_light)
            model.setShaderInput("near", 0.1)
            model.setShaderInput("bias", 0.012)
        else:
            p3d_light = render.attachNewNode('dummy_node')
        return model, p3d_light

    def _make_FBO(self, name, auxrgba=0):
        """
        This routine creates an offscreen buffer.  All the complicated
        parameters are basically demanding capabilities from the offscreen
        buffer - we demand that it be able to render to texture on every
        bitplane, that it can support aux bitplanes, that it track
        the size of the host window, that it can render to texture
        cumulatively, and so forth.
        """
        winprops = WindowProperties()
        props = FrameBufferProperties()
        props.setRgbColor(True)
        props.setRgbaBits(8, 8, 8, 8)
        props.setDepthBits(1)
        props.setAuxRgba(auxrgba)
        return base.graphicsEngine.makeOutput(
            base.pipe, name, -2,
            props, winprops,
            GraphicsPipe.BFSizeTrackHost | GraphicsPipe.BFCanBindEvery |
            GraphicsPipe.BFRttCumulative | GraphicsPipe.BFRefuseWindow,
            base.win.getGsg(), base.win)

    def _update(self, task):
        """
        Update task, currently only updates the forward rendering camera pos/hpr
        """
        self.plain_cam.set_pos(base.cam.getPos(render))
        self.plain_cam.setHpr(base.cam.getHpr(render))
        return task.again

# this will replace the default Loader


class WrappedLoader(object):

    def __init__(self, original_loader):
        self.original_loader = original_loader
        self.texture_shader_inputs = []
        self.fix_srgb = ConfigVariableBool('framebuffer-srgb').getValue()
        self.shader_cache = {}

    def fixTransparancy(self, model):
        for tex_stage in model.findAllTextureStages():
            tex = model.findTexture(tex_stage)
            if tex:
                mode = tex_stage.getMode()
                tex_format = tex.getFormat()
                if mode == TextureStage.M_modulate and (tex_format == Texture.F_rgba or tex_format == Texture.F_srgb_alpha):
                    return
        model.setTransparency(TransparencyAttrib.MNone, 1)

    def fixSrgbTextures(self, model):
        for tex_stage in model.findAllTextureStages():
            tex = model.findTexture(tex_stage)
            if tex:
                file_name = tex.getFilename()
                tex_format = tex.getFormat()
                # print( tex_stage,  file_name, tex_format)
                if tex_stage.getMode() == TextureStage.M_normal:
                    tex_stage.setMode(TextureStage.M_normal_gloss)
                if tex_stage.getMode() != TextureStage.M_normal_gloss:
                    if tex_format == Texture.F_rgb:
                        tex_format = Texture.F_srgb
                    elif tex_format == Texture.F_rgba:
                        tex_format = Texture.F_srgb_alpha
                tex.setFormat(tex_format)
                model.setTexture(tex_stage, tex, 1)

    def setTextureInputs(self, model):
        slots_filled = set()
        # find all the textures, easy mode - slot is fitting the stage mode
        # (eg. slot0 is diffuse/color)
        for slot, tex_stage in enumerate(model.findAllTextureStages()):
            tex = model.findTexture(tex_stage)
            if tex:
                mode = tex_stage.getMode()
                if mode in self.texture_shader_inputs[slot]['stage_modes']:
                    model.setShaderInput(self.texture_shader_inputs[
                                         slot]['input_name'], tex)
                    slots_filled.add(slot)
        # did we get all of them?
        if len(slots_filled) == len(self.texture_shader_inputs):
            return
        # what slots need filling?
        missing_slots = set(
            range(len(self.texture_shader_inputs))) - slots_filled
        for slot, tex_stage in enumerate(model.findAllTextureStages()):
            if slot in missing_slots:
                tex = model.findTexture(tex_stage)
                if tex:
                    mode = tex_stage.getMode()
                    for d in self.texture_shader_inputs:
                        if mode in d['stage_modes']:
                            i = self.texture_shader_inputs.index(d)
                            model.setShaderInput(self.texture_shader_inputs[
                                                 i]['input_name'], tex)
                            slots_filled.add(i)
        # did we get all of them this time?
        if len(slots_filled) == len(self.texture_shader_inputs):
            return
        missing_slots = set(
            range(len(self.texture_shader_inputs))) - slots_filled
        # set defaults
        for slot in missing_slots:
            model.setShaderInput(self.texture_shader_inputs[slot][
                                 'input_name'], self.texture_shader_inputs[slot]['default_texture'])

    def destroy(self):
        self.original_loader.destroy()

    def loadModel(self, modelPath, loaderOptions=None, noCache=None,
                  allowInstance=False, okMissing=None,
                  callback=None, extraArgs=[], priority=None):
        model = self.original_loader.loadModel(
            modelPath, loaderOptions, noCache, allowInstance, okMissing, callback, extraArgs, priority)

        if self.fix_srgb:
            self.fixSrgbTextures(model)
        self.setTextureInputs(model)
        self.fixTransparancy(model)
        return model

    def cancelRequest(self, cb):
        self.original_loader.cancelRequest(cb)

    def isRequestPending(self, cb):
        return self.original_loader.isRequestPending(cb)

    def loadModelOnce(self, modelPath):
        return self.original_loader.loadModelOnce(modelPath)

    def loadModelCopy(self, modelPath, loaderOptions=None):
        return self.original_loader.loadModelCopy(modelPath, loaderOptions)

    def loadModelNode(self, modelPath):
        return self.original_loader.loadModelNode(modelPath)

    def unloadModel(self, model):
        self.original_loader.unloadModel(model)

    def saveModel(self, modelPath, node, loaderOptions=None,
                  callback=None, extraArgs=[], priority=None):
        return self.original_loader.saveModel(modelPath, node, loaderOptions, callback, extraArgs, priority)

    def loadFont(self, modelPath,
                 spaceAdvance=None, lineHeight=None,
                 pointSize=None,
                 pixelsPerUnit=None, scaleFactor=None,
                 textureMargin=None, polyMargin=None,
                 minFilter=None, magFilter=None,
                 anisotropicDegree=None,
                 color=None,
                 outlineWidth=None,
                 outlineFeather=0.1,
                 outlineColor=VBase4(0, 0, 0, 1),
                 renderMode=None,
                 okMissing=False):
        return self.original_loader.loadFont(modelPath, spaceAdvance, lineHeight, pointSize, pixelsPerUnit, scaleFactor, textureMargin, polyMargin, minFilter, magFilter, anisotropicDegree, color, outlineWidth, outlineFeather, outlineColor, renderMode, okMissing)

    def loadTexture(self, texturePath, alphaPath=None,
                    readMipmaps=False, okMissing=False,
                    minfilter=None, magfilter=None,
                    anisotropicDegree=None, loaderOptions=None,
                    multiview=None, sRgb=False):
        tex = self.original_loader.loadTexture(
            texturePath, alphaPath, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview)
        if sRgb:
            tex_format = tex.getFormat()
            if tex_format == Texture.F_rgb:
                tex_format = Texture.F_srgb
            elif tex_format == Texture.F_rgba:
                tex_format = Texture.F_srgb_alpha
            tex.setFormat(tex_format)
        return tex

    def load3DTexture(self, texturePattern, readMipmaps=False, okMissing=False,
                      minfilter=None, magfilter=None, anisotropicDegree=None,
                      loaderOptions=None, multiview=None, numViews=2):
        return self.original_loader.load3DTexture(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview, numViews)

    def load2DTextureArray(self, texturePattern, readMipmaps=False, okMissing=False,
                           minfilter=None, magfilter=None, anisotropicDegree=None,
                           loaderOptions=None, multiview=None, numViews=2):
        return self.original_loader.load2DTextureArray(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview, numViews)

    def loadCubeMap(self, texturePattern, readMipmaps=False, okMissing=False,
                    minfilter=None, magfilter=None, anisotropicDegree=None,
                    loaderOptions=None, multiview=None):
        return self.original_loader.loadCubeMap(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview)

    def unloadTexture(self, texture):
        self.original_loader.unloadTexture(texture)

    def loadSfx(self, *args, **kw):
        return self.original_loader.loadSfx(*args, **kw)

    def loadMusic(self, *args, **kw):
        return self.original_loader.loadMusic(*args, **kw)

    def loadSound(self, manager, soundPath, positional=False,
                  callback=None, extraArgs=[]):
        return self.original_loader.loadSound(manager, soundPath, positional, callback, extraArgs)

    def unloadSfx(self, sfx):
        self.original_loader.unloadSfx(sfx)

    def loadShaderGLSL(self, v_shader, f_shader, define=None, version='#version 140'):
        # check if we already have a shader like that
        # note: this may fail depending on the dict implementation
        if (v_shader, f_shader, str(define)) in self.shader_cache:
            return self.shader_cache[(v_shader, f_shader, str(define))]
        # load the shader text
        with open(v_shader) as f:
            v_shader_txt = f.read()
        with open(f_shader) as f:
            f_shader_txt = f.read()
        # make the header
        if define:
            header = version + '\n'
            for name, value in define.items():
                header += '#define {0} {1}\n'.format(name, value)
            # put the header on top
            v_shader_txt = v_shader_txt.replace(version, header)
            f_shader_txt = f_shader_txt.replace(version, header)
        # make the shader
        shader = Shader.make(Shader.SL_GLSL, v_shader_txt, f_shader_txt)
        # store it
        self.shader_cache[(v_shader, f_shader, str(define))] = shader
        shader.set_filename(Shader.ST_vertex, v_shader)
        shader.set_filename(Shader.ST_fragment, f_shader)
        return shader

    def loadShader(self, shaderPath, okMissing=False):
        return self.original_loader.loadShader(shaderPath, okMissing)

    def unloadShader(self, shaderPath):
        self.original_loader.unloadShader(shaderPath)

    def asyncFlattenStrong(self, model, inPlace=True,
                           callback=None, extraArgs=[]):
        self.original_loader.asyncFlattenStrong(
            model, inPlace, callback, extraArgs)

# light classes:


class SceneLight(object):
    """
    Directional light(s) for the deferred renderer
    Because of the way directional lights are implemented (fullscreen quad),
    it's not very logical to have multiple SceneLights, but you can have multiple
    directional lights as part of one SceneLight instance.
    You can add and remove additional lights using add_light() and remove_light()
    This class curently has no properies access :(
    """

    def __init__(self, color=None, direction=None, main_light_name='main', shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.__color = {}
        self.__direction = {}
        self.__shadow_size = {}
        self.main_light_name = main_light_name
        if color and direction:
            self.add_light(color=color, direction=direction,
                           name=main_light_name, shadow_size=shadow_size)

    def add_light(self, color, direction, name, shadow_size=0):
        """
        Adds a directional light to this SceneLight
        """
        if len(self.__color) == 0:
            deferred_renderer.set_directional_light(
                color, direction, shadow_size)
            self.__color[name] = Vec3(color)
            self.__direction[name] = Vec3(direction)
            self.__shadow_size[name] = shadow_size
        else:
            self.__color[name] = Vec3(color)
            self.__direction[name] = Vec3(direction)
            self.__shadow_size[name] = shadow_size
            num_lights = len(self.__color)
            colors = PTALVecBase3f()
            for v in self.__color.values():
                colors.pushBack(v)
            directions = PTALVecBase3f()
            for v in self.__direction.values():
                directions.pushBack(v)
            deferred_renderer.set_filter_define(
                'final_light', 'NUM_LIGHTS', num_lights)
            deferred_renderer.set_filter_input(
                'final_light', 'light_color', colors)
            deferred_renderer.set_filter_input(
                'final_light', 'direction', directions)

    def remove_light(self, name=None):
        """
        Removes a light from this SceneLight,
        if name is None, the 'main' light (created at init) is removed
        """
        if name is None:
            name = self.main_light_name
        if name in self.__color:
            del self.__color[name]
            del self.__direction[name]
            del self.__shadow_size[name]
            if len(self.__color) == 0:
                deferred_renderer.set_directional_light(
                    (0, 0, 0), (0, 0, 0), 0)
            elif len(self.__color) == 1:
                deferred_renderer.set_filter_define(
                    'final_light', 'NUM_LIGHTS', None)
                last_name = self.__color.keys()[0]
                deferred_renderer.set_directional_light(self.__color[last_name], self.__direction[
                    last_name], self.__shadow_size[last_name])
            else:
                num_lights = len(self.__color)
                colors = PTALVecBase3f()
                for v in self.__color.values():
                    colors.pushBack(v)
                directions = PTALVecBase3f()
                for v in self.__direction.values():
                    directions.pushBack(v)
                deferred_renderer.set_filter_define(
                    'final_light', 'NUM_LIGHTS', num_lights)
                deferred_renderer.set_filter_input(
                    'final_light', 'light_color', colors)
                deferred_renderer.set_filter_input(
                    'final_light', 'direction', directions)
            return True
        return False

    def set_color(self, color, name=None):
        """
        Sets light color
        """
        if name is None:
            name = self.main_light_name
        deferred_renderer.set_directional_light(
            color, self.__direction[name], self.__shadow_size[name])
        self.__color[name] = color

    def set_direction(self, direction, name=None):
        """
        Sets light direction
        """
        if name is None:
            name = self.main_light_name
        deferred_renderer.set_directional_light(
            self.__color[name], direction, self.__shadow_size[name])
        self.__direction[name] = direction

    def remove(self):
        deferred_renderer.set_filter_define('final_light', 'NUM_LIGHTS', None)
        deferred_renderer.set_directional_light((0, 0, 0), (0, 0, 0), 0)

    def __del__(self):
        self.remove()


class SphereLight(object):
    """
    Point (omni) light for the deferred renderer.
    Create a new SphereLight for each light you want to use,
    remember to keep a reference to the light instance
    the light will be removed by the garbage collector when it goes out of scope

    It is recomended to use properties to configure the light after creation eg.
    l=SphereLight(...)
    l.pos=Point3(...)
    l.color=(r,g,b)
    l.radius= 13
    """

    def __init__(self, color, pos, radius, shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.__radius = radius
        self.__color = color
        self.geom, self.p3d_light = deferred_renderer.add_point_light(color=color,
                                                                      model="volume/sphere",
                                                                      pos=pos,
                                                                      radius=radius,
                                                                      shadow_size=shadow_size)

    def set_color(self, color):
        """
        Sets light color
        """
        self.geom.setShaderInput("light", Vec4(
            color, self.__radius * self.__radius))
        self.__color = color

    def set_radius(self, radius):
        """
        Sets light radius
        """
        self.geom.setShaderInput("light", Vec4(self.__color, radius * radius))
        self.geom.setScale(radius)
        self.__radius = radius
        try:
            for i in range(6):
                self.p3d_light.node().getLens(i).setNearFar(0.1, radius)
        except:
            pass

    def set_pos(self, *args):
        """
        Sets light position,
        you can pass in a NodePath as the first argument to make the pos relative to that node
        """
        if len(args) < 1:
            return
        elif len(args) == 1:  # one arg, must be a vector
            pos = Vec3(args[0])
        elif len(args) == 2:  # two args, must be a node and  vector
            pos = render.getRelativePoint(args[0], Vec3(args[1]))
        elif len(args) == 3:  # vector
            pos = Vec3(args[0], args[1], args[2])
        elif len(args) == 4:  # node and vector?
            pos = render.getRelativePoint(
                args[0], Vec3(args[0], args[1], args[2]))
        else:  # something ???
            pos = Vec3(args[0], args[1], args[2])
        self.geom.setShaderInput("light_pos", Vec4(pos, 1.0))
        self.geom.set_pos(render, pos)
        self.p3d_light.set_pos(render, pos)

    def remove(self):
        self.geom.removeNode()
        try:
            buff = self.p3d_light.node().getShadowBuffer(base.win.getGsg())
            buff.clearRenderTextures()
            base.win.getGsg().getEngine().removeWindow(buff)
            self.p3d_light.node().setShadowCaster(False)
        except:
            pass
        self.p3d_light.removeNode()

    def __del__(self):
        self.remove()

    @property
    def pos(self):
        return self.geom.getPos(render)

    @pos.setter
    def pos(self, p):
        self.set_pos(p)

    @property
    def color(self):
        return self.__color

    @color.setter
    def color(self, c):
        self.set_color(c)

    @property
    def radius(self):
        return self.__radius

    @radius.setter
    def radius(self, r):
        self.set_radius(float(r))


class ConeLight(object):
    """
    Spot light for the deferred renderer.
    Create a new ConeLight for each light you want to use,
    remember to keep a reference to the light instance
    the light will be removed by the garbage collector when it goes out of scope

    You can set the hpr of the light by passing a node or position as the look_at argument

    It is recomended to use properties to configure the light after creation eg.
    l=ConeLight(...)
    l.pos=Point3(...)
    l.color=(r,g,b)
    l.radius= 13
    l.fov=45.0
    l.hpr=Point3(...)
    the lookAt() function can also be used to set a hpr in a different way
    """

    def __init__(self, color, pos, radius, fov, hpr=None, look_at=None, shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.__radius = radius
        self.__color = color
        self.__pos = pos
        self.__hpr = hpr
        self.__fov = fov
        self.shadow_size = shadow_size
        if hpr is None:
            dummy = render.attachNewNode('dummy')
            dummy.set_pos(pos)
            dummy.lookAt(look_at)
            hpr = dummy.getHpr(render)
            dummy.removeNode()
        self.__hpr = hpr
        self.geom, self.p3d_light = deferred_renderer.add_cone_light(color=color,
                                                                     pos=pos,
                                                                     hpr=hpr,
                                                                     radius=radius,
                                                                     fov=fov,
                                                                     shadow_size=shadow_size)

    def set_fov(self, fov):
        """
        Sets the Field of View (in degrees) of the light
        Angles above 120 deg are not recomended,
        Angles above 179 deg are not supported
        """
        if fov > 179.0:
            fov = 179.0
        self.p3d_light.node().getLens().set_fov(fov)
        # we might as well start from square 1...
        self.geom.removeNode()
        xy_scale = math.tan(deg2Rad(fov * 0.5))
        self.geom = loader.loadModel("volume/cone")
        self.geom.reparentTo(deferred_renderer.light_root)
        self.geom.setScale(xy_scale, 1.0, xy_scale)
        self.geom.flattenStrong()
        self.geom.setScale(self.__radius)
        self.geom.set_pos(self.__pos)
        self.geom.setHpr(self.__hpr)
        self.geom.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        self.geom.setAttrib(CullFaceAttrib.make(
            CullFaceAttrib.MCullCounterClockwise))
        self.geom.setAttrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        self.geom.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        self.geom.setShader(loader.loadShaderGLSL(deferred_renderer.v.format(
            'spot_light'), deferred_renderer.f.format('spot_light'), deferred_renderer.shading_setup))
        self.geom.setShaderInput("light_radius", float(self.__radius))
        self.geom.setShaderInput("light_pos", Vec4(self.__pos, 1.0))
        self.geom.setShaderInput("light_fov", deg2Rad(fov))
        self.geom.setShaderInput("spot", self.p3d_light)
        self.__fov = fov

    def set_radius(self, radius):
        """
        Sets the radius (range) of the light
        """
        self.geom.setShaderInput("light_radius", float(radius))
        self.geom.setScale(radius)
        self.__radius = radius
        try:
            self.p3d_light.node().getLens().setNearFar(0.1, radius)
        except:
            pass

    def setHpr(self, hpr):
        """
        Sets the HPR of a light
        """
        self.geom.setHpr(hpr)
        self.p3d_light.setHpr(hpr)
        self.__hpr = hrp

    def set_pos(self, *args):
        """
        Sets light position,
        you can pass in a NodePath as the first argument to make the pos relative to that node
        """
        if len(args) < 1:
            return
        elif len(args) == 1:  # one arg, must be a vector
            pos = Vec3(args[0])
        elif len(args) == 2:  # two args, must be a node and  vector
            pos = render.getRelativePoint(args[0], Vec3(args[1]))
        elif len(args) == 3:  # vector
            pos = Vec3(args[0], args[1], args[2])
        elif len(args) == 4:  # node and vector?
            pos = render.getRelativePoint(
                args[0], Vec3(args[0], args[1], args[2]))
        else:  # something ???
            pos = Vec3(args[0], args[1], args[2])
        self.geom.set_pos(pos)
        self.p3d_light.set_pos(pos)
        self.__pos = pos

    def lookAt(self, node_or_pos):
        """
        Sets the hpr of the light so that it looks at the given node or pos
        """
        self.look_at(node_or_pos)

    def look_at(self, node_or_pos):
        """
        Sets the hpr of the light so that it looks at the given node or pos
        """
        self.geom.lookAt(node_or_pos)
        self.p3d_light.lookAt(node_or_pos)
        self.__hpr = self.p3d_light.getHpr(render)

    def remove(self):
        self.geom.removeNode()
        try:
            buff = self.p3d_light.node().getShadowBuffer(base.win.getGsg())
            buff.clearRenderTextures()
            base.win.getGsg().getEngine().removeWindow(buff)
            self.p3d_light.node().setShadowCaster(False)
        except:
            pass
        self.p3d_light.removeNode()

    def __del__(self):
        self.remove()

    @property
    def fov(self):
        return self.__fov

    @fov.setter
    def fov(self, f):
        self.set_fov(f)

    @property
    def hpr(self):
        return self.geom.getHpr(render)

    @hpr.setter
    def hpr(self, p):
        self.setHpr(p)

    @property
    def pos(self):
        return self.geom.getPos(render)

    @pos.setter
    def pos(self, p):
        self.set_pos(p)

    @property
    def color(self):
        return self.__color

    @color.setter
    def color(self, c):
        self.set_color(c)

    @property
    def radius(self):
        return self.__radius

    @radius.setter
    def radius(self, r):
        self.set_radius(float(r))
