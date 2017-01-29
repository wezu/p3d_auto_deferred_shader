from __future__ import print_function
from panda3d.core import *
#loadPrcFileData("", "show-buffers 1")
loadPrcFileData("", "shadow-depth-bits 32")
loadPrcFileData("", "depth-bits 32")
loadPrcFileData('','framebuffer-srgb true')
loadPrcFileData('','textures-power-2 None')
loadPrcFileData("", "sync-video 0")
loadPrcFileData("", "show-frame-rate-meter  1")
loadPrcFileData("", "texture-anisotropic-degree 2")
#loadPrcFileData("", "win-size 1024 768")
#loadPrcFileData("", "undecorated 1") #for video recording
#loadPrcFileData("", "win-size  1280 720") #for video recording
#loadPrcFileData("", "threading-model Cull/Draw")
from direct.showbase import ShowBase
from direct.showbase.DirectObject import DirectObject

from deferred_render import *

import random
import operator

class Demo(DirectObject):
    def __init__(self):
        base = ShowBase.ShowBase()
        DeferredRenderer(preset='full')

        column=loader.loadModel("models/column")
        column.reparentTo(defered_render)
        column2=column.copyTo(defered_render)
        column2.set_pos(10.0, 0, 0)
        column3=column.copyTo(defered_render)
        column3.set_pos(20.0, 0, 0)
        column4=column.copyTo(defered_render)
        column4.set_pos(30.0, 0, 0)
        column5=column.copyTo(defered_render)
        column5.set_pos(40.0, 0, 0)
        column6=column.copyTo(defered_render)
        column6.set_pos(50.0, 0, 0)
        box=loader.loadModel("models/box2")
        box.set_pos(2,2,0)
        box.setH(45)
        box.reparentTo(defered_render)

        frowney=loader.loadModel('frowney')
        frowney.set_pos(-2, -1, 1)
        frowney.setH(90)
        frowney.reparentTo(defered_render)

        #lights will vanish once out of scope, so keep a reference!
        #... but you can also remove lights by doing 'del self.light_1' or 'self.light_1=None'
        #also use keywords! else you'll never know what SphereLight((0.4,0.4,0.6), (0.9,0.0,2.0), 8.0, 256) is!!!
        self.light_0 = SceneLight(color=(0.01, 0.01, 0.005), direction=(-0.5, 0.5, 1.0))
        #self.light_0.add_light(color=(0.0, 0.0, 0.2), direction=(0.5, -0.5, -1.0), name='ambient') #not recomended but working
        self.light_1 = SphereLight(color=(0.4,0.4,0.6), pos=(2,3,2), radius=8.0, shadow_size=256)
        self.light_2 = ConeLight(color=(0.8, 0.8, 0.4), pos=(0,0,5), look_at=(10, 0, 0), radius=15.0, fov=30.0, shadow_size=256)

        self.accept('space', self.do_debug)
        self.accept('1', self.change_shadow_bias, [0.001])
        self.accept('2', self.change_shadow_bias, [-0.001])

        self.minimal=False
        self.bias=0.01


    def change_shadow_bias(self, bias):
        self.bias+=bias
        print( self.bias)
        self.light_2.geom.setShaderInput('bias', self.bias)

    def do_debug(self):
        #self.light_1.radius=30
        #self.light_2.look_at((5, 1, 0))
        #n=self.light_0.remove_light('ambient')
        #if not n:
        #    self.light_0.remove_light('main')
        #color1= (random.uniform(0,1), random.uniform(0,1), random.uniform(0,1))
        #color2= (1.0-color1[0], 1.0-color1[1], 1.0-color1[2])
        #self.light_0.set_color(color1, 'ambient')
        #self.light_0.set_color(color2, 'main')
        #if self.minimal==True:
        #    deferred_renderer.reset_filters(deferred_renderer.preset['full'])
        #    self.minimal=False
        #else:
        #    deferred_renderer.reset_filters(deferred_renderer.preset['minimal'])
        #    self.minimal=True
        pass

    def change_dof(self, value):
        deferred_renderer.set_filter_input('fog', 'dof_far', value, operator.add)

    def toggle_lut(self):
        current_value=deferred_renderer.get_filter_define('compose','DISABLE_LUT')
        if current_value is None:
            deferred_renderer.set_filter_define('compose', 'DISABLE_LUT', 1)
        else:
            deferred_renderer.set_filter_define('compose', 'DISABLE_LUT', None)

d=Demo()
base.run()
