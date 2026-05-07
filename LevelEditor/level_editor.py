bl_info = {
    "name": "Level Editor",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (4, 4, 0),
    "location": "View3D > Sidebar > Level Editor",
    "description": "01. レベルエディタ基盤の全項目 (01_01〜01_12)",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

import bpy
import json
import os
import math
import gpu
import mathutils
from gpu_extras.batch import batch_for_shader
import blf
import bpy_extras

# -------------------------------------------------------------
# 01_08. カスタムプロパティ & 01_10. Boxコライダー
# -------------------------------------------------------------
class LevelEditorProperties(bpy.types.PropertyGroup):
    is_export_target: bpy.props.BoolProperty(
        name="エクスポート対象",
        description="このオブジェクトをJSON出力に含めるかどうか",
        default=True
    )
    obj_type: bpy.props.EnumProperty(
        name="タイプ",
        description="オブジェクトの役割",
        items=[
            ('NONE', "なし", ""),
            ('PLAYER', "プレイヤー", ""),
            ('ENEMY', "エネミー", ""),
            ('OBSTACLE', "障害物", "")
        ]
    )
    # Boxコライダー用プロパティ
    has_box_collider: bpy.props.BoolProperty(
        name="Boxコライダー",
        description="当たり判定用のBoxコライダーを持つか",
        default=False
    )
    collider_size: bpy.props.FloatVectorProperty(
        name="コライダーサイズ",
        description="XYZの各辺の半分の長さ",
        default=(1.0, 1.0, 1.0),
        size=3
    )

# -------------------------------------------------------------
# 01_05. Operator (追加)
# -------------------------------------------------------------
class LEVELEDITOR_OT_add_object(bpy.types.Operator):
    """シーンにレベルエディタ用のオブジェクトを追加します"""
    bl_idname = "leveleditor.add_object"
    bl_label = "オブジェクト追加"
    bl_options = {'REGISTER', 'UNDO'}
    
    obj_type: bpy.props.StringProperty()
    
    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=2.0)
        obj = context.active_object
        obj.name = f"{self.obj_type}_OBJ"
        
        # カスタムプロパティの設定
        obj.leveleditor_props.is_export_target = True
        obj.leveleditor_props.obj_type = self.obj_type
        
        # 障害物ならデフォルトでコライダーをON
        if self.obj_type == "OBSTACLE":
            obj.leveleditor_props.has_box_collider = True
            
        return {'FINISHED'}

# -------------------------------------------------------------
# 01_07. ファイル出力 & 01_11. JSON出力
# -------------------------------------------------------------
class LEVELEDITOR_OT_export_json(bpy.types.Operator):
    """現在のシーンの対象オブジェクトをJSONに出力します"""
    bl_idname = "leveleditor.export_json"
    bl_label = "JSONをエクスポート"
    
    def execute(self, context):
        level_data = {"objects": []}
        
        for obj in context.scene.objects:
            # Meshかつエクスポート対象のみ
            if obj.type == 'MESH' and obj.leveleditor_props.is_export_target:
                obj_data = {
                    "name": obj.name,
                    "type": obj.leveleditor_props.obj_type,
                    "position": {
                        "x": obj.location.x,
                        "y": obj.location.y,
                        "z": obj.location.z
                    },
                    "rotation": {
                        "x": math.degrees(obj.rotation_euler.x),
                        "y": math.degrees(obj.rotation_euler.y),
                        "z": math.degrees(obj.rotation_euler.z)
                    },
                    "scale": {
                        "x": obj.scale.x,
                        "y": obj.scale.y,
                        "z": obj.scale.z
                    },
                    "collider": None
                }
                
                # コライダー情報
                if obj.leveleditor_props.has_box_collider:
                    col = obj.leveleditor_props.collider_size
                    obj_data["collider"] = {
                        "type": "BOX",
                        "size": {"x": col[0], "y": col[1], "z": col[2]}
                    }
                
                level_data["objects"].append(obj_data)
        
        filepath = bpy.data.filepath
        if not filepath:
            self.report({'WARNING'}, "先にBlenderファイルを保存してください。")
            return {'CANCELLED'}
            
        export_path = os.path.join(os.path.dirname(filepath), "level_data.json")
        
        # ファイル出力 (01_07, 01_11)
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(level_data, f, ensure_ascii=False, indent=4)
            
        self.report({'INFO'}, f"エクスポート完了: {export_path}")
        return {'FINISHED'}

