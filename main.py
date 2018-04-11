from panda3d.core import *
#loadPrcFileData("", "threading-model Cull/Draw")
loadPrcFileData("", "show-buffers 0")
loadPrcFileData("", "shadow-depth-bits 24")
loadPrcFileData("", "depth-bits 32")
loadPrcFileData('','framebuffer-srgb 0')
loadPrcFileData('','textures-power-2 None')
loadPrcFileData("", "sync-video 0")
loadPrcFileData("", "show-frame-rate-meter  1")
loadPrcFileData("", "texture-anisotropic-degree 2")
loadPrcFileData("", "win-size 1280 720")
from direct.showbase import ShowBase
from direct.showbase.DirectObject import DirectObject

#load the main components
from deferred_render import *
from camera import CameraControler
from options import Options

config_full={'shadows': 1024,
            'shading_setup': {'FORWARD_SIZE': 1, 'DISABLE_POM': 1, 'FORWARD_AUX': 1},
            'filter_setup': [{'inputs': {'random_tex': 'tex/noise.png', 'amount': 0.9, 'strength': 0.7, 'sample_rad': 0.01, 'falloff': 1.0},
                            'name': 'ao_basic',
                            'shader': 'ao'},
                            {'translate_tex_name': {'ao_basic': 'input_tex'},
                            'inputs': {'blur': 2.5},
                            'size': 0.5,
                            'name': 'ao',
                            'shader': 'blur'},
                            {'inputs': {'direction': LVector3f(0, 0, 0),
                            'ambient': LVector3f(0.02, 0.01, 0.01),
                            'light_color': LVector3f(0, 0, 0)},
                            'name': 'final_light',
                            'shader': 'dir_light'},
                            {'inputs': {'desat': 0.2, 'scale': 10.0, 'power': 2.0},
                            'size': 0.5,
                            'name': 'base_bloom',
                            'shader': 'bloom'},
                            {'translate_tex_name': {'base_bloom': 'input_tex'},
                            'inputs': {'blur': 3.0},
                            'size': 0.5,
                            'name': 'bloom',
                            'shader': 'blur'},
                            {'shader': 'ssr',
                            'name': 'base_ssr',
                            'define': {'maxDelta': 0.044, 'rayLength': 0.034, 'stepsCount': 16, 'fade': 0.3}},
                            {'inputs': {'noise_tex': 'tex/noise.png', 'blur': 6.0},
                            'name': 'ssr',
                            'shader': 'ref_blur'},
                            {'translate_tex_name': {'final_light': 'final_color'},
                            'inputs': {'noise_tex': 'tex/noise.png', 'lut_tex': 'tex/new_lut_nearest_f_rgb16_clamp.png'},
                            'name': 'compose',
                            'shader': 'mix'},
                            {'translate_tex_name': {'compose': 'input_tex'},
                            'inputs': {'fog_start': 20.0, 'dof_far_start': 15.0, 'dof_near': 5.0, 'fog_color': LVector3f(0.831, 0.831, 0.874), 'dof_far_max': 60.0, 'fog_max': 70.0},
                            'shader': 'fog'},
                            {'translate_tex_name': {'fog': 'input_tex'},
                            'inputs': {'blur': 6.0},
                            'shader': 'dof'},
                            {'translate_tex_name': {'dof': 'input_tex'},
                            'name': 'pre_aa',
                            'shader': 'chroma'},
                            {'inputs': {'subpix_shift': 0.125, 'span_max': 2.0, 'reduce_mul': 0.0625},
                            'shader': 'fxaa'}]
            }


class Demo(DirectObject):
    def __init__(self):
        base = ShowBase.ShowBase()
        base.setBackgroundColor(0.1, 0.1, 0.8, 1)
        base.disableMouse()

        #get the preset and setup
        options=Options('presets/full.ini')
        DeferredRenderer(**options.get())
        #if getting options from a ini fail just use the dict..
        #DeferredRenderer(**config_full)

        #set some other options...
        deferred_renderer.set_near_far(1.0,200.0)
        deferred_renderer.set_cubemap('tex/cube/skybox_#.png')

        #setup lights
        # light 0 2x directional light, one yellowish one blueish
        self.light_0 = SceneLight(color=(0.2, 0.2, 0.05), direction=Vec3(0.5, 0.0, 1.0), shadow_size=0)
        self.light_0.add_light(color=(0.1, 0.1, 0.15), direction=(-0.5, 0.0, 1.0), name='ambient') #not recomended but working
        #point light, attached to camera
        self.light_1 = SphereLight(color=(0.8, 0.8, 0.8), pos=(0,0,3), radius=10.0, shadow_size=512, shadow_bias=0.0089)
        #spotlight
        self.light_2 = ConeLight(color=(1.0, 0.0, 0.0), pos=(0,5,6), look_at=(0, 0, 0), radius=30.0, fov=60.0, shadow_size=1024)

        #init camera control
        self.cam_controler=CameraControler(pos=(0,0,0),
                                           offset=(0, 5, 5),
                                           speed=1.0,
                                           zoom_speed=2.0,
                                           limits=(2.0, 30.0, -40, 40.0))
        self.cam_controler.bind_keys()
        #attach light_1 to the camera node
        self.light_1.attach_to(self.cam_controler.node, Point3(0,0,3))


        #load a scene
        self.balls=loader.load_model('sample_assets/balls.egg')
        self.balls.reparent_to(deferred_render)
        self.grid=loader.load_model('sample_assets/plane.egg')
        self.grid.reparent_to(deferred_render)
        self.grid.set_scale(0.1)
        self.grid.set_z(-0.5)

d=Demo()
base.run()

