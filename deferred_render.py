import sys
if sys.version_info >= (3, 0):
    import builtins
    basestring = str
else:
    import __builtin__ as builtins
import math
from collections  import defaultdict
from panda3d.core import *
from direct.showbase.DirectObject import DirectObject

__all__ = ['SphereLight','ConeLight','SceneLight','DeferredRenderer']

class DeferredRenderer(DirectObject):
    def __init__(self, preset='medium', filter_setup=None, shading_setup=None, scene_mask=1, light_mask=2):
        #check if there are other DeferredRenderer in buildins
        if hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('There can only be one DeferredRenderer')

        builtins.deferred_renderer=self
        #template to load the shaders by name, without the directory and extension
        self.f='shaders/{}_f.glsl'
        self.v='shaders/{}_v.glsl'
        #last known window size, needed to test on window events if the window size changed
        self.last_window_size=(base.win.getXSize(), base.win.getYSize())

        #install a wrapped version of the loader in the builtins
        builtins.loader=WrappedLoader(builtins.loader)
        loader.texture_shader_inputs=[{'input_name':'tex_diffuse',
                                    'stage_modes':(TextureStage.M_modulate, TextureStage.M_modulate_glow,  TextureStage.M_modulate_gloss),
                                    'default_texture':loader.loadTexture('data/def_diffuse.png')},
                                    {'input_name':'tex_normal',
                                    'stage_modes':(TextureStage.M_normal, TextureStage.M_normal_height, TextureStage.M_normal_gloss),
                                    'default_texture':loader.loadTexture('data/def_normal.png')},
                                    {'input_name':'tex_shga',#Shine Height Alpha Glow
                                    'stage_modes':(TextureStage.M_selector,),#something different
                                    'default_texture':loader.loadTexture('data/def_shga.png')}]

        self.shading_preset={'full':{},
                            'medium':{'DISABLE_POM':1},
                            'minimal':{'DISABLE_POM':1, 'DISABLE_SHADOWS':1}
                           }
        #set up the deferred rendering buffers
        if shading_setup:
            self.shading_setup=shading_setup
        else:
            self.shading_setup=self.shading_preset[preset]

        self.setupGbuffer(self.shading_setup)

        self.preset={'full':[{'shader_name':'ao',
                             'inputs':{'random_tex':'data/random.png',
                                       'random_size':64.0,
                                        'sample_rad': 0.4,
                                        'intensity': 10.0,
                                        'scale': 0.9,
                                        'bias': 0.4,
                                        'fade_distance': 80.0}},
                            {'name':'final_light','shader_name':'dir_light',
                            'define':{'HALFLAMBERT':2.0},
                            'inputs':{'light_color': Vec3(0,0,0),'direction':Vec3(0,0,0)}},
                            {'name':'final_color','shader_name':'fog',
                            'inputs':{'fog_color': Vec4(0.1, 0.1, 0.1, 0.0),
                                      'fog_config': Vec4(10.0, 100.0, 2.0, 1.0), #start, stop, power, mix
                                      'dof_near': 0.5, #0.0..1.0 not distance!
                                      'dof_far': 60.0}}, #distance in units to full blur
                            {'shader_name':'ssr','inputs':{}},
                            {'shader_name':'bloom',
                            'size_factor':0.5,
                            'inputs':{'glow_power': 5.0}},
                            {'name':'bloom_blur', 'shader_name':'blur',
                             'inputs':{'blur':3.0},
                             'size_factor':0.5},
                            {'name':'compose','shader_name':'mix',
                            'inputs':{'lut_tex':'data/lut_v1.png',
                                      'noise_tex':'data/noise.png'}},
                            {'name':'pre_aa','shader_name':'dof',
                             'inputs':{'blur':6.0}},
                            {'shader_name':'fxaa',
                            'inputs':{ 'FXAA_SPAN_MAX' : 2.0,
                                       'FXAA_REDUCE_MUL': float(1.0/16.0),
                                       'FXAA_SUBPIX_SHIFT': float(1.0/8.0)}}
                            ],
                    'minimal':[{'name':'final_light','shader_name':'dir_light',
                                'define':{'HALFLAMBERT':1.0},
                                'inputs':{'light_color': Vec3(0,0,0),'direction':Vec3(0,0,0)}},
                               {'name':'compose','shader_name':'mix',
                               'translate_tex_name':{'final_light':'final_color'},
                                'define':{'DISABLE_SSR':1,
                                          'DISABLE_AO':1,
                                          'DISABLE_BLOOM':1,
                                          'DISABLE_LUT':1,
                                          'DISABLE_DITHERING':1},
                                'inputs':{'lut_tex':'data/lut_v1.png',
                                      'noise_tex':'data/noise.png'}},
                               {'shader_name':'fxaa',
                               'translate_tex_name':{'compose':'pre_aa'},
                                'inputs':{'FXAA_SPAN_MAX' : 2.0,
                                          'FXAA_REDUCE_MUL': float(1.0/16.0),
                                          'FXAA_SUBPIX_SHIFT': float(1.0/8.0)}}
                             ],
                    'medium':[{'shader_name':'ao', 'size_factor':0.5,
                             'inputs':{'random_tex':'data/random.png',
                                       'random_size':64.0,
                                        'sample_rad': 0.4,
                                        'intensity': 10.0,
                                        'scale': 0.9,
                                        'bias': 0.4,
                                        'fade_distance': 80.0}},
                            {'name':'final_light','shader_name':'dir_light',
                            'define':{'HALFLAMBERT':2.0},
                            'inputs':{'light_color': Vec3(0,0,0),'direction':Vec3(0,0,0)}},
                            {'name':'final_color','shader_name':'fog',
                            'inputs':{'fog_color': Vec4(0.1, 0.1, 0.1, 0.0),
                                      'fog_config': Vec4(1.0, 100.0, 2.0, 1.0), #start, stop, power, mix
                                      'dof_near': 0.5, #0.0..1.0 not distance!
                                      'dof_far': 60.0}}, #distance in units to full blur
                            {'shader_name':'bloom',
                            'size_factor':0.5,
                            'inputs':{'glow_power': 5.0}},
                            {'name':'bloom_blur', 'shader_name':'blur',
                             'inputs':{'blur':3.0},
                             'size_factor':0.5},
                             {'name':'compose','shader_name':'mix',
                             'define':{'DISABLE_SSR':1},
                             'inputs':{'lut_tex':'data/lut_v1.png',
                                      'noise_tex':'data/noise.png'}},
                            {'shader_name':'fxaa',
                            'translate_tex_name':{'compose':'pre_aa'},
                            'inputs':{ 'FXAA_SPAN_MAX' : 2.0,
                                       'FXAA_REDUCE_MUL': float(1.0/16.0),
                                       'FXAA_SUBPIX_SHIFT': float(1.0/8.0)}}
                            ]
                    }


        #post process
        self.filter_buff={}
        self.filter_quad={}
        self.filter_tex={}
        self.common_inputs={'render':render,
                            'camera': base.cam,
                            'depth_tex': self.depth,
                            'normal_tex': self.normal,
                            'albedo_tex': self.albedo,
                            'lit_tex': self.lit_tex,
                            'forward_tex':self.plain_tex}
        if filter_setup:
            self.filter_stages=filter_setup
        else:
            self.filter_stages=self.preset[preset]

        for stage in self.filter_stages[:-1]:
            self.addFilter(**stage)
        for name, tex in self.filter_tex.items():
            self.common_inputs[name]=tex
        for name, value in self.common_inputs.items():
            for filter_name, quad in self.filter_quad.items():
                quad.setShaderInput(name, value)

        #stick the last stage quad to render2d
        #this is a bit ugly...
        if 'name' in self.filter_stages[-1]:
            last_stage=self.filter_stages[-1]['name']
        else:
            last_stage=self.filter_stages[-1]['shader_name']
        self.filter_quad[last_stage]=self.lightbuffer.getTextureCard()
        self.reloadFilter(last_stage)
        self.filter_quad[last_stage].reparentTo(render2d)

        #listen to window events so that buffers can be resized with the window
        self.accept("window-event", self.on_window_event)
        #update task
        taskMgr.add(self.update, 'update_tsk')

    def reloadFilter(self, stage_name):
        id=self.getFilterStageIndex(stage_name)
        shader_name=self.filter_stages[id]['shader_name']
        inputs={}
        if 'inputs' in self.filter_stages[id]:
            inputs=self.filter_stages[id]['inputs']
        define=None
        if 'define' in self.filter_stages[id]:
            define=self.filter_stages[id]['define']
        self.filter_quad[stage_name].setShader(loader.loadShaderGLSL(self.v.format(shader_name), self.f.format(shader_name), define))
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value=loader.loadTexture(value)
            self.filter_quad[stage_name].setShaderInput(str(name), value)
        for name, value in self.common_inputs.items():
            self.filter_quad[stage_name].setShaderInput(name, value)
        if 'translate_tex_name' in self.filter_stages[id]:
            for old_name, new_name in self.filter_stages[id]['translate_tex_name'].items():
                value=self.filter_tex[old_name]
                self.filter_quad[stage_name].setShaderInput(str(new_name), value)

    def getFilterDefine(self, stage_name, name):
        if stage_name in self.filter_quad:
            id=self.getFilterStageIndex(stage_name)
            if 'define' in self.filter_stages[id]:
                if name in self.filter_stages[id]['define']:
                    return self.filter_stages[id]['define'][name]
        return None

    def setFilterDefine(self, stage_name, name, value):
        if stage_name in self.filter_quad:
            id=self.getFilterStageIndex(stage_name)
            if 'define' in self.filter_stages[id]:
                if value is None:
                    del self.filter_stages[id]['define'][name]
                else:
                    self.filter_stages[id]['define'][name]=value
            elif value is not None:
                self.filter_stages[id]['define']={name:value}
            #reload the shader
            self.reloadFilter(stage_name)

    def getFilterStageIndex(self, name):
        for index, stage in enumerate(self.filter_stages):
            if 'name' in stage:
                if stage['name']==name:
                    return index
            elif stage['shader_name']==name:
                return index
        raise IndexError('No stage named '+name)

    def setFilterInput(self, stage_name, name, value, modify_using=None):
        if stage_name in self.filter_quad:
            id=self.getFilterStageIndex(stage_name)
            if modify_using is not None:
                value=modify_using(self.filter_stages[id]['inputs'][name], value)
                self.filter_stages[id]['inputs'][name]=value
            if isinstance(value, basestring):
                value=loader.loadTexture(value)
            self.filter_quad[stage_name].setShaderInput(str(name), value)
            #print stage_name, name, value

    def setupGbuffer(self, define=None):
        self.modelbuffer = self.makeFBO("model buffer", 1)
        self.lightbuffer = self.makeFBO("light buffer", 0)

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

        self.modelbuffer.addRenderTexture(tex = self.depth,
                                          mode = GraphicsOutput.RTMBindOrCopy,
                                          bitplane  = GraphicsOutput.RTPDepth)
        self.modelbuffer.addRenderTexture(tex = self.albedo,
                                          mode = GraphicsOutput.RTMBindOrCopy,
                                          bitplane  = GraphicsOutput.RTPColor)
        self.modelbuffer.addRenderTexture(tex = self.normal,
                                          mode = GraphicsOutput.RTMBindOrCopy,
                                          bitplane  = GraphicsOutput.RTPAuxRgba0)
        self.lightbuffer.addRenderTexture(tex = self.lit_tex,
                                          mode = GraphicsOutput.RTMBindOrCopy,
                                          bitplane  = GraphicsOutput.RTPColor)
        # Set the near and far clipping planes.
        base.cam.node().getLens().setNearFar(1.0, 500.0)
        lens = base.cam.node().getLens()

        # This algorithm uses three cameras: one to render the models into the
        # model buffer, one to render the lights into the light buffer, and
        # one to render "plain" stuff (non-deferred shaded) stuff into the
        # light buffer.  Each camera has a bitmask to identify it.
        self.modelMask = 1
        self.lightMask = 2

        self.modelcam = base.makeCamera(win = self.modelbuffer,
                                        lens = lens,
                                        scene = render,
                                        mask = self.modelMask)
        self.lightcam = base.makeCamera(win = self.lightbuffer,
                                        lens = lens,
                                        scene = render,
                                        mask = self.lightMask)

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
        #root node and a list for the lights
        self.light_root=render.attachNewNode('light_root')
        self.light_root.setShader(loader.loadShaderGLSL( self.v.format('light'), self.f.format('light'), define))
        self.light_root.setShaderInput("albedo_tex", self.albedo)
        self.light_root.setShaderInput("depth_tex", self.depth)
        self.light_root.setShaderInput("normal_tex", self.normal)
        self.light_root.setShaderInput('win_size', Vec2(base.win.getXSize(), base.win.getYSize()))
        self.light_root.hide(BitMask32(self.modelMask))
        self.light_root.setShaderInput('camera', base.cam)
        self.light_root.setShaderInput('render', render)
        #self.light_root.hide(BitMask32(self.plainMask))

        self.geometry_root=render.attachNewNode('geometry_root')
        self.geometry_root.setShader(loader.loadShaderGLSL( self.v.format('geometry'), self.f.format('geometry'), define))
        self.geometry_root.hide(BitMask32(self.lightMask))
        #self.geometry_root.hide(BitMask32(self.plainMask))

        self.plain_root, self.plain_tex, self.plain_cam, self.plain_buff=self.makeForwardStage()
        self.plain_root.setShader(loader.loadShaderGLSL( self.v.format('forward'), self.f.format('forward'), define))
        self.plain_root.setShaderInput("depth_tex", self.depth)
        self.plain_root.setShaderInput('win_size', Vec2(base.win.getXSize(), base.win.getYSize()))
        self.plain_root.hide(BitMask32(self.lightMask))
        self.plain_root.hide(BitMask32(self.modelMask))

        #instal into buildins
        builtins.defered_render=self.geometry_root
        builtins.forward_render=self.plain_root

    def on_window_event(self, window):
        if window is not None:
            window_size=(base.win.getXSize(), base.win.getYSize())
            if self.last_window_size != window_size:
                self.modelbuffer.setSize(window_size[0],window_size[1])
                self.lightbuffer.setSize(window_size[0],window_size[1])
                self.plain_buff.setSize(window_size[0],window_size[1])
                for buff in self.filter_buff.values():
                    old_size=buff.getFbSize()
                    x_factor=float(old_size[0])/float(self.last_window_size[0])
                    y_factor=float(old_size[1])/float(self.last_window_size[1])
                    buff.setSize(int(window_size[0]*x_factor),int(window_size[1]*y_factor))
                self.last_window_size=window_size

    def addFilter(self, shader_name, inputs,
                  name=None, size_factor=1.0,
                  clear_color=None, translate_tex_name=None,
                  define=None):
        if name is None:
            name=shader_name
        index=len(self.filter_buff)
        quad, tex, buff=self.makeFilterStage(sort=index, size=size_factor, clear_color=clear_color)
        self.filter_buff[name]=buff
        self.filter_quad[name]=quad
        self.filter_tex[name]=tex

        quad.setShader(loader.loadShaderGLSL(self.v.format(shader_name), self.f.format(shader_name), define))
        #common inputs
        quad.setShaderInput('render', render)
        quad.setShaderInput('camera', base.cam)
        quad.setShaderInput('depth_tex', self.depth)
        quad.setShaderInput('normal_tex', self.normal)
        quad.setShaderInput("albedo_tex", self.albedo)
        quad.setShaderInput("lit_tex", self.lit_tex)
        for name, value in inputs.items():
            if isinstance(value, basestring):
                value=loader.loadTexture(value)
            quad.setShaderInput(str(name), value)
        if translate_tex_name:
            for old_name, new_name in translate_tex_name.items():
                value=self.filter_tex[old_name]
                quad.setShaderInput(str(new_name), value)

    def makeFilterStage(self, sort=0, size=1.0, clear_color=None):
        #make a root for the buffer
        root=NodePath("filterBufferRoot")
        tex=Texture()
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        buff_size_x=int(base.win.getXSize()*size)
        buff_size_y=int(base.win.getYSize()*size)
        #buff=base.win.makeTextureBuffer("buff", buff_size_x, buff_size_y, tex)
        winprops = WindowProperties()
        winprops.setSize(buff_size_x, buff_size_y)
        props = FrameBufferProperties()
        props.setRgbColor(True)
        props.setRgbaBits(8, 8, 8, 8)
        props.setDepthBits(0)
        buff= base.graphicsEngine.makeOutput(
            base.pipe, 'filter_stage', sort,
            props, winprops,
            GraphicsPipe.BF_resizeable,
            base.win.getGsg(), base.win)
        buff.addRenderTexture(tex = tex, mode = GraphicsOutput.RTMBindOrCopy, bitplane  = GraphicsOutput.RTPColor)
        #buff.setSort(sort)
        #buff.setSort(0)
        if clear_color:
            buff.setClearColor(clear_color)
            buff.setClearActive(GraphicsOutput.RTPColor, True)
        cam=base.makeCamera(win=buff)
        cam.reparentTo(root)
        cam.setPos(buff_size_x*0.5,buff_size_y*0.5,100)
        cam.setP(-90)
        lens = OrthographicLens()
        lens.setFilmSize(buff_size_x, buff_size_y)
        cam.node().setLens(lens)
        #plane with the texture, a blank texture for now
        cm = CardMaker("plane")
        cm.setFrame(0, buff_size_x, 0, buff_size_y)
        quad=root.attachNewNode(cm.generate())
        quad.lookAt(0, 0, -1)
        quad.setLightOff()
        return quad, tex, buff

    def makeForwardStage(self):
        root=NodePath("forwardRoot")
        tex=Texture()
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        buff_size_x=int(base.win.getXSize())
        buff_size_y=int(base.win.getYSize())
        buff=base.win.makeTextureBuffer("buff", buff_size_x, buff_size_y, tex)
        buff.setSort(2)
        buff.setClearColor((0, 0, 0, 0))
        cam=base.makeCamera(win=buff)
        cam.reparentTo(root)
        lens = base.cam.node().getLens()
        cam.node().setLens(lens)
        mask=BitMask32.bit(self.modelMask)
        mask.setBit(self.lightMask)
        cam.node().setCameraMask(mask)
        return root, tex, cam, buff

    def setDirectionalLight(self, color, direction, shadow_size=0):
        self.filter_quad['final_light'].setShaderInput('light_color', color)
        self.filter_quad['final_light'].setShaderInput('direction', direction)

    def addConeLight(self, color, pos=(0,0,0), hpr=(0,0,0), radius=1.0, fov=45.0, shadow_size=0.0):
        if fov >179.0:
            fov=179.0
        xy_scale=math.tan(deg2Rad(fov*0.5))
        model=loader.loadModel("volume/cone")
        #temp=model.copyTo(self.plain_root)
        #self.lights.append(model)
        model.reparentTo(self.light_root)
        model.setScale(xy_scale, 1.0, xy_scale)
        model.flattenStrong()
        model.setScale(radius)
        model.setPos(pos)
        model.setHpr(hpr)
        #debug=self.lights[-1].copyTo(self.plain_root)
        model.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        model.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))

        model.setShader(loader.loadShaderGLSL(self.v.format('spot_light'), self.f.format('spot_light'), self.shading_setup))
        model.setShaderInput("light_radius", float(radius))
        model.setShaderInput("light_pos", Vec4(pos,1.0))
        model.setShaderInput("light_fov", deg2Rad(fov))
        model.setShaderInput("light_pos", Vec4(pos,1.0))
        p3d_light = render.attachNewNode(Spotlight("Spotlight"))
        p3d_light.setPos(render, pos)
        p3d_light.setHpr(render, hpr)
        p3d_light.node().setExponent(20)
        if shadow_size >0.0:
            p3d_light.node().set_shadow_caster(True, 256, 256)
        #p3d_light.node().setCameraMask(self.modelMask)
        model.setShaderInput("spot", p3d_light)
        #p3d_light.node().showFrustum()
        p3d_light.node().getLens().setFov(fov)
        p3d_light.node().getLens().setFar(radius)
        p3d_light.node().getLens().setNear(1.0)
        return model, p3d_light

    def addPointLight(self, color, model="volume/sphere", pos=(0,0,0), radius=1.0, shadow_size=0):
        #light geometry
        if not isinstance(model, NodePath): #if we got a NodePath we use it as the geom for the light
            model=loader.loadModel(model)
        #self.lights.append(model)
        model.reparentTo(self.light_root)
        model.setPos(pos)
        model.setScale(radius)
        model.setShader(loader.loadShaderGLSL(self.v.format('light'), self.f.format('light'), self.shading_setup))
        model.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        model.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        model.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        model.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        #shader inpts
        model.setShaderInput("light", Vec4(color,radius*radius))
        model.setShaderInput("light_pos", Vec4(pos,1.0))
        if shadow_size > 0:
            model.setShader(loader.loadShaderGLSL(self.v.format('light_shadow'), self.f.format('light_shadow'), self.shading_setup))
            p3d_light = render.attachNewNode(PointLight("PointLight"))
            p3d_light.setPos(render, pos)
            p3d_light.node().set_shadow_caster(True, shadow_size, shadow_size)
            p3d_light.node().setCameraMask(self.modelMask)
            #p3d_light.node().showFrustum()
            for i in range(6):
                p3d_light.node().getLens(i).setNearFar(0.1, radius)
            model.setShaderInput("shadowcaster", p3d_light)
            model.setShaderInput("near", 0.1)
            model.setShaderInput("bias", 0.012)
        else:
            p3d_light = render.attachNewNode('dummy_node')
        return model, p3d_light

    def makeFBO(self, name, auxrgba=0):
        # This routine creates an offscreen buffer.  All the complicated
        # parameters are basically demanding capabilities from the offscreen
        # buffer - we demand that it be able to render to texture on every
        # bitplane, that it can support aux bitplanes, that it track
        # the size of the host window, that it can render to texture
        # cumulatively, and so forth.
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


    def update(self, task):
        self.plain_cam.setPos(base.cam.getPos(render))
        self.plain_cam.setHpr(base.cam.getHpr(render))
        return task.again