# -------------------------------------------------------------
# 01_12. ローダーと配置 (JSON読み込み)
# -------------------------------------------------------------
class LEVELEDITOR_OT_import_json(bpy.types.Operator):
    """JSONファイルからオブジェクトを読み込んで配置します"""
    bl_idname = "leveleditor.import_json"
    bl_label = "JSONをインポート"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        filepath = bpy.data.filepath
        if not filepath:
            self.report({'WARNING'}, "先にBlenderファイルを保存してください。")
            return {'CANCELLED'}
            
        import_path = os.path.join(os.path.dirname(filepath), "level_data.json")
        if not os.path.exists(import_path):
            self.report({'WARNING'}, "level_data.json が見つかりません。")
            return {'CANCELLED'}
            
        # JSONロード
        with open(import_path, 'r', encoding='utf-8') as f:
            level_data = json.load(f)
            
        # 配置処理
        for obj_data in level_data.get("objects", []):
            bpy.ops.mesh.primitive_cube_add()
            obj = context.active_object
            
            obj.name = obj_data["name"]
            
            pos = obj_data["position"]
            obj.location = (pos["x"], pos["y"], pos["z"])
            
            rot = obj_data["rotation"]
            obj.rotation_euler = (math.radians(rot["x"]), math.radians(rot["y"]), math.radians(rot["z"]))
            
            scl = obj_data["scale"]
            obj.scale = (scl["x"], scl["y"], scl["z"])
            
            obj.leveleditor_props.is_export_target = True
            obj.leveleditor_props.obj_type = obj_data.get("type", "NONE")
            
            if obj_data.get("collider"):
                obj.leveleditor_props.has_box_collider = True
                col_size = obj_data["collider"]["size"]
                obj.leveleditor_props.collider_size = (col_size["x"], col_size["y"], col_size["z"])
                
        self.report({'INFO'}, "インポート完了")
        return {'FINISHED'}

# -------------------------------------------------------------
# 01_04. Menu & 01_06. レベルエディタ制作 (パネルUI)
# -------------------------------------------------------------
class LEVELEDITOR_MT_menu(bpy.types.Menu):
    """3Dビューポートのヘッダーメニューに追加するカスタムメニュー"""
    bl_label = "Level Editor"
    bl_idname = "LEVELEDITOR_MT_menu"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("leveleditor.export_json", text="Export JSON", icon='EXPORT')
        layout.operator("leveleditor.import_json", text="Import JSON", icon='IMPORT')

def menu_func(self, context):
    self.layout.menu(LEVELEDITOR_MT_menu.bl_idname)

class LEVELEDITOR_PT_panel(bpy.types.Panel):
    """Nキーで表示されるサイドバーパネル"""
    bl_label = "Level Editor"
    bl_idname = "LEVELEDITOR_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Level Editor'
    
    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        
        # オブジェクト生成
        col = layout.column(align=True)
        col.label(text="新規作成:")
        col.operator("leveleditor.add_object", text="プレイヤー生成").obj_type = "PLAYER"
        col.operator("leveleditor.add_object", text="エネミー生成").obj_type = "ENEMY"
        col.operator("leveleditor.add_object", text="障害物生成").obj_type = "OBSTACLE"
        
        # 選択中オブジェクトのプロパティ
        if obj and obj.type == 'MESH':
            box = layout.box()
            box.label(text=f"選択中: {obj.name}", icon='OBJECT_DATA')
            box.prop(obj.leveleditor_props, "is_export_target")
            
            if obj.leveleditor_props.is_export_target:
                box.prop(obj.leveleditor_props, "obj_type")
                box.prop(obj.leveleditor_props, "has_box_collider")
                if obj.leveleditor_props.has_box_collider:
                    box.prop(obj.leveleditor_props, "collider_size")
        else:
            layout.separator()
            layout.label(text="(オブジェクト未選択)")
        
        # 入出力
        layout.separator()
        layout.label(text="データ入出力:")
        layout.operator("leveleditor.export_json", text="JSONエクスポート", icon='EXPORT')
        layout.operator("leveleditor.import_json", text="JSONインポート", icon='IMPORT')

