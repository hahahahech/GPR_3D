"""
鼠标和键盘事件处理
"""
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QWidget
import numpy as np
from .coordinates import CoordinateConverter
from .camera import CameraController
from .edit_mode import EditModeManager, PointOperator, LineOperator, PlaneOperator, ColorSelector


class EventHandler:
    """事件处理器 - 处理鼠标和键盘事件"""
    
    @staticmethod
    def mouse_press_event(view, event):
        """鼠标按下事件"""
        view._last_mouse_pos = event.pos()
        
        # 检查当前模式和工具
        if hasattr(view, '_mode_toolbar'):
            current_mode = view._mode_toolbar.get_current_mode()
            current_tool = view._mode_toolbar.get_current_tool()
            
            # 如果是编辑模式且选择了点工具
            if current_mode == 'edit' and current_tool == 'point':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_create_point(view, event.pos())
                    return

            # 编辑模式线工具：连续点击生成线段
            if current_mode == 'edit' and current_tool == 'line':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_create_line(view, event.pos())
                    return

            # 编辑模式面工具：选线成面
            if current_mode == 'edit' and current_tool == 'plane':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_create_plane(view, event.pos())
                    return

            # 编辑模式颜色工具：选中对象修改颜色
            if current_mode == 'edit' and current_tool == 'color_select':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_color_select(view, event.pos())
                    return
            
            # 如果是编辑模式且选择了选择工具，检查是否选中了点（用于拖拽）
            if current_mode == 'edit' and current_tool == 'edit_select':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    selected = EventHandler._try_select_edit_object_for_drag(view, event.pos())
                    if selected and selected.get('type') == 'point':
                        # 锁定点不可拖拽
                        if hasattr(view, '_edit_mode_manager') and selected['id'] in getattr(view._edit_mode_manager, '_locked_points', set()):
                            return
                        # 开始拖拽点
                        if hasattr(view, '_point_operator'):
                            view._point_operator.start_drag(selected['id'], event.pos(), view)
                        return
                    # 如果没有选中点，执行普通选择
                    EventHandler._try_select_object(view, event.pos())
                    return
        
        # 对象选择（其他情况）
        if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
            # 尝试选择对象
            EventHandler._try_select_object(view, event.pos())
            return
        
        # 检查按键组合（导航模式）
        modifiers = event.modifiers()
        button = event.button()
        
        if modifiers & Qt.AltModifier:
            if button == Qt.LeftButton:
                # Alt + 左键：旋转
                view._is_rotating = True
                view.setCursor(Qt.ClosedHandCursor)
            elif button == Qt.MidButton:
                # Alt + 中键：平移
                view._is_panning = True
                view.setCursor(Qt.SizeAllCursor)
            elif button == Qt.RightButton:
                # Alt + 右键：缩放
                view._is_zooming = True
                view.setCursor(Qt.SizeVerCursor)
        elif modifiers & Qt.ShiftModifier:
            if button == Qt.MidButton:
                # Shift + 中键：平移
                view._is_panning = True
                view.setCursor(Qt.SizeAllCursor)
        elif button == Qt.MidButton:
            # 单独中键：旋转（备用方案）
            view._is_rotating = True
            view.setCursor(Qt.ClosedHandCursor)
    
    @staticmethod
    def mouse_move_event(view, event):
        """鼠标移动事件"""
        # 更新坐标显示
        view._update_coordinate_display(event.pos())
        
        # 检查是否在拖拽点
        if hasattr(view, '_point_operator') and view._point_operator._is_dragging:
            view._point_operator.update_drag(event.pos(), view)
            view.view_changed.emit()
            return
        
        if view._last_mouse_pos is None:
            view._last_mouse_pos = event.pos()
            return
        
        current_pos = event.pos()
        delta = current_pos - view._last_mouse_pos
        
        if view._is_rotating:
            CameraController.handle_rotation(view, delta)
        elif view._is_panning:
            CameraController.handle_pan(view, delta)
        elif view._is_zooming:
            CameraController.handle_zoom_drag(view, delta)
        
        view._last_mouse_pos = current_pos
        view.view_changed.emit()
    
    @staticmethod
    def mouse_release_event(view, event):
        """鼠标释放事件"""
        # 结束点拖拽
        if hasattr(view, '_point_operator') and view._point_operator._is_dragging:
            view._point_operator.end_drag()
        
        view._is_rotating = False
        view._is_panning = False
        view._is_zooming = False
        
        # 恢复光标
        view.setCursor(Qt.ArrowCursor)
        
        view._last_mouse_pos = None
    
    @staticmethod
    def wheel_event(view, event):
        """滚轮事件（缩放）"""
        # 获取滚轮增量（通常为120的倍数）
        delta = event.angleDelta().y()
        
        # 缩放因子（正值放大，负值缩小）
        zoom_factor = 1.0 + (delta / 1200.0)  # 调整灵敏度
        
        CameraController.handle_zoom_wheel(view, zoom_factor)
        view.view_changed.emit()
    
    @staticmethod
    def key_press_event(view, event):
        """键盘事件处理"""
        # 按键传递给父类
        from pyvistaqt import QtInteractor
        QtInteractor.keyPressEvent(view, event)
    
    @staticmethod
    def _try_select_object(view, screen_pos: QPoint):
        """尝试选择对象"""
        # 检查当前模式和工具
        if hasattr(view, '_mode_toolbar'):
            current_mode = view._mode_toolbar.get_current_mode()
            current_tool = view._mode_toolbar.get_current_tool()
            
            # 如果是编辑模式且选择了编辑模式的选择工具
            if current_mode == 'edit' and current_tool == 'edit_select':
                EventHandler._try_select_edit_object(view, screen_pos)
                return
        
        # 其他情况使用原有的选择逻辑（物体模式等）
        try:
            # 使用PyVista的pick功能
            width = view.width()
            height = view.height()
            vtk_x = screen_pos.x()
            vtk_y = height - screen_pos.y() - 1
            
            # 尝试使用CellPicker
            try:
                from vtkmodules.vtkRenderingCore import vtkCellPicker
                picker = vtkCellPicker()
                picker.SetTolerance(0.001)
                
                if picker.Pick(vtk_x, vtk_y, 0, view.renderer):
                    actor = picker.GetActor()
                    if actor:
                        # 获取actor的名称（应该是对象的ID）
                        prop = actor.GetProperty()
                        # 尝试从actor获取对象ID
                        # PyVista的actor可能存储了名称信息
                        try:
                            # 通过actor的mapper获取数据
                            mapper = actor.GetMapper()
                            if mapper:
                                # 尝试从plotter的actors字典中查找
                                # 这是一个简化的实现，实际可能需要更复杂的查找
                                obj_id = None
                                # 遍历plotter的actors查找匹配的actor
                                for name, plotter_actor in view.actors.items():
                                    if plotter_actor == actor:
                                        obj_id = name
                                        break
                                
                                if obj_id:
                                    # 对象选择处理（简化实现）
                                    pass
                        except:
                            pass
            except:
                pass
        except:
            pass
    
    @staticmethod
    def _try_select_edit_object(view, screen_pos: QPoint):
        """
        尝试在编辑模式下选择对象（点、线、面）
        使用屏幕空间选择方法，考虑深度和像素距离
        
        Parameters:
        -----------
        view : InteractiveView
            交互式视图实例
        screen_pos : QPoint
            屏幕坐标
        """
        # 获取编辑模式管理器
        if not hasattr(view, '_edit_mode_manager'):
            return
        
        edit_manager = view._edit_mode_manager
        
        # 优先使用屏幕空间选择（更准确，考虑深度）
        selected = edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        
        # 如果屏幕空间选择失败，回退到原来的世界坐标方法
        if selected is None:
            world_pos = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
            if world_pos is None:
                # 如果转换失败，尝试使用焦点平面
                world_pos = CoordinateConverter.screen_to_world(
                    view, screen_pos, depth=0.0, clip_to_bounds=False
                )
            
            if world_pos is not None:
                # 执行选择（优先级：点 > 线 > 面，阈值0.1）
                selected = edit_manager.select_at_position(world_pos)
        
        if selected is None:
            # 未选中任何对象，不执行操作
            if hasattr(view, 'status_message'):
                view.status_message.emit('未选中任何对象')
            return
        
        # 选中了对象，聚焦到该对象
        focus_point = selected['focus_point']
        CameraController.focus_on_point(view, focus_point, zoom_factor=0.5)
        
        # 发送状态消息
        obj_type = selected['type']
        obj_id = selected['id']
        
        type_names = {
            'point': '点',
            'line': '线',
            'plane': '面'
        }
        type_name = type_names.get(obj_type, obj_type)
        
        if hasattr(view, 'status_message'):
            view.status_message.emit(f'已选中{type_name}: {obj_id}')
    
    @staticmethod
    def _try_create_point(view, screen_pos: QPoint):
        """
        尝试在编辑模式下创建点
        
        Parameters:
        -----------
        view : InteractiveView
            交互式视图实例
        screen_pos : QPoint
            屏幕坐标
        """
        # 获取点操作器
        if not hasattr(view, '_point_operator'):
            return
        
        point_operator = view._point_operator
        
        # 创建点
        point_id = point_operator.create_point_at_screen(screen_pos, view)
        
        if point_id is not None:
            if hasattr(view, 'status_message'):
                pos = point_operator.get_point_position(point_id)
                if pos is not None:
                    view.status_message.emit(
                        f'已创建点: {point_id} 位置: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})'
                    )
        else:
            if hasattr(view, 'status_message'):
                view.status_message.emit('创建点失败')

    @staticmethod
    def _try_create_line(view, screen_pos: QPoint):
        """
        尝试在编辑模式下创建线段（连续点击）
        """
        if not hasattr(view, '_line_operator'):
            return
        line_operator = view._line_operator
        line_id = line_operator.handle_click(screen_pos, view)
        if line_id is not None and hasattr(view, 'status_message'):
            view.status_message.emit(f'已创建线段: {line_id}')

    @staticmethod
    def _try_create_plane(view, screen_pos: QPoint):
        """
        尝试在编辑模式下根据选中的线生成面
        """
        if not hasattr(view, '_plane_operator'):
            return
        plane_operator = view._plane_operator
        plane_id = plane_operator.handle_click(screen_pos, view)
        if plane_id is not None and hasattr(view, 'status_message'):
            view.status_message.emit(f'已创建面: {plane_id}')

    @staticmethod
    def _try_color_select(view, screen_pos: QPoint):
        """
        颜色选择：点击对象并修改其颜色
        """
        if not hasattr(view, '_color_selector'):
            return
        color_selector = view._color_selector
        color_selector.handle_click(screen_pos, view)
    
    @staticmethod
    def _try_select_edit_object_for_drag(view, screen_pos: QPoint):
        """
        尝试在编辑模式下选择对象（用于拖拽）
        使用屏幕空间选择方法
        
        Parameters:
        -----------
        view : InteractiveView
            交互式视图实例
        screen_pos : QPoint
            屏幕坐标
        
        Returns:
        --------
        dict or None
            选中的对象信息，如果未选中返回None
        """
        # 获取编辑模式管理器
        if not hasattr(view, '_edit_mode_manager'):
            return None
        
        edit_manager = view._edit_mode_manager
        
        # 优先使用屏幕空间选择
        selected = edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        
        # 如果屏幕空间选择失败，回退到原来的方法
        if selected is None:
            world_pos = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
            if world_pos is None:
                world_pos = CoordinateConverter.screen_to_world(
                    view, screen_pos, depth=0.0, clip_to_bounds=False
                )
            
            if world_pos is not None:
                selected = edit_manager.select_at_position(world_pos)
        
        return selected

