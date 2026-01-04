"""
撤销/重做功能 - 基于命令模式的实现

提供完整的撤销/重做机制，支持各种编辑操作的撤销和重做。
所有操作都通过命令对象封装，确保操作的原子性和可逆性。
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Any
import numpy as np
from model.geometry import Point


class Command(ABC):
    """命令抽象基类 - 定义所有命令的基本接口"""

    @abstractmethod
    def do(self, view=None) -> bool:
        """
        执行命令

        Parameters:
        -----------
        view : InteractiveView, optional
            视图实例，用于渲染更新

        Returns:
        --------
        bool
            执行是否成功
        """
        pass

    @abstractmethod
    def undo(self, view=None) -> bool:
        """
        撤销命令

        Parameters:
        -----------
        view : InteractiveView, optional
            视图实例，用于渲染更新

        Returns:
        --------
        bool
            撤销是否成功
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        获取命令描述

        Returns:
        --------
        str
            命令的描述字符串
        """
        pass


class UndoManager:
    """撤销管理器 - 管理命令栈和撤销/重做操作"""

    def __init__(self, max_items: int = 100):
        """
        初始化撤销管理器

        Parameters:
        -----------
        max_items : int
            最大撤销项数量，默认100
        """
        self._max_items = max_items
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []

    def execute_and_push(self, command: Command, view=None) -> bool:
        """
        执行命令并推入撤销栈

        Parameters:
        -----------
        command : Command
            要执行的命令
        view : InteractiveView, optional
            视图实例

        Returns:
        --------
        bool
            执行是否成功
        """
        if command.do(view):
            self._undo_stack.append(command)
            self._redo_stack.clear()  # 执行新命令后清空重做栈
            # 限制栈大小
            if len(self._undo_stack) > self._max_items:
                self._undo_stack.pop(0)
            return True
        return False

    def undo(self, view=None) -> bool:
        """
        撤销最后的操作

        Parameters:
        -----------
        view : InteractiveView, optional
            视图实例

        Returns:
        --------
        bool
            撤销是否成功
        """
        if not self._undo_stack:
            return False

        command = self._undo_stack.pop()
        if command.undo(view):
            self._redo_stack.append(command)
            return True
        else:
            # 如果撤销失败，重新放回栈中
            self._undo_stack.append(command)
            return False

    def redo(self, view=None) -> bool:
        """
        重做最后撤销的操作

        Parameters:
        -----------
        view : InteractiveView, optional
            视图实例

        Returns:
        --------
        bool
            重做是否成功
        """
        if not self._redo_stack:
            return False

        command = self._redo_stack.pop()
        if command.do(view):
            self._undo_stack.append(command)
            return True
        else:
            # 如果重做失败，重新放回栈中
            self._redo_stack.append(command)
            return False

    def can_undo(self) -> bool:
        """检查是否可以撤销"""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """检查是否可以重做"""
        return len(self._redo_stack) > 0

    def clear(self):
        """清空所有撤销/重做历史"""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def set_max_items(self, max_items: int):
        """
        设置最大撤销项数量

        Parameters:
        -----------
        max_items : int
            新的最大数量
        """
        self._max_items = max_items
        # 如果当前栈超过新限制，截断
        while len(self._undo_stack) > self._max_items:
            self._undo_stack.pop(0)

    def get_undo_description(self) -> Optional[str]:
        """获取下一个撤销操作的描述"""
        if self._undo_stack:
            return self._undo_stack[-1].get_description()
        return None

    def get_redo_description(self) -> Optional[str]:
        """获取下一个重做操作的描述"""
        if self._redo_stack:
            return self._redo_stack[-1].get_description()
        return None


# =============================================================================
# 点操作命令
# =============================================================================

class CreatePointCommand(Command):
    """创建点命令"""

    def __init__(self, edit_manager, point_id: str, position: np.ndarray, color: Optional[tuple] = None, locked: bool = False):
        """
        初始化创建点命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        point_id : str
            点ID
        position : np.ndarray
            点位置 [x, y, z]
        color : tuple, optional
            点颜色 (r, g, b)
        locked : bool
            是否锁定
        """
        self.edit_manager = edit_manager
        self.point_id = point_id
        self.position = np.array(position, dtype=np.float64)
        self.color = color
        self.locked = locked

    def do(self, view=None) -> bool:
        """执行创建点"""
        if self.point_id in self.edit_manager._points:
            return False  # 点已存在
        point = Point(id=self.point_id, position=self.position)
        if self.color is not None:
            point.color = self.color
        self.edit_manager._points[self.point_id] = point
        # 使用点自身颜色或默认
        if self.point_id not in self.edit_manager._point_colors:
            self.edit_manager._point_colors[self.point_id] = tuple(point.color) if getattr(point, "color", None) is not None else (1.0, 0.0, 0.0)
        if self.locked:
            self.edit_manager._locked_points.add(self.point_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_point(self.point_id, view)
        return True

    def undo(self, view=None) -> bool:
        """撤销创建点 - 直接操作数据"""
        if self.point_id not in self.edit_manager._points:
            return False

        # 移除actor
        if self.point_id in self.edit_manager._point_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._point_actors[self.point_id])
            except:
                pass
            del self.edit_manager._point_actors[self.point_id]

        # 删除点数据
        del self.edit_manager._points[self.point_id]
        if self.point_id in self.edit_manager._point_colors:
            del self.edit_manager._point_colors[self.point_id]
        if self.point_id in self.edit_manager._locked_points:
            self.edit_manager._locked_points.remove(self.point_id)

        # 如果当前选中，清除选择
        if self.edit_manager._selected_point_id == self.point_id:
            self.edit_manager._selected_point_id = None

        return True

    def get_description(self) -> str:
        return f"创建点 {self.point_id}"


class RemovePointCommand(Command):
    """删除点命令"""

    def __init__(self, edit_manager, point_id: str):
        """
        初始化删除点命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        point_id : str
            要删除的点ID
        """
        self.edit_manager = edit_manager
        self.point_id = point_id
        # 保存删除前的状态
        self.saved_point = None
        self.saved_color = None
        self.was_locked = False

    def do(self, view=None) -> bool:
        """执行删除点"""
        if self.point_id in self.edit_manager._locked_points:
            return False
        if self.point_id not in self.edit_manager._points:
            return False

        # 保存点信息用于撤销
        self.saved_point = self.edit_manager._points[self.point_id]
        self.saved_color = self.edit_manager._point_colors.get(self.point_id)
        self.was_locked = self.point_id in self.edit_manager._locked_points

        # 执行删除操作
        # 移除actor
        if self.point_id in self.edit_manager._point_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._point_actors[self.point_id])
            except:
                pass
            del self.edit_manager._point_actors[self.point_id]

        del self.edit_manager._points[self.point_id]
        if self.point_id in self.edit_manager._point_colors:
            del self.edit_manager._point_colors[self.point_id]

        # 如果当前选中，清除选择
        if self.edit_manager._selected_point_id == self.point_id:
            self.edit_manager._selected_point_id = None
        return True

    def undo(self, view=None) -> bool:
        """撤销删除点（重新创建点）"""
        if self.saved_point is None:
            return False

        # 重新添加点
        if self.point_id in self.edit_manager._points:
            return False  # 点已存在

        self.edit_manager._points[self.point_id] = self.saved_point
        if self.saved_color is not None:
            self.edit_manager._point_colors[self.point_id] = self.saved_color
        if self.was_locked:
            self.edit_manager._locked_points.add(self.point_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_point(self.point_id, view)
        return True

    def get_description(self) -> str:
        return f"删除点 {self.point_id}"


class MovePointCommand(Command):
    """移动点命令"""

    def __init__(self, edit_manager, point_id: str, old_position: np.ndarray, new_position: np.ndarray):
        """
        初始化移动点命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        point_id : str
            点ID
        old_position : np.ndarray
            旧位置
        new_position : np.ndarray
            新位置
        """
        self.edit_manager = edit_manager
        self.point_id = point_id
        self.old_position = np.array(old_position, dtype=np.float64)
        self.new_position = np.array(new_position, dtype=np.float64)

    def do(self, view=None) -> bool:
        """执行移动点"""
        if self.point_id not in self.edit_manager._points:
            return False

        # 获取/规范化 Point 对象
        point_obj = self.edit_manager._points.get(self.point_id)
        if not isinstance(point_obj, Point):
            # 兼容历史数据（numpy 数组）
            point_obj = Point(id=self.point_id, position=np.array(point_obj, dtype=np.float64))
            self.edit_manager._points[self.point_id] = point_obj

        # 更新位置
        point_obj.set_position(
            float(self.new_position[0]),
            float(self.new_position[1]),
            float(self.new_position[2])
        )

        # 同步本地缓存（如果 point operator 有的话）
        if hasattr(self.edit_manager, '_point_objects'):
            self.edit_manager._point_objects[self.point_id] = point_obj

        # 更新渲染
        if hasattr(self.edit_manager, '_render_point'):
            self.edit_manager._render_point(self.point_id, view)
        return True

    def undo(self, view=None) -> bool:
        """撤销移动点（回到旧位置）"""
        if self.point_id not in self.edit_manager._points:
            return False

        # 获取/规范化 Point 对象
        point_obj = self.edit_manager._points.get(self.point_id)
        if not isinstance(point_obj, Point):
            # 兼容历史数据（numpy 数组）
            point_obj = Point(id=self.point_id, position=np.array(point_obj, dtype=np.float64))
            self.edit_manager._points[self.point_id] = point_obj

        # 更新位置到旧位置
        point_obj.set_position(
            float(self.old_position[0]),
            float(self.old_position[1]),
            float(self.old_position[2])
        )

        # 同步本地缓存（如果 point operator 有的话）
        if hasattr(self.edit_manager, '_point_objects'):
            self.edit_manager._point_objects[self.point_id] = point_obj

        # 更新渲染
        if hasattr(self.edit_manager, '_render_point'):
            self.edit_manager._render_point(self.point_id, view)
        return True

    def get_description(self) -> str:
        return f"移动点 {self.point_id}"


# =============================================================================
# 线操作命令
# =============================================================================

class CreateLineCommand(Command):
    """创建线命令"""

    def __init__(self, edit_manager, line_id: str, start: str, end: str, color: Optional[tuple] = None, locked: bool = False):
        """
        初始化创建线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        line_id : str
            线ID
        start : str
            起点点ID
        end : str
            终点点ID
        color : tuple, optional
            线颜色
        locked : bool
            是否锁定
        """
        self.edit_manager = edit_manager
        self.line_id = line_id
        self.start = start
        self.end = end
        self.color = color
        self.locked = locked

    def do(self, view=None) -> bool:
        """执行创建线"""
        if self.line_id in self.edit_manager._lines:
            return False  # 线已存在

        # 支持基于点ID的引用
        if isinstance(self.start, str) and isinstance(self.end, str):
            self.edit_manager._lines[self.line_id] = (self.start, self.end)
        else:
            self.edit_manager._lines[self.line_id] = (
                np.array(self.start, dtype=np.float64),
                np.array(self.end, dtype=np.float64)
            )

        if self.line_id not in self.edit_manager._line_colors:
            if self.color is not None:
                self.edit_manager._line_colors[self.line_id] = tuple(self.color)
            else:
                self.edit_manager._line_colors[self.line_id] = (0.0, 0.0, 1.0)  # blue

        if self.locked:
            self.edit_manager._locked_lines.add(self.line_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_line(self.line_id, view)

        return True

    def undo(self, view=None) -> bool:
        """撤销创建线"""
        if self.line_id in self.edit_manager._locked_lines:
            return False
        if self.line_id not in self.edit_manager._lines:
            return False

        # 移除actor
        if self.line_id in self.edit_manager._line_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._line_actors[self.line_id])
            except:
                pass
            del self.edit_manager._line_actors[self.line_id]

        del self.edit_manager._lines[self.line_id]
        if self.line_id in self.edit_manager._line_colors:
            del self.edit_manager._line_colors[self.line_id]

        # 如果当前选中，清除选择
        if self.edit_manager._selected_line_id == self.line_id:
            self.edit_manager._selected_line_id = None
        return True

    def get_description(self) -> str:
        return f"创建线 {self.line_id}"


class RemoveLineCommand(Command):
    """删除线命令"""

    def __init__(self, edit_manager, line_id: str):
        """
        初始化删除线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        line_id : str
            要删除的线ID
        """
        self.edit_manager = edit_manager
        self.line_id = line_id
        # 保存删除前的状态
        self.saved_start = None
        self.saved_end = None
        self.saved_color = None
        self.was_locked = False

    def do(self, view=None) -> bool:
        """执行删除线"""
        if self.line_id in self.edit_manager._locked_lines:
            return False
        if self.line_id not in self.edit_manager._lines:
            return False

        # 保存线信息用于撤销
        self.saved_start, self.saved_end = self.edit_manager._lines[self.line_id]
        self.saved_color = self.edit_manager._line_colors.get(self.line_id)
        self.was_locked = self.line_id in self.edit_manager._locked_lines

        # 执行删除操作
        # 移除actor
        if self.line_id in self.edit_manager._line_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._line_actors[self.line_id])
            except:
                pass
            del self.edit_manager._line_actors[self.line_id]

        del self.edit_manager._lines[self.line_id]
        if self.line_id in self.edit_manager._line_colors:
            del self.edit_manager._line_colors[self.line_id]

        # 如果当前选中，清除选择
        if self.edit_manager._selected_line_id == self.line_id:
            self.edit_manager._selected_line_id = None
        return True

    def undo(self, view=None) -> bool:
        """撤销删除线（重新创建线）"""
        if self.saved_start is None or self.saved_end is None:
            return False

        # 重新创建线
        if self.line_id in self.edit_manager._lines:
            return False  # 线已存在

        self.edit_manager._lines[self.line_id] = (self.saved_start, self.saved_end)
        if self.saved_color is not None:
            self.edit_manager._line_colors[self.line_id] = self.saved_color
        if self.was_locked:
            self.edit_manager._locked_lines.add(self.line_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_line(self.line_id, view)

        return True

    def get_description(self) -> str:
        return f"删除线 {self.line_id}"


# =============================================================================
# 折线操作命令
# =============================================================================

class CreatePolylineCommand(Command):
    """创建折线命令"""

    def __init__(self, edit_manager, polyline_id: str, point_ids: List[str], color: Optional[tuple] = None, locked: bool = False):
        """
        初始化创建折线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        polyline_id : str
            折线ID
        point_ids : List[str]
            组成折线的点ID列表
        color : tuple, optional
            折线颜色
        locked : bool
            是否锁定
        """
        self.edit_manager = edit_manager
        self.polyline_id = polyline_id
        self.point_ids = list(point_ids)
        self.color = color
        self.locked = locked

    def do(self, view=None) -> bool:
        """执行创建折线"""
        # basic validation
        if not isinstance(self.point_ids, list) or len(self.point_ids) < 2:
            return False
        
        # 获取Point对象列表
        from model.geometry import Polyline, Point
        point_objects = []
        for pid in self.point_ids:
            if pid in self.edit_manager._points:
                point_obj = self.edit_manager._points[pid]
                if not isinstance(point_obj, Point):
                    point_obj = Point(id=pid, position=np.array(point_obj, dtype=np.float64))
                    self.edit_manager._points[pid] = point_obj
                point_objects.append(point_obj)
            else:
                return False
        
        # 创建Polyline几何对象
        polyline_obj = Polyline(id=self.polyline_id, points=point_objects, color=self.color)
        
        # 存储几何对象
        self.edit_manager._polylines[self.polyline_id] = {
            'point_ids': list(self.point_ids),
            'geometry': polyline_obj
        }
        
        if self.polyline_id not in self.edit_manager._line_colors:
            if self.color is not None:
                self.edit_manager._line_colors[self.polyline_id] = tuple(self.color)
            else:
                self.edit_manager._line_colors[self.polyline_id] = (0.0, 0.0, 1.0)
        if self.locked:
            self.edit_manager._locked_lines.add(self.polyline_id)
        # render
        if view is not None:
            self.edit_manager._render_polyline(self.polyline_id, view)
        return True

    def undo(self, view=None) -> bool:
        """撤销创建折线"""
        if self.polyline_id not in self.edit_manager._polylines:
            return False
        if view is not None and self.polyline_id in self.edit_manager._polyline_actors:
            try:
                view.remove_actor(self.edit_manager._polyline_actors[self.polyline_id])
            except:
                pass
            self.edit_manager._polyline_actors.pop(self.polyline_id, None)
        self.edit_manager._polylines.pop(self.polyline_id, None)
        return True

    def get_description(self) -> str:
        return f"创建折线 {self.polyline_id}"


class RemovePolylineCommand(Command):
    """删除折线命令"""

    def __init__(self, edit_manager, polyline_id: str):
        """
        初始化删除折线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        polyline_id : str
            要删除的折线ID
        """
        self.edit_manager = edit_manager
        self.polyline_id = polyline_id
        # 保存删除前的状态
        self.saved_point_ids = None
        self.saved_color = None
        self.was_locked = False

    def do(self, view=None) -> bool:
        """执行删除折线"""
        if self.polyline_id not in self.edit_manager._polylines:
            return False

        # 保存折线信息用于撤销
        self.saved_point_ids = list(self.edit_manager._polylines[self.polyline_id])
        self.saved_color = self.edit_manager._line_colors.get(self.polyline_id)
        self.was_locked = self.polyline_id in self.edit_manager._locked_lines

        # 执行删除操作
        if view is not None and self.polyline_id in self.edit_manager._polyline_actors:
            try:
                view.remove_actor(self.edit_manager._polyline_actors[self.polyline_id])
            except:
                pass
            self.edit_manager._polyline_actors.pop(self.polyline_id, None)
        self.edit_manager._polylines.pop(self.polyline_id, None)
        return True

    def undo(self, view=None) -> bool:
        """撤销删除折线（重新创建折线）"""
        if self.saved_point_ids is None:
            return False

        # 重新创建折线
        if self.polyline_id in self.edit_manager._polylines:
            return False  # 折线已存在

        self.edit_manager._polylines[self.polyline_id] = list(self.saved_point_ids)
        if self.saved_color is not None:
            self.edit_manager._line_colors[self.polyline_id] = self.saved_color
        if self.was_locked:
            self.edit_manager._locked_lines.add(self.polyline_id)

        # render
        if view is not None:
            self.edit_manager._render_polyline(self.polyline_id, view)
        return True

    def get_description(self) -> str:
        return f"删除折线 {self.polyline_id}"


# =============================================================================
# 曲线操作命令
# =============================================================================

class CreateCurveCommand(Command):
    """创建曲线命令"""

    def __init__(self, edit_manager, curve_id: str, control_point_ids: List[str], degree: int = 3, num_points: int = 100, color: Optional[tuple] = None, locked: bool = False):
        """
        初始化创建曲线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        curve_id : str
            曲线ID
        control_point_ids : List[str]
            控制点ID列表
        degree : int
            曲线阶数
        num_points : int
            采样点数量
        color : tuple, optional
            曲线颜色
        locked : bool
            是否锁定
        """
        self.edit_manager = edit_manager
        self.curve_id = curve_id
        self.control_point_ids = list(control_point_ids)
        self.degree = degree
        self.num_points = num_points
        self.color = color
        self.locked = locked

    def do(self, view=None) -> bool:
        """执行创建曲线"""
        if self.curve_id in self.edit_manager._curves:
            return False
        if len(self.control_point_ids) < 2:
            return False
        
        # 获取Point对象列表
        from model.geometry import Curve, Point
        point_objects = []
        for pid in self.control_point_ids:
            if pid in self.edit_manager._points:
                point_obj = self.edit_manager._points[pid]
                if not isinstance(point_obj, Point):
                    point_obj = Point(id=pid, position=np.array(point_obj, dtype=np.float64))
                    self.edit_manager._points[pid] = point_obj
                point_objects.append(point_obj)
            else:
                return False
        
        # 创建Curve几何对象
        curve_obj = Curve(id=self.curve_id, control_points=point_objects, 
                         degree=int(self.degree), num_points=int(self.num_points), 
                         color=self.color)
        
        # 存储几何对象
        self.edit_manager._curves[self.curve_id] = {
            'control_point_ids': list(self.control_point_ids), 
            'degree': int(self.degree), 
            'num_points': int(self.num_points),
            'geometry': curve_obj
        }
        
        if self.color is not None:
            self.edit_manager._line_colors[self.curve_id] = tuple(self.color)
        if self.locked:
            self.edit_manager._locked_lines.add(self.curve_id)
        if view is not None:
            self.edit_manager._render_curve(self.curve_id, view)
        return True

    def undo(self, view=None) -> bool:
        """撤销创建曲线"""
        if self.curve_id not in self.edit_manager._curves:
            return False
        if view is not None and self.curve_id in self.edit_manager._curve_actors:
            try:
                view.remove_actor(self.edit_manager._curve_actors[self.curve_id])
            except:
                pass
            self.edit_manager._curve_actors.pop(self.curve_id, None)
        self.edit_manager._curves.pop(self.curve_id, None)
        return True

    def get_description(self) -> str:
        return f"创建曲线 {self.curve_id}"


class RemoveCurveCommand(Command):
    """删除曲线命令"""

    def __init__(self, edit_manager, curve_id: str):
        """
        初始化删除曲线命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        curve_id : str
            要删除的曲线ID
        """
        self.edit_manager = edit_manager
        self.curve_id = curve_id
        # 保存删除前的状态
        self.saved_control_ids = None
        self.saved_degree = None
        self.saved_num_points = None
        self.saved_color = None
        self.was_locked = False

    def do(self, view=None) -> bool:
        """执行删除曲线"""
        if self.curve_id not in self.edit_manager._curves:
            return False

        # 保存曲线信息用于撤销
        curve_data = self.edit_manager._curves[self.curve_id]
        self.saved_control_ids = list(curve_data['control_point_ids'])
        self.saved_degree = curve_data['degree']
        self.saved_num_points = curve_data['num_points']
        self.saved_color = self.edit_manager._line_colors.get(self.curve_id)
        self.was_locked = self.curve_id in self.edit_manager._locked_lines

        # 执行删除操作
        if view is not None and self.curve_id in self.edit_manager._curve_actors:
            try:
                view.remove_actor(self.edit_manager._curve_actors[self.curve_id])
            except:
                pass
            self.edit_manager._curve_actors.pop(self.curve_id, None)
        self.edit_manager._curves.pop(self.curve_id, None)
        return True

    def undo(self, view=None) -> bool:
        """撤销删除曲线（重新创建曲线）"""
        if self.saved_control_ids is None:
            return False

        # 重新创建曲线
        if self.curve_id in self.edit_manager._curves:
            return False  # 曲线已存在

        self.edit_manager._curves[self.curve_id] = {'control_point_ids': list(self.saved_control_ids), 'degree': int(self.saved_degree), 'num_points': int(self.saved_num_points)}
        if self.saved_color is not None:
            self.edit_manager._line_colors[self.curve_id] = self.saved_color
        if self.was_locked:
            self.edit_manager._locked_lines.add(self.curve_id)

        if view is not None:
            self.edit_manager._render_curve(self.curve_id, view)
        return True

    def get_description(self) -> str:
        return f"删除曲线 {self.curve_id}"


# =============================================================================
# 面操作命令
# =============================================================================

class CreatePlaneCommand(Command):
    """创建面命令"""

    def __init__(self, edit_manager, plane_id: str, vertices: np.ndarray, color: Optional[tuple] = None, locked: bool = False):
        """初始化创建面命令"""
        self.edit_manager = edit_manager
        self.plane_id = plane_id
        self.vertices = np.array(vertices, dtype=np.float64)
        self.color = color
        self.locked = locked

    def do(self, view=None) -> bool:
        """执行创建面"""
        if self.plane_id in self.edit_manager._planes:
            return False  # 面已存在

        vertices = np.array(self.vertices, dtype=np.float64)
        if vertices.shape[0] < 3:
            return False  # 至少需要3个点

        self.edit_manager._planes[self.plane_id] = vertices
        if self.plane_id not in self.edit_manager._plane_colors:
            if self.color is not None:
                self.edit_manager._plane_colors[self.plane_id] = tuple(self.color)
            else:
                self.edit_manager._plane_colors[self.plane_id] = (0.0, 1.0, 0.0)  # green
        if self.locked:
            self.edit_manager._locked_planes.add(self.plane_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_plane(self.plane_id, view)

        return True

    def undo(self, view=None) -> bool:
        """撤销创建面"""
        if self.plane_id in self.edit_manager._locked_planes:
            return False
        if self.plane_id not in self.edit_manager._planes:
            return False

        # 移除actor
        if self.plane_id in self.edit_manager._plane_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._plane_actors[self.plane_id])
            except:
                pass
            del self.edit_manager._plane_actors[self.plane_id]

        # 移除顶点标记actors
        if self.plane_id in self.edit_manager._plane_vertex_actors and view is not None:
            for actor in self.edit_manager._plane_vertex_actors[self.plane_id]:
                try:
                    view.remove_actor(actor)
                except:
                    pass
            del self.edit_manager._plane_vertex_actors[self.plane_id]

        del self.edit_manager._planes[self.plane_id]
        if self.plane_id in self.edit_manager._plane_colors:
            del self.edit_manager._plane_colors[self.plane_id]

        # 如果当前选中，清除选择
        if self.edit_manager._selected_plane_id == self.plane_id:
            self.edit_manager._selected_plane_id = None
        return True

    def get_description(self) -> str:
        return f"创建面 {self.plane_id}"


class RemovePlaneCommand(Command):
    """删除面命令"""

    def __init__(self, edit_manager, plane_id: str):
        """
        初始化删除面命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        plane_id : str
            要删除的面ID
        """
        self.edit_manager = edit_manager
        self.plane_id = plane_id
        # 保存删除前的状态
        self.saved_vertices = None
        self.saved_color = None
        self.was_locked = False

    def do(self, view=None) -> bool:
        """执行删除面"""
        if self.plane_id in self.edit_manager._locked_planes:
            return False
        if self.plane_id not in self.edit_manager._planes:
            return False

        # 保存面信息用于撤销
        self.saved_vertices = self.edit_manager._planes[self.plane_id].copy()
        self.saved_color = self.edit_manager._plane_colors.get(self.plane_id)
        self.was_locked = self.plane_id in self.edit_manager._locked_planes

        # 执行删除操作
        # 移除actor
        if self.plane_id in self.edit_manager._plane_actors and view is not None:
            try:
                view.remove_actor(self.edit_manager._plane_actors[self.plane_id])
            except:
                pass
            del self.edit_manager._plane_actors[self.plane_id]

        # 移除顶点标记actors
        if self.plane_id in self.edit_manager._plane_vertex_actors and view is not None:
            for actor in self.edit_manager._plane_vertex_actors[self.plane_id]:
                try:
                    view.remove_actor(actor)
                except:
                    pass
            del self.edit_manager._plane_vertex_actors[self.plane_id]

        del self.edit_manager._planes[self.plane_id]
        if self.plane_id in self.edit_manager._plane_colors:
            del self.edit_manager._plane_colors[self.plane_id]

        # 如果当前选中，清除选择
        if self.edit_manager._selected_plane_id == self.plane_id:
            self.edit_manager._selected_plane_id = None
        return True

    def undo(self, view=None) -> bool:
        """撤销删除面（重新创建面）"""
        if self.saved_vertices is None:
            return False

        # 重新创建面
        if self.plane_id in self.edit_manager._planes:
            return False  # 面已存在

        self.edit_manager._planes[self.plane_id] = self.saved_vertices.copy()
        if self.saved_color is not None:
            self.edit_manager._plane_colors[self.plane_id] = self.saved_color
        if self.was_locked:
            self.edit_manager._locked_planes.add(self.plane_id)

        # 如果提供了view，创建并添加actor
        if view is not None:
            self.edit_manager._render_plane(self.plane_id, view)

        return True

    def get_description(self) -> str:
        return f"删除面 {self.plane_id}"


# =============================================================================
# 颜色设置命令
# =============================================================================

class SetPointColorCommand(Command):
    """设置点颜色命令"""

    def __init__(self, edit_manager, point_id: str, new_color: tuple, old_color: Optional[tuple] = None):
        """
        初始化设置点颜色命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        point_id : str
            点ID
        new_color : tuple
            新颜色 (r, g, b)
        old_color : tuple, optional
            旧颜色，如果不提供则从当前状态获取
        """
        self.edit_manager = edit_manager
        self.point_id = point_id
        self.new_color = tuple(new_color)
        self.old_color = old_color

    def do(self, view=None) -> bool:
        """执行设置点颜色"""
        if self.old_color is None:
            self.old_color = self.edit_manager._point_colors.get(self.point_id, (1.0, 0.0, 0.0))
        self.edit_manager._point_colors[self.point_id] = self.new_color
        # 更新渲染
        actor = self.edit_manager._point_actors.get(self.point_id)
        if actor is not None:
            try:
                # 优先使用VTK Property 设置颜色，兼容不同版本
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*self.new_color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*self.new_color)
            except:
                pass
        if view is not None and actor is None and self.point_id in self.edit_manager._points:
            self.edit_manager._render_point(self.point_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass
        return True

    def undo(self, view=None) -> bool:
        """撤销设置点颜色"""
        if self.old_color is not None:
            self.edit_manager._point_colors[self.point_id] = self.old_color
            # 更新渲染
            actor = self.edit_manager._point_actors.get(self.point_id)
            if actor is not None:
                try:
                    if hasattr(actor, "GetProperty"):
                        actor.GetProperty().SetColor(*self.old_color)
                    if hasattr(actor, "prop"):
                        actor.prop.set_color(*self.old_color)
                except:
                    pass
            if view is not None:
                try:
                    view.render()
                except:
                    pass
            return True
        return False

    def get_description(self) -> str:
        return f"设置点 {self.point_id} 颜色"


class SetLineColorCommand(Command):
    """设置线颜色命令"""

    def __init__(self, edit_manager, line_id: str, new_color: tuple, old_color: Optional[tuple] = None):
        """
        初始化设置线颜色命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        line_id : str
            线ID
        new_color : tuple
            新颜色 (r, g, b)
        old_color : tuple, optional
            旧颜色，如果不提供则从当前状态获取
        """
        self.edit_manager = edit_manager
        self.line_id = line_id
        self.new_color = tuple(new_color)
        self.old_color = old_color

    def do(self, view=None) -> bool:
        """执行设置线颜色"""
        if self.old_color is None:
            self.old_color = self.edit_manager._line_colors.get(self.line_id, (0.0, 0.0, 1.0))
        self.edit_manager._line_colors[self.line_id] = self.new_color
        # 更新渲染
        actor = self.edit_manager._line_actors.get(self.line_id)
        if actor is not None:
            try:
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*self.new_color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*self.new_color)
            except:
                pass
        if view is not None and actor is None and self.line_id in self.edit_manager._lines:
            self.edit_manager._render_line(self.line_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass
        return True

    def undo(self, view=None) -> bool:
        """撤销设置线颜色"""
        if self.old_color is not None:
            self.edit_manager._line_colors[self.line_id] = self.old_color
            # 更新渲染
            actor = self.edit_manager._line_actors.get(self.line_id)
            if actor is not None:
                try:
                    if hasattr(actor, "GetProperty"):
                        actor.GetProperty().SetColor(*self.old_color)
                    if hasattr(actor, "prop"):
                        actor.prop.set_color(*self.old_color)
                except:
                    pass
            if view is not None:
                try:
                    view.render()
                except:
                    pass
            return True
        return False

    def get_description(self) -> str:
        return f"设置线 {self.line_id} 颜色"


class SetPlaneColorCommand(Command):
    """设置面颜色命令"""

    def __init__(self, edit_manager, plane_id: str, new_color: tuple, old_color: Optional[tuple] = None):
        """
        初始化设置面颜色命令

        Parameters:
        -----------
        edit_manager : EditModeManager
            编辑模式管理器
        plane_id : str
            面ID
        new_color : tuple
            新颜色 (r, g, b)
        old_color : tuple, optional
            旧颜色，如果不提供则从当前状态获取
        """
        self.edit_manager = edit_manager
        self.plane_id = plane_id
        self.new_color = tuple(new_color)
        self.old_color = old_color

    def do(self, view=None) -> bool:
        """执行设置面颜色"""
        if self.old_color is None:
            self.old_color = self.edit_manager._plane_colors.get(self.plane_id, (0.0, 1.0, 0.0))
        self.edit_manager._plane_colors[self.plane_id] = self.new_color
        # 更新渲染
        actor = self.edit_manager._plane_actors.get(self.plane_id)
        if actor is not None:
            try:
                if hasattr(actor, "GetProperty"):
                    actor.GetProperty().SetColor(*self.new_color)
                if hasattr(actor, "prop"):
                    actor.prop.set_color(*self.new_color)
            except:
                pass
        if view is not None and actor is None and self.plane_id in self.edit_manager._planes:
            self.edit_manager._render_plane(self.plane_id, view)
        if view is not None:
            try:
                view.render()
            except:
                pass
        return True

    def undo(self, view=None) -> bool:
        """撤销设置面颜色"""
        if self.old_color is not None:
            self.edit_manager._plane_colors[self.plane_id] = self.old_color
            # 更新渲染
            actor = self.edit_manager._plane_actors.get(self.plane_id)
            if actor is not None:
                try:
                    if hasattr(actor, "GetProperty"):
                        actor.GetProperty().SetColor(*self.old_color)
                    if hasattr(actor, "prop"):
                        actor.prop.set_color(*self.old_color)
                except:
                    pass
            if view is not None:
                try:
                    view.render()
                except:
                    pass
            return True
        return False

    def get_description(self) -> str:
        return f"设置面 {self.plane_id} 颜色"
