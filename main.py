from panda3d.core import *
loadPrcFileData("", "show-buffers 1")
loadPrcFileData("", "shadow-depth-bits 32")
loadPrcFileData("", "depth-bits 32")
loadPrcFileData('','framebuffer-srgb true')
loadPrcFileData('','textures-power-2 None')
loadPrcFileData("", "sync-video 0")
loadPrcFileData("", "show-frame-rate-meter  1")
loadPrcFileData("", "win-size 1024 768")
from direct.showbase import ShowBase
from direct.showbase.DirectObject import DirectObject
from deferred_render import DeferredRenderer
from direct.interval.IntervalGlobal import *
from direct.gui.OnscreenText import OnscreenText


class Demo(DirectObject):
    def __init__(self):
        base = ShowBase.ShowBase()
        #base.setBackgroundColor(0, 0, 0)
        self.renderer=DeferredRenderer()
        defered_render=self.renderer.geometry_root

        column=loader.loadModel("models/column")
        column.setPos(0.5,0.5,-4)
        column.reparentTo(defered_render)
        #column.setTransparency(TransparencyAttrib.MNone, 1)
        box=loader.loadModel("models/box2")
        box.setPos(2,2,-4)
        box.setH(45)
        #box.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullNone))
        box.reparentTo(defered_render)
        #box.setTransparency(TransparencyAttrib.MNone, 1)
        #box.reparentTo(self.renderer.plain_root)
        #box.setTransparency(TransparencyAttrib.MBinary, 1)

        frowney=loader.loadModel('frowney')
        frowney.setPos(-2, -1, -3)
        frowney.setH(90)
        frowney.reparentTo(defered_render)


        self.renderer.setDirectionalLight(Vec3(0.06, 0.06, 0.07), Vec3(0, 0.25, 1.0))
        self.renderer.addConeLight(color=(0.8, 0.8, 0.8), pos=(0,-4,1), hpr=(0,-60,0), radius=15.0, fov=60.0)
        #self.renderer.addLight(color=(0.3,0.3,0.5), pos=(2,2,2), radius=9.0)

d=Demo()
base.run()
