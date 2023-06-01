bl_info = {
    "name": "3DCityDB Importer/Exporter",
    "author": "Xingyue Wang",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > 3DCityDB",
    "description": "Visualise 3D City Database data in Blender",
    "warning": "",
    "wiki_url": "",
    "category": "Import-Export",
}
import bpy
from bpy.props import (StringProperty,
                       PointerProperty,
                       )             
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
from bpy.utils import (register_class,
                       unregister_class
                       )
import ctypes
import json
import psycopg2
from psycopg2.extras import RealDictCursor
# ------------------------------------------------------------------------
#    Functions
# ------------------------------------------------------------------------
def clearAll():
    """Delete previous objects when a new connection build"""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    return 0

def connectDatabase(db_host, db_name, db_user, db_password, sql):
    """Connect the database and fetch the data"""
    con = psycopg2.connect(
    host=db_host,
    database=db_name,
    user=db_user,
    password=db_password
    )
    with con.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()
        con.close()
    return rows

def createTable(con):
    """Create table"""
    with con.cursor() as cursor:
        cursor.execute("CREATE TABLE IF NOT EXISTS blender_export ("
                       "id SERIAL PRIMARY KEY,"
                       "building_id integer NOT NULL,"
                       "gmlid VARCHAR(128) NOT NULL,"
                       "height float,"
                       "year_of_construction date,"
                       "year_of_demolition date,"
                       "geometry geometry(MultiPolygonZ,25833) NOT NULL,"
                       "CONSTRAINT export_building_fk FOREIGN KEY (building_id) REFERENCES citydb.building (id)"
                       ");")
        con.commit()
    return 0

def insertIntoTable(con, building_id, gmlid, height, year_of_construction, year_of_demolition, wkt):
    sql = ("INSERT INTO blender_export (building_id,gmlid,height,year_of_construction,year_of_demolition,geometry) "
          "VALUES ('{}','{}','{}',to_date('{}','YYYY-MM-DD'),to_date('{}','YYYY-MM-DD'),ST_GeomFromText('{}'))"
          .format(building_id,gmlid,height,year_of_construction,year_of_demolition,wkt))
    sql = sql.replace("'None',", "null,")
    with con.cursor() as cursor:
        cursor.execute(sql)                       
        con.commit()
    return 0

def exportToDatabase(con, context):
    for obj in context.scene.objects:
        if obj.type == "MESH":
            building_id = obj["building_id"]
            gmlid = obj["gmlid"]
            height = obj["height"]
            year_of_construction = obj["year_of_construction"]
            year_of_demolition = obj["year_of_demolition"]
            # get coordinates of object
            coords = [v.co for v in obj.data.vertices]
            # coordinate arrays to tuples
            plain_v = [v.to_tuple() for v in coords]
            # coordinate tuples to WKT
            wkt = ("MultiPolygon Z (((" + ",".join(" ".join(str(i) for i in tuple) for tuple in plain_v) + 
            ","  + " ".join(str(i) for i in list(plain_v[0])) + ")))")
            insertIntoTable(con, building_id, gmlid, height, year_of_construction, year_of_demolition, wkt)
    return 0

def mergeSurfaces(context):
    name = []
    # deselect all the objects
    bpy.ops.object.select_all(action="DESELECT")
    # loop to record different gmlid
    for obj in context.scene.objects:
        if obj.name.split(".")[0] not in name:
            name.append(obj.name.split(".")[0])
    # merge surfaces of each building by gmlid
    for id in name:
        for obj in context.scene.objects:
            # select the object with the name(gmlid)
            if obj.name.startswith(id):
                obj.name = id
                obj.select_set(True)
                context.view_layer.objects.active = obj
            else:
                obj.select_set(False)
        # merge surfaces
        bpy.ops.object.join()

def separateSurfaces(context):
    for obj in context.scene.objects:
        if obj.type == 'MESH' and len(obj.data.polygons) > 1:
            obj.select_set(True)
            # Enter edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            # Select all faces
            bpy.ops.mesh.select_all(action='SELECT')
            # Separate the faces into individual objects
            bpy.ops.mesh.separate(type='LOOSE')
            # Exit edit mode
            bpy.ops.object.mode_set(mode='OBJECT')
          
def geojsonParser(rows, context):
    """Convert GeoJSON coordinates to Blender Objects"""
    # convert geojson of one row to dictionary
    for row in rows:
        vertices = []
        edges = []
        face = []
        faces = []
#        geometry = None
#        surface_gmlid = None
#        building_id = None
#        year_of_construction = None
#        year_of_demolition = None
#        height = None
#        id = None
        if "geometry" in row:
            geometry = row["geometry"]
