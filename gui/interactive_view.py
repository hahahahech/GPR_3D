"""
交互式建模视图核心类
实现轨道摄像机控制和用户交互
"""
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from pyvistaqt import QtInteractor
import pyvista as pv
import numpy as np
from typing import Optional, Tuple


class InteractiveView(QtInteractor):
    """交互式建模视图 - 实现轨道摄像机控制"""
    
    # 信号定义
    view_changed = pyqtSignal()  # 视图改变时发出信号
    
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
            self.workspace_bounds = np.array([-100.0, 100.0, -100.0, 100.0, -50.0, 0.0])
        else:
            self.workspace_bounds = np.array(workspace_bounds, dtype=np.float64)
        
        # 轨道摄像机参数
        self._orbit_center = self._calculate_workspace_center()
        self._camera_distance = self._calculate_initial_distance()
        
        # 投影模式：True=正交投影，False=透视投影
        self._is_orthographic = False
        
        # 鼠标交互状态
        self._last_mouse_pos = None
        self._is_rotating = False
        self._is_panning = False
        self._is_zooming = False
        
        # 初始化摄像机
        self._setup_camera()
        
        # 绘制建模空间边界框
        self._draw_workspace_bounds()
        
        # View Cube 将使用2D坐标轴实现，在GUI层创建
        
    def _calculate_workspace_center(self) -> np.ndarray:
        """计算建模空间中心点"""
        return np.array([
            (self.workspace_bounds[0] + self.workspace_bounds[1]) / 2.0,
            (self.workspace_bounds[2] + self.workspace_bounds[3]) / 2.0,
            (self.workspace_bounds[4] + self.workspace_bounds[5]) / 2.0
        ])
    
    def _calculate_initial_distance(self) -> float:
        """计算初始摄像机距离"""
        # 计算空间对角线长度
        dx = self.workspace_bounds[1] - self.workspace_bounds[0]
        dy = self.workspace_bounds[3] - self.workspace_bounds[2]
        dz = self.workspace_bounds[5] - self.workspace_bounds[4]
        diagonal = np.sqrt(dx**2 + dy**2 + dz**2)
        # 距离设为对角线的1.5倍，确保能看到整个空间
        return diagonal * 1.5
    
    def _setup_camera(self):
        """设置轨道摄像机"""
        # 设置摄像机位置（从斜上方看向中心）
        camera = self.renderer.GetActiveCamera()
        
        # 计算初始摄像机位置（等距投影）
        center = self._orbit_center
        distance = self._camera_distance
        
        # 默认视角：从(1, 1, 1)方向看向中心
        direction = np.array([1.0, 1.0, 0.5])
        direction = direction / np.linalg.norm(direction)
        
        camera_pos = center + direction * distance
        
        camera.SetPosition(camera_pos)
        camera.SetFocalPoint(center)
        camera.SetViewUp(0, 0, 1)  # Z轴向上
        
        # 设置投影模式
        camera.SetParallelProjection(self._is_orthographic)
        
        self.render()
    
    def _draw_workspace_bounds(self):
        """绘制建模空间边界框"""
        bounds = self.workspace_bounds
        
        # 创建边界框的8个顶点
        x_min, x_max = bounds[0], bounds[1]
        y_min, y_max = bounds[2], bounds[3]
        z_min, z_max = bounds[4], bounds[5]
        
        vertices = np.array([
            [x_min, y_min, z_min],  # 0
            [x_max, y_min, z_min],  # 1
            [x_max, y_max, z_min],  # 2
            [x_min, y_max, z_min],  # 3
            [x_min, y_min, z_max],  # 4
            [x_max, y_min, z_max],  # 5
            [x_max, y_max, z_max],  # 6
            [x_min, y_max, z_max],  # 7
        ])
        
        # 定义12条边（立方体的12条边）
        edges = np.array([
            [0, 1], [1, 2], [2, 3], [3, 0],  # 底面
            [4, 5], [5, 6], [6, 7], [7, 4],  # 顶面
            [0, 4], [1, 5], [2, 6], [3, 7],  # 垂直边
        ])
        
        # 创建线框 - 使用PolyData格式
        # PyVista的lines格式: [n_points, p0, p1, p2, ..., n_points, p0, p1, ...]
        lines_array = []
        for edge in edges:
            lines_array.append(2)  # 每条边有2个点
            lines_array.append(int(edge[0]))
            lines_array.append(int(edge[1]))
        
        # 创建PolyData对象
        lines_mesh = pv.PolyData(vertices)
        lines_mesh.lines = np.array(lines_array, dtype=np.int32)
        
        # 添加到场景（使用淡灰色，半透明）
        actor = self.add_mesh(
            lines_mesh,
            color='lightgray',
            line_width=1.0,
            opacity=0.3,
            name='workspace_bounds'
        )
        # 存储actor引用以便后续移除
        if not hasattr(self, '_workspace_bounds_actor'):
            self._workspace_bounds_actor = []
        self._workspace_bounds_actor.append(actor)
        
        # 不添加坐标轴（使用View Cube代替）
    
    def set_workspace_bounds(self, bounds: np.ndarray):
        """
        设置建模空间边界
        
        Parameters:
        -----------
        bounds : np.ndarray
            边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        """
        self.workspace_bounds = np.array(bounds, dtype=np.float64)
        self._orbit_center = self._calculate_workspace_center()
        self._camera_distance = self._calculate_initial_distance()
        
        # 移除旧的边界框（如果存在）
        if hasattr(self, '_workspace_bounds_actor'):
            for actor in self._workspace_bounds_actor:
                try:
                    self.remove_actor(actor)
                except:
                    pass
            self._workspace_bounds_actor = []
        
        # 重新绘制边界框和设置摄像机
        self._draw_workspace_bounds()
        self._setup_camera()
        self.render()
    
    def get_workspace_bounds(self) -> np.ndarray:
        """获取建模空间边界"""
        return self.workspace_bounds.copy()
    
    def reset_camera(self):
        """重置摄像机到初始位置"""
        self._setup_camera()
        self.view_changed.emit()
    
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
    
    # ========== View Cube (已移除，将使用2D坐标轴实现) ==========
    # View Cube 现在将使用2D坐标轴在GUI层实现
    
    def _setup_view_cube(self):
        """设置3D View Cube - 跟随相机旋转"""
        if not self._view_cube_enabled:
            return
        
        # 计算View Cube的位置（场景右上角）
        bounds = self.workspace_bounds
        scene_size = max(
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4]
        )
        cube_size = scene_size * 0.08  # View Cube大小为场景的8%
        
        # 计算View Cube位置（场景右上角，稍微偏移以避免与边界重叠）
        offset = cube_size * 0.6
        cube_center = np.array([
            bounds[1] - offset,  # X: 右上角
            bounds[3] - offset,  # Y: 右上角
            bounds[5] - offset   # Z: 右上角
        ])
        
        # 所有面都使用灰白色
        gray_white = [220, 220, 220]  # 灰白色
        face_colors = {
            'front': gray_white,
            'back': gray_white,
            'right': gray_white,
            'left': gray_white,
            'top': gray_white,
            'bottom': gray_white,
        }
        
        # 创建6个面的mesh
        half_size = cube_size / 2
        faces_data = {
            'front': {
                'vertices': np.array([
                    [-half_size, half_size, -half_size],
                    [half_size, half_size, -half_size],
                    [half_size, half_size, half_size],
                    [-half_size, half_size, half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['front']
            },
            'back': {
                'vertices': np.array([
                    [half_size, -half_size, -half_size],
                    [-half_size, -half_size, -half_size],
                    [-half_size, -half_size, half_size],
                    [half_size, -half_size, half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['back']
            },
            'right': {
                'vertices': np.array([
                    [half_size, half_size, -half_size],
                    [half_size, -half_size, -half_size],
                    [half_size, -half_size, half_size],
                    [half_size, half_size, half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['right']
            },
            'left': {
                'vertices': np.array([
                    [-half_size, -half_size, -half_size],
                    [-half_size, half_size, -half_size],
                    [-half_size, half_size, half_size],
                    [-half_size, -half_size, half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['left']
            },
            'top': {
                'vertices': np.array([
                    [-half_size, half_size, half_size],
                    [half_size, half_size, half_size],
                    [half_size, -half_size, half_size],
                    [-half_size, -half_size, half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['top']
            },
            'bottom': {
                'vertices': np.array([
                    [-half_size, -half_size, -half_size],
                    [half_size, -half_size, -half_size],
                    [half_size, half_size, -half_size],
                    [-half_size, half_size, -half_size]
                ]),
                'faces': np.array([4, 0, 1, 2, 3]),
                'color': face_colors['bottom']
            },
        }
        
        # 存储View Cube的actors和中心位置
        self._view_cube_actors = {}
        self._view_cube_center = cube_center
        self._view_cube_size = cube_size
        
        # 为每个面创建mesh并添加到场景
        for face_name, face_info in faces_data.items():
            # 平移顶点到cube_center
            vertices = face_info['vertices'] + cube_center
            mesh = pv.PolyData(vertices, faces=face_info['faces'])
            
            actor = self.add_mesh(
                mesh,
                color=face_info['color'],
                show_edges=True,
                edge_color='black',
                line_width=2,
                opacity=0.9,
                name=f'view_cube_{face_name}',
                pickable=True
            )
            self._view_cube_actors[face_name] = actor
            
            # 添加标签（文字显示在面的中心）
            face_center = vertices.mean(axis=0)
            # 标签稍微突出于面，以便清晰可见
            label_offset = np.array([0, 0, 0])
            if face_name == 'front':
                label_offset = np.array([0, half_size * 0.4, 0])  # 向前突出
            elif face_name == 'back':
                label_offset = np.array([0, -half_size * 0.4, 0])  # 向后突出
            elif face_name == 'right':
                label_offset = np.array([half_size * 0.4, 0, 0])  # 向右突出
            elif face_name == 'left':
                label_offset = np.array([-half_size * 0.4, 0, 0])  # 向左突出
            elif face_name == 'top':
                label_offset = np.array([0, 0, half_size * 0.4])  # 向上突出
            elif face_name == 'bottom':
                label_offset = np.array([0, 0, -half_size * 0.4])  # 向下突出
            
            label_pos = face_center + label_offset
            labels = {'front': '前', 'back': '后', 'right': '右', 
                     'left': '左', 'top': '上', 'bottom': '下'}
            
            # 使用较大的字体和深色，确保文字清晰可见
            text_actor = self.add_text(
                labels[face_name],
                position=label_pos,
                font_size=int(cube_size * 0.2),
                color='black',
                shadow=True,
                name=f'view_cube_label_{face_name}'
            )
            if not hasattr(self, '_view_cube_labels'):
                self._view_cube_labels = []
            self._view_cube_labels.append(text_actor)
    
    def _update_view_cube_orientation(self):
        """更新View Cube的方向以跟随相机旋转"""
        if not self._view_cube_enabled or not hasattr(self, '_view_cube_actors') or not self._view_cube_actors:
            return
        
        # 获取当前相机信息
        camera = self.renderer.GetActiveCamera()
        focal_point = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        view_up = np.array(camera.GetViewUp())
        
        # 计算相机方向（从焦点指向相机）
        direction = position - focal_point
        distance = np.linalg.norm(direction)
        if distance < 1e-6:
            return
        direction = direction / distance
        
        # 计算右向量和上向量
        right = np.cross(direction, view_up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-6:
            # 如果方向与view_up平行，使用默认右向量
            right = np.array([1, 0, 0])
        else:
            right = right / right_norm
        
        up = np.cross(right, direction)
        up = up / np.linalg.norm(up)
        
        # 构建旋转矩阵：将View Cube从世界坐标系旋转到相机坐标系
        # 但我们希望View Cube保持世界坐标系方向，只是视觉上跟随相机
        # 实际上，View Cube应该保持固定方向，不旋转
        # 这里我们保持View Cube不变，因为它代表的是世界坐标系的方向
        
        # View Cube应该跟随相机旋转，显示当前视角方向
        # 通过旋转View Cube使其面向相机，这样可以看到当前视角
        # 计算旋转矩阵：将View Cube从默认方向旋转到面向相机
        
        # 默认View Cube方向：前(+Y)、右(+X)、上(+Z)
        # 计算需要旋转的角度，使View Cube面向相机
        
        # 使用VTK的Transform来旋转View Cube
        from vtk import vtkTransform
        
        # 计算从View Cube中心到相机的方向
        cube_to_camera = position - self._view_cube_center
        cube_to_camera_norm = np.linalg.norm(cube_to_camera)
        if cube_to_camera_norm < 1e-6:
            return
        
        cube_to_camera = cube_to_camera / cube_to_camera_norm
        
        # 计算旋转：使View Cube的"前"面（+Y方向）指向相机
        # 默认前方向是[0, 1, 0]
        default_front = np.array([0.0, 1.0, 0.0])
        target_direction = -cube_to_camera  # 相机看向View Cube的方向
        
        # 计算旋转轴和角度
        rotation_axis = np.cross(default_front, target_direction)
        axis_norm = np.linalg.norm(rotation_axis)
        
        if axis_norm > 1e-6:
            rotation_axis = rotation_axis / axis_norm
            dot_product = np.clip(np.dot(default_front, target_direction), -1.0, 1.0)
            rotation_angle = np.arccos(dot_product) * 180.0 / np.pi
            
            # 应用旋转到所有View Cube的actors
            transform = vtkTransform()
            transform.Translate(self._view_cube_center)
            transform.RotateWXYZ(rotation_angle, rotation_axis[0], rotation_axis[1], rotation_axis[2])
            transform.Translate(-self._view_cube_center)
            
            for face_name, actor in self._view_cube_actors.items():
                actor.SetUserTransform(transform)
                
            # 同时更新标签位置
            for label_actor in self._view_cube_labels:
                # 标签也需要跟随旋转，但保持面向相机
                pass  # 标签可以保持世界坐标，或者也应用旋转
    
    def set_view_cube_enabled(self, enabled: bool):
        """设置View Cube是否启用"""
        self._view_cube_enabled = enabled
        if not enabled:
            self._remove_view_cube()
        else:
            self._setup_view_cube()
        self.render()
    
    def _remove_view_cube(self):
        """移除View Cube"""
        if hasattr(self, '_view_cube_actors'):
            for face_name, actor in self._view_cube_actors.items():
                try:
                    self.remove_actor(actor)
                except:
                    pass
            self._view_cube_actors = {}
        
        if hasattr(self, '_view_cube_labels'):
            for label_actor in self._view_cube_labels:
                try:
                    self.remove_actor(label_actor)
                except:
                    pass
            self._view_cube_labels = []
    
    def _get_view_cube_face_at_position(self, screen_pos: QPoint) -> Optional[str]:
        """
        根据屏幕位置获取View Cube的面
        
        Parameters:
        -----------
        screen_pos : QPoint
            屏幕坐标位置
            
        Returns:
        --------
        Optional[str]
            面的名称（'front', 'back', 'right', 'left', 'top', 'bottom'）或None
        """
        if not self._view_cube_enabled or not hasattr(self, '_view_cube_actors'):
            return None
        
        # 使用PyVista的拾取功能
        try:
            # 使用pick来拾取actor
            picked_actors = []
            x, y = screen_pos.x(), screen_pos.y()
            
            # 遍历所有View Cube的actors，检查哪个被点击
            for face_name, actor in self._view_cube_actors.items():
                # 使用VTK的Picker来检查
                from vtk import vtkPropPicker
                picker = vtkPropPicker()
                if picker.Pick(x, y, 0, self.renderer):
                    picked_actor = picker.GetActor()
                    if picked_actor == actor:
                        return face_name
            
            # 备用方法：使用PyVista的pick方法
            try:
                picked = self.pick(x, y)
                if picked is not None:
                    # 检查picked的actor是否是View Cube的一部分
                    if hasattr(picked, 'actor'):
                        picked_actor = picked.actor
                        for face_name, actor in self._view_cube_actors.items():
                            if actor == picked_actor:
                                return face_name
            except:
                pass
            
            return None
            
        except Exception as e:
            # 如果拾取失败，返回None
            return None
    
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
        camera = self.renderer.GetActiveCamera()
        center = self._orbit_center
        distance = self._camera_distance
        
        # 定义各个视角的方向向量和上向量
        views = {
            'front': {
                'direction': np.array([0.0, 1.0, 0.0]),  # 从-Y看向+Y
                'view_up': np.array([0.0, 0.0, 1.0])     # Z轴向上
            },
            'back': {
                'direction': np.array([0.0, -1.0, 0.0]),  # 从+Y看向-Y
                'view_up': np.array([0.0, 0.0, 1.0])
            },
            'top': {
                'direction': np.array([0.0, 0.0, 1.0]),   # 从-Z看向+Z（俯视）
                'view_up': np.array([0.0, 1.0, 0.0])      # Y轴向上（北向）
            },
            'bottom': {
                'direction': np.array([0.0, 0.0, -1.0]),  # 从+Z看向-Z（仰视）
                'view_up': np.array([0.0, 1.0, 0.0])
            },
            'left': {
                'direction': np.array([-1.0, 0.0, 0.0]),  # 从+X看向-X
                'view_up': np.array([0.0, 0.0, 1.0])
            },
            'right': {
                'direction': np.array([1.0, 0.0, 0.0]),   # 从-X看向+X
                'view_up': np.array([0.0, 0.0, 1.0])
            },
            'iso': {
                'direction': np.array([1.0, 1.0, 0.5]),   # 等轴测视图
                'view_up': np.array([0.0, 0.0, 1.0])
            }
        }
        
        if view_name not in views:
            view_name = 'iso'  # 默认使用等轴测视图
        
        view_config = views[view_name]
        direction = view_config['direction']
        direction = direction / np.linalg.norm(direction)
        
        # 计算摄像机位置
        camera_pos = center - direction * distance
        
        # 设置摄像机
        camera.SetPosition(camera_pos)
        camera.SetFocalPoint(center)
        camera.SetViewUp(view_config['view_up'])
        
        # 更新轨道中心
        self._orbit_center = center
        
        self.render()
        self.view_changed.emit()
    
    # ========== 鼠标事件处理 ==========
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        self._last_mouse_pos = event.pos()
        
        # 检查按键组合
        modifiers = event.modifiers()
        button = event.button()
        
        if modifiers & Qt.AltModifier:
            if button == Qt.LeftButton:
                # Alt + 左键：旋转
                self._is_rotating = True
                self.setCursor(Qt.ClosedHandCursor)
            elif button == Qt.MidButton:
                # Alt + 中键：平移
                self._is_panning = True
                self.setCursor(Qt.SizeAllCursor)
            elif button == Qt.RightButton:
                # Alt + 右键：缩放
                self._is_zooming = True
                self.setCursor(Qt.SizeVerCursor)
        elif modifiers & Qt.ShiftModifier:
            if button == Qt.MidButton:
                # Shift + 中键：平移
                self._is_panning = True
                self.setCursor(Qt.SizeAllCursor)
        elif button == Qt.MidButton:
            # 单独中键：旋转（备用方案）
            self._is_rotating = True
            self.setCursor(Qt.ClosedHandCursor)
        
        # 调用父类方法以保持PyVista的默认行为（如果需要）
        # super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._last_mouse_pos is None:
            return
        
        current_pos = event.pos()
        delta = current_pos - self._last_mouse_pos
        
        if self._is_rotating:
            self._handle_rotation(delta)
        elif self._is_panning:
            self._handle_pan(delta)
        elif self._is_zooming:
            self._handle_zoom_drag(delta)
        
        self._last_mouse_pos = current_pos
        self.view_changed.emit()
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        self._is_rotating = False
        self._is_panning = False
        self._is_zooming = False
        self.setCursor(Qt.ArrowCursor)
        self._last_mouse_pos = None
    
    def wheelEvent(self, event):
        """滚轮事件（缩放）"""
        # 获取滚轮增量（通常为120的倍数）
        delta = event.angleDelta().y()
        
        # 缩放因子（正值放大，负值缩小）
        zoom_factor = 1.0 + (delta / 1200.0)  # 调整灵敏度
        
        self._handle_zoom_wheel(zoom_factor)
        self.view_changed.emit()
    
    # ========== 摄像机控制方法 ==========
    
    def _handle_rotation(self, delta: QPoint):
        """处理旋转操作"""
        camera = self.renderer.GetActiveCamera()
        
        # 获取当前摄像机参数
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        view_up = np.array(camera.GetViewUp())
        
        # 计算当前距离
        distance = np.linalg.norm(position - center)
        
        # 计算旋转角度（根据鼠标移动距离）
        # 将屏幕坐标转换为角度
        rotation_sensitivity = 0.5  # 旋转灵敏度
        
        # 水平旋转（绕Z轴）
        azimuth = -delta.x() * rotation_sensitivity
        
        # 垂直旋转（绕水平轴）
        elevation = -delta.y() * rotation_sensitivity
        
        # 应用旋转
        # 水平旋转：绕Z轴旋转
        if azimuth != 0:
            # 计算从中心到摄像机的方向向量
            direction = position - center
            direction_xy = direction[:2]
            length_xy = np.linalg.norm(direction_xy)
            
            if length_xy > 1e-6:
                # 计算当前方位角
                current_azimuth = np.arctan2(direction[1], direction[0])
                new_azimuth = current_azimuth + np.radians(azimuth)
                
                # 更新方向
                direction[0] = length_xy * np.cos(new_azimuth)
                direction[1] = length_xy * np.sin(new_azimuth)
                position = center + direction
        
        # 垂直旋转：限制在合理范围内（避免翻转）
        if elevation != 0:
            direction = position - center
            direction_xy = direction[:2]
            length_xy = np.linalg.norm(direction_xy)
            current_elevation = np.arcsin(direction[2] / np.linalg.norm(direction))
            
            # 限制仰角范围（-85度到85度）
            max_elevation = np.radians(85)
            new_elevation = np.clip(
                current_elevation + np.radians(elevation),
                -max_elevation,
                max_elevation
            )
            
            # 更新Z坐标
            direction[2] = distance * np.sin(new_elevation)
            length_xy = distance * np.cos(new_elevation)
            
            # 保持XY方向不变，只更新长度
            if length_xy > 1e-6:
                direction_xy_normalized = direction_xy / np.linalg.norm(direction_xy)
                direction[:2] = direction_xy_normalized * length_xy
            
            position = center + direction
        
        # 更新摄像机位置
        camera.SetPosition(position)
        camera.SetFocalPoint(center)
        
        # 更新view_up向量（保持Z轴向上）
        # 计算新的view_up，使其垂直于视线方向
        direction_normalized = (position - center) / np.linalg.norm(position - center)
        right = np.cross(direction_normalized, view_up)
        new_view_up = np.cross(right, direction_normalized)
        new_view_up = new_view_up / np.linalg.norm(new_view_up)
        camera.SetViewUp(new_view_up)
        
        self.render()
    
    def _handle_pan(self, delta: QPoint):
        """处理平移操作"""
        camera = self.renderer.GetActiveCamera()
        
        # 获取当前摄像机参数
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        view_up = np.array(camera.GetViewUp())
        
        # 计算摄像机坐标系
        direction = position - center
        distance = np.linalg.norm(direction)
        forward = -direction / distance  # 指向中心的方向
        
        # 计算右向量和上向量
        right = np.cross(forward, view_up)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)
        up = up / np.linalg.norm(up)
        
        # 计算平移距离（根据摄像机距离和窗口大小）
        window_size = self.size()
        pan_sensitivity = distance / min(window_size.width(), window_size.height()) * 2.0
        
        # 计算平移向量
        pan_x = -delta.x() * pan_sensitivity
        pan_y = delta.y() * pan_sensitivity
        
        # 应用平移
        new_center = center + right * pan_x + up * pan_y
        new_position = position + right * pan_x + up * pan_y
        
        # 更新摄像机
        camera.SetFocalPoint(new_center)
        camera.SetPosition(new_position)
        
        # 更新轨道中心
        self._orbit_center = new_center
        
        self.render()
    
    def _handle_zoom_wheel(self, zoom_factor: float):
        """处理滚轮缩放"""
        camera = self.renderer.GetActiveCamera()
        
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        
        # 计算当前距离
        direction = position - center
        distance = np.linalg.norm(direction)
        
        # 应用缩放
        new_distance = distance / zoom_factor
        
        # 限制最小和最大距离
        min_distance = self._camera_distance * 0.1
        max_distance = self._camera_distance * 5.0
        new_distance = np.clip(new_distance, min_distance, max_distance)
        
        # 更新摄像机位置
        direction_normalized = direction / distance
        new_position = center + direction_normalized * new_distance
        
        camera.SetPosition(new_position)
        self._camera_distance = new_distance
        
        self.render()
    
    def _handle_zoom_drag(self, delta: QPoint):
        """处理拖拽缩放（Alt + 右键）"""
        # 垂直移动控制缩放
        zoom_sensitivity = 0.01
        zoom_factor = 1.0 - delta.y() * zoom_sensitivity
        
        self._handle_zoom_wheel(zoom_factor)
    
    def get_camera_info(self) -> dict:
        """获取当前摄像机信息"""
        camera = self.renderer.GetActiveCamera()
        return {
            'position': np.array(camera.GetPosition()),
            'focal_point': np.array(camera.GetFocalPoint()),
            'view_up': np.array(camera.GetViewUp()),
            'distance': self._camera_distance,
            'orbit_center': self._orbit_center.copy()
        }
    
    def set_camera_info(self, camera_info: dict):
        """设置摄像机信息"""
        camera = self.renderer.GetActiveCamera()
        camera.SetPosition(camera_info['position'])
        camera.SetFocalPoint(camera_info['focal_point'])
        camera.SetViewUp(camera_info['view_up'])
        self._camera_distance = camera_info.get('distance', self._camera_distance)
        self._orbit_center = camera_info.get('orbit_center', self._orbit_center)
        self.render()
        self.view_changed.emit()



def create_workspace_bounds_mesh(bounds: np.ndarray):
    """
    创建建模空间边界框的网格对象
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    pyvista.PolyData
        边界框线框网格
    """
    import pyvista as pv
    
    x_min, x_max = bounds[0], bounds[1]
    y_min, y_max = bounds[2], bounds[3]
    z_min, z_max = bounds[4], bounds[5]
    
    # 创建边界框的8个顶点
    vertices = np.array([
        [x_min, y_min, z_min],  # 0
        [x_max, y_min, z_min],  # 1
        [x_max, y_max, z_min],  # 2
        [x_min, y_max, z_min],  # 3
        [x_min, y_min, z_max],  # 4
        [x_max, y_min, z_max],  # 5
        [x_max, y_max, z_max],  # 6
        [x_min, y_max, z_max],  # 7
    ])
    
    # 定义12条边（立方体的12条边）
    edges = np.array([
        [0, 1], [1, 2], [2, 3], [3, 0],  # 底面
        [4, 5], [5, 6], [6, 7], [7, 4],  # 顶面
        [0, 4], [1, 5], [2, 6], [3, 7],  # 垂直边
    ])
    
    # 创建线框 - 使用PolyData格式
    lines_array = []
    for edge in edges:
        lines_array.append(2)  # 每条边有2个点
        lines_array.append(int(edge[0]))
        lines_array.append(int(edge[1]))
    
    # 创建PolyData对象
    lines_mesh = pv.PolyData(vertices)
    lines_mesh.lines = np.array(lines_array, dtype=np.int32)
    
    return lines_mesh


def calculate_workspace_center(bounds: np.ndarray) -> np.ndarray:
    """
    计算建模空间中心点
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    np.ndarray
        中心点坐标 [x, y, z]
    """
    return np.array([
        (bounds[0] + bounds[1]) / 2.0,
        (bounds[2] + bounds[3]) / 2.0,
        (bounds[4] + bounds[5]) / 2.0
    ])


def calculate_initial_camera_distance(bounds: np.ndarray) -> float:
    """
    计算初始摄像机距离
    
    Parameters:
    -----------
    bounds : np.ndarray
        边界 [xmin, xmax, ymin, ymax, zmin, zmax]
        
    Returns:
    --------
    float
        建议的摄像机距离
    """
    # 计算空间对角线长度
    dx = bounds[1] - bounds[0]
    dy = bounds[3] - bounds[2]
    dz = bounds[5] - bounds[4]
    diagonal = np.sqrt(dx**2 + dy**2 + dz**2)
    # 距离设为对角线的1.5倍，确保能看到整个空间
    return diagonal * 1.5


def get_default_workspace_bounds() -> np.ndarray:
    """
    获取默认的建模空间边界
    
    Returns:
    --------
    np.ndarray
        默认边界 [xmin, xmax, ymin, ymax, zmin, zmax]
    """
    return np.array([-100.0, 100.0, -100.0, 100.0, -50.0, 0.0])
