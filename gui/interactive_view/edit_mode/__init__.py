"""
编辑模式相关功能模块
"""
import numpy as np
from typing import Optional, Dict, List, Tuple, Any, Union
from PyQt5.QtCore import QPoint
import pyvista as pv
from model.geometry import Point
from utils.undo import (
    UndoManager,
    CreatePointCommand,
    CreateLineCommand,
    CreatePolylineCommand,
    CreateCurveCommand,
    CreatePlaneCommand,
    SetPointColorCommand, SetLineColorCommand, SetPlaneColorCommand
)

from .select import SelectionManager
from .point import PointOperator
from .line import LineOperator
from .plane import PlaneOperator
from .color_select import ColorSelector
from .lashen import StretchOperator

class EditModeManager:
    """编辑模式管理器 - 管理点、线、面的数据"""
    
    def __init__(self):
        """初始化编辑模式管理器"""
        # 存储点、线、面的数据
        self._points: Dict[str, Point] = {}  # {id: Point对象}
        self._lines: Dict[str, Tuple[Union[np.ndarray, str], Union[np.ndarray, str]]] = {}  # {id: (start, end)} start/end 可以是坐标或 point id
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
        
        # 折线/曲线对象存储（连续线/曲线作为单一对象）
        self._polylines: Dict[str, List[str]] = {}  # {polyline_id: [point_id,...]}
        self._polyline_actors: Dict[str, Any] = {}  # {polyline_id: actor}
        self._curves: Dict[str, Dict] = {}  # {curve_id: {control_point_ids, degree, num_points}}
        self._curve_actors: Dict[str, Any] = {}  # {curve_id: actor}
        
        # 撤销管理器
        self._undo_manager = UndoManager(max_items=100)
        
        # 选择管理器
        self._selection_manager = SelectionManager(self)
        
        # 当前选中的对象
        self._selected_point_id: Optional[str] = None
        self._selected_line_id: Optional[str] = None
        self._selected_plane_id: Optional[str] = None
        self._active_plane_id: Optional[str] = None
    
    # ========== 选择相关属性访问 ==========
    
    @property
    def selected_point_id(self):
        return self._selected_point_id
    
    @property
    def selected_line_id(self):
        return self._selected_line_id
    
    @property
    def selected_plane_id(self):
        return self._selected_plane_id
    
    @property
    def active_plane_id(self):
        return self._active_plane_id
    
    @property
    def points(self):
        return self._points
    
    @property
    def lines(self):
        return self._lines
    
    @property
    def planes(self):
        return self._planes
    
    @property
    def locked_points(self):
        return self._locked_points
    
    # ========== 选择方法委托 ==========
    
    def handle_selection_and_action(self, view, screen_pos: QPoint):
        """委托给选择管理器处理"""
        return self._selection_manager.handle_selection_and_action(view, screen_pos)
    
    def select_at_screen_position(self, screen_pos: QPoint, view, pixel_threshold: int = 10):
        """委托给选择管理器处理"""
        return self._selection_manager.select_at_screen_position(screen_pos, view, pixel_threshold)
    
    def select_at_position(self, world_pos: np.ndarray, threshold: float = 0.1):
        """委托给选择管理器处理"""
        return self._selection_manager.select_at_position(world_pos, threshold)
    
    def set_active_plane(self, plane_id: Optional[str]):
        """设置活动平面"""
        self._active_plane_id = plane_id
    
    def get_active_plane_vertices(self) -> Optional[np.ndarray]:
        """获取活动平面的顶点"""
        if self._active_plane_id is None:
            return None
        return self._planes.get(self._active_plane_id)
    
    # ========== 数据管理 ==========
    
    def add_point_object(self, point: Point, view=None, locked: bool = False) -> bool:
        """
        添加点对象（使用Point类）
        """
        command = CreatePointCommand(self, point.id, point.position,
                                   getattr(point, "color", None), locked)
        return self._undo_manager.execute_and_push(command, view)

    def add_point(self, point_id: str, position: np.ndarray, view=None, locked: bool = False) -> bool:
        """
        兼容旧接口：通过id和位置创建Point对象并添加
        """
        point = Point(id=point_id, position=np.array(position, dtype=np.float64))
        return self.add_point_object(point, view, locked=locked)
    
    def add_line(self, line_id: str, start: Union[str, np.ndarray], end: Union[str, np.ndarray], view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """
        添加线段
        start, end: 可以是点ID（字符串）或坐标（np.ndarray）
        """
        command = CreateLineCommand(self, line_id, start, end, color, locked)
        return self._undo_manager.execute_and_push(command, view)

    # ========== 折线（Polyline）支持 ==========
    def add_polyline(self, polyline_id: str, point_ids: List[str], view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """
        添加或更新折线对象（由若干点 ID 组成），在场景中作为单一对象渲染。
        如果 polyline_id 已存在则覆盖其点序列（用于增量更新）。
        """
        command = CreatePolylineCommand(self, polyline_id, point_ids, color, locked)
        return self._undo_manager.execute_and_push(command, view)

    # ========== 曲线对象支持（Curve） ==========
    def add_curve(self, curve_id: str, control_point_ids: List[str], degree: int = 3, num_points: int = 100, view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """
        添加曲线对象：只保存控制点 ID；渲染时使用样本化的线（不创建样本点为数据）。
        """
        command = CreateCurveCommand(self, curve_id, control_point_ids, degree, num_points, color, locked)
        return self._undo_manager.execute_and_push(command, view)
    
    def add_plane(self, plane_id: str, vertices: np.ndarray, view=None, color: Optional[tuple] = None, locked: bool = False) -> bool:
        """添加面 """
        command = CreatePlaneCommand(self, plane_id, vertices, color, locked)
        return self._undo_manager.execute_and_push(command, view)
    
    # ========== 颜色设置 ==========
    def set_point_color(self, point_id: str, color: Tuple[float, float, float], view=None):
        old_color = self._point_colors.get(point_id, (1.0, 0.0, 0.0))
        command = SetPointColorCommand(self, point_id, color, old_color)
        return self._undo_manager.execute_and_push(command, view)

    def set_line_color(self, line_id: str, color: Tuple[float, float, float], view=None):
        old_color = self._line_colors.get(line_id, (0.0, 0.0, 1.0))
        command = SetLineColorCommand(self, line_id, color, old_color)
        return self._undo_manager.execute_and_push(command, view)

    def set_plane_color(self, plane_id: str, color: Tuple[float, float, float], view=None):
        old_color = self._plane_colors.get(plane_id, (0.0, 1.0, 0.0))
        command = SetPlaneColorCommand(self, plane_id, color, old_color)
        return self._undo_manager.execute_and_push(command, view)
    
    # ========== 撤销/重做功能 ==========

    def undo(self, view=None) -> bool:
        """执行撤销操作"""
        return self._undo_manager.undo(view)

    def redo(self, view=None) -> bool:
        """执行重做操作"""
        return self._undo_manager.redo(view)
    
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
            render_points_as_spheres=False,
            reset_camera=False,
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
        # resolve possible point-id references
        start, end = self._lines[line_id]
        try:
            if isinstance(start, str):
                start_pos = self._points[start].position
            else:
                start_pos = start
        except Exception:
            start_pos = np.array(start, dtype=np.float64)
        try:
            if isinstance(end, str):
                end_pos = self._points[end].position
            else:
                end_pos = end
        except Exception:
            end_pos = np.array(end, dtype=np.float64)
        
        # 创建线mesh
        points = np.array([start_pos, end_pos])
        lines = np.array([2, 0, 1], dtype=np.int32)
        line_mesh = pv.PolyData(points, lines=lines)
        
        # 添加到场景
        color = self._line_colors.get(line_id, (0.0, 0.0, 1.0))
        actor = view.add_mesh(
            line_mesh,
            color=color,
            line_width=3,
            reset_camera=False,
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
            reset_camera=False,
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
    
    def _render_polyline(self, polyline_id: str, view):
        """按 point ids 渲染折线（单一 actor）"""
        if polyline_id not in self._polylines:
            return
        
        polyline_data = self._polylines[polyline_id]
        polyline_obj = polyline_data['geometry']
        coords = polyline_obj.get_vertices()
        
        if len(coords) < 2:
            return
        line_mesh = pv.lines_from_points(np.array(coords))
        color = self._line_colors.get(polyline_id, (0.0, 0.0, 1.0))
        actor = view.add_mesh(line_mesh, color=color, line_width=2, name=f'polyline_{polyline_id}')
        self._polyline_actors[polyline_id] = actor
    
    def _render_curve(self, curve_id: str, view):
        """渲染曲线"""
        if curve_id not in self._curves:
            return
        
        curve_data = self._curves[curve_id]
        curve_obj = curve_data['geometry']
        control_points = [cp.position for cp in curve_obj.control_points]
        degree = curve_obj.degree
        num_points = curve_obj.num_points
        
        if len(control_points) < 2:
            return
        
        # 使用 LineOperator 生成曲线
        if hasattr(view, '_line_operator'):
            line_operator = view._line_operator
            curve_points = line_operator.generate_smooth_curve(control_points, degree, num_points)
            actor = line_operator.render_curve_mesh(curve_points, curve_id, view)
            if actor is not None:
                self._curve_actors[curve_id] = actor
        else:
            # 回退：简单的直线连接
            import pyvista as pv
            line_mesh = pv.lines_from_points(np.array(control_points))
            color = self._line_colors.get(curve_id, (0.0, 1.0, 1.0))
            actor = view.add_mesh(line_mesh, color=color, line_width=3, name=f'curve_{curve_id}')
            self._curve_actors[curve_id] = actor

__all__ = ['EditModeManager', 'SelectionManager', 'PointOperator', 'LineOperator', 'PlaneOperator', 'ColorSelector', 'StretchOperator']