#        if "surface_gmlid" in row:
#            surface_gmlid = row["surface_gmlid"]
        if "building_id" in row:
            building_id = row["building_id"]
        if "year_of_construction" in row:
            year_of_construction = row["year_of_construction"]
        if "year_of_demolition" in row:
            year_of_demolition = row["year_of_demolition"]
        if "height" in row:
            height = row["height"]
        if "gmlid" in row:
            id = row["gmlid"]
        if geometry is not None:
            geometry = json.loads(geometry)
            if geometry["type"] == "Polygon":
                for array in geometry["coordinates"]:
                    for point in array:
                        vertices.append(tuple(point))
                # delete the repeating coordinates
                vertices.pop(len(vertices)-1)
                # append vertices tuple in faces
                for i in range(int(len(vertices))):
                    face.append(i)
                faces.append(tuple(face))
            if geometry['type'] == "MultiPolygon":
                for arrays in geometry["coordinates"]:
                    for array in arrays:
                        for point in array:
                            vertices.append(tuple(point))
                # delete the repeating coordinates
                vertices.append(tuple(point))
                # append vertices tuple in faces
                for i in range(int(len(vertices))):
                    face.append(i)
                faces.append(tuple(face))                
        # generate object in blender
        new_mesh = bpy.data.meshes.new(id)
        new_mesh.from_pydata(vertices, edges, faces)
        new_mesh.update()
        new_object = bpy.data.objects.new(id, new_mesh)
        # add height, gmlid, year_of_construction,year_of_demolition as object properties
        new_object["height"] = str(height)
#        new_object["surface_gmlid"] = surface_gmlid
        new_object["gmlid"] = id
        new_object["building_id"] = building_id
        new_object["year_of_construction"] = str(year_of_construction)
        new_object["year_of_demolition"] = str(year_of_demolition)
        context.collection.objects.link(new_object)

# ------------------------------------------------------------------------
#    Operator
# ------------------------------------------------------------------------
class DatabaseConnector(Operator):
    """Connect to database"""
    bl_idname = "database.connect"
    bl_label = "Database Connect"
    
    def execute(self, context):
        # clear all objects in blender before adding database data
        clearAll()
        
        db_host = bpy.data.scenes["Scene"].MyProperties.host
        db_name = bpy.data.scenes["Scene"].MyProperties.name
        db_user = bpy.data.scenes["Scene"].MyProperties.user
        db_password = bpy.data.scenes["Scene"].MyProperties.password
        sql = bpy.data.scenes["Scene"].MyProperties.sql
        
        if db_host != "" and db_name != "" and db_user != "" and db_password != "" and sql != "":
            rows = connectDatabase(db_host, db_name, db_user, db_password, sql)
            # convert GeoJSON data to blender objects
            geojsonParser(rows,context)
        else:
            ctypes.windll.user32.MessageBoxW(0, "Please enter all database Information!", "Warning", 1)

        return {'FINISHED'}
    
class ClearInformation(Operator):
    """Clear Information Box"""
    bl_idname = "dbinfo.clear"
    bl_label = "Clear All DB Info"
    
    def execute(self, context):
        bpy.data.scenes["Scene"].MyProperties.host = ""
        bpy.data.scenes["Scene"].MyProperties.name = ""
        bpy.data.scenes["Scene"].MyProperties.user = ""
        bpy.data.scenes["Scene"].MyProperties.password = ""
        bpy.data.scenes["Scene"].MyProperties.sql = ""
        return {'FINISHED'}
    
class DatabaseExporter(Operator):
    """Export data to a new table"""
    bl_idname = "database.export"
    bl_label = "Export to Database"
    
    def execute(self, context):
        db_host = bpy.data.scenes["Scene"].MyProperties.host
        db_name = bpy.data.scenes["Scene"].MyProperties.name
        db_user = bpy.data.scenes["Scene"].MyProperties.user
        db_password = bpy.data.scenes["Scene"].MyProperties.password
        con = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
        )
        createTable(con)
        exportToDatabase(con, context)
        con.close()
        return {'FINISHED'}

class MergeSurfaces(Operator):
    """Merge surface geometry to buildings"""
    bl_idname = "surface.merge"
    bl_label = "Merge Surfaces to Buildings"
    
    def execute(self,context):
        mergeSurfaces(context)
        return {'FINISHED'}
    
