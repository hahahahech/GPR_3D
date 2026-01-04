"""
点操作功能模块
实现编辑模式下点的创建、编辑、删除等操作
使用 model.geometry.Point 类
"""
import numpy as np
from typing import Optional, Dict, List, Tuple, Set
from PyQt5.QtCore import QPoint
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from model.geometry import Point
from ..coordinates import CoordinateConverter
from utils.undo import MovePointCommand


class PointOperator:
    """点操作器 - 处理点的创建、编辑、删除等操作"""
    
    def __init__(self, edit_mode_manager):
        """初始化点操作器"""
        self.edit_manager = edit_mode_manager
        self.view = None
        
        # 存储 Point 对象（与 EditModeManager 中的 _points 字典同步）
        self._point_objects: Dict[str, Point] = {}  # {id: Point}
        
                
        # 捕捉设置
        self._snap_to_grid = False
        self._grid_spacing = 10.0
        self._snap_to_point = True
        self._snap_to_line = True
        self._snap_to_plane = True
        self._snap_threshold = 0.1
        
        # 约束设置
        self._constraint_axis = None  # 'x', 'y', 'z', None
        self._constraint_plane = None  # 'xy', 'xz', 'yz', None
    
    # ========== 创建点 ==========
    
    def create_point_at_world(self, world_pos: np.ndarray, view) -> Optional[str]:
        """在世界坐标位置直接创建点"""
        # 限制点在工作空间边界内
        bounds = view.workspace_bounds
        clamped_pos = np.array([
            np.clip(world_pos[0], bounds[0], bounds[1]),  # X
            np.clip(world_pos[1], bounds[2], bounds[3]),  # Y
            np.clip(world_pos[2], bounds[4], bounds[5])   # Z
        ])
        
        # 生成点ID
        point_id = self._generate_point_id()
        # 创建 Point 对象
        try:
            point = Point(
                id=point_id,
                position=clamped_pos,
                name=None
            )
        except Exception as e:
            print(f"创建点失败: {e}")
            return None
        
        # 添加到管理器（直接使用 Point 对象，保持引用一致）
        if self.edit_manager.add_point_object(point, view):
            self._point_objects[point_id] = point
            return point_id
        return None
    
    
    # ========== 编辑点 ==========
    
    def move_point(self, point_id: str, new_position: np.ndarray, view) -> bool:
        """移动点到指定位置"""
        if point_id not in self.edit_manager._points:
            return False

        # 获取旧位置
        point_obj = self.edit_manager._points.get(point_id)
        if isinstance(point_obj, Point):
            old_position = point_obj.position.copy()
        else:
            old_position = np.array(point_obj, dtype=np.float64)

        # 应用捕捉并限制在工作空间
        new_position = self._apply_snap(new_position, view)
        new_position = self._clamp_to_workspace(new_position, view)

        # 使用命令模式执行移动
        command = MovePointCommand(self.edit_manager, point_id, old_position, new_position)
        return self.edit_manager._undo_manager.execute_and_push(command, view)

    # ========== 捕捉功能 ==========
    
    def _apply_snap(self, position: np.ndarray, view) -> np.ndarray:
        """应用捕捉到位置"""
        result = position.copy()
        
        # 网格捕捉
        if self._snap_to_grid:
            result = self._snap_to_grid_position(result)
        
        # 点捕捉
        if self._snap_to_point:
            snapped = self._snap_to_nearest_point(result)
            if snapped is not None:
                result = snapped
        
        # 线捕捉
        if self._snap_to_line:
            snapped = self._snap_to_nearest_line(result)
            if snapped is not None:
                result = snapped
        
        # 面捕捉
        if self._snap_to_plane:
            snapped = self._snap_to_nearest_plane(result)
            if snapped is not None:
                result = snapped
        
        return result

    def _clamp_to_workspace(self, position: np.ndarray, view) -> np.ndarray:
        """
        将位置限制在工作空间边界内
        """
        if view is None or not hasattr(view, 'workspace_bounds'):
            return position
        bounds = view.workspace_bounds
        clamped = position.copy()
        clamped[0] = np.clip(clamped[0], bounds[0], bounds[1])
        clamped[1] = np.clip(clamped[1], bounds[2], bounds[3])
        clamped[2] = np.clip(clamped[2], bounds[4], bounds[5])
        return clamped
    
    def _snap_to_grid_position(self, position: np.ndarray) -> np.ndarray:
        """捕捉到网格位置"""
        return np.round(position / self._grid_spacing) * self._grid_spacing
    
    def _snap_to_nearest_point(self, position: np.ndarray) -> Optional[np.ndarray]:
        """捕捉到最近的点"""
        min_dist = self._snap_threshold
        nearest = None
        
        for point_obj in self.edit_manager._points.values():
            point_pos = point_obj.position
            dist = np.linalg.norm(position - point_pos)
            if dist < min_dist:
                min_dist = dist
                nearest = point_pos
        
        return nearest
    
    def _snap_to_nearest_line(self, position: np.ndarray) -> Optional[np.ndarray]:
        """捕捉到最近的线"""
        min_dist = self._snap_threshold
        nearest = None
        
        for start, end in self.edit_manager._lines.values():
            # resolve possible point-id references
            try:
                if isinstance(start, str):
                    s_pos = self.edit_manager._points[start].position
                else:
                    s_pos = start
            except Exception:
                s_pos = np.array(start, dtype=np.float64)
            try:
                if isinstance(end, str):
                    e_pos = self.edit_manager._points[end].position
                else:
                    e_pos = end
            except Exception:
                e_pos = np.array(end, dtype=np.float64)
            # 计算点到线段的最短距离
            from gui.interactive_view.edit_mode.select import SelectionManager
            dist = SelectionManager.distance_point_to_line(position, s_pos, e_pos)
            if dist < min_dist:
                # 计算线段上最近的点
                line_vec = e_pos - s_pos
                line_len = np.linalg.norm(line_vec)
                if line_len > 1e-10:
                    line_vec_normalized = line_vec / line_len
                    point_vec = position - s_pos
                    t = np.dot(point_vec, line_vec_normalized)
                    t = np.clip(t, 0.0, line_len)
                    nearest = s_pos + line_vec_normalized * t
                    min_dist = dist
        
        return nearest
    
    def _snap_to_nearest_plane(self, position: np.ndarray) -> Optional[np.ndarray]:
        """捕捉到最近的面"""
        min_dist = self._snap_threshold
        nearest = None
        
        for vertices in self.edit_manager._planes.values():
            # 计算点到面的距离
            from gui.interactive_view.edit_mode.select import SelectionManager
            dist = SelectionManager.distance_point_to_plane(position, vertices)
            if dist < min_dist:
                # 计算面上最近的点（简化：使用面的中心点）
                nearest = np.mean(vertices, axis=0)
                min_dist = dist
        
        return nearest
    
    # ========== 约束功能 ==========
    
    def _apply_constraints(self, offset: np.ndarray) -> np.ndarray:
        """应用移动约束"""
        if self._constraint_axis is None and self._constraint_plane is None:
            return offset
        
        result = offset.copy()
        
        # 轴约束
        if self._constraint_axis == 'x':
            result[1] = 0
            result[2] = 0
        elif self._constraint_axis == 'y':
            result[0] = 0
            result[2] = 0
        elif self._constraint_axis == 'z':
            result[0] = 0
            result[1] = 0
        
        # 平面约束
        if self._constraint_plane == 'xy':
            result[2] = 0
        elif self._constraint_plane == 'xz':
            result[1] = 0
        elif self._constraint_plane == 'yz':
            result[0] = 0
        
        return result
    
    def _generate_point_id(self) -> str:
        """生成唯一的点ID"""
        existing_ids = set(self.edit_manager._points.keys())
        counter = 0
        while True:
            point_id = f"point_{counter}"
            if point_id not in existing_ids:
                return point_id
            counter += 1

    # ========== 查询功能 ==========
    
    def get_point_position(self, point_id: str) -> Optional[np.ndarray]:
        """获取点的位置"""
        if point_id in self.edit_manager._points:
            return self.edit_manager._points[point_id].position.copy()
        return None

