from __future__ import print_function
import sys
import math
#from functools import lru_cache
from direct.showbase.DirectObject import DirectObject
from panda3d.core import *
if sys.version_info >= (3, 0):
    print ("I'm on python 3.x!")
    import builtins
    basestring = str
else:
    import __builtin__ as builtins

__author__ = "wezu"
__copyright__ = "Copyright 2017"
__license__ = "ISC"
__version__ = "0.11"
__email__ = "wezu.dev@gmail.com"
__all__ = ['SphereLight', 'ConeLight', 'SceneLight', 'DeferredRenderer']


class DeferredRenderer(DirectObject):
    """
    DeferredRenderer is a singelton class that takes care of rendering
    It installs itself in the buildins,
    it also creates a deferred_render and forward_render nodes.
    """

    def __init__(self, preset='medium', filter_setup=None, shading_setup=None, shadows=None, scene_mask=1, light_mask=2):
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
        self.last_window_size = (base.win.get_x_size(), base.win.get_y_size())

        self.shadow_size=shadows

        self.modelMask = scene_mask
        self.lightMask = light_mask

        # install a wrapped version of the loader in the builtins
        builtins.loader = WrappedLoader(builtins.loader)
        loader.texture_shader_inputs = [{'input_name': 'tex_diffuse',
                                         'stage_modes': (TextureStage.M_modulate, TextureStage.M_modulate_glow, TextureStage.M_modulate_gloss),
                                         'default_texture': loader.load_texture('tex/def_diffuse.png')},
                                        {'input_name': 'tex_normal',
                                         'stage_modes': (TextureStage.M_normal, TextureStage.M_normal_height, TextureStage.M_normal_gloss),
                                         'default_texture': loader.load_texture('tex/def_normal.png')},
                                        {'input_name': 'tex_shga',  # Shine Height Alpha Glow
                                         # something different
                                         'stage_modes': (TextureStage.M_selector,),
                                         'default_texture': loader.load_texture('tex/def_shga.png')}]

        self.shading_preset = {'custom':{},
                               'full': {},
                               'medium': {'DISABLE_POM': 1, 'DISABLE_SOFTSHADOW':1},
                               'minimal': {'DISABLE_POM': 1, 'DISABLE_SOFTSHADOW':1, 'DISABLE_NORMALMAP': 1}
                               }
        # set up the deferred rendering buffers
        if shading_setup is not None:
            self.shading_setup = shading_setup
        else:
            self.shading_setup = self.shading_preset[preset]

        self._setup_g_buffer(self.shading_setup)

        self.preset = {'custom': [{'shader': 'ao',
                                 'inputs': {'random_tex': 'tex/random.png',
                                            'random_size': 64.0,
                                            'sample_rad': 0.4,
                                            'intensity': 10.0,
                                            'scale': 0.9,
                                            'bias': 0.4,
                                            'fade_distance': 80.0}},
                                {'name': 'final_light', 'shader': 'dir_light',
                                 'define': {'HALFLAMBERT': 2.0},
                                 'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                {'shader': 'bloom',
                                 'size': 0.5,
                                 'inputs': {'glow_power': 2.0}},
                                {'name': 'bloom_blur', 'shader': 'blur',
                                'translate_tex_name' :{ 'bloom': 'input_tex'},
                                 'inputs': {'blur': 3.0},
                                 'size': 0.5},
                                {'name': 'pre_aa', 'shader': 'mix',
                                 'translate_tex_name': {'final_light': 'final_color'},
                                 'define': {'DISABLE_SSR': 1},
                                 'inputs': {'lut_tex': 'tex/lut_v1.png',
                                            'noise_tex': 'tex/noise.png'}},
                                {'shader': 'fxaa',
                                 'inputs': {'span_max': 2.0,
                                            'reduce_mul': float(1.0 / 16.0),
                                            'subpix_shift': float(1.0 / 8.0)}}
                                ],
                      'full': [{'shader': 'ao',
                                 'inputs': {'random_tex': 'tex/random.png',
                                            'random_size': 64.0,
                                            'sample_rad': 0.4,
                                            'intensity': 10.0,
                                            'scale': 0.9,
                                            'bias': 0.4,
                                            'fade_distance': 80.0}},
                                {'name': 'final_light', 'shader': 'dir_light',
                                 'define': {'HALFLAMBERT': 2.0},
                                 'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                {'shader': 'fog',
                                 'inputs': {'fog_color': Vec4(0.0, 0.0, 0.0, 0.0),
                                            # start, stop, power, mix
                                            'fog_config': Vec4(25.0, 60.0, 2.0, 1.0),
                                            'dof_near': 3.0,  # 0.0..1.0 not distance!
                                            'dof_far': 55.0}},  # distance in units to full blur
                                {'shader': 'ssr', 'inputs': {}},
                                {'shader': 'bloom',
                                 'size': 0.5,
                                 'inputs': {'glow_power': 2.0}},
                                {'name': 'bloom_blur', 'shader': 'blur',
                                 'translate_tex_name' :{ 'bloom': 'input_tex'},
                                 'inputs': {'blur': 4.0},
                                 'size': 0.5},
                                {'name': 'compose', 'shader': 'mix',
                                 'translate_tex_name': {'fog': 'final_color'},
                                 'inputs': {'lut_tex': 'tex/lut_v1.png',
                                            'noise_tex': 'tex/noise.png'}},
                                {'name': 'pre_aa', 'shader': 'dof',
                                 'inputs': {'blur': 4.0}},
                                {'shader': 'fxaa',
                                 'inputs': {'span_max': 2.0,
                                            'reduce_mul': float(1.0 / 16.0),
                                            'subpix_shift': float(1.0 / 8.0)}}
                                ],
                       'minimal': [{'name': 'final_light', 'shader': 'dir_light',
                                    'define': {'HALFLAMBERT': 2.0},
                                    'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                   {'name': 'compose', 'shader': 'mix',
                                    'translate_tex_name': {'final_light': 'final_color'},
                                    'define': {'DISABLE_SSR': 1,
                                               'DISABLE_AO': 1,
                                               'DISABLE_BLOOM': 1,
                                               'DISABLE_LUT': 1,
                                               'DISABLE_DITHERING': 1},
                                    'inputs': {'lut_tex': 'tex/lut_v1.png',
                                               'noise_tex': 'tex/noise.png'}},
                                   {'shader': 'fxaa',
                                    'translate_tex_name': {'compose': 'pre_aa'},
                                    'inputs': {'span_max': 2.0,
                                               'reduce_mul': float(1.0 / 16.0),
                                               'subpix_shift': float(1.0 / 8.0)}}
                                   ],
                       'medium': [{'shader': 'ao', 'size': 0.5,
                                   'inputs': {'random_tex': 'tex/random.png',
                                              'random_size': 64.0,
                                              'sample_rad': 0.4,
                                              'intensity': 10.0,
                                              'scale': 0.9,
                                              'bias': 0.4,
                                              'fade_distance': 80.0}},
                                  {'name': 'final_light', 'shader': 'dir_light',
                                   'define': {'HALFLAMBERT': 2.0},
                                   'inputs': {'light_color': Vec3(0, 0, 0), 'direction': Vec3(0, 0, 0)}},
                                  {'shader': 'fog',
                                   'inputs': {'fog_color': Vec4(0.1, 0.1, 0.1, 0.0),
                                              # start, stop, power, mix
                                              'fog_config': Vec4(1.0, 100.0, 2.0, 1.0),
                                              'dof_near': 0.5,  # 0.0..1.0 not distance!
                                              'dof_far': 60.0}},  # distance in units to full blur
                                  {'shader': 'bloom',
                                   'size': 0.5,
                                   'inputs': {'glow_power': 5.0}},
                                  {'name': 'bloom_blur', 'shader': 'blur',
                                   'inputs': {'blur': 3.0},
                                   'size': 0.5},
                                  {'name': 'compose', 'shader': 'mix',
                                   'translate_tex_name': {'fog': 'final_color'},
                                   'define': {'DISABLE_SSR': 1},
                                   'inputs': {'lut_tex': 'tex/lut_v1.png',
                                              'noise_tex': 'tex/noise.png'}},
                                  {'shader': 'fxaa',
                                   'translate_tex_name': {'compose': 'pre_aa'},
                                   'inputs': {'span_max': 2.0,
                                              'reduce_mul': float(1.0 / 16.0),
                                              'subpix_shift': float(1.0 / 8.0)}}
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
                quad.set_shader_input(name, value)

        # stick the last stage quad to render2d
        # this is a bit ugly...
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader']
        self.filter_quad[last_stage] = self.lightbuffer.get_texture_card()
        self.reload_filter(last_stage)
        self.filter_quad[last_stage].reparent_to(render2d)

        # listen to window events so that buffers can be resized with the
        # window
        self.accept("window-event", self._on_window_event)
        # update task
        taskMgr.add(self._update, '_update_tsk', sort=5)

    def reset_filters(self, filter_setup, shading_setup=None):
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
            buff.clear_render_textures()
            base.win.get_gsg().get_engine().remove_window(buff)
        # remove quads, but keep the last one (detach it)
        # the last one should also be self.lightbuffer.get_texture_card()
        # so we don't need to keep a reference to it
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader']
        for name, quad in self.filter_quad.items():
            if name != last_stage:
                quad.remove_node()
            else:
                quad.detach_node()
        for cam in self.filter_cam.values():
            cam.remove_node()
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
                quad.set_shader_input(name, value)
        # stick the last stage quad to render2d
        # this is a bit ugly...
        if 'name' in self.filter_stages[-1]:
            last_stage = self.filter_stages[-1]['name']
        else:
            last_stage = self.filter_stages[-1]['shader']
        self.filter_quad[last_stage] = self.lightbuffer.get_texture_card()
        self.reload_filter(last_stage)
        self.filter_quad[last_stage].reparent_to(render2d)

        # reapply the directional lights
        self.set_filter_define(
            'final_light', 'NUM_LIGHTS', dir_light_num_lights)
        if dir_light_color:
            self.set_filter_input('final_light', None, dir_light_color)
            self.set_filter_input('final_light', None, dir_light_dir)

        if shading_setup != self.shading_setup:
            self.light_root.set_shader(loader.load_shader_GLSL(
                self.v.format('light'), self.f.format('light'), shading_setup))
            self.geometry_root.set_shader(loader.load_shader_GLSL(
                self.v.format('geometry'), self.f.format('geometry'), shading_setup))
            self.plain_root.set_shader(loader.load_shader_GLSL(
                self.v.format('forward'), self.f.format('forward'), shading_setup))
            self.shading_setup=shading_setup

    def reload_filter(self, stage_name):
        """
        Reloads the shader and inputs of a given filter stage
        """
        id = self._get_filter_stage_index(stage_name)
        shader = self.filter_stages[id]['shader']
        inputs = {}
        if 'inputs' in self.filter_stages[id]:
            inputs = self.filter_stages[id]['inputs']
        define = None
        if 'define' in self.filter_stages[id]:
            define = self.filter_stages[id]['define']
        self.filter_quad[stage_name].set_shader(loader.load_shader_GLSL(
            self.v.format(shader), self.f.format(shader), define))
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value = loader.load_texture(value)
            self.filter_quad[stage_name].set_shader_input(str(name), value)
        for name, value in self.common_inputs.items():
            self.filter_quad[stage_name].set_shader_input(name, value)
        if 'translate_tex_name' in self.filter_stages[id]:
            for old_name, new_name in self.filter_stages[id]['translate_tex_name'].items():
                value = self.filter_tex[old_name]
                self.filter_quad[stage_name].set_shader_input(
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
            elif stage['shader'] == name:
                return index
        raise IndexError('No stage named ' + name)

    def get_filter_input(self, stage_name, name):
        """
        Returns the shader input from a given stage
        """
        if stage_name in self.filter_quad:
            id = self._get_filter_stage_index(stage_name)
            return self.filter_quad[stage_name].get_shader_input(str(name))
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
                self.filter_quad[stage_name].set_shader_input(value)
                return
            if modify_using is not None:
                value = modify_using(self.filter_stages[id][
                                     'inputs'][name], value)
                self.filter_stages[id]['inputs'][name] = value
            if isinstance(value, basestring):
                tex = loader.load_texture(value, sRgb='srgb'in value)
                if 'nearest' in value:
                    tex.set_magfilter(SamplerState.FT_nearest)
                    tex.set_minfilter(SamplerState.FT_nearest)
                if 'f_rgb16' in value:
                    tex.set_format(Texture.F_rgb16)
                if 'clamp' in value:
                    tex.set_wrap_u(Texture.WMClamp)
                    tex.set_wrap_v(Texture.WMClamp)
                value=tex
            self.filter_quad[stage_name].set_shader_input(str(name), value)
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
        self.depth.set_wrap_u(Texture.WM_clamp)
        self.depth.set_wrap_v(Texture.WM_clamp)
        self.depth.set_format(Texture.F_depth_component32)
        self.depth.set_component_type(Texture.T_float)
        self.albedo = Texture()
        self.normal = Texture()
        self.normal.set_format(Texture.F_rgba16)
        self.normal.set_component_type(Texture.T_float)
        self.lit_tex = Texture()
        self.lit_tex.set_wrap_u(Texture.WM_clamp)
        self.lit_tex.set_wrap_v(Texture.WM_clamp)

        self.modelbuffer.add_render_texture(tex=self.depth,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPDepth)
        self.modelbuffer.add_render_texture(tex=self.albedo,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPColor)
        self.modelbuffer.add_render_texture(tex=self.normal,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPAuxRgba0)
        self.lightbuffer.add_render_texture(tex=self.lit_tex,
                                          mode=GraphicsOutput.RTMBindOrCopy,
                                          bitplane=GraphicsOutput.RTPColor)
        # Set the near and far clipping planes.
        base.cam.node().get_lens().set_near_far(3.0, 70.0)
        lens = base.cam.node().get_lens()

        # This algorithm uses three cameras: one to render the models into the
        # model buffer, one to render the lights into the light buffer, and
        # one to render "plain" stuff (non-deferred shaded) stuff into the
        # light buffer.  Each camera has a bitmask to identify it.
        # self.modelMask = 1
        # self.lightMask = 2

        self.modelcam = base.make_camera(win=self.modelbuffer,
                                        lens=lens,
                                        scene=render,
                                        mask=BitMask32.bit(self.modelMask))
        self.lightcam = base.make_camera(win=self.lightbuffer,
                                        lens=lens,
                                        scene=render,
                                        mask=BitMask32.bit(self.lightMask))

        # Panda's main camera is not used.
        base.cam.node().setActive(0)

        # Take explicit control over the order in which the three
        # buffers are rendered.
        self.modelbuffer.setSort(1)
        self.lightbuffer.setSort(2)
        base.win.setSort(3)

        # Within the light buffer, control the order of the two cams.
        self.lightcam.node().get_display_region(0).setSort(1)

        # By default, panda usually clears the screen before every
        # camera and before every window.  Tell it not to do that.
        # Then, tell it specifically when to clear and what to clear.
        self.modelcam.node().get_display_region(0).disable_clears()
        self.lightcam.node().get_display_region(0).disable_clears()
        base.cam.node().get_display_region(0).disable_clears()
        base.cam2d.node().get_display_region(0).disable_clears()
        self.modelbuffer.disable_clears()
        base.win.disable_clears()

        self.modelbuffer.set_clear_color_active(1)
        self.modelbuffer.set_clear_depth_active(1)
        self.lightbuffer.set_clear_color_active(1)
        self.lightbuffer.set_clear_color((0, 0, 0, 0))
        self.modelbuffer.set_clear_color((0, 0, 0, 0))
        self.modelbuffer.set_clear_active(GraphicsOutput.RTPAuxRgba0, True)

        render.set_state(RenderState.make_empty())

        # Create two subroots, to help speed cull traversal.
        # root node and a list for the lights
        self.light_root = render.attach_new_node('light_root')
        self.light_root.set_shader(loader.load_shader_GLSL(
            self.v.format('light'), self.f.format('light'), define))
        self.light_root.set_shader_input("albedo_tex", self.albedo)
        self.light_root.set_shader_input("depth_tex", self.depth)
        self.light_root.set_shader_input("normal_tex", self.normal)
        self.light_root.set_shader_input('win_size', Vec2(
            base.win.get_x_size(), base.win.get_y_size()))
        self.light_root.hide(BitMask32.bit(self.modelMask))
        self.light_root.set_shader_input('camera', base.cam)
        self.light_root.set_shader_input('render', render)
        # self.light_root.hide(BitMask32(self.plainMask))

        self.geometry_root = render.attach_new_node('geometry_root')
        self.geometry_root.set_shader(loader.load_shader_GLSL(
            self.v.format('geometry'), self.f.format('geometry'), define))
        self.geometry_root.hide(BitMask32.bit(self.lightMask))
        # self.geometry_root.hide(BitMask32(self.plainMask))

        self.plain_root, self.plain_tex, self.plain_cam, self.plain_buff = self._make_forward_stage()
        self.plain_root.set_shader(loader.load_shader_GLSL(
            self.v.format('forward'), self.f.format('forward'), define))
        self.plain_root.set_shader_input("depth_tex", self.depth)
        self.plain_root.set_shader_input('win_size', Vec2(
            base.win.get_x_size(), base.win.get_y_size()))
        mask=BitMask32.bit(self.modelMask)
        #mask.set_bit(self.lightMask)
        self.plain_root.hide(mask)

        #set aa
        #render.setAntialias(AntialiasAttrib.M_multisample)

        # instal into buildins
        builtins.deferred_render = self.geometry_root
        builtins.forward_render = self.plain_root

    def _on_window_event(self, window):
        """
        Function called when something hapens to the main window
        Currently it's only function is to resize all the buffers to fit
        the new size of the window if the size of the window changed
        """
        if window is not None:
            window_size = (base.win.get_x_size(), base.win.get_y_size())
            if self.last_window_size != window_size:
                self.modelbuffer.set_size(window_size[0], window_size[1])
                self.lightbuffer.set_size(window_size[0], window_size[1])
                self.plain_buff.set_size(window_size[0]//2, window_size[1]//2)
                for buff in self.filter_buff.values():
                    old_size = buff.get_fb_size()
                    x_factor = float(old_size[0]) / \
                        float(self.last_window_size[0])
                    y_factor = float(old_size[1]) / \
                        float(self.last_window_size[1])
                    buff.set_size(
                        int(window_size[0] * x_factor), int(window_size[1] * y_factor))
                self.last_window_size = window_size

    def add_filter(self, shader, inputs={},
                   name=None, size=1.0,
                   clear_color=(0, 0, 0, 0), translate_tex_name=None,
                   define=None):
        """
        Creates and adds filter stage to the filter stage dicts:
        the created buffer is put in self.filter_buff[name]
        the created fullscreen quad is put in self.filter_quad[name]
        the created fullscreen texture is put in self.filter_tex[name]
        the created camera is put in self.filter_cam[name]
        """
        #print(inputs)
        if name is None:
            name = shader
        index = len(self.filter_buff)
        quad, tex, buff, cam = self._make_filter_stage(
            sort=index, size=size, clear_color=clear_color, name=name)
        self.filter_buff[name] = buff
        self.filter_quad[name] = quad
        self.filter_tex[name] = tex
        self.filter_cam[name] = cam

        quad.set_shader(loader.load_shader_GLSL(self.v.format(
            shader), self.f.format(shader), define))
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value = loader.load_texture(value, sRgb=loader.use_srgb)
            quad.set_shader_input(str(name), value)
        if translate_tex_name:
            for old_name, new_name in translate_tex_name.items():
                value = self.filter_tex[old_name]
                quad.set_shader_input(str(new_name), value)

    def _make_filter_stage(self, sort=0, size=1.0, clear_color=None, name=None):
        """
        Creates a buffer, quad, camera and texture needed for a filter stage
        Use add_filter() not this function
        """
        # make a root for the buffer
        root = NodePath("filterBufferRoot")
        tex = Texture()
        tex.set_wrap_u(Texture.WM_clamp)
        tex.set_wrap_v(Texture.WM_clamp)
        buff_size_x = int(base.win.get_x_size() * size)
        buff_size_y = int(base.win.get_y_size() * size)
        # buff=base.win.makeTextureBuffer("buff", buff_size_x, buff_size_y, tex)
        winprops = WindowProperties()
        winprops.set_size(buff_size_x, buff_size_y)
        props = FrameBufferProperties()
        props.set_rgb_color(True)
        props.set_rgba_bits(8, 8, 8, 8)
        props.set_depth_bits(0)
        buff = base.graphicsEngine.make_output(
            base.pipe, 'filter_stage_'+name, sort,
            props, winprops,
            GraphicsPipe.BF_resizeable,
            base.win.get_gsg(), base.win)
        buff.add_render_texture(
            tex=tex, mode=GraphicsOutput.RTMBindOrCopy, bitplane=GraphicsOutput.RTPColor)
        # buff.setSort(sort)
        # buff.setSort(0)
        if clear_color is None:
            buff.set_clear_active(GraphicsOutput.RTPColor, False)
        else:
            buff.set_clear_color(clear_color)
            buff.set_clear_active(GraphicsOutput.RTPColor, True)

        cam = base.make_camera(win=buff)
        cam.reparent_to(root)
        cam.set_pos(buff_size_x * 0.5, buff_size_y * 0.5, 100)
        cam.setP(-90)
        lens = OrthographicLens()
        lens.set_film_size(buff_size_x, buff_size_y)
        cam.node().set_lens(lens)
        # plane with the texture, a blank texture for now
        cm = CardMaker("plane")
        cm.setFrame(0, buff_size_x, 0, buff_size_y)
        quad = root.attach_new_node(cm.generate())
        quad.look_at(0, 0, -1)
        quad.set_light_off()
        return quad, tex, buff, cam

    def _make_forward_stage(self):
        """
        Creates nodes, buffers and whatnot needed for forward rendering
        """
        root = NodePath("forwardRoot")
        tex = Texture()
        tex.set_wrap_u(Texture.WM_clamp)
        tex.set_wrap_v(Texture.WM_clamp)
        buff_size_x = int(base.win.get_x_size()/2)
        buff_size_y = int(base.win.get_y_size()/2)

        winprops = WindowProperties()
        winprops.set_size(buff_size_x, buff_size_y)
        props = FrameBufferProperties()
        props.set_rgb_color(True)
        props.set_rgba_bits(8, 8, 8, 8)
        props.set_depth_bits(0)
        buff = base.graphicsEngine.make_output(
            base.pipe, 'forward_stage', 2,
            props, winprops,
            GraphicsPipe.BF_resizeable,
            base.win.get_gsg(), base.win)
        buff.add_render_texture(
            tex=tex, mode=GraphicsOutput.RTMBindOrCopy, bitplane=GraphicsOutput.RTPColor)
        buff.set_clear_color((0, 0, 0, 0))
        cam = base.make_camera(win=buff)
        cam.reparent_to(root)
        lens = base.cam.node().get_lens()
        cam.node().set_lens(lens)
        mask = BitMask32.bit(self.modelMask)
        mask.set_bit(self.lightMask)
        cam.node().set_camera_mask(mask)
        return root, tex, cam, buff

    def set_directional_light(self, color, direction, shadow_size=0):
        """
        Sets value for a directional light,
        use the SceneLight class to set the lights!
        """
        self.filter_quad['final_light'].set_shader_input('light_color', color)
        self.filter_quad['final_light'].set_shader_input('direction', direction)

    def add_cone_light(self, color, pos=(0, 0, 0), hpr=(0, 0, 0), radius=1.0, fov=45.0, shadow_size=0.0):
        """
        Creates a spotlight,
        use the ConeLight class, not this function!
        """
        if fov > 179.0:
            fov = 179.0
        xy_scale = math.tan(deg2Rad(fov * 0.5))
        model = loader.load_model("models/cone")
        # temp=model.copyTo(self.plain_root)
        # self.lights.append(model)
        model.reparent_to(self.light_root)
        model.set_scale(xy_scale, 1.0, xy_scale)
        model.flatten_strong()
        model.set_scale(radius)
        model.set_pos(pos)
        model.setHpr(hpr)
        # debug=self.lights[-1].copyTo(self.plain_root)
        model.set_attrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.set_attrib(CullFaceAttrib.make(
            CullFaceAttrib.MCullCounterClockwise))
        model.set_attrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.set_attrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))

        model.set_shader(loader.load_shader_GLSL(self.v.format(
            'spot_light'), self.f.format('spot_light'), self.shading_setup))
        model.set_shader_input("light_radius", float(radius))
        model.set_shader_input("light_pos", Vec4(pos, 1.0))
        model.set_shader_input("light_fov", deg2Rad(fov))
        p3d_light = render.attach_new_node(Spotlight("Spotlight"))
        p3d_light.set_pos(render, pos)
        p3d_light.setHpr(render, hpr)
        p3d_light.node().set_exponent(20)
        p3d_light.node().set_color(Vec4(color, 1.0))
        if shadow_size > 0.0:
            p3d_light.node().set_shadow_caster(True, shadow_size, shadow_size)
            model.set_shader_input("bias", 0.001)
            model.set_shader(loader.load_shader_GLSL(self.v.format(
            'spot_light_shadow'), self.f.format('spot_light_shadow'), self.shading_setup))
        # p3d_light.node().set_camera_mask(self.modelMask)
        model.set_shader_input("spot", p3d_light)
        #p3d_light.node().showFrustum()
        p3d_light.node().get_lens().set_fov(fov)
        p3d_light.node().get_lens().set_far(radius)
        p3d_light.node().get_lens().set_near(1.0)
        return model, p3d_light

    def add_point_light(self, color, model="models/sphere", pos=(0, 0, 0), radius=1.0, shadow_size=0):
        """
        Creates a omni (point) light,
        Use the SphereLight class to create lights!!!
        """
        # light geometry
        # if we got a NodePath we use it as the geom for the light
        if not isinstance(model, NodePath):
            model = loader.load_model(model)
        # self.lights.append(model)
        model.reparent_to(self.light_root)
        model.set_pos(pos)
        model.set_scale(radius*1.1)
        model.set_shader(loader.load_shader_GLSL(self.v.format(
            'light'), self.f.format('light'), self.shading_setup))
        model.set_attrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.set_attrib(CullFaceAttrib.make(
            CullFaceAttrib.MCullCounterClockwise))
        model.set_attrib(ColorBlendAttrib.make(
            ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.set_attrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        # shader inpts
        model.set_shader_input("light", Vec4(color, radius * radius))
        model.set_shader_input("light_pos", Vec4(pos, 1.0))
        if shadow_size > 0:
            model.set_shader(loader.load_shader_GLSL(self.v.format(
                'light_shadow'), self.f.format('light_shadow'), self.shading_setup))
            p3d_light = render.attach_new_node(PointLight("PointLight"))
            p3d_light.set_pos(render, pos)
            p3d_light.node().set_shadow_caster(True, shadow_size, shadow_size)
            #p3d_light.node().set_camera_mask(self.modelMask)
            p3d_light.node().set_camera_mask(BitMask32.bit(13))
            #p3d_light.node().showFrustum()
            for i in range(6):
                p3d_light.node().get_lens(i).set_near_far(0.1, radius)
                #p3d_light.node().get_lens(i).makeBounds()
            #p3d_light.node().setBounds(OmniBoundingVolume())
            #p3d_light.node().setFinal(True)

            model.set_shader_input("shadowcaster", p3d_light)
            model.set_shader_input("near", 0.1)
            model.set_shader_input("bias", (1.0/radius)*0.095)
        else:
            p3d_light = render.attach_new_node('dummy_node')
        return model, p3d_light

    def _make_FBO(self, name, auxrgba=0, multisample=0, srgb=False):
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
        props.set_rgb_color(True)
        props.set_rgba_bits(8, 8, 8, 8)
        props.set_depth_bits(16)
        props.set_aux_rgba(auxrgba)
        props.set_srgb_color(srgb)
        if multisample>0:
            props.set_multisamples(multisample)
        return base.graphicsEngine.make_output(
            base.pipe, name, -2,
            props, winprops,
            GraphicsPipe.BFSizeTrackHost | GraphicsPipe.BFCanBindEvery |
            GraphicsPipe.BFRttCumulative | GraphicsPipe.BFRefuseWindow,
            base.win.get_gsg(), base.win)

    def _update(self, task):
        """
        Update task, currently only updates the forward rendering camera pos/hpr
        """
        self.plain_cam.set_pos_hpr(base.cam.get_pos(render), base.cam.get_hpr(render))
        return task.again

# this will replace the default Loader


class WrappedLoader(object):

    def __init__(self, original_loader):
        self.original_loader = original_loader
        self.texture_shader_inputs = []
        self.use_srgb = ConfigVariableBool('framebuffer-srgb').getValue()
        self.shader_cache = {}

    def _from_snake_case(self, attr):
        camel_case=''
        up=False
        for char in attr:
            if up:
                char=char.upper()
            if char == "_":
                up=True
            else:
                up=False
                camel_case+=char
        return camel_case

    #@lru_cache(maxsize=64)
    def __getattr__(self,attr):
        new_attr=self._from_snake_case(attr)
        if hasattr(self, new_attr):
            return self.__getattribute__(new_attr)

    def fix_transparency(self, model):
        for tex_stage in model.findAllTextureStages():
            tex = model.findTexture(tex_stage)
            if tex:
                mode = tex_stage.getMode()
                tex_format = tex.getFormat()
                if mode == TextureStage.M_modulate and (tex_format == Texture.F_rgba or tex_format == Texture.F_srgb_alpha):
                    return
        model.setTransparency(TransparencyAttrib.MNone, 1)
        #model.clear_transparency()

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
        #print ('Fixing model', model)
        slots_filled = set()
        # find all the textures, easy mode - slot is fitting the stage mode
        # (eg. slot0 is diffuse/color)
        for slot, tex_stage in enumerate(model.findAllTextureStages()):
            if slot >= len(self.texture_shader_inputs):
                break
            tex = model.findTexture(tex_stage)
            if tex:
                #print('Found tex:', tex.getFilename())
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
            if slot >= len(self.texture_shader_inputs):
                break
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
        #print ('Fail for model:', model)
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

        if self.use_srgb:
            self.fixSrgbTextures(model)
        self.setTextureInputs(model)
        self.fix_transparency(model)
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
        with open(getModelPath().findFile(v_shader).toOsSpecific()) as f:
            v_shader_txt = f.read()
        with open(getModelPath().findFile(f_shader).toOsSpecific()) as f:
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
        try:
            shader.set_filename(Shader.ST_vertex, v_shader)
            shader.set_filename(Shader.ST_fragment, f_shader)
        except:
            print('Shader filenames will not be available, consider using a dev version of Panda3D')
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
        self.__color[name] = color
        if len(self.__color) == 1:
            deferred_renderer.set_directional_light(
                color, self.__direction[name], self.__shadow_size[name])
        else:
            colors = PTALVecBase3f()
            for v in self.__color.values():
                colors.pushBack(v)
            deferred_renderer.set_filter_input(
                    'final_light', 'light_color', colors)

    def set_direction(self, direction, name=None):
        """
        Sets light direction
        """
        if name is None:
            name = self.main_light_name
        self.__direction[name] = direction
        if len(self.__color) == 1:
            deferred_renderer.set_directional_light(
                self.__color[name], direction, self.__shadow_size[name])
        else:
            directions = PTALVecBase3f()
            for v in self.__direction.values():
                directions.pushBack(v)
            deferred_renderer.set_filter_input(
                    'final_light', 'direction', directions)

    def remove(self):
        deferred_renderer.set_filter_define('final_light', 'NUM_LIGHTS', None)
        deferred_renderer.set_directional_light((0, 0, 0), (0, 0, 0), 0)

    def __del__(self):
        try:
            self.remove()
        except:
            pass


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

    def __init__(self, color, pos, radius, shadow_size=None, shadow_bias=None):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.__radius = radius
        self.__color = color
        if shadow_size is None:
            shadow_size=deferred_renderer.shadow_size
        self.geom, self.p3d_light = deferred_renderer.add_point_light(color=color,
                                                                      model="models/sphere",
                                                                      pos=pos,
                                                                      radius=radius,
                                                                      shadow_size=shadow_size)
        if shadow_bias:
            self.set_shadow_bias(shadow_bias)

    def set_shadow_size(self, size):
        self.p3d_light.node().set_shadow_caster(True, size, size)

    def set_shadow_bias(self, bias):
        self.geom.setShaderInput("bias", bias)

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
        #self.geom.setShaderInput("light_pos", Vec4(pos, 1.0))
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
        try:
            self.remove()
        except:
            pass

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
    def set_color(self, color):
        self.p3d_light.node().set_color(Vec4(color))

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
        self.geom = loader.load_model("models/cone")
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
        self.geom.set_shader_input("light_radius", float(self.__radius))
        self.geom.set_shader_input("light_pos", Vec4(self.__pos, 1.0))
        self.geom.set_shader_input("light_fov", deg2Rad(fov))
        self.geom.set_shader_input("spot", self.p3d_light)
        self.__fov = fov

    def set_radius(self, radius):
        """
        Sets the radius (range) of the light
        """
        self.geom.set_shader_input("light_radius", float(radius))
        self.geom.set_scale(radius)
        self.__radius = radius
        try:
            self.p3d_light.node().get_lens().set_near_far(0.1, radius)
        except:
            pass

    def setHpr(self, hpr):
        """
        Sets the HPR of a light
        """
        self.geom.set_hpr(hpr)
        self.p3d_light.set_hpr(hpr)
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
            pos = render.get_relative_point(args[0], Vec3(args[1]))
        elif len(args) == 3:  # vector
            pos = Vec3(args[0], args[1], args[2])
        elif len(args) == 4:  # node and vector?
            pos = render.get_relative_point(
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
        self.geom.look_at(node_or_pos)
        self.p3d_light.look_at(node_or_pos)
        self.__hpr = self.p3d_light.get_hpr(render)

    def remove(self):
        self.geom.removeNode()
        try:
            buff = self.p3d_light.node().get_shadow_buffer(base.win.getGsg())
            buff.clear_render_textures()
            base.win.get_gsg().get_engine().remove_window(buff)
            self.p3d_light.node().set_shadow_caster(False)
        except:
            pass
        self.p3d_light.removeNode()

    def __del__(self):
        try:
            self.remove()
        except:
            pass

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
