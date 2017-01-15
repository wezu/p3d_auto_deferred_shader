import sys
if sys.version_info >= (3, 0):
    import builtins
else:
    import __builtin__ as builtins
import math

from panda3d.core import *
from direct.filter.FilterManager import *

class DeferredRenderer():
    def __init__(self, scene_mask=1, light_mask=2):

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

        #Wrapper(builtins.loader)

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

        self.aux=Texture()

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
        self.lights=[]
        self.light_root=render.attachNewNode('light_root')
        self.light_root.setShader((Shader.load(Shader.SLGLSL, 'shaders/light_v.glsl', 'shaders/light_f.glsl')))
        self.light_root.setShaderInput("albedo_tex", self.albedo)
        self.light_root.setShaderInput("depth_tex", self.depth)
        self.light_root.setShaderInput("normal_tex", self.normal)
        self.light_root.setShaderInput('win_size', Vec2(base.win.getXSize(), base.win.getYSize()))
        self.light_root.hide(BitMask32(self.modelMask))
        self.light_root.setShaderInput('camera', base.cam)
        self.light_root.setShaderInput('render', render)
        #self.light_root.hide(BitMask32(self.plainMask))

        self.geometry_root=render.attachNewNode('geometry_root')
        self.geometry_root.setShader((Shader.load(Shader.SLGLSL, 'shaders/geometry_v.glsl', 'shaders/geometry_f.glsl')))
        self.geometry_root.hide(BitMask32(self.lightMask))
        #self.geometry_root.hide(BitMask32(self.plainMask))

        self.plain_root, self.plain_tex, self.plain_cam=self.makeForwardStage()
        self.plain_root.setShader((Shader.load(Shader.SLGLSL, 'shaders/forward_v.glsl', 'shaders/forward_f.glsl')))
        self.plain_root.setShaderInput("depth_tex", self.depth)
        self.plain_root.setShaderInput('win_size', Vec2(base.win.getXSize(), base.win.getYSize()))
        self.plain_root.hide(BitMask32(self.lightMask))
        self.plain_root.hide(BitMask32(self.modelMask))

        # Cause the final results to be rendered into the main window on a
        # card.
        self.final_card = self.lightbuffer.getTextureCard()
        #self.final_card.setTexture(self.lit_tex)

        #post process
        self.quad_stage0, self.tex_stage0 = self.makeFilterStage(4, size=1.0)
        self.quad_stage0.setShader(Shader.load(Shader.SLGLSL, 'shaders/ao_v.glsl', 'shaders/ao_f.glsl'))
        self.quad_stage0.setShaderInput("depth_tex", self.depth)
        self.quad_stage0.setShaderInput("normal_tex", self.normal)
        self.quad_stage0.setShaderInput("random_tex", loader.loadTexture('data/random.png'))
        self.quad_stage0.setShaderInput("random_size", 64.0)
        self.quad_stage0.setShaderInput("sample_rad", 0.4)
        self.quad_stage0.setShaderInput("intensity", 10.0)
        self.quad_stage0.setShaderInput("scale", 0.9)
        self.quad_stage0.setShaderInput("bias", 0.4)
        self.quad_stage0.setShaderInput("fade_distance", 100.0)
        self.quad_stage0.setShaderInput('win_size', Vec2(base.win.getXSize()*1.0, base.win.getYSize()*1.0))
        self.quad_stage0.setShaderInput('camera', base.cam)

        self.quad_stage1, self.tex_stage1 = self.makeFilterStage(5, size=1.0)
        self.quad_stage1.setShader(Shader.load(Shader.SLGLSL, 'shaders/dir_light_v.glsl', 'shaders/dir_light_f.glsl'))
        self.quad_stage1.setShaderInput("depth_tex", self.depth)
        self.quad_stage1.setShaderInput("normal_tex", self.normal)
        self.quad_stage1.setShaderInput("albedo_tex", self.albedo)
        self.quad_stage1.setShaderInput("lit_tex", self.lit_tex)
        self.quad_stage1.setShaderInput('camera', base.cam)
        self.quad_stage1.setShaderInput('light_color', Vec3(0,0,0))
        self.quad_stage1.setShaderInput('direction', Vec3(0,0,0))

        self.quad_stage2, self.tex_stage2 = self.makeFilterStage(6, size=0.5)
        self.quad_stage2.setShader(Shader.load(Shader.SLGLSL, 'shaders/ssr_v.glsl', 'shaders/ssr_f.glsl'))
        self.quad_stage2.setShaderInput("color_tex", self.tex_stage1)
        self.quad_stage2.setShaderInput("normal_tex", self.normal)
        self.quad_stage2.setShaderInput("depth_tex", self.depth)
        self.quad_stage2.setShaderInput('win_size', Vec2(base.win.getXSize()*0.5, base.win.getYSize()*0.5))
        self.quad_stage2.setShaderInput('camera', base.cam)

        self.quad_stage3, self.tex_stage3 = self.makeFilterStage(7, size=0.5)
        self.quad_stage3.setShader(Shader.load(Shader.SLGLSL, 'shaders/bloom_v.glsl', 'shaders/bloom_f.glsl'))
        self.quad_stage3.setShaderInput("color_tex", self.tex_stage1)
        self.quad_stage3.setShaderInput("normal_tex", self.normal)
        self.quad_stage3.setShaderInput("glow_power", 5.0)

        self.quad_stage4, self.tex_stage4 = self.makeFilterStage(8, size=0.5)
        self.quad_stage4.setShader(Shader.load(Shader.SLGLSL, 'shaders/blur_v.glsl', 'shaders/blur_f.glsl'))
        self.quad_stage4.setShaderInput("input_map", self.tex_stage3)
        self.quad_stage4.setShaderInput("blur", 3.0)

        self.quad_stage6, self.tex_stage6 = self.makeFilterStage(9)
        self.quad_stage6.setShader(Shader.load(Shader.SLGLSL, 'shaders/mix_v.glsl', 'shaders/mix_f.glsl'))
        self.quad_stage6.setShaderInput("ssr_tex", self.tex_stage2)
        self.quad_stage6.setShaderInput("ao_tex", self.tex_stage0)
        self.quad_stage6.setShaderInput("lit_tex", self.tex_stage1)
        self.quad_stage6.setShaderInput("bloom_tex", self.tex_stage4)
        self.quad_stage6.setShaderInput("lut_tex", loader.loadTexture('data/lut_v1.png'))
        self.quad_stage6.setShaderInput("noise_tex", loader.loadTexture('data/noise.png'))
        self.quad_stage6.setShaderInput("forward_tex", self.plain_tex)
        self.quad_stage6.setShaderInput('win_size', Vec2(base.win.getXSize()*1.0, base.win.getYSize()*1.0))

        self.final_card.reparentTo(render2d)
        self.final_card.setShader(Shader.load(Shader.SLGLSL, 'shaders/fxaa_v.glsl', 'shaders/fxaa_f.glsl'))
        self.final_card.setShaderInput('tex0', self.tex_stage6)
        self.final_card.setShaderInput('win_size', Vec2(base.win.getXSize(), base.win.getYSize()))
        self.final_card.setShaderInput('FXAA_SPAN_MAX' , float(2.0))
        self.final_card.setShaderInput('FXAA_REDUCE_MUL', float(1.0/16.0))
        self.final_card.setShaderInput('FXAA_SUBPIX_SHIFT', float(1.0/8.0))

        taskMgr.add(self.update, 'update_tsk')

    def makeFilterStage(self, sort=0, size=1.0):
        #make a root for the buffer
        root=NodePath("filterBufferRoot")
        tex=Texture()
        tex.setWrapU(Texture.WM_clamp)
        tex.setWrapV(Texture.WM_clamp)
        buff_size_x=int(base.win.getXSize()*size)
        buff_size_y=int(base.win.getYSize()*size)
        buff=base.win.makeTextureBuffer("buff", buff_size_x, buff_size_y, tex)
        #buff.setSort(sort)
        buff.setSort(0)
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
        return quad, tex

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
        return root, tex, cam

    def setDirectionalLight(self, color, direction):
        self.quad_stage1.setShaderInput('light_color', color)
        self.quad_stage1.setShaderInput('direction', direction)

    def addConeLight(self, color, pos=(0,0,0), hpr=(0,0,0), radius=1.0, fov=45.0, model_size_margin=1.0):
        if fov >179.0:
            fov=179.0
        xy_scale=math.tan(deg2Rad(fov*0.5))
        model=loader.loadModel("volume/cone")

        #temp=model.copyTo(self.plain_root)

        self.lights.append(model)
        self.lights[-1].reparentTo(self.light_root)
        self.lights[-1].setScale(xy_scale, 1.0, xy_scale)
        self.lights[-1].flattenStrong()
        self.lights[-1].setScale(radius*model_size_margin)
        self.lights[-1].setPos(pos)
        self.lights[-1].setHpr(hpr)
        #debug=self.lights[-1].copyTo(self.plain_root)
        self.lights[-1].setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        self.lights[-1].setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        self.lights[-1].setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        self.lights[-1].setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))

        self.lights[-1].setShader((Shader.load(Shader.SLGLSL, 'shaders/spot_light_v.glsl', 'shaders/spot_light_f.glsl')))
        self.lights[-1].setShaderInput("light_radius", float(radius))
        self.lights[-1].setShaderInput("light_pos", Vec4(pos,1.0))
        self.lights[-1].setShaderInput("light_fov", deg2Rad(fov))
        self.lights[-1].setShaderInput("light_pos", Vec4(pos,1.0))
        p3d_light = render.attachNewNode(Spotlight("Spotlight"))
        p3d_light.setPos(render, pos)
        p3d_light.setHpr(render, hpr)
        p3d_light.node().set_shadow_caster(True, 256, 256)
        #p3d_light.node().setCameraMask(self.modelMask)
        self.lights[-1].setShaderInput("spot", p3d_light)
        #p3d_light.node().showFrustum()
        p3d_light.node().getLens().setFov(fov)
        p3d_light.node().getLens().setFar(radius)
        p3d_light.node().getLens().setNear(1.0)

    def addLight(self, color, model="volume/sphere", pos=(0,0,0), radius=1.0):
        #light geometry
        if not isinstance(model, NodePath): #if we got a NodePath we use it as the geom for the light
            model=loader.loadModel(model)
        self.lights.append(model)
        self.lights[-1].reparentTo(self.light_root)
        self.lights[-1].setPos(pos)
        self.lights[-1].setScale(radius)
        self.lights[-1].setAttrib(DepthTestAttrib.make(RenderAttrib.MLess))
        self.lights[-1].setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullCounterClockwise))
        self.lights[-1].setAttrib(ColorBlendAttrib.make(ColorBlendAttrib.MAdd, ColorBlendAttrib.OOne, ColorBlendAttrib.OOne))
        self.lights[-1].setAttrib(DepthWriteAttrib.make(DepthWriteAttrib.MOff))
        #shader inpts
        self.lights[-1].setShaderInput("light", Vec4(color,radius*radius))
        self.lights[-1].setShaderInput("light_pos", Vec4(pos,1.0))

        p3d_light = render.attachNewNode(PointLight("PointLight"))
        p3d_light.setPos(render, pos)
        p3d_light.node().set_shadow_caster(True, 256, 256)
        p3d_light.node().setCameraMask(self.modelMask)
        #p3d_light.node().showFrustum()
        for i in range(6):
            p3d_light.node().getLens(i).setNearFar(0.1, radius)
        self.lights[-1].setShaderInput("shadowcaster", p3d_light)
        self.lights[-1].setShaderInput("near", 0.1)
        self.lights[-1].setShaderInput("bias", 0.012)
        #self.lights[-1].setShaderInput("camera", base.cam)

        #return the index of the light to remove it later
        return self.lights.index(self.lights[-1])

    def removeLight(self, lightID):
        if self.lights[lightID]:
            self.lights[lightID].removeNode()
            self.lights[lightID]=None


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
                    multiview = None):
        return self.original_loader.loadTexture(texturePath, alphaPath, readMipmaps, okMissing, minfilter, magfilter, anisotropicDegree, loaderOptions, multiview)

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

    def loadShader(self, shaderPath, okMissing = False):
        return self.original_loader.loadShader(shaderPath, okMissing)

    def unloadShader(self, shaderPath):
        self.original_loader.unloadShader(shaderPath)

    def asyncFlattenStrong(self, model, inPlace = True,
                           callback = None, extraArgs = []):
        self.original_loader.asyncFlattenStrong(model, inPlace, callback, extraArgs)

