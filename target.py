# ------------------------------------------------------------------------------
#   BSD 2-Clause License
#   
#   Copyright (c) 2019, Thomas Larsson
#   All rights reserved.
#   
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#   
#   1. Redistributions of source code must retain the above copyright notice, this
#      list of conditions and the following disclaimer.
#   
#   2. Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#   
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#   DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#   FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#   DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#   SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#   CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#   OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#   OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

import bpy
from bpy.props import *
from bpy_extras.io_utils import ExportHelper
import math
import os

from . import utils
from . import t_pose
from .utils import *
from .armature import CArmature


class CTargetInfo:
    def __init__(self, name):
        self.name = name
        self.filepath = "None"
        self.bones = []
        self.parents = {}
        

    def readFile(self, filepath):
        import json
        print("Read target file", filepath)
        self.filepath = filepath
        with open(filepath, "r") as fp:
            struct = json.load(fp)
        self.name = struct["name"]
        self.bones = [(key, nameOrNone(value)) for key,value in struct["bones"].items()]
        if "parents" in struct.keys():
            self.parents = struct["parents"]
        

    def addAutoBones(self, rig):
        self.bones = []
        for pb in rig.pose.bones:
            if pb.McpBone:
                self.bones.append( (pb.name, pb.McpBone) )
        self.addParents(rig)
        

    def addManualBones(self, rig):
        for pb in rig.pose.bones:
            pb.McpBone = ""
        for bname,mhx in self.bones:
            if bname in rig.pose.bones.keys():
                rig.pose.bones[bname].McpBone = mhx
            else:
                print("  ", bname)
        self.addParents(rig)
        
        
    def addParents(self, rig):        
        for pb in rig.pose.bones:
            if pb.McpBone:
                pb.McpParent = ""
                par = pb.parent
                while par:
                    if par.McpBone:
                        pb.McpParent = par.name
                        break
                    par = par.parent
        for bname,pname in self.parents.items():
            pb = rig.pose.bones[bname]
            pb.McpParent = pname
        print("Parents")
        for pb in rig.pose.bones:
            if pb.McpBone:
                print("  ", pb.name, pb.McpParent)
          

    def testRig(self, name, rig):
        from .armature import validBone
        print("Testing %s" % name)
        for (bname, mhxname) in self.bones:
            try:
                pb = rig.pose.bones[bname]
            except KeyError:
                pb = None
            if pb is None or not validBone(pb):
                print("  Did not find bone %s (%s)" % (bname, mhxname))
                print("WARNING:\nTarget armature %s does not match armature %s.\nBones:" % (rig.name, name))
                for pair in self.bones:
                    print("  %s : %s" % pair)
                return

#
#   Global variables
#

_targetInfo = {}

def getTargetInfo(rigname):
    global _targetInfo
    return _targetInfo[rigname]

def loadTargets():
    global _targetInfo
    _targetInfo = {}

def isTargetInited(scn):
    return ( _targetInfo != {} )

def ensureTargetInited(scn):
    if not isTargetInited(scn):
        initTargets(scn)

#
#   getTargetArmature(rig, context):
#

def getTargetArmature(rig, context):
    from .t_pose import putInRestPose
    global _targetInfo

    scn = context.scene
    setCategory("Identify Target Rig")
    ensureTargetInited(scn)

    if scn.McpTargetRig == "Automatic":
        name = guessTargetArmatureFromList(rig, scn)
    else:
        name = scn.McpTargetRig

    if name == "Automatic":
        setCategory("Automatic Target Rig")
        amt = CArmature()
        amt.findArmature(rig, ignoreHiddenLayers=scn.McpIgnoreHiddenLayers)
        scn.McpTargetRig = "Automatic"
        amt.display("Target")

        info = _targetInfo[name] = CTargetInfo(name)
        info.addAutoBones(rig)
        rig.McpTPoseFile = ""
        clearCategory()
        return info

    else:
        setCategory("Manual Target Rig")
        scn.McpTargetRig = name
        info = _targetInfo[name]
        if not info.testRig(name, rig):
            pass
        print("Target armature %s" % name)
        info.addManualBones(rig)
        clearCategory()
        return info


def guessTargetArmatureFromList(rig, scn):
    ensureTargetInited(scn)
    print("Guessing target")
    if isMhxRig(rig):
        return "MHX"
    elif isMakeHuman(rig):
        return "Makehuman"
    elif isRigify2(rig):
        return "Rigify 2"
    elif isRigify(rig):
        return "Rigify"
    elif isMhx7Rig(rig):
        return "MH-alpha7"
    elif isGenesis12(rig):
        return "Genesis 1,2"
    elif isGenesis38(rig):
        return "Genesis 3,8"
    else:
        return "Automatic"

#
#   findTargetKeys(mhx, list):
#

def findTargetKeys(mhx, list):
    bones = []
    for (bone, mhx1) in list:
        if mhx1 == mhx:
            bones.append(bone)
    return bones

###############################################################################
#
#    Target armatures
#
###############################################################################

#    (mhx bone, text)

