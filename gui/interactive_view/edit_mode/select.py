"""
编辑模式相关逻辑
实现点、线、面的选择和管理
"""
import numpy as np
from typing import Optional, Dict, List, Tuple, Any
from PyQt5.QtCore import QPoint
import pyvista as pv
from model.geometry import Point


class EditModeManager:
    """编辑模式管理器 - 管理点、线、面的数据和选择逻辑"""
    
    # 选择阈值（世界坐标单位）
    SELECTION_THRESHOLD = 0.1
    
    def __init__(self):
        """初始化编辑模式管理器"""
        # 存储点、线、面的数据
        self._points: Dict[str, Point] = {}  # {id: Point对象}
        self._lines: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}  # {id: (start, end)}
        self._planes: Dict[str, np.ndarray] = {}  # {id: vertices (Nx3 array)}
        # 只读/锁定集合（边界等不可操作对象）
        self._locked_points: set = set()
        self._locked_lines: set = set()
        self._locked_planes: set = set()
        # 颜色记录（RGB 0-1）
        self._point_colors: Dict[str, Tuple[float, float, float]] = {}  # {id: (r,g,b)}
        self._line_colors: Dict[str, Tuple[float, float, float]] = {}   # {id: (r,g,b)}
        self._plane_colors: Dict[str, Tuple[float, float, float]] = {}  # {id: (r,g,b)}
        
        # 存储actor引用（用于渲染）
        self._point_actors: Dict[str, Any] = {}  # {id: actor}
        self._line_actors: Dict[str, Any] = {}  # {id: actor}
        self._plane_actors: Dict[str, Any] = {}  # {id: actor}
        self._plane_vertex_actors: Dict[str, List[Any]] = {}  # {id: [vertex actors]}
        
        # 当前选中的对象
        self._selected_point_id: Optional[str] = None
        self._selected_line_id: Optional[str] = None
        self._selected_plane_id: Optional[str] = None
    
    # ========== 数据管理 ==========
    
    def add_point_object(self, point: Point, view=None, locked: bool = False) -> bool:
        """
        添加点对象（使用Point类）
        """
        if point.id in self._points:
            return False  # 点已存在
        self._points[point.id] = point
        # 使用点自身颜色或默认
        if point.id not in self._point_colors:
            self._point_colors[point.id] = tuple(point.color) if getattr(point, "color", None) is not None else (1.0, 0.0, 0.0)
        if locked:
            self._locked_points.add(point.id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self._render_point(point.id, view)
        return True

    def add_point(self, point_id: str, position: np.ndarray, view=None, locked: bool = False) -> bool:
        """
        兼容旧接口：通过id和位置创建Point对象并添加
        """
        point = Point(id=point_id, position=np.array(position, dtype=np.float64))
        return self.add_point_object(point, view, locked=locked)
    
    def add_line(self, line_id: str, start: np.ndarray, end: np.ndarray, view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """
        添加线
        
        Parameters:
        -----------
        line_id : str
            线的唯一标识符
        start : np.ndarray
            起点 [x, y, z]
        end : np.ndarray
            终点 [x, y, z]
        view : InteractiveView, optional
            视图实例，如果提供则立即渲染
        
        Returns:
        --------
        bool
            是否成功添加
        """
        if line_id in self._lines:
            return False  # 线已存在
        
        self._lines[line_id] = (
            np.array(start, dtype=np.float64),
            np.array(end, dtype=np.float64)
        )
        if line_id not in self._line_colors:
            if color is not None:
                self._line_colors[line_id] = tuple(color)
            else:
                self._line_colors[line_id] = (0.0, 0.0, 1.0)  # blue
        if locked:
            self._locked_lines.add(line_id)
        
        # 如果提供了view，创建并添加actor
        if view is not None:
            self._render_line(line_id, view)
        
        return True
    
    def add_plane(self, plane_id: str, vertices: np.ndarray, view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """
        添加面
        
        Parameters:
        -----------
        plane_id : str
            面的唯一标识符
        vertices : np.ndarray
            面的顶点 (Nx3 array)，至少3个点
        view : InteractiveView, optional
            视图实例，如果提供则立即渲染
        
        Returns:
        --------
        bool
            是否成功添加
        """
        if plane_id in self._planes:
            return False  # 面已存在
        
        vertices = np.array(vertices, dtype=np.float64)
        if vertices.shape[0] < 3:
            return False  # 至少需要3个点
        
        self._planes[plane_id] = vertices
        if plane_id not in self._plane_colors:
            if color is not None:
                self._plane_colors[plane_id] = tuple(color)
            else:
                self._plane_colors[plane_id] = (0.0, 1.0, 0.0)  # green
        if locked:
            self._locked_planes.add(plane_id)
        
        # 如果提供了view，创建并添加actor
        if view is not None:
            self._render_plane(plane_id, view)
        
        return True
    
    def remove_point(self, point_id: str, view=None) -> bool:
        """移除点"""
        if point_id in self._locked_points:
            return False
        if point_id not in self._points:
            return False
        
        # 移除actor
        if point_id in self._point_actors and view is not None:
            try:
                view.remove_actor(self._point_actors[point_id])
            except:
                pass
            del self._point_actors[point_id]
        
        del self._points[point_id]
        if point_id in self._point_colors:
            del self._point_colors[point_id]
        
        # 如果当前选中，清除选择
        if self._selected_point_id == point_id:
            self._selected_point_id = None
        
        return True
    
    def remove_line(self, line_id: str, view=None) -> bool:
        """移除线"""
        if line_id in self._locked_lines:
            return False
        if line_id not in self._lines:
            return False
        
        # 移除actor
        if line_id in self._line_actors and view is not None:
            try:
                view.remove_actor(self._line_actors[line_id])
            except:
                pass
            del self._line_actors[line_id]
        
        del self._lines[line_id]
        if line_id in self._line_colors:
            del self._line_colors[line_id]
        
        # 如果当前选中，清除选择
        if self._selected_line_id == line_id:
            self._selected_line_id = None
        
        return True
    
    def remove_plane(self, plane_id: str, view=None) -> bool:
        """移除面"""
        if plane_id in self._locked_planes:
            return False
        if plane_id not in self._planes:
            return False
        
        # 移除actor
        if plane_id in self._plane_actors and view is not None:
            try:
                view.remove_actor(self._plane_actors[plane_id])
            except:
                pass
            del self._plane_actors[plane_id]

        # 移除顶点标记actors
        if plane_id in self._plane_vertex_actors and view is not None:
            for actor in self._plane_vertex_actors[plane_id]:
                try:
                    view.remove_actor(actor)
                except:
                    pass
            del self._plane_vertex_actors[plane_id]
        
        del self._planes[plane_id]
        if plane_id in self._plane_colors:
            del self._plane_colors[plane_id]
        
        # 如果当前选中，清除选择
        if self._selected_plane_id == plane_id:
            self._selected_plane_id = None
        
        return True
    
    def clear_all(self, view=None):
        """清除所有点、线、面"""
        # 清除所有点
        point_ids = list(self._points.keys())
        for point_id in point_ids:
            self.remove_point(point_id, view)
        
        # 清除所有线
        line_ids = list(self._lines.keys())
        for line_id in line_ids:
            self.remove_line(line_id, view)
        
        # 清除所有面
        plane_ids = list(self._planes.keys())
        for plane_id in plane_ids:
            self.remove_plane(plane_id, view)
    
    # ========== 距离计算 ==========
    
    @staticmethod
    def distance_point_to_point(point1: np.ndarray, point2: np.ndarray) -> float:
        """计算点到点的距离"""
        return np.linalg.norm(point1 - point2)
    
    @staticmethod
    def distance_point_to_line(point: np.ndarray, line_start: np.ndarray, line_end: np.ndarray) -> float:
        """
        计算点到线段的最短距离
        
        Parameters:
        -----------
        point : np.ndarray
            点坐标 [x, y, z]
        line_start : np.ndarray
            线段起点 [x, y, z]
        line_end : np.ndarray
            线段终点 [x, y, z]
        
        Returns:
        --------
        float
            最短距离
        """
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
        """
        计算点到面的最短距离（点到面的距离）
        
        Parameters:
        -----------
        point : np.ndarray
            点坐标 [x, y, z]
        plane_vertices : np.ndarray
            面的顶点 (Nx3 array)
        
        Returns:
        --------
        float
            最短距离
        """
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
        # 使用面上任意一点（第一个顶点）
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
        
        Parameters:
        -----------
        point : np.ndarray
            点坐标 [x, y]
        vertices : np.ndarray
            多边形顶点 (Nx2)
        
        Returns:
        --------
        bool
            点是否在多边形内
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
    
    def select_at_screen_position(self, screen_pos: QPoint, view, pixel_threshold: int = 10) -> Optional[Dict[str, Any]]:
        """
        在屏幕坐标位置选择对象（基于屏幕像素距离，考虑深度）
        
        Parameters:
        -----------
        screen_pos : QPoint
            屏幕坐标（像素）
        view : InteractiveView
            视图实例
        pixel_threshold : int
            屏幕像素阈值，默认10像素
        
        Returns:
        --------
        dict or None
            选中的对象信息，格式：
            {
                'type': 'point' | 'line' | 'plane',
                'id': str,
                'data': ...  # 对象数据
                'focus_point': np.ndarray  # 聚焦点
            }
            如果未选中任何对象，返回None
        """
        renderer = view.renderer
        width = view.width()
        height = view.height()
        
        # 获取相机位置（用于深度排序）
        camera = renderer.GetActiveCamera()
        camera_pos = np.array(camera.GetPosition())
        
        # 将Qt坐标转换为VTK坐标
        vtk_x = screen_pos.x()
        vtk_y = height - screen_pos.y() - 1
        
        # 候选对象列表（按优先级和深度排序）
        candidates = []
        
        # 1. 检查点
        for point_id, point_obj in self._points.items():
            # 将世界坐标转换为屏幕坐标
            point_pos = point_obj.position
            display_pos = [0.0, 0.0, 0.0]
            renderer.SetWorldPoint(point_pos[0], point_pos[1], point_pos[2], 1.0)
            renderer.WorldToDisplay()
            display_pos = renderer.GetDisplayPoint()
            
            # 计算屏幕像素距离
            screen_dist = np.sqrt(
                (display_pos[0] - vtk_x) ** 2 + 
                (display_pos[1] - vtk_y) ** 2
            )
            
            if screen_dist <= pixel_threshold:
                # 计算到相机的距离（用于深度排序）
                depth = np.linalg.norm(point_pos - camera_pos)
                candidates.append({
                    'type': 'point',
                    'id': point_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': point_pos.copy(),
                    'focus_point': point_pos.copy()
                })
        
        # 2. 检查线
        for line_id, (start, end) in self._lines.items():
            # 将线的两个端点投影到屏幕
            start_display = [0.0, 0.0, 0.0]
            end_display = [0.0, 0.0, 0.0]
            
            renderer.SetWorldPoint(start[0], start[1], start[2], 1.0)
            renderer.WorldToDisplay()
            start_display = renderer.GetDisplayPoint()
            
            renderer.SetWorldPoint(end[0], end[1], end[2], 1.0)
            renderer.WorldToDisplay()
            end_display = renderer.GetDisplayPoint()
            
            # 计算点到线段的屏幕距离
            start_screen = np.array([start_display[0], start_display[1]])
            end_screen = np.array([end_display[0], end_display[1]])
            click_screen = np.array([vtk_x, vtk_y])
            
            # 计算点到线段的屏幕距离
            line_vec = end_screen - start_screen
            line_len = np.linalg.norm(line_vec)
            
            if line_len > 1e-6:
                line_vec_normalized = line_vec / line_len
                point_vec = click_screen - start_screen
                t = np.dot(point_vec, line_vec_normalized)
                t = np.clip(t, 0.0, line_len)
                closest_screen = start_screen + line_vec_normalized * t
                screen_dist = np.linalg.norm(click_screen - closest_screen)
            else:
                # 线段退化为点
                screen_dist = np.linalg.norm(click_screen - start_screen)
            
            if screen_dist <= pixel_threshold:
                # 计算线的中点到相机的距离
                mid_point = (start + end) / 2.0
                depth = np.linalg.norm(mid_point - camera_pos)
                candidates.append({
                    'type': 'line',
                    'id': line_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': (start.copy(), end.copy()),
                    'focus_point': mid_point
                })
        
        # 3. 检查面
        for plane_id, vertices in self._planes.items():
            # 将面的顶点投影到屏幕
            screen_vertices = []
            for vertex in vertices:
                display_pos = [0.0, 0.0, 0.0]
                renderer.SetWorldPoint(vertex[0], vertex[1], vertex[2], 1.0)
                renderer.WorldToDisplay()
                display_pos = renderer.GetDisplayPoint()
                screen_vertices.append([display_pos[0], display_pos[1]])
            
            screen_vertices = np.array(screen_vertices)
            click_screen = np.array([vtk_x, vtk_y])
            
            # 检查点击是否在面的屏幕投影内
            inside = self._point_in_polygon(click_screen, screen_vertices)
            
            if inside:
                # 如果点在面内，屏幕距离为0
                screen_dist = 0.0
            else:
                # 计算点到面的屏幕距离（使用面的中心点）
                center_screen = np.mean(screen_vertices, axis=0)
                screen_dist = np.linalg.norm(click_screen - center_screen)
            
            if inside or screen_dist <= pixel_threshold:
                # 计算面的中心到相机的距离
                center = np.mean(vertices, axis=0)
                depth = np.linalg.norm(center - camera_pos)
                candidates.append({
                    'type': 'plane',
                    'id': plane_id,
                    'screen_dist': screen_dist,
                    'depth': depth,
                    'data': vertices.copy(),
                    'focus_point': center
                })
        
        # 如果没有候选对象，返回None
        if not candidates:
            self._selected_point_id = None
            self._selected_line_id = None
            self._selected_plane_id = None
            return None
        
        # 排序：优先级（点>线>面），然后按深度（最近优先），最后按屏幕距离
        priority_order = {'point': 0, 'line': 1, 'plane': 2}
        candidates.sort(key=lambda x: (
            priority_order[x['type']],  # 优先级
            x['depth'],  # 深度（最近优先）
            x['screen_dist']  # 屏幕距离
        ))
        
        # 选择第一个候选对象
        selected = candidates[0]
        
        # 更新选择状态
        if selected['type'] == 'point':
            self._selected_point_id = selected['id']
            self._selected_line_id = None
            self._selected_plane_id = None
        elif selected['type'] == 'line':
            self._selected_point_id = None
            self._selected_line_id = selected['id']
            self._selected_plane_id = None
        elif selected['type'] == 'plane':
            self._selected_point_id = None
            self._selected_line_id = None
            self._selected_plane_id = selected['id']
        
        return {
            'type': selected['type'],
            'id': selected['id'],
            'data': selected['data'],
            'focus_point': selected['focus_point']
        }
    
    def select_at_position(self, world_pos: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        在指定世界坐标位置选择对象（优先级：点 > 线 > 面）
        
        Parameters:
        -----------
        world_pos : np.ndarray
            世界坐标位置 [x, y, z]
        
        Returns:
        --------
        dict or None
            选中的对象信息，格式：
            {
                'type': 'point' | 'line' | 'plane',
                'id': str,
                'data': ...  # 对象数据
            }
            如果未选中任何对象，返回None
        """
        threshold = self.SELECTION_THRESHOLD
        
        # 1. 优先检查点
        closest_point_id = None
        min_point_distance = threshold
        
        for point_id, point_obj in self._points.items():
            distance = self.distance_point_to_point(world_pos, point_obj.position)
            if distance < min_point_distance:
                min_point_distance = distance
                closest_point_id = point_id
        
        if closest_point_id is not None:
            self._selected_point_id = closest_point_id
            self._selected_line_id = None
            self._selected_plane_id = None
            return {
                'type': 'point',
                'id': closest_point_id,
                'data': self._points[closest_point_id].position.copy(),
                'focus_point': self._points[closest_point_id].position.copy()
            }
        
        # 2. 检查线
        closest_line_id = None
        min_line_distance = threshold
        
        for line_id, (start, end) in self._lines.items():
            distance = self.distance_point_to_line(world_pos, start, end)
            if distance < min_line_distance:
                min_line_distance = distance
                closest_line_id = line_id
        
        if closest_line_id is not None:
            self._selected_point_id = None
            self._selected_line_id = closest_line_id
            self._selected_plane_id = None
            # 计算线的中点
            start, end = self._lines[closest_line_id]
            focus_point = (start + end) / 2.0
            return {
                'type': 'line',
                'id': closest_line_id,
                'data': (start.copy(), end.copy()),
                'focus_point': focus_point
            }
        
        # 3. 检查面
        closest_plane_id = None
        min_plane_distance = float('inf')
        
        for plane_id, vertices in self._planes.items():
            distance = self.distance_point_to_plane(world_pos, vertices)
            if distance < min_plane_distance:
                min_plane_distance = distance
                closest_plane_id = plane_id
        
        if closest_plane_id is not None and min_plane_distance < threshold:
            self._selected_point_id = None
            self._selected_line_id = None
            self._selected_plane_id = closest_plane_id
            # 计算面的中心点
            vertices = self._planes[closest_plane_id]
            focus_point = np.mean(vertices, axis=0)
            return {
                'type': 'plane',
                'id': closest_plane_id,
                'data': vertices.copy(),
                'focus_point': focus_point
            }
        
        # 未选中任何对象
        self._selected_point_id = None
        self._selected_line_id = None
        self._selected_plane_id = None
        return None
    
    # ========== 渲染相关 ==========
    
    def _render_point(self, point_id: str, view):
        """渲染点"""
        if point_id not in self._points:
            return
        
        point_obj = self._points[point_id]
        # 兼容历史数据：如果是 ndarray，转换为 Point
        if not isinstance(point_obj, Point):
            point_obj = Point(id=point_id, position=np.array(point_obj, dtype=np.float64))
            self._points[point_id] = point_obj
        position = point_obj.position
        
        # 创建点mesh
        point_mesh = pv.PolyData([position])
        
        # 添加到场景
        color = self._point_colors.get(point_id, (1.0, 0.0, 0.0))
        actor = view.add_mesh(
            point_mesh,
            color=color,
            point_size=10,
            render_points_as_spheres=True,
            name=f'edit_point_{point_id}'
        )
        if point_id.startswith("boundary_point_"):
            try:
                actor.GetProperty().SetPointSize(8)
            except:
                pass
        
        self._point_actors[point_id] = actor
    
    def _render_line(self, line_id: str, view):
        """渲染线"""
        if line_id not in self._lines:
            return
        
        start, end = self._lines[line_id]
        
        # 创建线mesh
        points = np.array([start, end])
        lines = np.array([2, 0, 1], dtype=np.int32)
        line_mesh = pv.PolyData(points, lines=lines)
        
        # 添加到场景
        color = self._line_colors.get(line_id, (0.0, 0.0, 1.0))
        actor = view.add_mesh(
            line_mesh,
            color=color,
            line_width=3,
            name=f'edit_line_{line_id}'
        )
        if line_id.startswith("boundary_line_"):
            try:
                actor.GetProperty().SetLineWidth(2.0)
            except:
                pass
        
        self._line_actors[line_id] = actor
    
    def _render_plane(self, plane_id: str, view):
        """渲染面"""
        if plane_id not in self._planes:
            return
        
        vertices = self._planes[plane_id]
        
        # 创建面mesh（使用第一个点作为中心，创建三角形扇）
        # 简化实现：假设面是凸多边形
        if vertices.shape[0] == 3:
            # 三角形
            faces = np.array([3, 0, 1, 2], dtype=np.int32)
        elif vertices.shape[0] == 4:
            # 四边形（两个三角形）
            faces = np.array([3, 0, 1, 2, 3, 0, 2, 3], dtype=np.int32)
        else:
            # 多边形（使用第一个点作为中心，创建三角形扇）
            faces = []
            for i in range(1, vertices.shape[0] - 1):
                faces.extend([3, 0, i, i + 1])
            faces = np.array(faces, dtype=np.int32)
        
        plane_mesh = pv.PolyData(vertices, faces=faces)
        
        # 添加到场景
        color = self._plane_colors.get(plane_id, (0.0, 1.0, 0.0))
        # 边界面使用浅灰色边缘，其他面使用深绿色
        edge_color = 'lightgray' if plane_id.startswith('boundary_plane_') else 'darkgreen'
        actor = view.add_mesh(
            plane_mesh,
            color=color,
            opacity=0.5,
            show_edges=True,
            edge_color=edge_color,
            name=f'edit_plane_{plane_id}'
        )
        if plane_id.startswith("boundary_plane_"):
            try:
                actor.GetProperty().SetOpacity(0.05)  # 非常透明，几乎看不见
            except:
                pass
        
        self._plane_actors[plane_id] = actor

        # 面的顶点只作为数据存在，不渲染为视觉实体
        # 只有用户明确创建的点（_points 中的 Point 对象）才会被渲染
        self._plane_vertex_actors[plane_id] = []
    
    def update_rendering(self, view):
        """更新所有对象的渲染"""
        # 重新渲染所有点
        for point_id in list(self._point_actors.keys()):
            if point_id in self._points:
                try:
                    view.remove_actor(self._point_actors[point_id])
                except:
                    pass
                self._render_point(point_id, view)
        
        # 重新渲染所有线
        for line_id in list(self._line_actors.keys()):
            if line_id in self._lines:
                try:
                    view.remove_actor(self._line_actors[line_id])
                except:
                    pass
                self._render_line(line_id, view)
        
        # 重新渲染所有面
        for plane_id in list(self._plane_actors.keys()):
            if plane_id in self._planes:
                try:
                    view.remove_actor(self._plane_actors[plane_id])
                except:
                    pass
                # 移除旧的顶点标记
                if plane_id in self._plane_vertex_actors:
                    for actor in self._plane_vertex_actors[plane_id]:
                        try:
                            view.remove_actor(actor)
                        except:
                            pass
                self._render_plane(plane_id, view)

    # ========== 颜色设置 ==========
    def set_point_color(self, point_id: str, color: Tuple[float, float, float], view=None):
        self._point_colors[point_id] = color
        actor = self._point_actors.get(point_id)
        if actor is not None:
            try:
                # 优先使用VTK Property 设置颜色，兼容不同版本
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*color)
            except:
                pass
        if view is not None and actor is None and point_id in self._points:
            self._render_point(point_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass

    def set_line_color(self, line_id: str, color: Tuple[float, float, float], view=None):
        self._line_colors[line_id] = color
        actor = self._line_actors.get(line_id)
        if actor is not None:
            try:
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*color)
            except:
                pass
        if view is not None and actor is None and line_id in self._lines:
            self._render_line(line_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass

    def set_plane_color(self, plane_id: str, color: Tuple[float, float, float], view=None):
        self._plane_colors[plane_id] = color
        actor = self._plane_actors.get(plane_id)
        if actor is not None:
            try:
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*color)
            except:
                pass
        if view is not None and actor is None and plane_id in self._planes:
            self._render_plane(plane_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass
    
    # ========== 获取选中对象 ==========
    
    def get_selected_point(self) -> Optional[Tuple[str, np.ndarray]]:
        """获取当前选中的点"""
        if self._selected_point_id is None:
            return None
        return (self._selected_point_id, self._points[self._selected_point_id].position.copy())
    
    def get_selected_line(self) -> Optional[Tuple[str, Tuple[np.ndarray, np.ndarray]]]:
        """获取当前选中的线"""
        if self._selected_line_id is None:
            return None
        start, end = self._lines[self._selected_line_id]
        return (self._selected_line_id, (start.copy(), end.copy()))
    
    def get_selected_plane(self) -> Optional[Tuple[str, np.ndarray]]:
        """获取当前选中的面"""
        if self._selected_plane_id is None:
            return None
        return (self._selected_plane_id, self._planes[self._selected_plane_id].copy())
    
    def get_all_points(self) -> Dict[str, np.ndarray]:
        """获取所有点"""
        return {k: v.position.copy() for k, v in self._points.items()}
    
    def get_all_lines(self) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """获取所有线"""
        return {k: (v[0].copy(), v[1].copy()) for k, v in self._lines.items()}
    
    def get_all_planes(self) -> Dict[str, np.ndarray]:
        """获取所有面"""
        return {k: v.copy() for k, v in self._planes.items()}