class WrappedLoader(object):
    def __init__(self, original_loader):
        self.original_loader=original_loader
        self.texture_shader_inputs=[]
        self.fix_srgb=ConfigVariableBool('framebuffer-srgb').getValue()
        self.shader_cache={}

    def fixTransparancy(self, model):
        for tex_stage in model.findAllTextureStages():
            tex=model.findTexture(tex_stage)
            if tex:
                mode=tex_stage.getMode()
                tex_format=tex.getFormat()
                if mode == TextureStage.M_modulate and (tex_format == Texture.F_rgba or tex_format == Texture.F_srgb_alpha):
                    return
        model.setTransparency(TransparencyAttrib.MNone, 1)

    def fixSrgbTextures(self, model):
        for tex_stage in model.findAllTextureStages():
            tex=model.findTexture(tex_stage)
            if tex:
                file_name=tex.getFilename()
                tex_format=tex.getFormat()
                #print tex_stage,  file_name, tex_format
                if tex_stage.getMode()==TextureStage.M_normal:
                    tex_stage.setMode(TextureStage.M_normal_gloss)
                if tex_stage.getMode()!=TextureStage.M_normal_gloss:
                    if tex_format==Texture.F_rgb:
                        tex_format=Texture.F_srgb
                    elif tex_format==Texture.F_rgba:
                        tex_format=Texture.F_srgb_alpha
                tex.setFormat(tex_format)
                model.setTexture(tex_stage, tex, 1)

    def setTextureInputs(self, model):
        slots_filled=set()
        #find all the textures, easy mode - slot is fitting the stage mode (eg. slot0 is diffuse/color)
        for slot, tex_stage in enumerate(model.findAllTextureStages()):
            tex=model.findTexture(tex_stage)
            if tex:
                mode=tex_stage.getMode()
                if mode in self.texture_shader_inputs[slot]['stage_modes']:
                    model.setShaderInput(self.texture_shader_inputs[slot]['input_name'],tex)
                    #model.setTextureOff(tex_stage, 1)
                    slots_filled.add(slot)
                    #print 'good slot:', slot, 'tex:',tex.getFilename(), 'input:', self.texture_shader_inputs[slot]['input_name']
                #else:
                    #print 'IDK? slot:',slot, 'mode:', mode, 'tex:',tex.getFilename()
        #print 'slots_filled pass1:', slots_filled
        #did we get all of them?
        if  len(slots_filled) == len(self.texture_shader_inputs):
            return
        #what slots need filling?
        missing_slots=set(range(len(self.texture_shader_inputs)))-slots_filled
        #print 'missing after pass1:', missing_slots
        for slot, tex_stage in enumerate(model.findAllTextureStages()):
            if slot in missing_slots:
                tex=model.findTexture(tex_stage)
                if tex:
                    mode=tex_stage.getMode()
                    for d in self.texture_shader_inputs:
                        if mode in d['stage_modes']:
                            i=self.texture_shader_inputs.index(d)
                            model.setShaderInput(self.texture_shader_inputs[i]['input_name'],tex)
                            slots_filled.add(i)
                            #print 'ok slot:', i, 'tex:',tex.getFilename(), 'input:', self.texture_shader_inputs[i]['input_name']
        #print 'slots_filled pass2:', slots_filled
        #did we get all of them this time?
        if  len(slots_filled) == len(self.texture_shader_inputs):
            return
        missing_slots=set(range(len(self.texture_shader_inputs)))-slots_filled
        #print 'missing after pass2:', missing_slots
        #set defaults
        for slot in missing_slots:
            model.setShaderInput(self.texture_shader_inputs[slot]['input_name'],self.texture_shader_inputs[slot]['default_texture'])
            #print 'default for slot:', slot, 'input:', self.texture_shader_inputs[slot]['input_name'], self.texture_shader_inputs[slot]['default_texture'].getFilename()

    def destroy(self):
        self.original_loader.destroy()

    def loadModel(self, modelPath, loaderOptions = None, noCache = None,
                  allowInstance = False, okMissing = None,
                  callback = None, extraArgs = [], priority = None):
        model=self.original_loader.loadModel(modelPath, loaderOptions, noCache, allowInstance, okMissing, callback, extraArgs, priority)

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

    def loadModelCopy(self, modelPath, loaderOptions = None):
        return self.original_loader.loadModelCopy(modelPath, loaderOptions)

    def loadModelNode(self, modelPath):
        return self.original_loader.loadModelNode(modelPath)

    def unloadModel(self, model):
        self.original_loader.unloadModel(model)

    def saveModel(self, modelPath, node, loaderOptions = None,
                  callback = None, extraArgs = [], priority = None):
        return self.original_loader.saveModel(modelPath, node, loaderOptions, callback, extraArgs, priority)

    def loadFont(self, modelPath,
                 spaceAdvance = None, lineHeight = None,
                 pointSize = None,
                 pixelsPerUnit = None, scaleFactor = None,
                 textureMargin = None, polyMargin = None,
                 minFilter = None, magFilter = None,
                 anisotropicDegree = None,
                 color = None,
                 outlineWidth = None,
                 outlineFeather = 0.1,
                 outlineColor = VBase4(0, 0, 0, 1),
                 renderMode = None,
                 okMissing = False):
        return self.original_loader.loadFont(modelPath, spaceAdvance, lineHeight, pointSize, pixelsPerUnit, scaleFactor, textureMargin, polyMargin, minFilter, magFilter, anisotropicDegree, color, outlineWidth, outlineFeather, outlineColor, renderMode, okMissing)

    def loadTexture(self, texturePath, alphaPath = None,
                    readMipmaps = False, okMissing = False,
                    minfilter = None, magfilter = None,
                    anisotropicDegree = None, loaderOptions = None,
                    multiview = None, sRgb=False):
        tex=self.original_loader.loadTexture(texturePath, alphaPath, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview)
        if sRgb:
            tex_format=tex.getFormat()
            if tex_format==Texture.F_rgb:
                tex_format=Texture.F_srgb
            elif tex_format==Texture.F_rgba:
                tex_format=Texture.F_srgb_alpha
            tex.setFormat(tex_format)
        return tex

    def load3DTexture(self, texturePattern, readMipmaps = False, okMissing = False,
                      minfilter = None, magfilter = None, anisotropicDegree = None,
                      loaderOptions = None, multiview = None, numViews = 2):
        return self.original_loader.load3DTexture(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview, numViews)

    def load2DTextureArray(self, texturePattern, readMipmaps = False, okMissing = False,
                      minfilter = None, magfilter = None, anisotropicDegree = None,
                      loaderOptions = None, multiview = None, numViews = 2):
        return self.original_loader.load2DTextureArray(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview, numViews)

    def loadCubeMap(self, texturePattern, readMipmaps = False, okMissing = False,
                    minfilter = None, magfilter = None, anisotropicDegree = None,
                    loaderOptions = None, multiview = None):
        return self.original_loader.loadCubeMap(texturePattern, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview)

    def unloadTexture(self, texture):
        self.original_loader.unloadTexture(texture)

    def loadSfx(self, *args, **kw):
        return self.original_loader.loadSfx(*args, **kw)

    def loadMusic(self, *args, **kw):
        return self.original_loader.loadMusic(*args, **kw)

    def loadSound(self, manager, soundPath, positional = False,
                  callback = None, extraArgs = []):
        return self.original_loader.loadSound( manager, soundPath, positional, callback, extraArgs)

    def unloadSfx(self, sfx):
        self.original_loader.unloadSfx( sfx)

    def loadShaderGLSL(self, v_shader, f_shader, define=None, version='#version 140'):
        #check if we already have a shader like that
        #note: this may fail depending on the dict implementation
        if (v_shader, f_shader, str(define)) in self.shader_cache:
            return self.shader_cache[(v_shader, f_shader, str(define))]
        #load the shader text
        with open(v_shader) as f:
            v_shader_txt = f.read()
        with open(f_shader) as f:
            f_shader_txt = f.read()
        #make the header
        if define:
            header=version+'\n'
            for name, value in define.items():
                header+='#define {0} {1}\n'.format(name, value)
            #put the header on top
            v_shader_txt=v_shader_txt.replace(version, header)
            f_shader_txt=f_shader_txt.replace(version, header)
        #make the shader
        shader= Shader.make(Shader.SL_GLSL,v_shader_txt, f_shader_txt)
        #store it
        self.shader_cache[(v_shader, f_shader, str(define))]=shader
        shader.set_filename(Shader.ST_vertex, v_shader)
        shader.set_filename(Shader.ST_fragment, f_shader)
        return shader

    def loadShader(self, shaderPath, okMissing = False):
        return self.original_loader.loadShader(shaderPath, okMissing)

    def unloadShader(self, shaderPath):
        self.original_loader.unloadShader(shaderPath)

    def asyncFlattenStrong(self, model, inPlace = True,
                           callback = None, extraArgs = []):
        self.original_loader.asyncFlattenStrong(model, inPlace, callback, extraArgs)

