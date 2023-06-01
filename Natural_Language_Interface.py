#import sys
import numpy as np
from mathutils import Vector
import nltk
from nltk.stem import WordNetLemmatizer
#from nltk.tag.senna import SennaTagger
import bpy
from bpy.props import (StringProperty,
                       PointerProperty,
                       )    
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup
                       )
from bpy.utils import (register_class,
                       unregister_class
                       )
#nltk.download('punkt')
#nltk.download('wordnet')
#nltk.download('averaged_perceptron_tagger')
# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------
def occlusion_test(scene, depsgraph, camera, resolution_x, resolution_y):
    # get vectors which define view frustum of camera
    top_right, _, bottom_left, top_left = camera.data.view_frame(scene=scene)

    camera_quaternion = camera.matrix_world.to_quaternion()
    camera_translation = camera.matrix_world.translation

    # get iteration range for both the x and y axes, sampled based on the resolution
    x_range = np.linspace(top_left[0], top_right[0], resolution_x)
    y_range = np.linspace(top_left[1], bottom_left[1], resolution_y)

    z_dir = top_left[2]

    hit_data = set()

    # iterate over all X/Y coordinates
    for x in x_range:
        for y in y_range:
            # get current pixel vector from camera center to pixel
            pixel_vector = Vector((x, y, z_dir))
            # rotate that vector according to camera rotation
            pixel_vector.rotate(camera_quaternion)
            pixel_vector.normalized()

            is_hit, _, _, _, hit_obj, _ = scene.ray_cast(depsgraph, camera_translation, pixel_vector)

            if is_hit:
                hit_data.add(hit_obj)

    return hit_data

def selectObjectsInCameraView(context):
    # sampling resolution of raytracing from the camera
    # usually scene objects are not pixel-sized, so you can get away with fewer pixels
    res_ratio = 0.25
    res_x = int(context.scene.render.resolution_x * res_ratio)
    res_y = int(context.scene.render.resolution_y * res_ratio)

    visible_objs = occlusion_test(context.scene, context.evaluated_depsgraph_get(), 
                context.scene.objects['Camera'], res_x, res_y)
    # deselect the objects in the scene
    bpy.ops.object.select_all(action="DESELECT")
    for obj in visible_objs:
        obj.select_set(True)
        
def selectObjectsByHeight(context, adjs, numbers):
    # Get selected objects from the context  
    selected_objs = bpy.context.selected_objects
    if "highest" in adjs:
        height = 0
        building = None
    if "lowest" in adjs:
        height = float('inf')
        building = None    
    if "high" in adjs:
        height = 30
        buildings = []
    if "low" in adjs:
        height = 15
        buildings = []   
    if "higher" in adjs or "lower" in adjs:
        height = numbers[0]
        buildings = []
    for obj in selected_objs:
        if "height" in obj.keys():
            if "highest" in adjs:
                if float(obj['height']) > height:
                    height = float(obj['height'])
                    building = obj                    
            if "lowest" in adjs:
                if float(obj['height']) < height:
                    height = float(obj['height'])
                    building = obj
            if "high" in adjs:
                if float(obj['height']) > height:
                    buildings.append(obj)
            if "low" in adjs:
                if float(obj['height']) < height:
                    buildings.append(obj)
            if "higher" in adjs:
                if float(obj['height']) > float(height):
                    buildings.append(obj)
            if "lower" in adjs:
                if float(obj['height']) < float(height):
                    buildings.append(obj)    
    if "highest" in adjs or "lowest" in adjs:
        bpy.ops.object.select_all(action='DESELECT')
        building.select_set(True)
    if "high" in adjs or "low" in adjs or "higher" in adjs or "lower" in adjs:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in buildings:
            obj.select_set(True)
   
