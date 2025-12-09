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


class PointOperator:
    """点操作器 - 处理点的创建、编辑、删除等操作"""
    
    def __init__(self, edit_mode_manager):
        """
        初始化点操作器
        
        Parameters:
        -----------
        edit_mode_manager : EditModeManager
            编辑模式管理器实例
        """
        self.edit_manager = edit_mode_manager
        self.view = None
        
        # 存储 Point 对象（与 EditModeManager 中的 _points 字典同步）
        self._point_objects: Dict[str, Point] = {}  # {id: Point}
        
        # 操作状态
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_point_id = None
        self._drag_start_world_pos = None
        
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
    
    def create_point_at_screen(self, screen_pos: QPoint, view) -> Optional[str]:
        """
        在屏幕坐标位置创建点
        
        Parameters:
        -----------
        screen_pos : QPoint
            屏幕坐标
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        str or None
            创建的点ID，如果失败返回None
        """
        # 转换为世界坐标
        world_pos = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
        if world_pos is None:
            world_pos = CoordinateConverter.screen_to_world(
                view, screen_pos, depth=0.0, clip_to_bounds=False
            )
        
        if world_pos is None:
            return None
        
        # 应用捕捉并限制在工作空间
        world_pos = self._apply_snap(world_pos, view)
        world_pos = self._clamp_to_workspace(world_pos, view)
        
        # 生成点ID
        point_id = self._generate_point_id()
        
        # 创建 Point 对象
        try:
            point = Point(
                id=point_id,
                position=world_pos,
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
    
    def create_point_at_position(self, position: np.ndarray, view, name: Optional[str] = None) -> Optional[str]:
        """
        在指定世界坐标位置创建点
        
        Parameters:
        -----------
        position : np.ndarray
            世界坐标 [x, y, z]
        view : InteractiveView
            视图实例
        name : str, optional
            点的名称
        
        Returns:
        --------
        str or None
            创建的点ID，如果失败返回None
        """
        # 应用捕捉并限制在工作空间
        position = self._apply_snap(position, view)
        position = self._clamp_to_workspace(position, view)
        
        # 生成点ID
        point_id = self._generate_point_id()
        
        # 创建 Point 对象
        try:
            point = Point(
                id=point_id,
                position=position,
                name=name
            )
        except Exception as e:
            print(f"创建点失败: {e}")
            return None
        
        # 添加到管理器
        if self.edit_manager.add_point(point_id, point.position, view):
            # 同时存储 Point 对象
            self._point_objects[point_id] = point
            return point_id
        return None
    
    # ========== 编辑点 ==========
    
    def start_drag(self, point_id: str, screen_pos: QPoint, view):
        """
        开始拖拽点
        
        Parameters:
        -----------
        point_id : str
            要拖拽的点ID
        screen_pos : QPoint
            鼠标屏幕坐标
        view : InteractiveView
            视图实例
        """
        if point_id not in self.edit_manager._points:
            return
        
        self._is_dragging = True
        self._drag_point_id = point_id
        self._drag_start_pos = screen_pos
        
        # 获取当前点的世界坐标
        current_pos = self.edit_manager._points[point_id].position
        self._drag_start_world_pos = current_pos.copy()
    
    def update_drag(self, screen_pos: QPoint, view):
        """
        更新拖拽位置
        
        Parameters:
        -----------
        screen_pos : QPoint
            当前鼠标屏幕坐标
        view : InteractiveView
            视图实例
        """
        if not self._is_dragging or self._drag_point_id is None:
            return
        
        # 获取当前鼠标位置对应的世界坐标
        current_world = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
        if current_world is None:
            current_world = CoordinateConverter.screen_to_world(
                view, screen_pos, depth=0.0, clip_to_bounds=False
            )
        
        if current_world is None:
            return
        
        # 计算偏移量
        offset = current_world - self._drag_start_world_pos
        
        # 应用约束
        offset = self._apply_constraints(offset)
        
        # 计算新位置
        new_pos = self._drag_start_world_pos + offset
        
        # 应用捕捉并限制在工作空间
        new_pos = self._apply_snap(new_pos, view)
        new_pos = self._clamp_to_workspace(new_pos, view)
        
        # 更新点位置
        self.move_point(self._drag_point_id, new_pos, view)
    
    def end_drag(self):
        """结束拖拽"""
        self._is_dragging = False
        self._drag_point_id = None
        self._drag_start_pos = None
        self._drag_start_world_pos = None
    
    def move_point(self, point_id: str, new_position: np.ndarray, view) -> bool:
        """
        移动点到指定位置
        
        Parameters:
        -----------
        point_id : str
            点ID
        new_position : np.ndarray
            新位置 [x, y, z]
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        bool
            是否成功移动
        """
        if point_id not in self.edit_manager._points:
            return False
        
        # 应用捕捉并限制在工作空间
        new_position = self._apply_snap(new_position, view)
        new_position = self._clamp_to_workspace(new_position, view)
        
        # 获取/规范化 Point 对象
        point_obj = self.edit_manager._points.get(point_id)
        if not isinstance(point_obj, Point):
            # 兼容历史数据（numpy 数组）
            point_obj = Point(id=point_id, position=np.array(point_obj, dtype=np.float64))
            self.edit_manager._points[point_id] = point_obj
        # 更新位置
        point_obj.set_position(
            float(new_position[0]),
            float(new_position[1]),
            float(new_position[2])
        )
        # 同步本地缓存
        self._point_objects[point_id] = point_obj
        
        # 更新渲染
        self._update_point_rendering(point_id, view)
        return True
    
    def move_point_by_offset(self, point_id: str, offset: np.ndarray, view) -> bool:
        """
        通过偏移量移动点
        
        Parameters:
        -----------
        point_id : str
            点ID
        offset : np.ndarray
            偏移量 [dx, dy, dz]
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        bool
            是否成功移动
        """
        if point_id not in self.edit_manager._points:
            return False
        
        point_obj = self.edit_manager._points[point_id]
        if isinstance(point_obj, Point):
            current_pos = point_obj.position
        else:
            current_pos = np.array(point_obj, dtype=np.float64)
        new_pos = current_pos + offset
        
        return self.move_point(point_id, new_pos, view)
    
    def set_point_position(self, point_id: str, x: float, y: float, z: float, view) -> bool:
        """
        设置点的精确位置
        
        Parameters:
        -----------
        point_id : str
            点ID
        x, y, z : float
            新坐标
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        bool
            是否成功设置
        """
        return self.move_point(point_id, np.array([x, y, z], dtype=np.float64), view)
    
    def translate_point(self, point_id: str, vector: np.ndarray, view) -> bool:
        """
        平移点（使用 Point 类的 translate 方法）
        
        Parameters:
        -----------
        point_id : str
            点ID
        vector : np.ndarray
            平移向量 [dx, dy, dz]
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        bool
            是否成功平移
        """
        if point_id not in self._point_objects:
            # 如果 Point 对象不存在，使用普通移动方法
            return self.move_point_by_offset(point_id, vector, view)
        
        # 使用 Point 对象的 translate 方法
        point = self._point_objects[point_id]
        point.translate(vector)
        
        # 同步到 EditModeManager
        self.edit_manager._points[point_id] = point.position.copy()
        
        # 更新渲染
        self._update_point_rendering(point_id, view)
        return True
    
    # ========== 删除点 ==========
    
    def delete_point(self, point_id: str, view) -> bool:
        """
        删除点
        
        Parameters:
        -----------
        point_id : str
            点ID
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        bool
            是否成功删除
        """
        # 从 EditModeManager 删除
        success = self.edit_manager.remove_point(point_id, view)
        
        # 从 Point 对象字典删除
        if point_id in self._point_objects:
            del self._point_objects[point_id]
        
        return success
    
    def delete_points(self, point_ids: List[str], view) -> int:
        """
        删除多个点
        
        Parameters:
        -----------
        point_ids : List[str]
            点ID列表
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        int
            成功删除的点数量
        """
        success_count = 0
        for point_id in point_ids:
            if self.delete_point(point_id, view):
                success_count += 1
        return success_count
    
    def delete_selected_point(self, view) -> bool:
        """删除当前选中的点"""
        selected = self.edit_manager.get_selected_point()
        if selected is None:
            return False
        point_id, _ = selected
        return self.delete_point(point_id, view)
    
    def delete_all_points(self, view) -> int:
        """
        删除所有点
        
        Parameters:
        -----------
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        int
            删除的点数量
        """
        point_ids = list(self.edit_manager._points.keys())
        return self.delete_points(point_ids, view)
    
    # ========== 复制/克隆 ==========
    
    def duplicate_point(self, point_id: str, view, offset: Optional[np.ndarray] = None) -> Optional[str]:
        """
        复制点
        
        Parameters:
        -----------
        point_id : str
            要复制的点ID
        view : InteractiveView
            视图实例
        offset : np.ndarray, optional
            偏移量，如果提供则在新位置创建点
        
        Returns:
        --------
        str or None
            新点的ID，如果失败返回None
        """
        if point_id not in self.edit_manager._points:
            return None
        
        position = self.edit_manager._points[point_id].copy()
        
        # 如果提供了偏移量，应用偏移
        if offset is not None:
            position = position + offset
        
        # 获取原点的名称（如果有）
        name = None
        if point_id in self._point_objects:
            name = self._point_objects[point_id].name
        
        # 创建新点
        new_id = self._generate_point_id()
        return self.create_point_at_position(position, view, name)
    
    def duplicate_selected_point(self, view, offset: Optional[np.ndarray] = None) -> Optional[str]:
        """复制当前选中的点"""
        selected = self.edit_manager.get_selected_point()
        if selected is None:
            return None
        point_id, _ = selected
        return self.duplicate_point(point_id, view, offset)
    
    def mirror_point(self, point_id: str, mirror_plane: str, view) -> Optional[str]:
        """
        镜像点
        
        Parameters:
        -----------
        point_id : str
            要镜像的点ID
        mirror_plane : str
            镜像平面：'xy', 'xz', 'yz', 'x', 'y', 'z'
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        str or None
            新点的ID，如果失败返回None
        """
        if point_id not in self.edit_manager._points:
            return None
        
        position = self.edit_manager._points[point_id].copy()
        
        # 应用镜像变换
        if mirror_plane == 'xy':
            position[2] = -position[2]
        elif mirror_plane == 'xz':
            position[1] = -position[1]
        elif mirror_plane == 'yz':
            position[0] = -position[0]
        elif mirror_plane == 'x':
            position[0] = -position[0]
        elif mirror_plane == 'y':
            position[1] = -position[1]
        elif mirror_plane == 'z':
            position[2] = -position[2]
        else:
            return None
        
        # 获取原点的名称（如果有）
        name = None
        if point_id in self._point_objects:
            name = self._point_objects[point_id].name
        
        # 创建新点
        new_id = self._generate_point_id()
        return self.create_point_at_position(position, view, name)
    
    # ========== 合并点 ==========
    
    def merge_points(self, point_ids: List[str], view, threshold: float = 0.1) -> Optional[str]:
        """
        合并多个点（在阈值范围内）
        
        Parameters:
        -----------
        point_ids : List[str]
            要合并的点ID列表
        view : InteractiveView
            视图实例
        threshold : float
            合并阈值
        
        Returns:
        --------
        str or None
            合并后的点ID，如果失败返回None
        """
        if len(point_ids) < 2:
            return None
        
        # 收集所有点的位置
        positions = []
        names = []
        for point_id in point_ids:
            if point_id in self.edit_manager._points:
                positions.append(self.edit_manager._points[point_id])
                if point_id in self._point_objects:
                    names.append(self._point_objects[point_id].name)
        
        if len(positions) < 2:
            return None
        
        # 计算中心位置
        center = np.mean(positions, axis=0)
        
        # 合并名称（使用第一个非空名称）
        merged_name = None
        for name in names:
            if name is not None:
                merged_name = name
                break
        
        # 创建新点
        new_id = self._generate_point_id()
        if self.create_point_at_position(center, view, merged_name) is None:
            return None
        
        # 删除旧点
        for point_id in point_ids:
            self.delete_point(point_id, view)
        
        return new_id
    
    def merge_duplicate_points(self, view, threshold: float = 0.1) -> int:
        """
        合并所有重复的点
        
        Parameters:
        -----------
        view : InteractiveView
            视图实例
        threshold : float
            合并阈值
        
        Returns:
        --------
        int
            合并的点对数量
        """
        merged_count = 0
        point_ids = list(self.edit_manager._points.keys())
        
        i = 0
        while i < len(point_ids):
            point_id = point_ids[i]
            if point_id not in self.edit_manager._points:
                i += 1
                continue
            
            position = self.edit_manager._points[point_id]
            duplicates = [point_id]
            
            # 查找所有重复的点
            j = i + 1
            while j < len(point_ids):
                other_id = point_ids[j]
                if other_id not in self.edit_manager._points:
                    j += 1
                    continue
                
                other_pos = self.edit_manager._points[other_id]
                dist = np.linalg.norm(position - other_pos)
                
                if dist < threshold:
                    duplicates.append(other_id)
                    point_ids.remove(other_id)
                
                j += 1
            
            # 如果有重复，合并它们
            if len(duplicates) > 1:
                self.merge_points(duplicates, view, threshold)
                merged_count += len(duplicates) - 1
            
            i += 1
        
        return merged_count
    
    # ========== 捕捉功能 ==========
    
    def _apply_snap(self, position: np.ndarray, view) -> np.ndarray:
        """
        应用捕捉到位置
        
        Parameters:
        -----------
        position : np.ndarray
            原始位置
        view : InteractiveView
            视图实例
        
        Returns:
        --------
        np.ndarray
            应用捕捉后的位置
        """
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
            # 计算点到线段的最短距离
            dist = self.edit_manager.distance_point_to_line(position, start, end)
            if dist < min_dist:
                # 计算线段上最近的点
                line_vec = end - start
                line_len = np.linalg.norm(line_vec)
                if line_len > 1e-10:
                    line_vec_normalized = line_vec / line_len
                    point_vec = position - start
                    t = np.dot(point_vec, line_vec_normalized)
                    t = np.clip(t, 0.0, line_len)
                    nearest = start + line_vec_normalized * t
                    min_dist = dist
        
        return nearest
    
    def _snap_to_nearest_plane(self, position: np.ndarray) -> Optional[np.ndarray]:
        """捕捉到最近的面"""
        min_dist = self._snap_threshold
        nearest = None
        
        for vertices in self.edit_manager._planes.values():
            # 计算点到面的距离
            dist = self.edit_manager.distance_point_to_plane(position, vertices)
            if dist < min_dist:
                # 计算面上最近的点（简化：使用面的中心点）
                nearest = np.mean(vertices, axis=0)
                min_dist = dist
        
        return nearest
    
    # ========== 约束功能 ==========
    
    def _apply_constraints(self, offset: np.ndarray) -> np.ndarray:
        """
        应用移动约束
        
        Parameters:
        -----------
        offset : np.ndarray
            原始偏移量
        
        Returns:
        --------
        np.ndarray
            应用约束后的偏移量
        """
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
    
    def set_constraint_axis(self, axis: Optional[str]):
        """
        设置轴约束
        
        Parameters:
        -----------
        axis : str or None
            'x', 'y', 'z' 或 None（无约束）
        """
        self._constraint_axis = axis
    
    def set_constraint_plane(self, plane: Optional[str]):
        """
        设置平面约束
        
        Parameters:
        -----------
        plane : str or None
            'xy', 'xz', 'yz' 或 None（无约束）
        """
        self._constraint_plane = plane
    
    # ========== 工具方法 ==========
    
    def _update_point_rendering(self, point_id: str, view):
        """更新点的渲染"""
        if point_id in self.edit_manager._point_actors:
            try:
                view.remove_actor(self.edit_manager._point_actors[point_id])
            except:
                pass
            self.edit_manager._render_point(point_id, view)
        view.render()
    
    def _generate_point_id(self) -> str:
        """生成唯一的点ID"""
        existing_ids = set(self.edit_manager._points.keys())
        counter = 0
        while True:
            point_id = f"point_{counter}"
            if point_id not in existing_ids:
                return point_id
            counter += 1
    
    def get_point_object(self, point_id: str) -> Optional[Point]:
        """
        获取 Point 对象
        
        Parameters:
        -----------
        point_id : str
            点ID
        
        Returns:
        --------
        Point or None
            Point 对象，如果不存在返回None
        """
        if point_id in self._point_objects:
            return self._point_objects[point_id]
        
        # 如果不存在，从 EditModeManager 创建
        if point_id in self.edit_manager._points:
            position = self.edit_manager._points[point_id]
            point = Point(
                id=point_id,
                position=position,
                name=None
            )
            self._point_objects[point_id] = point
            return point
        
        return None
    
    def get_all_point_objects(self) -> Dict[str, Point]:
        """
        获取所有 Point 对象
        
        Returns:
        --------
        Dict[str, Point]
            所有点的字典
        """
        # 确保所有点都有对应的 Point 对象
        for point_id in self.edit_manager._points.keys():
            if point_id not in self._point_objects:
                position = self.edit_manager._points[point_id]
                self._point_objects[point_id] = Point(
                    id=point_id,
                    position=position,
                    name=None
                )
        
        return self._point_objects.copy()
    
    def sync_point_objects(self):
        """同步 Point 对象与 EditModeManager 中的数据"""
        # 从 EditModeManager 更新 Point 对象的位置
        for point_id, position in self.edit_manager._points.items():
            if point_id in self._point_objects:
                try:
                    self._point_objects[point_id].set_position(
                        float(position[0]),
                        float(position[1]),
                        float(position[2])
                    )
                except:
                    # 如果更新失败，重新创建
                    name = self._point_objects[point_id].name
                    self._point_objects[point_id] = Point(
                        id=point_id,
                        position=position,
                        name=name
                    )
            else:
                # 创建新的 Point 对象
                self._point_objects[point_id] = Point(
                    id=point_id,
                    position=position,
                    name=None
                )
        
        # 删除不存在的点
        existing_ids = set(self.edit_manager._points.keys())
        to_remove = [pid for pid in self._point_objects.keys() if pid not in existing_ids]
        for pid in to_remove:
            del self._point_objects[pid]
    
    # ========== 设置捕捉选项 ==========
    
    def set_snap_to_grid(self, enabled: bool, spacing: float = 10.0):
        """
        设置网格捕捉
        
        Parameters:
        -----------
        enabled : bool
            是否启用网格捕捉
        spacing : float
            网格间距
        """
        self._snap_to_grid = enabled
        self._grid_spacing = spacing
    
    def set_snap_to_point(self, enabled: bool, threshold: float = 0.1):
        """
        设置点捕捉
        
        Parameters:
        -----------
        enabled : bool
            是否启用点捕捉
        threshold : float
            捕捉阈值
        """
        self._snap_to_point = enabled
        self._snap_threshold = threshold
    
    def set_snap_to_line(self, enabled: bool):
        """
        设置线捕捉
        
        Parameters:
        -----------
        enabled : bool
            是否启用线捕捉
        """
        self._snap_to_line = enabled
    
    def set_snap_to_plane(self, enabled: bool):
        """
        设置面捕捉
        
        Parameters:
        -----------
        enabled : bool
            是否启用面捕捉
        """
        self._snap_to_plane = enabled
    
    # ========== 查询功能 ==========
    
    def get_point_position(self, point_id: str) -> Optional[np.ndarray]:
        """
        获取点的位置
        
        Parameters:
        -----------
        point_id : str
            点ID
        
        Returns:
        --------
        np.ndarray or None
            点的位置，如果不存在返回None
        """
        if point_id in self.edit_manager._points:
            return self.edit_manager._points[point_id].position.copy()
        return None
    
    def get_point_name(self, point_id: str) -> Optional[str]:
        """
        获取点的名称
        
        Parameters:
        -----------
        point_id : str
            点ID
        
        Returns:
        --------
        str or None
            点的名称，如果不存在返回None
        """
        if point_id in self._point_objects:
            return self._point_objects[point_id].name
        return None
    
    def set_point_name(self, point_id: str, name: Optional[str]):
        """
        设置点的名称
        
        Parameters:
        -----------
        point_id : str
            点ID
        name : str or None
            点的名称
        """
        if point_id not in self._point_objects:
            # 如果 Point 对象不存在，创建一个
            if point_id in self.edit_manager._points:
                self._point_objects[point_id] = Point(
                    id=point_id,
                    position=self.edit_manager._points[point_id],
                    name=name
                )
        else:
            self._point_objects[point_id].name = name

