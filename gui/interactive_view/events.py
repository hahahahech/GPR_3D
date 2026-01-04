"""
鼠标和键盘事件处理
"""
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QWidget
import numpy as np
from .coordinates import CoordinateConverter
from .camera import CameraController
from .edit_mode import EditModeManager, PointOperator, LineOperator, PlaneOperator, ColorSelector
from vtkmodules.vtkRenderingCore import vtkCellPicker

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
            select_enabled = False
            try:
                if hasattr(view._mode_toolbar, 'is_select_enabled'):
                    select_enabled = view._mode_toolbar.is_select_enabled()
            except Exception:
                select_enabled = False

            # 独立选择模式：开启后可与其它工具共存。
            # 左键点击优先用于选择/拖拽（不按 Alt 时），否则才交给具体工具。
            if current_mode == 'edit' and select_enabled and (current_tool is None or current_tool == 'edit_select'):
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    # 获取编辑模式管理器
                    if hasattr(view, '_edit_mode_manager'):
                        view._edit_mode_manager.handle_selection_and_action(view, event.pos())
                    return
            # 如果是编辑模式且选择了点工具
            if current_mode == 'edit' and current_tool == 'point':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_create_point(view, event.pos())
                    return

           # 编辑模式折线工具：左键添加控制点，右键生成折线
            if current_mode == 'edit' and current_tool == 'polyline':
                # 左键用于添加控制点，右键用于结束并生成折线
                if not (event.modifiers() & Qt.AltModifier):
                    if event.button() == Qt.LeftButton:
                        # add control point
                        EventHandler._try_create_polyline(view, event, finalize=False)
                        return
                    elif event.button() == Qt.RightButton:
                        EventHandler._try_create_polyline(view, event, finalize=True)
                        return
            # 编辑模式曲线工具：多点选取后右键结束生成曲线
            if current_mode == 'edit' and current_tool == 'curve':
                # 左键用于添加控制点，右键用于结束并生成曲线
                if not (event.modifiers() & Qt.AltModifier):
                    if event.button() == Qt.LeftButton:
                        # add control point
                        EventHandler._try_create_curve(view, event, finalize=False)
                        return
                    elif event.button() == Qt.RightButton:
                        EventHandler._try_create_curve(view, event, finalize=True)
                        return

            # 编辑模式面工具：左键选中点/线，右键生成面
            if current_mode == 'edit' and current_tool == 'plane':
                if not (event.modifiers() & Qt.AltModifier):
                    if event.button() == Qt.LeftButton:
                        # 选中点或线
                        EventHandler._try_select_for_plane(view, event.pos())
                        return
                    elif event.button() == Qt.RightButton:
                        # 生成面
                        EventHandler._try_finalize_plane(view)
                        return
            # 编辑模式拉伸工具：点击选择点为拉伸目标（占位）
            if current_mode == 'edit' and current_tool == 'lashen':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_create_stretch(view, event.pos())
                    return

            # 编辑模式颜色工具：选中对象修改颜色
            if current_mode == 'edit' and current_tool == 'color_select':
                if event.button() == Qt.LeftButton and not (event.modifiers() & Qt.AltModifier):
                    EventHandler._try_color_select(view, event.pos())
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
            if button == Qt.MidButton:
                # Alt + 中键：平移
                view._is_panning = True
                view.setCursor(Qt.SizeAllCursor)
        elif button == Qt.MidButton:
            # 单独中键：旋转
            view._is_rotating = True
            view.setCursor(Qt.ClosedHandCursor)
    
    @staticmethod
    def mouse_move_event(view, event):
        """鼠标移动事件"""
        # 更新坐标显示
        view._update_coordinate_display(event.pos())
        
                
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
            select_enabled = False
            try:
                if hasattr(view._mode_toolbar, 'is_select_enabled'):
                    select_enabled = view._mode_toolbar.is_select_enabled()
            except Exception:
                select_enabled = False
            
            # 独立选择开关
            if current_mode == 'edit' and select_enabled and (current_tool is None or current_tool == 'edit_select'):
                EventHandler._try_select_edit_object(view, screen_pos)
                return

            # 兼容旧逻辑：仍支持 edit_select 作为 tool
            if current_mode == 'edit' and current_tool == 'edit_select':
                EventHandler._try_select_edit_object(view, screen_pos)
                return
        
        # 其他情况使用原有的选择逻辑（物体模式等）
            # 使用PyVista的pick功能
            width = view.width()
            height = view.height()
            vtk_x = screen_pos.x()
            vtk_y = height - screen_pos.y() - 1
            
            # 尝试使用CellPicker

            picker = vtkCellPicker()
            picker.SetTolerance(0.001)
            
            if picker.Pick(vtk_x, vtk_y, 0, view.renderer):
                actor = picker.GetActor()
                if actor:
                    # 获取actor的名称（应该是对象的ID）
                    # prop = actor.GetProperty()
                    # 尝试从actor获取对象ID
                    # PyVista的actor可能存储了名称信息
                       
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
    
    @staticmethod
    def _try_select_edit_object(view, screen_pos: QPoint):
        """
        尝试在编辑模式下选择对象（点、线、面）
        使用屏幕空间选择方法，考虑深度和像素距离
        """
        # 获取编辑模式管理器
        edit_manager = view._edit_mode_manager
        
        # 优先使用屏幕空间选择（更准确，考虑深度）
        selected = edit_manager.select_at_screen_position(screen_pos, view, pixel_threshold=10)
        
        if selected is None:
            # 未选中任何对象，不执行操作
            if hasattr(view, 'status_message'):
                view.status_message.emit('未选中任何对象')
            return
        
        # 发送状态消息
        obj_type = selected['type']
        obj_id = selected['id']
        
        type_names = {
            'point': '点',
            'line': '线',
            'plane': '面'
        }
        type_name = type_names.get(obj_type, obj_type)
        
        # 如果是点，设置选中状态
        if obj_type == 'point':
            edit_manager._selected_point_id = obj_id
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'已选中{type_name}: {obj_id}')
        else:
            # 如果不是点，清除点选中状态
            if hasattr(edit_manager, '_selected_point_id'):
                edit_manager._selected_point_id = None
            if hasattr(view, 'status_message'):
                view.status_message.emit(f'已选中{type_name}: {obj_id}')
        return

    @staticmethod
    def _try_create_point(view, screen_pos: QPoint):
        """
        尝试在编辑模式下创建点
        """
        if not hasattr(view, '_point_operator'):
            return
        
        point_operator = view._point_operator
        
        # 获取世界坐标
        world_pos = CoordinateConverter.screen_to_world_raycast(view, screen_pos)
        if world_pos is None:
            world_pos = CoordinateConverter.screen_to_world(
                view, screen_pos, depth=0.0, clip_to_bounds=False
            )
        
        if world_pos is None:
            if hasattr(view, 'status_message'):
                view.status_message.emit('无法获取世界坐标')
            return

        # 使用世界坐标创建点
        point_id = point_operator.create_point_at_world(world_pos, view)
        
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
    def _try_create_polyline(view,event, finalize: bool = False):
        """
        尝试在编辑模式下创建折线
        """
        if not hasattr(view, '_line_operator'):
            return
        line_operator = view._line_operator
        polyline_id = line_operator.handle_polyline_click(event.pos(), view, finalize=finalize)
        if polyline_id is not None and hasattr(view, 'status_message'):
            view.status_message.emit(f'已创建折线: {polyline_id}')

    @staticmethod
    def _try_create_curve(view, event, finalize: bool = False):
        """
        尝试在编辑模式下创建曲线（curve 工具）
        - event: QMouseEvent（包含 pos() 和 button()）
        - finalize: True 表示结束并生成曲线（通常由右键触发）
        """
        if not hasattr(view, '_line_operator'):
            return
        line_operator = view._line_operator
        # Pass the event.pos() and finalize flag
        curve_id = line_operator.handle_curve_click(event.pos(), view, finalize=finalize)
        if curve_id is not None and hasattr(view, 'status_message'):
            view.status_message.emit(f'已创建曲线: {curve_id}')

    @staticmethod
    def _try_select_for_plane(view, screen_pos: QPoint):
        """
        左键点击：选中点或线用于生成面
        """
        if not hasattr(view, '_plane_operator'):
            return
        plane_operator = view._plane_operator
        plane_operator.add_selection(screen_pos, view)
    
    @staticmethod
    def _try_finalize_plane(view):
        """
        右键点击：根据已选中的点/线生成面
        """
        if not hasattr(view, '_plane_operator'):
            return
        plane_operator = view._plane_operator
        plane_operator.finalize_plane(view)

    @staticmethod
    def _try_create_stretch(view, screen_pos: QPoint):
        """
        占位：拉伸工具的触发入口，调用 StretchOperator.handle_click
        """
        if not hasattr(view, '_stretch_operator'):
            return
        stretch_op = view._stretch_operator
        pid = stretch_op.handle_click(screen_pos, view)
        if pid is not None and hasattr(view, 'status_message'):
            view.status_message.emit(f'拉伸目标点: {pid}')

    @staticmethod
    def _try_color_select(view, screen_pos: QPoint):
        """
        颜色选择：点击对象并修改其颜色
        """
        if not hasattr(view, '_color_selector'):
            return
        color_selector = view._color_selector
        color_selector.handle_click(screen_pos, view)
    

