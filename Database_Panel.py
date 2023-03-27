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
                       "gmlid VARCHAR(128) NOT NULL,"
                       "envelope geometry(PolygonZ,25833) NOT NULL"
                       ");")
        con.commit()
    return 0

def insertIntoTable(con, gmlid, wkt):
    with con.cursor() as cursor:
        cursor.execute("INSERT INTO blender_export (gmlid, envelope) "
                       "VALUES ('{}',ST_GeomFromText('{}'))".format(gmlid, wkt)
                       )
        con.commit()
    return 0

def exportToDatabase(con):
    for obj in bpy.context.scene.objects:
        gmlid = obj.name
        # get coordinates of object
        coords = [v.co for v in obj.data.vertices]
        # coordinate arrays to tuples
        plain_v = [v.to_tuple() for v in coords]
        # coordinate tuples to WKT
        wkt = "Polygon Z ((" + ",".join(" ".join(str(i) for i in tuple) for tuple in plain_v) + ","  + " ".join(str(i) for i in list(plain_v[0])) + "))"
        insertIntoTable(con, gmlid, wkt)
    return 0

def geojsonParser(rows):
    """Convert GeoJSON coordinates to Blender Objects"""
    # convert geojson of one row to dictionary
    for row in rows:
        vertices = []
        edges = []
        face = []
        faces = []
        geometry = row['geometry']
        if geometry is not None:
            geometry = json.loads(geometry)
            id = row['gmlid']
            if geometry['type'] == "Polygon":
                for array in geometry['coordinates']:
                    for point in array:
                        vertices.append(tuple(point))
                # delete the repeating coordinates
                vertices.pop(len(vertices)-1)
                # append vertices tuple in faces
                for i in range(int(len(vertices))):
                    face.append(i)
                faces.append(tuple(face))
            if geometry['type'] == "MultiPolygon":
                for array in geometry['coordinates']:
                    for a in array:
                        for point in a:
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
        bpy.context.collection.objects.link(new_object)
    return {'FINISHED'}
# ------------------------------------------------------------------------
#    Operator
# ------------------------------------------------------------------------
class DatabaseConnector(Operator):
    """Connect to database"""
    bl_idname = "database.connect"
    bl_label = "Database Connect"
    
    def execute(self, context):
        clearAll()
        
        db_host = bpy.data.scenes['Scene'].my_tool.host
        db_name = bpy.data.scenes['Scene'].my_tool.name
        db_user = bpy.data.scenes['Scene'].my_tool.user
        db_password = bpy.data.scenes['Scene'].my_tool.password
        sql = bpy.data.scenes['Scene'].my_tool.sql
        
        if db_host != "" and db_name != "" and db_user != "" and db_password != "" and sql != "":
            rows = connectDatabase(db_host, db_name, db_user, db_password, sql)
            # convert GeoJSON data to blender objects
            geojsonParser(rows)
        else:
            ctypes.windll.user32.MessageBoxW(0, "Please enter all database Information!", "Warning", 1)

        return {'FINISHED'}
    
class ClearInformation(Operator):
    """Clear Information Box"""
    bl_idname = "dbinfo.clear"
    bl_label = "Clear All DB Info"
    
    def execute(self, context):
        bpy.data.scenes['Scene'].my_tool.host = ""
        bpy.data.scenes['Scene'].my_tool.name = ""
        bpy.data.scenes['Scene'].my_tool.user = ""
        bpy.data.scenes['Scene'].my_tool.password = ""
        bpy.data.scenes['Scene'].my_tool.sql = ""
        return {'FINISHED'}
    
class DatabaseExporter(Operator):
    """Export data to a new table"""
    bl_idname = "database.export"
    bl_label = "Export to Database"
    
    def execute(self, context):
        db_host = bpy.data.scenes['Scene'].my_tool.host
        db_name = bpy.data.scenes['Scene'].my_tool.name
        db_user = bpy.data.scenes['Scene'].my_tool.user
        db_password = bpy.data.scenes['Scene'].my_tool.password
        con = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
        )
        createTable(con)
        exportToDatabase(con)
        con.close()
        return {'FINISHED'} 

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
        default = "123456",
        maxlen = 1024,
        )
    sql: StringProperty(
        name = "SQL",
        description = "SQL",
        default = "SELECT co_ts.gmlid AS gmlid, ST_Asgeojson(ST_Collect(sg.geometry)) AS geometry FROM citydb.thematic_surface AS ts INNER JOIN citydb.cityobject AS co_ts ON ( co_ts.id = ts.id ) INNER JOIN citydb.surface_geometry AS sg ON ( ts.lod2_multi_surface_id= sg.root_id ) GROUP BY co_ts.gmlid;",
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
        scene = context.scene
        mytool = scene.my_tool

        layout.prop(mytool, "host")
        layout.prop(mytool, "name")
        layout.prop(mytool, "user")
        layout.prop(mytool, "password")
        layout.prop(mytool, "sql")
        layout.separator()
        layout.operator(DatabaseConnector.bl_idname)
        layout.operator(DatabaseExporter.bl_idname)
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
)

def register():
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.my_tool = PointerProperty(type=MyProperties)

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.my_tool

if __name__ == "__main__":
    register()