def selectObjectsByDate(context, verbs, cons, numbers):
    selected_objs = bpy.context.selected_objects
    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_objs:
        if "constructed" in verbs:
            if "year_of_construction" in obj.keys():
                if "before" in cons:
                    if int(obj['year_of_construction'][:4]) < int(numbers[0]):
                        obj.select_set(True)
                if "after" in cons:
                    if int(obj['year_of_construction'][:4]) > int(numbers[0]):
                        obj.select_set(True)
                if "in" in cons:
                    if int(obj['year_of_construction'][:4]) == int(numbers[0]):
                        obj.select_set(True)                                
        if "demolished" in verbs or "destroyed" in verbs:
            if "year_of_demolition" in obj.keys():
                if "before" in cons:
                    if int(obj['year_of_demolition'][:4]) < int(numbers[0]):
                        obj.select_set(True)
                if "after" in cons:
                    if int(obj['year_of_demolition'][:4]) > int(numbers[0]):
                        obj.select_set(True)
                if "in" in cons:
                    if int(obj['year_of_demolition'][:4]) == int(numbers[0]):
                        obj.select_set(True)
                            
def selectObjectsByPosition(context, adjs):
    selected_objs = context.selected_objects
    camera_location = bpy.data.objects['Camera'].location
    if "left" in adjs or "right" in adjs:
        bpy.ops.object.select_all(action='DESELECT')

    for obj in selected_objs:
        if obj.type == "MESH":
            coords = [v.co for v in obj.data.vertices]
        if "left" in adjs:          
            if all(coord.y < camera_location.y for coord in coords):
                obj.select_set(True)
        if "right" in adjs:
            if all(coord.y > camera_location.y for coord in coords):
                obj.select_set(True)

# ------------------------------------------------------------------------
#    Operator
# ------------------------------------------------------------------------
class SelectObjectsInCameraView(Operator):
    """Select objects in Camera View"""
    bl_label = "Select Objects in Camera View"
    bl_idname = "select.objects"
    
    def execute(self,context):
        selectObjectsInCameraView(context)
        return {'FINISHED'}
    
class QuerySelector(Operator):
    """Select the objects by the query"""
    bl_label = "Query Selector"
    bl_idname = "query.select"
    
    def execute(self, context):        
#        home = sys.exec_prefix
        query = bpy.data.scenes['Scene'].Properties.query
        # tokenization
        tokens = nltk.word_tokenize(query)
        # lemmatization
        lemmatizer = WordNetLemmatizer()
        lemmatized_tokens = [lemmatizer.lemmatize(token) for token in tokens]
        # tag the pos
#        tagged_tokens = SennaTagger(home+'/senna').tag(lemmatized_tokens)
        tagged_tokens = nltk.pos_tag(lemmatized_tokens)
        nouns = [token for token, pos in tagged_tokens if pos.startswith('N')]
        adjs = [token for token, pos in tagged_tokens if pos.startswith('JJ')]
        verbs = [token for token, pos in tagged_tokens if pos.startswith('VB')]
        cons = [token for token, pos in tagged_tokens if pos.startswith('IN')]
        numbers = [token for token, pos in tagged_tokens if pos.startswith('CD')]
        if "building" in nouns: 
            if adjs is not None:    
                selectObjectsByHeight(context, adjs, numbers)
            if "constructed" in verbs or "demolished" in verbs or "destroyed" in verbs:                
                selectObjectsByDate(context, verbs, cons, numbers)
            if "left" in adjs or "right" in adjs or "left" in nouns or "right" in nouns:    
                selectObjectsByPosition(context, adjs)
                selectObjectsByPosition(context, nouns)                             

        return {'FINISHED'}
# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------
class Properties(PropertyGroup):
    query: StringProperty(
        name = "Query Words",
        description ="Natural Language Query",
        default = "select the high buildings constructed before 1940",
#select the building constructed after 1940
#select the high buildings constructed before 1940
        maxlen = 1024,
        )

# ------------------------------------------------------------------------
#    Panel
# ------------------------------------------------------------------------
class Natural_Language_PT_Panel(Panel):
    bl_label = "Natural Language Interface"
    bl_idname = "Natural_Language_PT"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Natural Language"

    def draw(self, context):
        layout = self.layout
        props = context.scene.Properties
        
        layout.prop(props, "query")
        layout.operator(SelectObjectsInCameraView.bl_idname)
        layout.operator(QuerySelector.bl_idname)

# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------
classes = (
        SelectObjectsInCameraView,
        Natural_Language_PT_Panel,
        Properties,
        QuerySelector,
        )

def register():
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.Properties = bpy.props.PointerProperty(type=Properties)
    
def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.Properties
    
if __name__ == "__main__":
    register()