class SceneLight(object):
    def __init__(self, color, direction, shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        deferred_renderer.setDirectionalLight(color, direction, shadow_size=0)
        self.color=color
        self.direction=direction
        self.shadow_size=shadow_size

    def setColor(self, color):
        deferred_renderer.setDirectionalLight(color, self.direction, self.shadow_size)

    def setDirection(self, direction):
        deferred_renderer.setDirectionalLight(self.color, direction, self.shadow_size)

    def remove(self):
        deferred_renderer.setDirectionalLight((0,0,0), self.direction, self.shadow_size)

    def __del__(self):
        self.remove()


class SphereLight(object):
    def __init__(self, color, pos, radius, shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.radius=radius
        self.color=color
        self.geom, self.p3d_light=deferred_renderer.addPointLight(color=color,
                                                            model="volume/sphere",
                                                            pos=pos,
                                                            radius=radius,
                                                            shadow_size=shadow_size)
    def setColor(self, color):
        self.geom.setShaderInput("light", Vec4(color,self.radius*self.radius))
        self.color=color

    def setRadius(self, radius):
        self.geom.setShaderInput("light", Vec4(self.color,radius*radius))
        self.geom.setScale(radius)
        self.radius=radius
        try:
            for i in range(6):
                self.p3d_light.node().getLens(i).setNearFar(0.1, radius)
        except:
            pass

    def setPos(self, pos):
        self.geom.setShaderInput("light_pos", Vec4(pos,1.0))
        self.geom.setPos(render, pos)
        self.p3d_light.setPos(render, pos)

    def remove(self):
        self.geom.removeNode()
        try:
            buff=self.p3d_light.node().getShadowBuffer(base.win.getGsg())
            buff.clearRenderTextures()
            base.win.getGsg().getEngine().removeWindow(buff)
            self.p3d_light.node().setShadowCaster(False)
        except:
            pass
        self.p3d_light.removeNode()

    def __del__(self):
        self.remove()

class ConeLight(object):
    def __init__(self, color, pos, radius, fov, hpr=None, look_at=None, shadow_size=0):
        if not hasattr(builtins, 'deferred_renderer'):
            raise RuntimeError('You need a DeferredRenderer')
        self.radius=radius
        self.color=color
        self.pos=pos
        self.hpr=hpr
        self.fov=fov
        self.shadow_size=shadow_size
        if hpr is None:
            dummy=render.attachNewNode('dummy')
            dummy.setPos(pos)
            dummy.lookAt(look_at)
            hpr=dummy.getHpr(render)
            dummy.removeNode()
        self.hpr=hpr
        self.geom, self.p3d_light=deferred_renderer.addConeLight(color=color,
                                                                 pos=pos,
                                                                 hpr=hpr,
                                                                 radius=radius,
                                                                 fov=fov,
                                                                 shadow_size=shadow_size)

    def setFov(self, fov):
        if fov >179.0:
            fov=179.0
        self.p3d_light.node().getLens().setFov(fov)
        #we might as well start from square 1...
        self.geom.removeNode()
        xy_scale=math.tan(deg2Rad(fov*0.5))
        self.geom=loader.loadModel("volume/cone")
        self.geom.reparentTo(deferred_renderer.light_root)
        self.geom.setScale(xy_scale, 1.0, xy_scale)
        self.geom.flattenStrong()
        self.geom.setScale(self.radius)
        self.geom.setPos(self.pos)
        self.geom.setHpr(self.hpr)
        self.geom.setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        self.geom.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        self.geom.setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        self.geom.setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        self.geom.setShader(loader.loadShaderGLSL(deferred_renderer.v.format('spot_light'), deferred_renderer.f.format('spot_light'), deferred_renderer.shading_setup))
        self.geom.setShaderInput("light_radius", float(self.radius))
        self.geom.setShaderInput("light_pos", Vec4(self.pos,1.0))
        self.geom.setShaderInput("light_fov", deg2Rad(fov))
        self.geom.setShaderInput("spot", self.p3d_light)

    def setRadius(self, radius):
        self.geom.setShaderInput("light_radius", float(self.radius))
        self.geom.setScale(self.radius)
        self.radius=radius
        try:
            self.p3d_light.node().getLens().setNearFar(0.1, radius)
        except:
            pass

    def setHpr(self, hpr):
        self.geom.setHpr(hpr)
        self.p3d_light.setHpr(hpr)
        self.hpr=hrp

    def setPos(self, pos):
        self.geom.setPos(pos)
        self.p3d_light.setPos(pos)
        self.pos=pos

    def remove(self):
        self.geom.removeNode()
        try:
            buff=self.p3d_light.node().getShadowBuffer(base.win.getGsg())
            buff.clearRenderTextures()
            base.win.getGsg().getEngine().removeWindow(buff)
            self.p3d_light.node().setShadowCaster(False)
        except:
            pass
        self.p3d_light.removeNode()

    def __del__(self):
        self.remove()
