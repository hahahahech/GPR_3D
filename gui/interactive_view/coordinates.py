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
        """使用射线投射获取鼠标指向的世界坐标（与场景的交点）"""
        try:
            # 使用PyVista的pick功能进行射线投射
            try:
                picked = view.pick_mouse_position()
                if picked and hasattr(picked, 'point'):
                    return np.array(picked.point)
            except:
                pass
            
            # 如果pick_mouse_position不可用，尝试使用VTK的WorldPointPicker
            try:
                from vtkmodules.vtkRenderingCore import vtkWorldPointPicker
                width = view.width()
                height = view.height()
                vtk_x = screen_pos.x()
                vtk_y = height - screen_pos.y() - 1
                world_picker = vtkWorldPointPicker()
                world_picker.Pick(vtk_x, vtk_y, 0, view.renderer)
                picked_pos = world_picker.GetPickPosition()
                if picked_pos and any(abs(p) > 1e-6 for p in picked_pos):
                    return np.array(picked_pos)
            except:
                pass
        except Exception:
            pass
    
    @staticmethod
    def screen_to_world(view, screen_pos: QPoint, depth: float = 0.0, clip_to_bounds: bool = True) -> Optional[np.ndarray]:
        """将屏幕坐标转换为世界坐标"""
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
    
    @staticmethod
    def screen_to_plane_relative(view, screen_pos: QPoint, plane_vertices: np.ndarray) -> Optional[np.ndarray]:
        """
        获取光标在选中平面中的相对位置（2D平面坐标）
        当视角移动到平面法线方向（正上方）后，将屏幕坐标投影到平面上，
        并返回在平面局部坐标系中的2D相对位置
        """
        try:
            if plane_vertices is None or len(plane_vertices) < 3:
                return None
            
            # 计算平面的原点、法线和局部坐标系
            p0 = plane_vertices[0]  # 平面原点
            v1 = plane_vertices[1] - p0  # 第一个方向向量
            v2 = plane_vertices[2] - p0  # 第二个方向向量
            
            # 计算平面法线
            normal = np.cross(v1, v2)
            normal_len = np.linalg.norm(normal)
            if normal_len < 1e-8:
                return None
            normal = normal / normal_len
            
            # 构建平面局部坐标系的基向量
            # U轴：沿着第一个边的方向
            u_axis = v1 / np.linalg.norm(v1)
            # V轴：垂直于U轴和法线
            v_axis = np.cross(normal, u_axis)
            v_axis = v_axis / np.linalg.norm(v_axis)
            
            # 从屏幕坐标获取射线
            renderer = view.renderer
            camera = renderer.GetActiveCamera()
            
            # 将屏幕坐标转换为VTK坐标
            width = view.width()
            height = view.height()
            vtk_x = screen_pos.x()
            vtk_y = height - screen_pos.y() - 1
            
            # 获取射线的起点和方向
            # 使用DisplayToWorld转换获取近平面和远平面的点
            renderer.SetDisplayPoint(vtk_x, vtk_y, 0.0)
            renderer.DisplayToWorld()
            near_point = np.array(renderer.GetWorldPoint()[:3]) / renderer.GetWorldPoint()[3]
            
            renderer.SetDisplayPoint(vtk_x, vtk_y, 1.0)
            renderer.DisplayToWorld()
            far_point = np.array(renderer.GetWorldPoint()[:3]) / renderer.GetWorldPoint()[3]
            
            # 射线方向
            ray_dir = far_point - near_point
            ray_dir = ray_dir / np.linalg.norm(ray_dir)
            
            # 计算射线与平面的交点
            # 平面方程: dot(normal, P - p0) = 0
            # 射线方程: P = near_point + t * ray_dir
            # 求解 t: dot(normal, near_point + t * ray_dir - p0) = 0
            denom = np.dot(normal, ray_dir)
            if abs(denom) < 1e-8:
                # 射线与平面平行
                return None
            
            t = np.dot(normal, p0 - near_point) / denom
            if t < 0:
                # 交点在射线起点后面
                return None
            
            # 计算交点
            intersection = near_point + t * ray_dir
            
            # 将交点转换到平面局部坐标系
            vec = intersection - p0
            u = np.dot(vec, u_axis)
            v = np.dot(vec, v_axis)
            
            return np.array([u, v])
            
        except Exception as e:
            print(f"平面相对坐标转换失败: {e}")
            return None
    
    @staticmethod
    def screen_to_world_on_plane(view, screen_pos: QPoint, plane_vertices: np.ndarray) -> Optional[np.ndarray]:
        """
        将屏幕坐标通过选中平面转换为世界坐标
        先获取在平面上的相对位置，再转换为世界坐标
        """
        # 第一步：获取平面相对坐标
        relative_pos = CoordinateConverter.screen_to_plane_relative(view, screen_pos, plane_vertices)
        if relative_pos is None:
            return None
        
        # 第二步：转换为世界坐标
        return CoordinateConverter.plane_relative_to_world(plane_vertices, relative_pos)
    
    @staticmethod
    def plane_relative_to_world(plane_vertices: np.ndarray, relative_pos: np.ndarray) -> Optional[np.ndarray]:
        """将平面内的2D相对位置转换为3D世界坐标"""
        try:
            if plane_vertices is None or len(plane_vertices) < 3:
                return None
            
            if relative_pos is None or len(relative_pos) != 2:
                return None
            
            # 计算平面的原点和局部坐标系
            p0 = plane_vertices[0]  # 平面原点
            v1 = plane_vertices[1] - p0  # 第一个方向向量
            v2 = plane_vertices[2] - p0  # 第二个方向向量
            
            # 计算平面法线
            normal = np.cross(v1, v2)
            normal_len = np.linalg.norm(normal)
            if normal_len < 1e-8:
                return None
            normal = normal / normal_len
            
            # 构建平面局部坐标系的基向量
            # U轴：沿着第一个边的方向
            u_axis = v1 / np.linalg.norm(v1)
            # V轴：垂直于U轴和法线
            v_axis = np.cross(normal, u_axis)
            v_axis = v_axis / np.linalg.norm(v_axis)
            
            # 将局部坐标转换为世界坐标
            u, v = relative_pos[0], relative_pos[1]
            world_pos = p0 + u * u_axis + v * v_axis
            
            return world_pos
            
        except Exception as e:
            print(f"平面坐标转世界坐标失败: {e}")
            return None
    
    @staticmethod
    def constrain_to_line_entity(world_pos: np.ndarray, edit_manager, entity_id: str) -> Optional[np.ndarray]:
        """
        将世界坐标限制在线实体上（折线或曲线）
        直接传入实体ID，自动识别实体类型并进行坐标限制
        --------
        Optional[np.ndarray]
            限制在线实体上的点，如果实体不存在则返回None
        """
        try:
            # 检查是否为折线
            if hasattr(edit_manager, '_polylines') and entity_id in edit_manager._polylines:
                return CoordinateConverter.constrain_to_polyline_entity(world_pos, edit_manager, entity_id)
            
            # 检查是否为曲线
            elif hasattr(edit_manager, '_curves') and entity_id in edit_manager._curves:
                return CoordinateConverter.constrain_to_curve_entity(world_pos, edit_manager, entity_id)
            
            # 实体不存在
            return None
            
        except Exception as e:
            print(f"限制坐标到线实体失败: {e}")
            return None
    
    @staticmethod
    def constrain_to_polyline_entity(world_pos: np.ndarray, edit_manager, polyline_id: str) -> Optional[np.ndarray]:
        """
        将世界坐标限制到折线实体上
        
        Parameters:
        -----------
        world_pos : np.ndarray
            要限制的世界坐标点 (3,)
        edit_manager : EditModeManager
            编辑模式管理器
        polyline_id : str
            折线ID
            
        Returns:
        --------
        Optional[np.ndarray]
            限制在折线上的点，如果折线不存在则返回None
        """
        try:
            if not hasattr(edit_manager, '_polylines') or polyline_id not in edit_manager._polylines:
                return None
            
            point_ids = edit_manager._polylines[polyline_id]
            polyline_points = []
            
            for pid in point_ids:
                if pid in edit_manager.points:
                    polyline_points.append(edit_manager.points[pid].position)
            
            if len(polyline_points) >= 2:
                return CoordinateConverter.constrain_to_polyline(world_pos, polyline_points)
            
            return None
            
        except Exception as e:
            print(f"限制坐标到折线实体失败: {e}")
            return None
    
    @staticmethod
    def constrain_to_curve_entity(world_pos: np.ndarray, edit_manager, curve_id: str) -> Optional[np.ndarray]:
        """
        将世界坐标限制到曲线实体上
        
        Parameters:
        -----------
        world_pos : np.ndarray
            要限制的世界坐标点 (3,)
        edit_manager : EditModeManager
            编辑模式管理器
        curve_id : str
            曲线ID
            
        Returns:
        --------
        Optional[np.ndarray]
            限制在曲线上的点，如果曲线不存在则返回None
        """
        try:
            if not hasattr(edit_manager, '_curves') or curve_id not in edit_manager._curves:
                return None
            
            curve_data = edit_manager._curves[curve_id]
            control_point_ids = curve_data.get('control_point_ids', [])
            
            if len(control_point_ids) < 2:
                return None
            
            # 获取控制点坐标
            control_points = []
            for pid in control_point_ids:
                if pid in edit_manager.points:
                    control_points.append(edit_manager.points[pid].position)
            
            if len(control_points) < 2:
                return None
            
            # 生成曲线的采样点用于距离计算
            from gui.interactive_view.edit_mode.line import LineOperator
            line_operator = LineOperator(edit_manager)
            
            # 使用曲线生成方法获取采样点
            curve_points = line_operator.generate_smooth_curve(
                control_points, 
                num_points=100,  # 生成100个采样点
                degree=curve_data.get('degree', 3)
            )
            
            if curve_points is not None and len(curve_points) >= 2:
                # 将曲线视为折线进行处理
                return CoordinateConverter.constrain_to_polyline(world_pos, curve_points)
            
            return None
            
        except Exception as e:
            print(f"限制坐标到曲线实体失败: {e}")
            return None
    
    @staticmethod
    def constrain_to_selected_line_if_near(view, screen_pos: QPoint, pixel_threshold: int = 20) -> Optional[np.ndarray]:
        """
        当选中线且光标靠近线时，将世界坐标限制到线上
        
        Parameters:
        -----------
        view : InteractiveView
            视图对象
        screen_pos : QPoint
            屏幕坐标位置
        pixel_threshold : int
            像素阈值，默认20像素
            
        Returns:
        --------
        Optional[np.ndarray]
            如果选中线且光标靠近线，返回限制在线上的坐标
            否则返回普通的世界坐标或None
        """
        try:
            # 获取编辑管理器
            edit_manager = getattr(view, '_edit_mode_manager', None)
            if edit_manager is None:
                return None
            
            # 检查是否有选中的线
            selected_line_id = getattr(edit_manager, 'selected_line_id', None)
            if selected_line_id is None:
                # 没有选中的线，返回普通世界坐标
                return CoordinateConverter.screen_to_world(view, screen_pos)
            
            # 检查光标是否靠近选中的线
            from gui.interactive_view.edit_mode.select import SelectionManager
            selector = SelectionManager(edit_manager)
            
            # 检测光标位置的对象
            selected = selector.select_at_screen_position(screen_pos, view, pixel_threshold=pixel_threshold)
            
            if selected is None or selected.get('type') != 'line' or selected.get('id') != selected_line_id:
                # 光标没有靠近选中的线，返回普通世界坐标
                return CoordinateConverter.screen_to_world(view, screen_pos)
            
            # 光标靠近选中的线，获取普通世界坐标
            world_pos = CoordinateConverter.screen_to_world(view, screen_pos)
            if world_pos is None:
                return None
            
            # 将世界坐标限制到选中的线上
            constrained_pos = CoordinateConverter.constrain_to_line_entity(world_pos, edit_manager, selected_line_id)
            
            return constrained_pos if constrained_pos is not None else world_pos
            
        except Exception as e:
            print(f"限制到选中线失败: {e}")
            # 出错时返回普通世界坐标
            return CoordinateConverter.screen_to_world(view, screen_pos)
    
    @staticmethod
    def get_world_position_with_line_constraint(view, screen_pos: QPoint, pixel_threshold: int = 20) -> Optional[np.ndarray]:
        """
        获取世界坐标，如果选中线且光标靠近线则自动限制到线上
        
        这是 constrain_to_selected_line_if_near 的别名方法，提供更直观的命名
        
        Parameters:
        -----------
        view : InteractiveView
            视图对象
        screen_pos : QPoint
            屏幕坐标位置
        pixel_threshold : int
            像素阈值，默认20像素
            
        Returns:
        --------
        Optional[np.ndarray]
            世界坐标（可能被限制到线上）
        """
        return CoordinateConverter.constrain_to_selected_line_if_near(view, screen_pos, pixel_threshold)
    
    @staticmethod
    def _constrain_to_polyline_entity(world_pos: np.ndarray, edit_manager, polyline_id: str) -> Optional[np.ndarray]:
        """将坐标限制到折线实体上"""
        try:
            point_ids = edit_manager._polylines[polyline_id]
            polyline_points = []
            
            for pid in point_ids:
                if pid in edit_manager.points:
                    polyline_points.append(edit_manager.points[pid].position)
            
            if len(polyline_points) >= 2:
                return CoordinateConverter.constrain_to_polyline(world_pos, polyline_points)
            
            return None
            
        except Exception as e:
            print(f"限制坐标到折线实体失败: {e}")
            return None
    
    @staticmethod
    def _constrain_to_curve_entity(world_pos: np.ndarray, edit_manager, curve_id: str) -> Optional[np.ndarray]:
        """将坐标限制到曲线实体上"""
        try:
            curve_data = edit_manager._curves[curve_id]
            control_point_ids = curve_data.get('control_point_ids', [])
            
            if len(control_point_ids) < 2:
                return None
            
            # 获取控制点坐标
            control_points = []
            for pid in control_point_ids:
                if pid in edit_manager.points:
                    control_points.append(edit_manager.points[pid].position)
            
            if len(control_points) < 2:
                return None
            
            # 生成曲线的采样点用于距离计算
            from gui.interactive_view.edit_mode.line import LineOperator
            line_operator = LineOperator(edit_manager)
            
            # 使用曲线生成方法获取采样点
            curve_points = line_operator.generate_smooth_curve(
                control_points, 
                num_points=100,  # 生成100个采样点
                degree=curve_data.get('degree', 3)
            )
            
            if curve_points is not None and len(curve_points) >= 2:
                # 将曲线视为折线进行处理
                return CoordinateConverter.constrain_to_polyline(world_pos, curve_points)
            
            return None
            
        except Exception as e:
            print(f"限制坐标到曲线实体失败: {e}")
            return None