TargetBoneNames = [
    ('hips',         'Root bone'),
    ('spine',        'Lower spine'),
    ('spine-1',      'Middle spine'),
    ('chest',        'Upper spine'),
    ('neck',         'Neck'),
    ('head',         'Head'),
    None,
    ('shoulder.L',   'L shoulder'),
    ('upper_arm.L',  'L upper arm'),
    ('forearm.L',    'L forearm'),
    ('hand.L',       'L hand'),
    None,
    ('shoulder.R',   'R shoulder'),
    ('upper_arm.R',  'R upper arm'),
    ('forearm.R',    'R forearm'),
    ('hand.R',       'R hand'),
    None,
    ('hip.L',        'L hip'),
    ('thigh.L',      'L thigh'),
    ('shin.L',       'L shin'),
    ('foot.L',       'L foot'),
    ('toe.L',        'L toes'),
    None,
    ('hip.R',        'R hip'),
    ('thigh.R',      'R thigh'),
    ('shin.R',       'R shin'),
    ('foot.R',       'R foot'),
    ('toe.R',        'R toes'),
]

###############################################################################
#
#    Target initialization
#
###############################################################################

def initTargets(scn):
    global _targetInfo
    _targetInfo = { "Automatic" : CTargetInfo("Automatic") }
    path = os.path.join(os.path.dirname(__file__), "target_rigs")
    for fname in os.listdir(path):
        filepath = os.path.join(path, fname)
        (name, ext) = os.path.splitext(fname)
        if ext == ".json" and os.path.isfile(filepath):
            info = CTargetInfo("Manual")
            info.readFile(filepath)
            _targetInfo[info.name] = info

    enums =[]
    keys = list(_targetInfo.keys())
    keys.sort()
    for key in keys:
        enums.append((key,key,key))

    bpy.types.Scene.McpTargetRig = EnumProperty(
        items = enums,
        name = "Target rig",
        default = 'Automatic')
    print("Defined McpTargetRig")


class MCP_OT_InitTargets(bpy.types.Operator):
    bl_idname = "mcp.init_targets"
    bl_label = "Init Target Panel"
    bl_description = "(Re)load all .trg files in the target_rigs directory."
    bl_options = {'UNDO'}

    def execute(self, context):
        from .t_pose import initTPoses, initTargetTPose
        try:
            initTPoses()
            initTargetTPose(context.scene)
            initTargets(context.scene)
        except MocapError:
            bpy.ops.mcp.error('INVOKE_DEFAULT')
        return{'FINISHED'}
        

class MCP_OT_GetTargetRig(bpy.types.Operator):
    bl_idname = "mcp.get_target_rig"
    bl_label = "Identify Target Rig"
    bl_description = "Identify the target rig type of the active armature."
    bl_options = {'UNDO'}

    def execute(self, context):
        from .retarget import changeTargetData, restoreTargetData
        rig = context.object
        scn = context.scene
        data = changeTargetData(rig, scn)
        scn.McpTargetRig = "Automatic"        
        try:
            getTargetArmature(rig, context)
        except MocapError:
            bpy.ops.mcp.error('INVOKE_DEFAULT')
        finally:
            restoreTargetData(rig, data)
        return{'FINISHED'}


def saveTargetFile(filepath, context):
    from collections import OrderedDict
    from .t_pose import saveTPose
    from .json import saveJson

    rig = context.object
    scn = context.scene
    fname,ext = os.path.splitext(filepath)
    name = os.path.basename(fname).capitalize().replace(" ","_")
    arm = OrderedDict()
    struct = {"name" : name, "url" : "", "armature" : arm}
    for pb in rig.pose.bones:
        if pb.McpBone:
            arm[pb.name] = pb.McpBone

    filepath = fname + ".json"
    saveJson(struct, filepath)  
    print("Saved %s" % filepath)

    if scn.McpSaveTargetTPose:
        tposePath = fname + "-tpose.json"
        saveTPose(context, tposePath)


class MCP_OT_SaveTargetFile(bpy.types.Operator, ExportHelper):
    bl_idname = "mcp.save_target_file"
    bl_label = "Save Target File"
    bl_description = "Save a .json file for this character"
    bl_options = {'UNDO'}

    filename_ext = ".trg"
    filter_glob : StringProperty(default="*.trg", options={'HIDDEN'})
    filepath : StringProperty(name="File Path", description="Filepath to target file", maxlen=1024, default="")

    def execute(self, context):
        try:
            saveTargetFile(self.properties.filepath, context)
        except MocapError:
            bpy.ops.mcp.error('INVOKE_DEFAULT')
        return{'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

#----------------------------------------------------------
#   Initialize
#----------------------------------------------------------

classes = [
    MCP_OT_InitTargets,
    MCP_OT_GetTargetRig,
    MCP_OT_SaveTargetFile,
]

def initialize():
    bpy.types.Scene.McpTargetRig = EnumProperty(
        items = [("Automatic", "Automatic", "Automatic")],
        name = "Target rig",
        default = "Automatic")    
        
    bpy.types.Scene.McpTargetTPose = EnumProperty(
        items = [("Default", "Default", "Default")],
        name = "Target T-pose",
        default = "Default")              

    for cls in classes:
        bpy.utils.register_class(cls)


def uninitialize():
    for cls in classes:
        bpy.utils.unregister_class(cls)