#helper calss
class Wrapper(object):
    def __init__(self,wrapped_object):
        self.wrapped_object = wrapped_object

        self.pre_hooks={}
        self.pre_hooks_args={}
        self.post_hooks={}
        self.post_hooks_args={}

    def set_pre_hook(self, function_name, function_to_call, args=None):
        self.pre_hooks[function_name]=function_to_call
        if args is not None:
            if not isinstance(args, (tuple, list, set)):
                args=[args]
            self.pre_hooks_args[function_name]=args

    def set_post_hook(self, function_name, function_to_call, args=None):
        self.post_hooks[function_name]=function_to_call
        if args is not None:
            if not isinstance(args, (tuple, list, set)):
                args=[args]
            self.post_hooks_args[function_name]=args

    def __getattr__(self,attr):
        orig_attr = self.wrapped_object.__getattribute__(attr)
        if callable(orig_attr):
            def hooked(*args, **kwargs):
                self.pre_hook(attr)
                result = orig_attr(*args, **kwargs)
                # prevent wrapped_object from becoming unwrapped
                if result == self.wrapped_object:
                    return self
                self.post_hook(attr)
                return result
            return hooked
        else:
            return orig_attr

    def pre_hook(self, attr):
        attr=str(attr)
        if attr in self.pre_hooks:
            if attr in self.pre_hooks_args:
                self.pre_hooks[attr](*self.pre_hooks_args[attr])
            else:
                self.pre_hooks[attr]()

    def post_hook(self, attr):
        attr=str(attr)
        if attr in self.post_hooks:
            if attr in self.post_hooks_args:
                self.post_hooks[attr](*self.post_hooks_args[attr])
            else:
                self.post_hooks[attr]()
