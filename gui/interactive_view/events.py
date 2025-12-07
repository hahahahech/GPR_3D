"""
鼠标和键盘事件处理
"""
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtWidgets import QWidget
import numpy as np
from .coordinates import CoordinateConverter
from .camera import CameraController


class EventHandler:
    """事件处理器 - 处理鼠标和键盘事件"""
    
    @staticmethod
    def mouse_press_event(view, event):
        """鼠标按下事件"""
        view._last_mouse_pos = event.pos()
        
        # 对象选择
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

