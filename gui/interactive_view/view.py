"""
交互式建模视图核心类
"""
from PyQt5.QtWidgets import QLabel, QToolButton, QMenu, QWidgetAction, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap
import os
from pyvistaqt import QtInteractor
import pyvista as pv
import numpy as np
from typing import Optional
from .mode_toolbar import ModeToolbar
from .workspace import (
    create_workspace_bounds_mesh,
    calculate_workspace_center,
    calculate_initial_camera_distance,
    get_default_workspace_bounds,
    create_grid_mesh,
    create_origin_axes_mesh
)
from .camera import CameraController
from .coordinates import CoordinateConverter
from .events import EventHandler
from .edit_mode import EditModeManager, PointOperator, LineOperator, PlaneOperator, ColorSelector


class InteractiveView(QtInteractor):
    """交互式建模视图 - 实现轨道摄像机控制"""
    
    # 信号定义
    view_changed = pyqtSignal()  # 视图改变时发出信号
    status_message = pyqtSignal(str)  # 状态消息信号
    mode_changed = pyqtSignal(str)  # 模式改变时发出信号，参数是模式名称
    tool_changed = pyqtSignal(str)  # 工具改变时发出信号，参数是工具名称
    
    def __init__(self, parent=None, 
                 workspace_bounds: Optional[np.ndarray] = None,
                 background_color: str = 'white'):
        """
        初始化交互式视图
        
        Parameters:
        -----------
        parent : QWidget, optional
            父窗口
        workspace_bounds : np.ndarray, optional
            建模空间边界 [xmin, xmax, ymin, ymax, zmin, zmax]
            如果为None，使用默认值 [-100, 100, -100, 100, -50, 0]
        background_color : str
            背景颜色，默认白色
        """
        super().__init__(parent)
        
        # 设置背景颜色
        self.set_background(background_color)
        
        # 建模空间边界
        if workspace_bounds is None:
            self.workspace_bounds = get_default_workspace_bounds()
        else:
            self.workspace_bounds = np.array(workspace_bounds, dtype=np.float64)
        
        # 轨道摄像机参数
        self._orbit_center = self._calculate_workspace_center()
        self._camera_distance = self._calculate_initial_distance()
        
        # 投影模式：True=正交投影，False=透视投影
        self._is_orthographic = False
        
        # 显示状态
        self._show_grid = False  # 是否显示网格
        self._show_origin_axes = False  # 是否显示原点坐标轴
        self._grid_actor = None  # 网格actor
        self._origin_axes_actor = None  # 原点坐标轴actor
        self._grid_spacing = 10.0  # 网格间距
        
        # 模式选择
        self._current_mode = 'object'  # 当前模式：'object'（物体模式）或 'edit'（编辑模式）
        
        # 编辑工具选择
        self._current_tool = None  # 当前工具：'point', 'line', 'curve', 'plane' 或 None
        self._tool_buttons = {}  # 存储工具按钮引用
        
        # 物体模式操作工具选择
        self._current_object_tool = None  # 当前物体操作工具：'select', 'box_select', 'translate', 'scale', 'rotate' 或 None
        self._object_tool_buttons = {}  # 存储物体操作工具按钮引用
        
        # 鼠标交互状态
        self._last_mouse_pos = None
        self._is_rotating = False
        self._is_panning = False
        self._is_zooming = False
        
        # 初始化摄像机
        CameraController.setup_camera(self)
        
        # 绘制建模空间边界框
        self._draw_workspace_bounds()
        
        # 初始化网格和坐标轴（默认不显示）
        self._update_grid()
        self._update_origin_axes()
        # 创建模式切换和工具选择工具栏
        self._mode_toolbar = ModeToolbar(self)

        # 保留这些状态变量（用于向后兼容）
        self._current_mode = self._mode_toolbar.get_current_mode()
        self._current_tool = None
        self._current_object_tool = None
        
        # 创建编辑模式管理器
        self._edit_mode_manager = EditModeManager()
        
        # 创建点操作器
        self._point_operator = PointOperator(self._edit_mode_manager)
        # 创建线操作器
        self._line_operator = LineOperator(self._edit_mode_manager)
        # 创建面操作器
        self._plane_operator = PlaneOperator(self._edit_mode_manager)
        # 创建颜色选择器
        self._color_selector = ColorSelector(self._edit_mode_manager)

        # 初始化边界几何（不可操作，仅可选）
        self._init_boundary_geometry()
        
        # 创建左下角坐标显示标签
        self._coord_label = QLabel(self)
        self._coord_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 200); "
            "border: 1px solid gray; "
            "padding: 3px; "
            "border-radius: 3px;"
        )
        self._coord_label.setFont(QFont('Arial', 9))
        self._coord_label.setText("X: --, Y: --, Z: --")
        self._coord_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._coord_label.hide()  # 初始隐藏，鼠标移动时显示
        self._update_coord_label_position()
    
    # ========== 工作空间相关方法 ==========
    
    def _calculate_workspace_center(self) -> np.ndarray:
        """计算建模空间中心点"""
        return calculate_workspace_center(self.workspace_bounds)
    
    def _calculate_initial_distance(self) -> float:
        """计算初始摄像机距离"""
        return calculate_initial_camera_distance(self.workspace_bounds)
    
    def set_workspace_bounds(self, bounds: np.ndarray):
        """
        设置工作空间边界
        
        Parameters:
        -----------
        bounds : np.ndarray
            新的边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        """
        self.workspace_bounds = np.array(bounds, dtype=np.float64)
        
        # 重新计算轨道中心
        self._orbit_center = self._calculate_workspace_center()
        
        # 重新计算初始距离
        initial_distance = self._calculate_initial_distance()
        
        # 如果当前距离小于新的初始距离，则更新
        camera = self.renderer.GetActiveCamera()
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        current_distance = np.linalg.norm(position - center)
        
        if current_distance < initial_distance:
            self._camera_distance = initial_distance
            # 更新摄像机位置
            direction = position - center
            if np.linalg.norm(direction) > 1e-6:
                direction_normalized = direction / np.linalg.norm(direction)
                new_position = self._orbit_center + direction_normalized * initial_distance
                camera.SetPosition(new_position)
                camera.SetFocalPoint(self._orbit_center)
        
        # 移除旧的边界框（如果存在）
        if hasattr(self, '_workspace_bounds_actor'):
            for actor in self._workspace_bounds_actor:
                try:
                    self.remove_actor(actor)
                except:
                    pass
            self._workspace_bounds_actor = []
        
        # 重新绘制边界框
        self._draw_workspace_bounds()
        
        # 更新网格和坐标轴（如果已显示）
        if self._show_grid:
            self._update_grid()
        if self._show_origin_axes:
            self._update_origin_axes()
        
        # 更新坐标标签位置
        if hasattr(self, '_coord_label'):
            self._update_coord_label_position()
        
        self.render()
        self.view_changed.emit()

    def _init_boundary_geometry(self):
        """初始化边界点/线/面为锁定对象（仅可选不可操作）"""
        bounds = self.workspace_bounds
        x_min, x_max = bounds[0], bounds[1]
        y_min, y_max = bounds[2], bounds[3]
        z_min, z_max = bounds[4], bounds[5]

        # 8 个顶点
        corners = np.array([
            [x_min, y_min, z_min],
            [x_max, y_min, z_min],
            [x_max, y_max, z_min],
            [x_min, y_max, z_min],
            [x_min, y_min, z_max],
            [x_max, y_min, z_max],
            [x_max, y_max, z_max],
            [x_min, y_max, z_max],
        ])
        for i, pos in enumerate(corners):
            # 边界点只作为数据存在，不渲染
            self._edit_mode_manager.add_point(f"boundary_point_{i}", pos, view=None, locked=True)

        # 12 条边
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # 底面
            (4, 5), (5, 6), (6, 7), (7, 4),  # 顶面
            (0, 4), (1, 5), (2, 6), (3, 7)   # 垂直边
        ]
        for idx, (a, b) in enumerate(edges):
            # 边界线只作为数据存在，不渲染
            self._edit_mode_manager.add_line(
                f"boundary_line_{idx}",
                corners[a],
                corners[b],
                view=None,
                locked=True
            )

        # 6 个面（保持透明，可选不可编辑）
        faces = [
            [0, 1, 2, 3],  # bottom z_min
            [4, 5, 6, 7],  # top z_max
            [0, 1, 5, 4],  # front y_min
            [1, 2, 6, 5],  # right x_max
            [2, 3, 7, 6],  # back y_max
            [3, 0, 4, 7],  # left x_min
        ]
        for idx, verts_idx in enumerate(faces):
            verts = corners[verts_idx]
            plane_id = f"boundary_plane_{idx}"
            # 浅灰色透明（只作为数据存在，不渲染）
            color = (0.9, 0.9, 0.9)
            self._edit_mode_manager.add_plane(
                plane_id,
                verts,
                view=None,
                color=color,
                locked=True
            )
    
    def get_workspace_bounds(self) -> np.ndarray:
        """
        获取当前工作空间边界
        
        Returns:
        --------
        np.ndarray
            边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        """
        return self.workspace_bounds.copy()
    
    def _draw_workspace_bounds(self):
        """绘制建模空间边界框"""
        bounds = self.workspace_bounds
        
        # 创建边界框网格
        lines_mesh = create_workspace_bounds_mesh(bounds)
        
        # 添加到场景（使用淡灰色，半透明）
        actor = self.add_mesh(
            lines_mesh,
            color='lightgray',
            line_width=1.0,
            opacity=0.3,
            name='workspace_bounds'
        )
        # 边界框仅用于视觉参考，禁止拾取，避免阻挡编辑点选/拖拽
        try:
            actor.PickableOff()
        except Exception:
            try:
                actor.SetPickable(False)
            except Exception:
                pass
        # 存储actor引用以便后续移除
        if not hasattr(self, '_workspace_bounds_actor'):
            self._workspace_bounds_actor = []
        self._workspace_bounds_actor.append(actor)
    
    # ========== 投影模式控制 ==========
    
    def set_projection_mode(self, orthographic: bool):
        """
        设置投影模式
        
        Parameters:
        -----------
        orthographic : bool
            True=正交投影，False=透视投影
        """
        self._is_orthographic = orthographic
        camera = self.renderer.GetActiveCamera()
        camera.SetParallelProjection(orthographic)
        self.render()
        self.view_changed.emit()
    
    def get_projection_mode(self) -> bool:
        """
        获取当前投影模式
        
        Returns:
        --------
        bool
            True=正交投影，False=透视投影
        """
        return self._is_orthographic
    
    def toggle_projection_mode(self):
        """切换投影模式"""
        self.set_projection_mode(not self._is_orthographic)
    
    # ========== 快速视角切换 ==========
    
    def set_view(self, view_name: str):
        """
        设置快速视角
        
        Parameters:
        -----------
        view_name : str
            视角名称，可选值：
            - 'front': 前视图（+Y方向）
            - 'back': 后视图（-Y方向）
            - 'top': 俯视图（+Z方向，北向）
            - 'bottom': 底视图（-Z方向）
            - 'left': 左视图（-X方向）
            - 'right': 右视图（+X方向）
            - 'iso': 等轴测视图（默认）
        """
        CameraController.set_view(self, view_name)
    
    def reset_camera(self):
        """重置摄像机到初始位置"""
        CameraController.setup_camera(self)
        self.view_changed.emit()
    
    # ========== 网格和坐标轴控制 ==========
    
    def set_show_grid(self, show: bool):
        """
        设置是否显示网格
        
        Parameters:
        -----------
        show : bool
            True=显示网格，False=隐藏网格
        """
        self._show_grid = show
        self._update_grid()
        self.render()
        self.view_changed.emit()
    
    def get_show_grid(self) -> bool:
        """
        获取网格显示状态
        
        Returns:
        --------
        bool
            True=显示，False=隐藏
        """
        return self._show_grid
    
    def toggle_grid(self):
        """切换网格显示状态"""
        self.set_show_grid(not self._show_grid)
    
    def set_grid_spacing(self, spacing: float):
        """
        设置网格间距
        
        Parameters:
        -----------
        spacing : float
            网格间距
        """
        if spacing <= 0:
            raise ValueError("网格间距必须大于0")
        self._grid_spacing = spacing
        if self._show_grid:
            self._update_grid()
            self.render()
            self.view_changed.emit()
    
    def get_grid_spacing(self) -> float:
        """获取网格间距"""
        return self._grid_spacing
    
    def _update_grid(self):
        """更新网格显示"""
        # 移除旧的网格
        if self._grid_actor is not None:
            try:
                self.remove_actor(self._grid_actor)
            except:
                pass
            self._grid_actor = None
        
        # 如果显示网格，创建新的网格
        if self._show_grid:
            grid_mesh = create_grid_mesh(self.workspace_bounds, self._grid_spacing, z=0.0)
            self._grid_actor = self.add_mesh(
                grid_mesh,
                color='lightgray',
                line_width=0.5,
                opacity=0.5,
                name='grid'
            )
            # 网格只作参考，禁用拾取
            try:
                self._grid_actor.PickableOff()
            except Exception:
                try:
                    self._grid_actor.SetPickable(False)
                except Exception:
                    pass
    
    def set_show_origin_axes(self, show: bool):
        """
        设置是否显示原点坐标轴
        
        Parameters:
        -----------
        show : bool
            True=显示坐标轴，False=隐藏坐标轴
        """
        self._show_origin_axes = show
        self._update_origin_axes()
        self.render()
        self.view_changed.emit()
    
    def get_show_origin_axes(self) -> bool:
        """
        获取原点坐标轴显示状态
        
        Returns:
        --------
        bool
            True=显示，False=隐藏
        """
        return self._show_origin_axes
    
    def toggle_origin_axes(self):
        """切换原点坐标轴显示状态"""
        self.set_show_origin_axes(not self._show_origin_axes)
    
    def _update_origin_axes(self):
        """更新原点坐标轴显示"""
        # 移除旧的坐标轴
        if self._origin_axes_actor is not None:
            try:
                # 如果是列表，分别移除每个actor
                if isinstance(self._origin_axes_actor, list):
                    for actor in self._origin_axes_actor:
                        try:
                            self.remove_actor(actor)
                        except:
                            pass
                else:
                    self.remove_actor(self._origin_axes_actor)
            except:
                pass
            self._origin_axes_actor = None
        
        # 如果显示坐标轴，创建新的坐标轴
        if self._show_origin_axes:
            axes_mesh = create_origin_axes_mesh(self.workspace_bounds)
            # X轴用红色，Y轴用绿色
            # 由于PolyData不支持不同颜色，我们分别创建两个actor
            # X轴
            x_axis_vertices = np.array([
                [0.0, 0.0, 0.0],
                axes_mesh.points[1]  # X轴端点
            ])
            x_axis_mesh = pv.PolyData(x_axis_vertices)
            x_axis_mesh.lines = np.array([2, 0, 1], dtype=np.int32)
            
            # Y轴
            y_axis_vertices = np.array([
                [0.0, 0.0, 0.0],
                axes_mesh.points[2]  # Y轴端点
            ])
            y_axis_mesh = pv.PolyData(y_axis_vertices)
            y_axis_mesh.lines = np.array([2, 0, 1], dtype=np.int32)
            
            # 添加X轴（红色）
            x_actor = self.add_mesh(
                x_axis_mesh,
                color='red',
                line_width=2.0,
                name='origin_axis_x'
            )
            try:
                x_actor.PickableOff()
            except Exception:
                try:
                    x_actor.SetPickable(False)
                except Exception:
                    pass
            
            # 添加Y轴（绿色）
            y_actor = self.add_mesh(
                y_axis_mesh,
                color='green',
                line_width=2.0,
                name='origin_axis_y'
            )
            try:
                y_actor.PickableOff()
            except Exception:
                try:
                    y_actor.SetPickable(False)
                except Exception:
                    pass
            
            # 存储两个actor（使用列表）
            self._origin_axes_actor = [x_actor, y_actor]
    # ========== 坐标显示 ==========
    
    def _update_coord_label_position(self):
        """更新坐标标签位置（左下角）"""
        if hasattr(self, '_coord_label') and self._coord_label:
            margin = 10
            label_width = 200
            label_height = 25
            self._coord_label.setGeometry(
                margin,
                self.height() - label_height - margin,
                label_width,
                label_height
            )
    
    def _update_coordinate_display(self, screen_pos: QPoint):
        """更新坐标显示"""
        if not hasattr(self, '_coord_label'):
            return
        # 使用射线投射获取鼠标指向的世界坐标
        world_pos = CoordinateConverter.screen_to_world_raycast(self, screen_pos)
        if world_pos is not None:
            self._coord_label.setText(
                f"X: {world_pos[0]:.1f}, Y: {world_pos[1]:.1f}, Z: {world_pos[2]:.1f}"
            )
            self._coord_label.show()
        else:
            self._coord_label.setText("X: --, Y: --, Z: --")
    
    # ========== 摄像机控制公共 API ==========
    
    def get_camera_info(self) -> dict:
        """获取当前摄像机信息"""
        return CameraController.get_camera_info(self)
    
    def set_camera_info(self, camera_info: dict):
        """设置摄像机信息"""
        CameraController.set_camera_info(self, camera_info)
    
    # ========== Qt 事件处理方法 ==========
    # 这些方法必须保留，因为它们是 Qt 的事件处理接口
    # 内部直接调用 EventHandler 的静态方法
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        EventHandler.mouse_press_event(self, event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        EventHandler.mouse_move_event(self, event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        EventHandler.mouse_release_event(self, event)
    
    def wheelEvent(self, event):
        """滚轮事件（缩放）"""
        EventHandler.wheel_event(self, event)
    
    def keyPressEvent(self, event):
        """键盘事件处理"""
        EventHandler.key_press_event(self, event)

    def get_current_mode(self) -> str:
        """获取当前模式"""
        return self._mode_toolbar.get_current_mode()
    
    def set_mode(self, mode: str):
        """设置模式"""
        self._mode_toolbar.set_mode(mode)
    
    def get_current_tool(self) -> Optional[str]:
        """获取当前选择的工具"""
        return self._mode_toolbar.get_current_tool()
    
    def set_tool(self, tool_id: Optional[str]):
        """设置工具"""
        self._mode_toolbar.set_tool(tool_id)
    
    def get_current_object_tool(self) -> Optional[str]:
        """获取当前选择的物体操作工具"""
        return self._mode_toolbar.get_current_object_tool()
    
    def set_object_tool(self, tool_id: Optional[str]):
        """设置物体操作工具"""
        self._mode_toolbar.set_object_tool(tool_id)
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        if hasattr(self, '_coord_label'):
            self._update_coord_label_position()
        if hasattr(self, '_mode_toolbar'):
            self._mode_toolbar.update_positions()

