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
        #column.setTransparency(TransparencyAttrib.MNone, 1)
        box=loader.loadModel("models/box2")
        box.setPos(2,2,0)
        box.setH(45)
        #box.setAttrib(CullFaceAttrib.make(CullFaceAttrib.MCullNone))
        box.reparentTo(defered_render)
        #box.setTransparency(TransparencyAttrib.MNone, 1)
        #box.reparentTo(self.renderer.plain_root)
        #box.setTransparency(TransparencyAttrib.MBinary, 1)

        frowney=loader.loadModel('frowney')
        frowney.setPos(-2, -1, 1)
        frowney.setH(90)
        frowney.reparentTo(defered_render)


        self.renderer.setDirectionalLight(Vec3(0.4, 0.4, 0.4), Vec3(-0.5, 0.5, 1.0))
        #self.renderer.addConeLight(color=(0.8, 0.8, 0.8), pos=(0,-4,1), hpr=(0,-60,0), radius=15.0, fov=60.0)
        #self.renderer.addLight(color=(0.3,0.3,0.5), pos=(2,3,2), radius=12.0)
        self.accept('space', self.do_debug)

    def do_debug(self):
        for name, buff in self.renderer.filter_buff.items():
            print name, buff.getFbSize()

d=Demo()
base.run()
