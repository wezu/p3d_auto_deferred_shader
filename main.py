from panda3d.core import *
#loadPrcFileData("", "show-buffers 1")
loadPrcFileData("", "shadow-depth-bits 32")
loadPrcFileData("", "depth-bits 32")
loadPrcFileData('','framebuffer-srgb true')
loadPrcFileData('','textures-power-2 None')
loadPrcFileData("", "sync-video 0")
loadPrcFileData("", "show-frame-rate-meter  1")
loadPrcFileData("", "texture-anisotropic-degree 2")
loadPrcFileData("", "win-size 1024 768")
from direct.showbase import ShowBase
from direct.showbase.DirectObject import DirectObject

from deferred_render import *

import operator

class Demo(DirectObject):
    def __init__(self):
        base = ShowBase.ShowBase()
        self.renderer=DeferredRenderer(preset='full')

        column=loader.loadModel("models/column")
        column.reparentTo(defered_render)
        column2=column.copyTo(defered_render)
        column2.setPos(10.0, 0, 0)
        column3=column.copyTo(defered_render)
        column3.setPos(20.0, 0, 0)
        column4=column.copyTo(defered_render)
        column4.setPos(30.0, 0, 0)
        column5=column.copyTo(defered_render)
        column5.setPos(40.0, 0, 0)
        column6=column.copyTo(defered_render)
        column6.setPos(50.0, 0, 0)
        box=loader.loadModel("models/box2")
        box.setPos(2,2,0)
        box.setH(45)
        box.reparentTo(defered_render)

        frowney=loader.loadModel('frowney')
        frowney.setPos(-2, -1, 1)
        frowney.setH(90)
        frowney.reparentTo(defered_render)

        #lights will vanish once out of scope, so keep a reference!
        #... but you can also remove lights by doing 'del self.light_1' or 'self.light_1=None'
        #also use keywords! else you'll never know what SphereLight((0.4,0.4,0.6), (0.9,0.0,2.0), 8.0, 256) is!!!
        self.light_0=SceneLight(color=(0.1, 0.1, 0.12), direction=(-0.5, 0.5, 1.0))
        self.light_1=SphereLight(color=(0.4,0.4,0.6), pos=(2,3,2), radius=8.0, shadow_size=0)
        self.light_2=ConeLight(color=(0.8, 0.8, 0.4), pos=(0,0,5), look_at=(10, 0, 0), radius=15.0, fov=30.0, shadow_size=0)

        self.accept('space', self.do_debug)
        self.accept('1', self.change_dof, [1.0])
        self.accept('2', self.change_dof, [-1.0])

    def do_debug(self):
        del self.light_2

    def change_dof(self, value):
        self.renderer.setFilterInput('fog', 'dof_far', value, operator.add)

    def toggle_lut(self):
        current_value=self.renderer.getFilterDefine('compose','DISABLE_LUT')
        if current_value is None:
            self.renderer.setFilterDefine('compose', 'DISABLE_LUT', 1)
        else:
            self.renderer.setFilterDefine('compose', 'DISABLE_LUT', None)

d=Demo()
base.run()
