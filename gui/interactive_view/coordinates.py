"""
坐标转换相关方法
"""
from PyQt5.QtCore import QPoint
import numpy as np
from typing import Optional


class CoordinateConverter:
    """坐标转换器 - 用于屏幕坐标到世界坐标的转换"""
    
    @staticmethod
    def screen_to_world_raycast(view, screen_pos: QPoint) -> Optional[np.ndarray]:
        """
        使用射线投射获取鼠标指向的世界坐标（与场景的交点）
        
        Parameters:
        -----------
        view : InteractiveView
            交互式视图实例
        screen_pos : QPoint
            屏幕坐标（像素）
            
        Returns:
        --------
        np.ndarray or None
            世界坐标 [x, y, z]，如果转换失败返回None
        """
        try:
            # 使用PyVista的pick功能进行射线投射
            # 获取屏幕坐标（VTK坐标系）
            width = view.width()
            height = view.height()
            vtk_x = screen_pos.x()
            vtk_y = height - screen_pos.y() - 1
            
            # 使用PyVista的pick方法进行射线投射
            # 这会返回鼠标指向的第一个actor的交点
            try:
                picked = view.pick_mouse_position()
                if picked and hasattr(picked, 'point'):
                    return np.array(picked.point)
            except:
                # 如果pick_mouse_position不可用，尝试使用VTK的WorldPointPicker
                try:
                    from vtkmodules.vtkRenderingCore import vtkWorldPointPicker
                    world_picker = vtkWorldPointPicker()
                    world_picker.Pick(vtk_x, vtk_y, 0, view.renderer)
                    picked_pos = world_picker.GetPickPosition()
                    if picked_pos and any(abs(p) > 1e-6 for p in picked_pos):
                        return np.array(picked_pos)
                except:
                    pass
            
            # 如果没有击中任何物体，使用焦点平面的坐标
            return CoordinateConverter.screen_to_world(
                view, screen_pos, depth=0.0, clip_to_bounds=False
            )
        except Exception as e:
            # 如果出错，使用简单的屏幕到世界坐标转换
            return CoordinateConverter.screen_to_world(
                view, screen_pos, depth=0.0, clip_to_bounds=False
            )
    
    @staticmethod
    def screen_to_world(view, screen_pos: QPoint, depth: float = 0.0, clip_to_bounds: bool = True) -> Optional[np.ndarray]:
        """
        将屏幕坐标转换为世界坐标
        
        Parameters:
        -----------
        view : InteractiveView
            交互式视图实例
        screen_pos : QPoint
            屏幕坐标（像素）
        depth : float
            深度值（0.0表示在焦点平面上，正值表示远离相机）
        clip_to_bounds : bool
            是否限制坐标在工作空间边界内，默认True
            
        Returns:
        --------
        np.ndarray or None
            世界坐标 [x, y, z]，如果转换失败返回None
        """
        try:
            # 获取渲染器
            renderer = view.renderer
            
            # 获取屏幕尺寸
            width = view.width()
            height = view.height()
            
            # 将Qt坐标转换为VTK坐标（Y轴翻转）
            vtk_x = screen_pos.x()
            vtk_y = height - screen_pos.y() - 1
            
            # 使用VTK的屏幕到世界坐标转换
            # 首先获取焦点平面的点
            world_pos = [0.0, 0.0, 0.0]
            renderer.SetDisplayPoint(vtk_x, vtk_y, depth)
            renderer.DisplayToWorld()
            world_pos = renderer.GetWorldPoint()
            
            if world_pos[3] != 0.0:
                # 齐次坐标转换为3D坐标
                world_pos = np.array([
                    world_pos[0] / world_pos[3],
                    world_pos[1] / world_pos[3],
                    world_pos[2] / world_pos[3]
                ])
                
                # 如果启用限制，将坐标限制在工作空间内部（包含边界）
                if clip_to_bounds:
                    # 限制X坐标在空间内部（包含边界）
                    world_pos[0] = np.clip(world_pos[0], 
                                         view.workspace_bounds[0], 
                                         view.workspace_bounds[1])
                    # 限制Y坐标在空间内部（包含边界）
                    world_pos[1] = np.clip(world_pos[1], 
                                         view.workspace_bounds[2], 
                                         view.workspace_bounds[3])
                    # 限制Z坐标在空间内部（包含边界）
                    world_pos[2] = np.clip(world_pos[2], 
                                         view.workspace_bounds[4], 
                                         view.workspace_bounds[5])
                
                return world_pos
            else:
                return None
        except Exception as e:
            print(f"屏幕坐标转换失败: {e}")
            return None