# -------------------------------------------------------------
# 01_09. Blenderの描画拡張 (Viewport描画)
# -------------------------------------------------------------
draw_handler = None

def draw_callback_px():
    context = bpy.context
    if not context.scene: return
    
    # シェーダーの取得 (Blender 4.0+対応)
    try:
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    except ValueError:
        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)
    
    for obj in context.scene.objects:
        if obj.type == 'MESH' and obj.leveleditor_props.is_export_target:
            
            # コライダーのワイヤーフレーム描画 (01_10対応)
            if obj.leveleditor_props.has_box_collider:
                matrix = obj.matrix_world
                sx, sy, sz = obj.leveleditor_props.collider_size
                
                # Boxの8頂点
                coords = [
                    ( sx,  sy,  sz), ( sx, -sy,  sz), (-sx, -sy,  sz), (-sx,  sy,  sz),
                    ( sx,  sy, -sz), ( sx, -sy, -sz), (-sx, -sy, -sz), (-sx,  sy, -sz)
                ]
                world_coords = [matrix @ mathutils.Vector(c) for c in coords]
                
                # ワイヤーフレームの線(インデックス)
                indices = [
                    (0,1), (1,2), (2,3), (3,0),
                    (4,5), (5,6), (6,7), (7,4),
                    (0,4), (1,5), (2,6), (3,7)
                ]
                
                batch = batch_for_shader(shader, 'LINES', {"pos": world_coords}, indices=indices)
                shader.bind()
                # 少し透明な赤色
                shader.uniform_float("color", (1.0, 0.2, 0.2, 0.6))
                batch.draw(shader)
                
            # タイプ名などのテキスト描画 (blf使用)
            region = context.region
            rv3d = context.region_data
            if region and rv3d:
                # 3D座標から画面2D座標へ変換
                pos2d = bpy_extras.view3d_utils.location_3d_to_region_2d(region, rv3d, obj.location)
                if pos2d:
                    blf.position(0, pos2d[0], pos2d[1], 0)
                    blf.size(0, 16)
                    
                    # オブジェクトタイプで色分け
                    if obj.leveleditor_props.obj_type == 'PLAYER':
                        blf.color(0, 0.2, 1.0, 0.2, 1.0)
                    elif obj.leveleditor_props.obj_type == 'ENEMY':
                        blf.color(0, 1.0, 0.2, 0.2, 1.0)
                    else:
                        blf.color(0, 1.0, 1.0, 1.0, 1.0)
                        
                    label_text = f"[{obj.leveleditor_props.obj_type}]"
                    blf.draw(0, label_text)

    gpu.state.blend_set('NONE')

# -------------------------------------------------------------
# 登録処理 (01_01, 01_02, 01_03)
# -------------------------------------------------------------
classes = (
    LevelEditorProperties,
    LEVELEDITOR_OT_add_object,
    LEVELEDITOR_OT_export_json,
    LEVELEDITOR_OT_import_json,
    LEVELEDITOR_MT_menu,
    LEVELEDITOR_PT_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # カスタムプロパティをObjectクラスにアタッチ
    bpy.types.Object.leveleditor_props = bpy.props.PointerProperty(type=LevelEditorProperties)
    
    # ビューポートの上部メニューに追加
    bpy.types.VIEW3D_MT_editor_menus.append(menu_func)
    
    # 描画ハンドラの登録
    global draw_handler
    draw_handler = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (), 'WINDOW', 'POST_VIEW')

def unregister():
    global draw_handler
    if draw_handler:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handler, 'WINDOW')
        draw_handler = None
        
    bpy.types.VIEW3D_MT_editor_menus.remove(menu_func)
    del bpy.types.Object.leveleditor_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
