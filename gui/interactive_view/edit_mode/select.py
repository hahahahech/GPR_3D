"""
选择逻辑模块
实现点、线、面的选择检测和处理
"""
import numpy as np
from typing import Optional, Dict, List, Tuple, Any, Union
from PyQt5.QtCore import QPoint
from gui.interactive_view.camera import CameraController
from gui.interactive_view.coordinates import CoordinateConverter
from model.geometry import Surface

class SelectionManager:
    """选择管理器 - 负责对象选择检测和处理逻辑"""
    
    # 选择阈值（世界坐标单位）
    SELECTION_THRESHOLD = 0.1
    
    def __init__(self, edit_manager):
        """初始化选择管理器"""
        self._edit_manager = edit_manager

    def get_active_plane(self) -> Optional[str]:
        """返回当前激活的面ID或 None"""
        return self._edit_manager.active_plane_id

    def get_active_plane_vertices(self) -> Optional[np.ndarray]:
        """返回当前激活面的顶点坐标或 None"""
        return self._edit_manager.get_active_plane_vertices()
    
    # ========== 距离计算 ==========
    
    @staticmethod
    def distance_point_to_line(point: np.ndarray, line_start: np.ndarray, line_end: np.ndarray) -> float:
        """计算点到线段的最短距离"""
        # 线段方向向量
        line_vec = line_end - line_start
        line_len = np.linalg.norm(line_vec)
        
        if line_len < 1e-10:
            # 线段退化为点
            return np.linalg.norm(point - line_start)
        
        line_vec_normalized = line_vec / line_len
        
        # 从起点到目标点的向量
        point_vec = point - line_start
        
        # 投影到线段方向上的长度
        t = np.dot(point_vec, line_vec_normalized)
        
        # 限制在线段范围内
        t = np.clip(t, 0.0, line_len)
        
        # 线段上最近的点
        closest_point = line_start + line_vec_normalized * t
        
        # 返回距离
        return np.linalg.norm(point - closest_point)
    
    @staticmethod
    def distance_point_to_plane(point: np.ndarray, plane_vertices: np.ndarray) -> float:
        """计算点到面的最短距离（点到面的距离）"""
        if plane_vertices.shape[0] < 3:
            return float('inf')
        
        # 计算面的法向量（使用前三个点）
        v1 = plane_vertices[1] - plane_vertices[0]
        v2 = plane_vertices[2] - plane_vertices[0]
        normal = np.cross(v1, v2)
        normal_len = np.linalg.norm(normal)
        
        if normal_len < 1e-10:
            # 面退化为线或点，计算到所有顶点的最小距离
            distances = [np.linalg.norm(point - v) for v in plane_vertices]
            return min(distances)
        
        normal = normal / normal_len
        
        # 计算点到面的距离
        # 使用面上任意一点（第一个点）
        plane_point = plane_vertices[0]
        point_vec = point - plane_point
        
        # 点到面的距离 = |(point - plane_point) · normal|
        distance = abs(np.dot(point_vec, normal))
        
        return distance
    
    # ========== 选择逻辑 ==========
    
    @staticmethod
    def _point_in_polygon(point: np.ndarray, vertices: np.ndarray) -> bool:
        """
        判断点是否在多边形内（屏幕空间）
        使用射线法（Ray Casting Algorithm）
        """
        x, y = point[0], point[1]
        n = len(vertices)
        inside = False
        
        p1x, p1y = vertices[0]
        for i in range(1, n + 1):
            p2x, p2y = vertices[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        else:
                            xinters = p1x  # 水平边，使用p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def _select_points_at_screen(self, renderer, camera_pos, vtk_x, vtk_y, pixel_threshold):
        """检测屏幕位置的点候选对象"""
        candidates = []
        for point_id, point_obj in self._edit_manager.points.items():
            pos = point_obj.position
            renderer.SetWorldPoint(pos[0], pos[1], pos[2], 1.0)
            renderer.WorldToDisplay()
            display_pos = renderer.GetDisplayPoint()
            screen_dist = np.sqrt((display_pos[0] - vtk_x)**2 + (display_pos[1] - vtk_y)**2)
            
            if screen_dist <= pixel_threshold:
                depth = np.linalg.norm(pos - camera_pos)
                candidates.append({
                    'type': 'point',
                    'id': point_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': pos.copy(),
                    'focus_point': pos.copy()
                })
        return candidates
    
    def _select_lines_at_screen(self, renderer, camera_pos, vtk_x, vtk_y, pixel_threshold):
        """检测屏幕位置的线候选对象"""
        candidates = []
        for line_id, (start, end) in self._edit_manager.lines.items():
            try:
                if isinstance(start, str):
                    start_pos = self._edit_manager.points[start].position
                else:
                    start_pos = np.array(start, dtype=np.float64)
                if isinstance(end, str):
                    end_pos = self._edit_manager.points[end].position
                else:
                    end_pos = np.array(end, dtype=np.float64)
            except Exception:
                continue
            
            # 投影起点和终点到屏幕
            renderer.SetWorldPoint(start_pos[0], start_pos[1], start_pos[2], 1.0)
            renderer.WorldToDisplay()
            start_screen = np.array(renderer.GetDisplayPoint()[:2])
            
            renderer.SetWorldPoint(end_pos[0], end_pos[1], end_pos[2], 1.0)
            renderer.WorldToDisplay()
            end_screen = np.array(renderer.GetDisplayPoint()[:2])
            
            # 计算点到线段的距离
            click_screen = np.array([vtk_x, vtk_y])
            line_vec = end_screen - start_screen
            line_len = np.linalg.norm(line_vec)
            
            if line_len < 1e-6:
                screen_dist = np.linalg.norm(click_screen - start_screen)
            else:
                t = np.dot(click_screen - start_screen, line_vec) / (line_len ** 2)
                t = np.clip(t, 0.0, 1.0)
                closest_point = start_screen + t * line_vec
                screen_dist = np.linalg.norm(click_screen - closest_point)
            
            if screen_dist <= pixel_threshold:
                mid_pos = (start_pos + end_pos) / 2.0
                depth = np.linalg.norm(mid_pos - camera_pos)
                candidates.append({
                    'type': 'line',
                    'id': line_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': (start_pos.copy(), end_pos.copy()),
                    'focus_point': mid_pos
                })
        return candidates
    
    def _select_planes_at_screen(self, renderer, camera_pos, vtk_x, vtk_y, pixel_threshold):
        """检测屏幕位置的面候选对象"""
        candidates = []
        for plane_id, vertices in self._edit_manager.planes.items():
            # 将面的顶点投影到屏幕
            screen_vertices = []
            for vertex in vertices:
                renderer.SetWorldPoint(vertex[0], vertex[1], vertex[2], 1.0)
                renderer.WorldToDisplay()
                display_pos = renderer.GetDisplayPoint()
                screen_vertices.append([display_pos[0], display_pos[1]])

            screen_vertices = np.array(screen_vertices)
            click_screen = np.array([vtk_x, vtk_y])

            # 检查点击是否在面的屏幕投影内
            inside = self._point_in_polygon(click_screen, screen_vertices)

            if inside:
                screen_dist = 0.0
            else:
                center_screen = np.mean(screen_vertices, axis=0)
                screen_dist = np.linalg.norm(click_screen - center_screen)

            if inside or screen_dist <= pixel_threshold:
                center = np.mean(vertices, axis=0)
                depth = np.linalg.norm(center - camera_pos)
                # 检测是否为边界面
                is_boundary = plane_id.startswith('boundary_')
                candidates.append({
                    'type': 'plane',
                    'id': plane_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': vertices.copy(),
                    'focus_point': center,
                    'is_boundary': is_boundary
                })
        return candidates
    
    def select_at_screen_position(self, screen_pos: QPoint, view, pixel_threshold: int = 10) -> Optional[Dict[str, Any]]:
        """在屏幕坐标位置选择对象（基于屏幕像素距离，考虑深度） """
        renderer = view.renderer
        width = view.width()
        height = view.height()
        
        # 获取相机位置（用于深度排序）
        camera = renderer.GetActiveCamera()
        camera_pos = np.array(camera.GetPosition())
        
        # 将Qt坐标转换为VTK坐标
        vtk_x = screen_pos.x()
        vtk_y = height - screen_pos.y() - 1
        
        # 按顺序检测：点 > 线 > 面
        candidates = []
        
        # 1. 检测点
        point_candidates = self._select_points_at_screen(renderer, camera_pos, vtk_x, vtk_y, pixel_threshold)
        candidates.extend(point_candidates)
        
        # 2. 检测线
        line_candidates = self._select_lines_at_screen(renderer, camera_pos, vtk_x, vtk_y, pixel_threshold)
        candidates.extend(line_candidates)
        
        # 3. 检测面
        plane_candidates = self._select_planes_at_screen(renderer, camera_pos, vtk_x, vtk_y, pixel_threshold)
        candidates.extend(plane_candidates)
        
        # 如果没有候选对象，返回None
        if not candidates:
            self._edit_manager._selected_point_id = None
            self._edit_manager._selected_line_id = None
            self._edit_manager._selected_plane_id = None
            self._edit_manager.set_active_plane(None)
            return None
        
        # 排序：按类型优先级（点>线>面），面中生成的面优先于边界面，然后按深度，最后按屏幕距离
        type_priority = {'point': 0, 'line': 1, 'plane': 2}
        candidates.sort(key=lambda x: (
            type_priority[x['type']], 
            x.get('is_boundary', False),  # 生成的面(False)优先于边界面(True)
            x['depth'], 
            x['screen_dist']
        ))

        # 根据选中对象类型更新状态
        selected = candidates[0]
        sel_type = selected['type']
        
        if sel_type == 'point':
            self._edit_manager._selected_point_id = selected['id']
            self._edit_manager._selected_line_id = None
            self._edit_manager._selected_plane_id = None
            self._edit_manager.set_active_plane(None)
        elif sel_type == 'line':
            self._edit_manager._selected_point_id = None
            self._edit_manager._selected_line_id = selected['id']
            self._edit_manager._selected_plane_id = None
            self._edit_manager.set_active_plane(None)
        elif sel_type == 'plane':
            self._edit_manager._selected_point_id = None
            self._edit_manager._selected_line_id = None
            self._edit_manager._selected_plane_id = selected['id']
            self._edit_manager.set_active_plane(selected['id'])
            
            # 聚焦到面
            plane_data = self._edit_manager.planes.get(self._edit_manager._selected_plane_id)
            if plane_data is not None:
                if hasattr(plane_data, 'vertices') and hasattr(plane_data, 'normal'):
                    # Surface 对象，直接使用
                    CameraController.focus_on_plane(view, plane_data)
                else:
                    # 旧的顶点数组格式，创建临时 Surface 对象
                    temp_surface = Surface(
                        id=self._edit_manager._selected_plane_id,
                        vertices=plane_data,
                        surface_type='polygon'
                    )
                    CameraController.focus_on_plane(view, temp_surface)


        return {
            'type': selected['type'],
            'id': selected['id'],
            'data': selected['data'],
            'focus_point': selected['focus_point']
        }
    
    def select_at_position(self, world_pos: np.ndarray) -> Optional[Dict[str, Any]]:
        """在指定世界坐标位置选择面对象"""
        # 仅检查面，忽略点与线的选择逻辑
        threshold = self.SELECTION_THRESHOLD
        closest_plane_id = None
        min_plane_distance = float('inf')
        for plane_id, vertices in self._edit_manager.planes.items():
            try:
                distance = self.distance_point_to_plane(world_pos, vertices)
            except Exception:
                continue
            if distance < min_plane_distance:
                min_plane_distance = distance
                closest_plane_id = plane_id

        if closest_plane_id is not None and min_plane_distance < threshold:
            self._edit_manager._selected_point_id = None
            self._edit_manager._selected_line_id = None
            self._edit_manager._selected_plane_id = closest_plane_id
            self._edit_manager.set_active_plane(closest_plane_id)
            vertices = self._edit_manager.planes[closest_plane_id]
            focus_point = np.mean(vertices, axis=0)
            return {
                'type': 'plane',
                'id': closest_plane_id,
                'data': vertices.copy(),
                'focus_point': focus_point
            }
        
        # 未选中任何对象
        self._edit_manager._selected_point_id = None
        self._edit_manager._selected_line_id = None
        self._edit_manager._selected_plane_id = None
        self._edit_manager.set_active_plane(None)
        return None
    
    # ========== 选择处理逻辑 ==========
    
    def handle_selection_and_action(self, view, screen_pos: QPoint):
        """
        处理选择和操作逻辑
        1. 检测选中的对象
        2. 根据对象类型执行相应操作
        """
        # 1. 检测选中的对象
        selected = self.detect_selected_object(view, screen_pos)
        
        if selected is None:
            # 未选中任何对象
            self.clear_selection()
            return
        
        # 2. 根据对象类型处理
        if selected['type'] == 'point':
            self.handle_point_selection(selected, view, screen_pos)
        elif selected['type'] == 'line':
            self.handle_line_selection(selected, view)
        elif selected['type'] == 'plane':
            self.handle_plane_selection(selected, view)
    
    def detect_selected_object(self, view, screen_pos: QPoint):
        """
        检测选中的对象
        """
        # 优先使用屏幕空间选择
        selected = self.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        
        # 如果屏幕空间选择失败，回退到原来的方法
        if selected is None:
            world_pos = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
            if world_pos is None:
                world_pos = CoordinateConverter.screen_to_world(
                    view, screen_pos, depth=0.0, clip_to_bounds=False
                )
            
            if world_pos is not None:
                selected = self.select_at_position(world_pos)
        
        return selected
    
    def handle_point_selection(self, selected, view, screen_pos: QPoint):
        """
        处理点选择逻辑
        """
        point_id = selected['id']
        
        # 1. 设置选中状态
        self.set_point_selected(point_id)
        
        # 2. 检查锁定状态
        if self.is_point_locked(point_id):
            # 锁定点只选择，不拖拽
            self.send_selection_message(view, selected)
            return
        
        # 3. 启动拖拽
        if hasattr(view, '_point_operator'):
            view._point_operator.start_drag(point_id, screen_pos, view)
    
    def handle_line_selection(self, selected, view):
        """
        处理线选择逻辑
        """
        line_id = selected['id']
        self.set_line_selected(line_id)
        self.send_selection_message(view, selected)
    
    def handle_plane_selection(self, selected, view):
        """
        处理面选择逻辑
        """
        plane_id = selected['id']
        self.set_plane_selected(plane_id)
        self.send_selection_message(view, selected)
    
    def set_point_selected(self, point_id: str):
        """
        设置点选中状态
        """
        self._edit_manager._selected_point_id = point_id
        self._edit_manager._selected_line_id = None
        self._edit_manager._selected_plane_id = None
        self._edit_manager.set_active_plane(None)
    
    def set_line_selected(self, line_id: str):
        """
        设置线选中状态
        """
        self._edit_manager._selected_point_id = None
        self._edit_manager._selected_line_id = line_id
        self._edit_manager._selected_plane_id = None
        self._edit_manager.set_active_plane(None)
    
    def set_plane_selected(self, plane_id: str):
        """
        设置面选中状态
        """
        self._edit_manager._selected_point_id = None
        self._edit_manager._selected_line_id = None
        self._edit_manager._selected_plane_id = plane_id
        self._edit_manager.set_active_plane(plane_id)
    
    def clear_selection(self):
        """
        清除所有选择状态
        """
        self._edit_manager._selected_point_id = None
        self._edit_manager._selected_line_id = None
        self._edit_manager._selected_plane_id = None
        self._edit_manager.set_active_plane(None)
    
    def is_point_locked(self, point_id: str) -> bool:
        """
        检查点是否被锁定
        """
        locked_points = self._edit_manager.locked_points
        return point_id in locked_points
    
    def send_selection_message(self, view, selected):
        """
        发送选择状态消息
        """
        if hasattr(view, 'status_message'):
            obj_type = selected['type']
            obj_id = selected['id']
            
            type_names = {
                'point': '点',
                'line': '线',
                'plane': '面'
            }
            type_name = type_names.get(obj_type, obj_type)
            view.status_message.emit(f'已选中{type_name}: {obj_id}')
    
    # ========== 视觉高亮功能 ==========
    
    def highlight_object(self, obj_type: str, obj_id: str, view, highlight_color=(1.0, 1.0, 0.0)):
        """
        高亮对象（改变颜色）
        """
        # 保存原始颜色
        original_color = self._get_object_color(obj_type, obj_id)
        
        # 设置高亮颜色
        self._set_object_color(obj_type, obj_id, highlight_color, view)
        
        # 返回原始颜色用于恢复
        return original_color
    
    def restore_object_color(self, obj_type: str, obj_id: str, original_color, view):
        """
        恢复对象的原始颜色
        """
        self._set_object_color(obj_type, obj_id, original_color, view)
    
    def _get_object_color(self, obj_type: str, obj_id: str):
        """
        获取对象的当前颜色
        """
        if obj_type == 'point':
            return self._edit_manager._point_colors.get(obj_id, (1.0, 0.0, 0.0))
        elif obj_type == 'line':
            return self._edit_manager._line_colors.get(obj_id, (0.0, 0.0, 1.0))
        elif obj_type == 'plane':
            return self._edit_manager._plane_colors.get(obj_id, (0.0, 1.0, 0.0))
        else:
            return (1.0, 1.0, 1.0)  # 默认白色
    
    def _set_object_color(self, obj_type: str, obj_id: str, color: tuple, view):
        """
        设置对象颜色
        """
        if obj_type == 'point':
            self._edit_manager.set_point_color(obj_id, color, view)
        elif obj_type == 'line':
            self._edit_manager.set_line_color(obj_id, color, view)
        elif obj_type == 'plane':
            self._edit_manager.set_plane_color(obj_id, color, view)
    
    def switch_highlight(self, new_obj_type: str, new_obj_id: str, view, highlight_color=(1.0, 1.0, 0.0)):
        """
        切换高亮对象（恢复上一个，高亮新的）
        """
        # 如果有之前的高亮对象，先恢复其颜色
        if hasattr(self, '_current_highlight'):
            prev_type, prev_id, prev_color = self._current_highlight
            self.restore_object_color(prev_type, prev_id, prev_color, view)
        
        # 高亮新对象并保存信息
        original_color = self.highlight_object(new_obj_type, new_obj_id, view, highlight_color)
        self._current_highlight = (new_obj_type, new_obj_id, original_color)
        
        return original_color
    
    def clear_highlight(self, view):
        """
        清除当前高亮
        """
        if hasattr(self, '_current_highlight'):
            prev_type, prev_id, prev_color = self._current_highlight
            self.restore_object_color(prev_type, prev_id, prev_color, view)
            delattr(self, '_current_highlight')
    
    def get_current_highlight(self):
        """
        获取当前高亮对象信息
        """
        return getattr(self, '_current_highlight', None)
    
    # ========== 撤销/重做功能 ==========

    def undo(self, view=None) -> bool:
        """执行撤销操作"""
        return self._undo_manager.undo(view)

    def redo(self, view=None) -> bool:
        """执行重做操作"""
        return self._undo_manager.redo(view)

