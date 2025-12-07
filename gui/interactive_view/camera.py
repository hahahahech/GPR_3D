"""
摄像机控制相关方法
"""
from PyQt5.QtCore import QPoint
import numpy as np


class CameraController:
    """摄像机控制器 - 处理旋转、平移、缩放等操作"""
    
    @staticmethod
    def setup_camera(view):
        """设置轨道摄像机"""
        # 设置摄像机位置（从斜上方看向中心）
        camera = view.renderer.GetActiveCamera()
        
        # 计算初始摄像机位置（等距投影）
        center = view._orbit_center
        distance = view._camera_distance
        
        # 默认视角：从(1, 1, 1)方向看向中心
        direction = np.array([1.0, 1.0, 0.5])
        direction = direction / np.linalg.norm(direction)
        
        camera_pos = center + direction * distance
        
        camera.SetPosition(camera_pos)
        camera.SetFocalPoint(center)
        camera.SetViewUp(0, 0, 1)  # Z轴向上
        
        # 设置投影模式
        camera.SetParallelProjection(view._is_orthographic)
        
        view.render()
    
    @staticmethod
    def handle_rotation(view, delta: QPoint):
        """处理旋转操作 - 使用球面坐标系"""
        camera = view.renderer.GetActiveCamera()
        
        # 获取当前摄像机参数
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        view_up = np.array(camera.GetViewUp())
        
        # 计算从中心到相机的方向向量
        direction = position - center
        distance = np.linalg.norm(direction)
        
        if distance < 1e-6:
            return  # 避免除零错误
        
        # 归一化方向向量
        direction_normalized = direction / distance
        
        # ========== 使用球面坐标系计算当前角度 ==========
        # 计算当前方位角（在XY平面上的角度，0-2π）
        # azimuth = atan2(y, x)
        current_azimuth = np.arctan2(direction[1], direction[0])
        
        # 计算当前仰角（与XY平面的夹角，-π/2到π/2）
        # elevation = arcsin(z / distance)
        current_elevation = np.arcsin(np.clip(direction[2] / distance, -1.0, 1.0))
        
        # ========== 计算旋转增量 ==========
        rotation_sensitivity = 0.5  # 旋转灵敏度（度/像素）
        azimuth_delta = -delta.x() * rotation_sensitivity  # 水平旋转（左右：向右拖相机向右转）
        elevation_delta = delta.y() * rotation_sensitivity  # 垂直旋转（上下：向上拖相机向上看，注意屏幕Y向下）
        
        # ========== 应用旋转 ==========
        # 更新方位角
        new_azimuth = current_azimuth + np.radians(azimuth_delta)
        
        # 更新仰角（限制在-85°到85°之间，避免翻转）
        max_elevation = np.radians(85)
        new_elevation = np.clip(
            current_elevation + np.radians(elevation_delta),
            -max_elevation,
            max_elevation
        )
        
        # ========== 从球面坐标计算新的笛卡尔坐标 ==========
        # 球面坐标转笛卡尔坐标：
        # x = distance * cos(elevation) * cos(azimuth)
        # y = distance * cos(elevation) * sin(azimuth)
        # z = distance * sin(elevation)
        cos_elevation = np.cos(new_elevation)
        new_direction = np.array([
            distance * cos_elevation * np.cos(new_azimuth),
            distance * cos_elevation * np.sin(new_azimuth),
            distance * np.sin(new_elevation)
        ])
        
        # 计算新位置
        new_position = center + new_direction
        
        # ========== 更新摄像机 ==========
        camera.SetPosition(new_position)
        camera.SetFocalPoint(center)
        
        # ========== 更新view_up向量（保持相机不翻转）==========
        # 使用世界坐标的上向量（0,0,1）作为参考
        world_up = np.array([0.0, 0.0, 1.0])
        new_direction_normalized = new_direction / distance
        
        # 计算右向量（相机坐标系的右方向）
        right = np.cross(new_direction_normalized, world_up)
        right_norm = np.linalg.norm(right)
        
        if right_norm < 1e-6:
            # 如果相机方向与world_up平行（几乎垂直），使用默认右向量
            right = np.array([1.0, 0.0, 0.0])
        else:
            right = right / right_norm
        
        # 计算新的上向量（垂直于视线方向，尽量接近world_up）
        new_view_up = np.cross(right, new_direction_normalized)
        new_view_up = new_view_up / np.linalg.norm(new_view_up)
        
        camera.SetViewUp(new_view_up)
        
        view.render()
    
    @staticmethod
    def handle_pan(view, delta: QPoint):
        """处理平移操作"""
        camera = view.renderer.GetActiveCamera()
        
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
        window_size = view.size()
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
        view._orbit_center = new_center
        
        view.render()
    
    @staticmethod
    def handle_zoom_wheel(view, zoom_factor: float):
        """处理滚轮缩放"""
        camera = view.renderer.GetActiveCamera()
        
        center = np.array(camera.GetFocalPoint())
        position = np.array(camera.GetPosition())
        
        # 计算当前距离
        direction = position - center
        distance = np.linalg.norm(direction)
        
        # 计算初始距离（基于当前工作空间）
        initial_distance = view._calculate_initial_distance()
        
        # 应用缩放
        new_distance = distance / zoom_factor
        
        # 限制最小和最大距离
        # 最小距离：初始距离的一半（不能缩小到一半以下）
        min_distance = initial_distance * 0.5
        max_distance = initial_distance * 5.0
        new_distance = np.clip(new_distance, min_distance, max_distance)
        
        # 更新摄像机位置
        direction_normalized = direction / distance
        new_position = center + direction_normalized * new_distance
        
        camera.SetPosition(new_position)
        view._camera_distance = new_distance
        
        view.render()
    
    @staticmethod
    def handle_zoom_drag(view, delta: QPoint):
        """处理拖拽缩放（Alt + 右键）"""
        # 垂直移动控制缩放
        zoom_sensitivity = 0.01
        zoom_factor = 1.0 - delta.y() * zoom_sensitivity
        
        CameraController.handle_zoom_wheel(view, zoom_factor)
    
    @staticmethod
    def get_camera_info(view) -> dict:
        """获取当前摄像机信息"""
        camera = view.renderer.GetActiveCamera()
        return {
            'position': np.array(camera.GetPosition()),
            'focal_point': np.array(camera.GetFocalPoint()),
            'view_up': np.array(camera.GetViewUp()),
            'distance': view._camera_distance,
            'orbit_center': view._orbit_center.copy()
        }
    
    @staticmethod
    def set_camera_info(view, camera_info: dict):
        """设置摄像机信息"""
        camera = view.renderer.GetActiveCamera()
        camera.SetPosition(camera_info['position'])
        camera.SetFocalPoint(camera_info['focal_point'])
        camera.SetViewUp(camera_info['view_up'])
        view._camera_distance = camera_info.get('distance', view._camera_distance)
        view._orbit_center = camera_info.get('orbit_center', view._orbit_center)
        view.render()
        view.view_changed.emit()
    
    @staticmethod
    def set_view(view, view_name: str):
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
        camera = view.renderer.GetActiveCamera()
        center = view._orbit_center
        distance = view._camera_distance
        
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
        view._orbit_center = center
        
        view.render()
        view.view_changed.emit()