class SeparateBuildingsToSurfaces(Operator):
    """Separate Buildings to single surfaces for expotation"""
    bl_idname = "building.separate"
    bl_label = "Separate Buildings to Surfaces"
    
    def execute(self,context):
        separateSurfaces(context)
        return {'FINISHED'}

class PopupWindow(Operator):
    """Make an object property pop up window"""
    bl_idname = "popup.click"
    bl_label = "Popup Property Window"
    
    name_label = "Name:"
    height_label = "Height:"
    construction_label = "Year of Construction"
    demolition_label = "Year of Demolition"
    def execute(self, context):
        return {'FINISHED'}
    
    def invoke(self, context, event):
        if context.selected_objects:
            # get the set of selected objects
            obj = context.selected_objects
            # read object gmlid and height properties
            if "gmlid" in obj[0].keys():
                self.gmlid = obj[0]["gmlid"]
            else:
                self.gmlid = None
        else:
            self.gmlid = None
        return context.window_manager.invoke_props_dialog(self)
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.MyProperties
        row = layout.row()
        # print the properties in the layout of popup window
        row.label(text=self.name_label)
        row.label(text=self.gmlid)
        layout.prop(context.selected_objects[0], '["height"]')
        layout.prop(context.selected_objects[0], '["year_of_construction"]')
        layout.prop(context.selected_objects[0], '["year_of_demolition"]')
                    
# ------------------------------------------------------------------------
#    Scene Properties
# ------------------------------------------------------------------------

class MyProperties(PropertyGroup):
    host: StringProperty(
        name = "Host",
        description ="Database Host",
        default = "localhost",
        maxlen = 1024,
        )
    name: StringProperty(
        name = "Name",
        description =" Database Name",
        default="3DCityDB",
        maxlen=1024,
        )
    user: StringProperty(
        name = "User",
        description = "Database User",
        default = "postgres",
        maxlen = 1024,
        )
    password: StringProperty(
        name = "Password",
        description = "Database Password",
        subtype = "PASSWORD",
        default = "123456",
        maxlen = 1024,
        )
    sql: StringProperty(
        name = "SQL",
        description = "SQL",
        default = """SELECT b.id AS building_id, co_ts.gmlid AS surface_gmlid, b.measured_height AS height, 
        co.gmlid AS gmlid, ST_Asgeojson(ST_Collect(sg.geometry)) AS geometry,
        b.year_of_construction AS year_of_construction, b.year_of_demolition AS year_of_demolition
        FROM citydb.thematic_surface AS ts INNER JOIN citydb.cityobject AS co_ts 
        ON (co_ts.id = ts.id) INNER JOIN citydb.surface_geometry AS sg 
        ON (ts.lod2_multi_surface_id = sg.root_id) INNER JOIN citydb.building AS b ON ( b.id = ts.building_id )
        INNER JOIN citydb.cityobject as co ON (co.id = b.id)       
        GROUP BY ts.id, b.id, co_ts.gmlid, co.gmlid ORDER BY b.id, ts.id;""",
        maxlen = 1024,
        )
#select building_id, gmlid, height, year_of_construction, year_of_demolition, ST_asgeojson(geometry) as geometry from blender_export;
    gmlid: StringProperty(
        name = "gmlid",
        description = "GMLID",
        maxlen = 1024,
        )
        
# ------------------------------------------------------------------------
#    Panel
# ------------------------------------------------------------------------
class Database_PT_Connect_Panel(Panel):
    bl_label = "PostgreSQL DB Connection"
    bl_idname = "Database_PT_connect"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Database"

    def draw(self, context):
        layout = self.layout
        props = context.scene.MyProperties
        layout.prop(props, "host")
        layout.prop(props, "name")
        layout.prop(props, "user")
        layout.prop(props, "password")
        layout.prop(props, "sql")
        layout.separator()
        
        layout.operator(DatabaseConnector.bl_idname)
        layout.operator(DatabaseExporter.bl_idname)
        layout.operator(MergeSurfaces.bl_idname)
        layout.operator(SeparateBuildingsToSurfaces.bl_idname)
        layout.operator(PopupWindow.bl_idname)
        layout.operator(ClearInformation.bl_idname)
        
# ------------------------------------------------------------------------
#    Registration
# ------------------------------------------------------------------------
classes = (
    MyProperties,
    Database_PT_Connect_Panel,
    DatabaseConnector,
    ClearInformation,
    DatabaseExporter,
    MergeSurfaces,
    SeparateBuildingsToSurfaces,
    PopupWindow,
)

def register():
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.MyProperties = PointerProperty(type=MyProperties)
    
def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.MyProperties
    
if __name__ == "__main__":
    register()