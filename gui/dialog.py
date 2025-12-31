
"""
对话框模块
包含各种输入对话框
"""
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QDialogButtonBox
from PyQt5.QtCore import Qt
import numpy as np


class CoordinateInputDialog(QDialog):
    """坐标输入对话框"""
    def __init__(self, view, parent=None):
        super().__init__(parent)
        self.view = view
        self.setWindowTitle("输入点坐标")
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # X坐标
        x_layout = QHBoxLayout()
        x_layout.addWidget(QLabel("X:"))
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-1e6, 1e6)
        self.x_spin.setDecimals(1)
        self.x_spin.setSingleStep(0.1)
        self.x_spin.setValue(0.0)
        x_layout.addWidget(self.x_spin)
        layout.addLayout(x_layout)
        
        # Y坐标
        y_layout = QHBoxLayout()
        y_layout.addWidget(QLabel("Y:"))
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-1e6, 1e6)
        self.y_spin.setDecimals(1)
        self.y_spin.setSingleStep(0.1)
        self.y_spin.setValue(0.0)
        y_layout.addWidget(self.y_spin)
        layout.addLayout(y_layout)
        
        # Z坐标
        z_layout = QHBoxLayout()
        z_layout.addWidget(QLabel("Z:"))
        self.z_spin = QDoubleSpinBox()
        self.z_spin.setRange(-1e6, 1e6)
        self.z_spin.setDecimals(1)
        self.z_spin.setSingleStep(0.1)
        self.z_spin.setValue(0.0)
        z_layout.addWidget(self.z_spin)
        layout.addLayout(z_layout)
        
        # 按钮
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_coordinates(self):
        """获取输入的坐标"""
        try:
            return [self.x_spin.value(), self.y_spin.value(), self.z_spin.value()]
        except Exception:
            return None
    
    def accept(self):
        """点击OK按钮时，直接创建点"""
        coords = self.get_coordinates()
        if coords is not None:
            self._create_point_at_coordinates(coords)
        super().accept()
    
    def _create_point_at_coordinates(self, coords):
        """在指定坐标创建点"""
        try:
            # 获取 point_operator
            if not hasattr(self.view, '_point_operator'):
                if hasattr(self.view, 'status_message'):
                    self.view.status_message.emit('无法获取点操作器')
                return
            
            point_operator = self.view._point_operator
            world_pos = np.array(coords, dtype=np.float64)
            
            # 调用 create_point_at_world 创建点
            point_id = point_operator.create_point_at_world(world_pos, self.view)
            
            if point_id is not None:
                if hasattr(self.view, 'status_message'):
                    self.view.status_message.emit(
                        f'已创建点: {point_id} 位置: ({coords[0]:.1f}, {coords[1]:.1f}, {coords[2]:.1f})'
                    )
                # 触发视图更新
                if hasattr(self.view, 'view_changed'):
                    self.view.view_changed.emit()
            else:
                if hasattr(self.view, 'status_message'):
                    self.view.status_message.emit('创建点失败')
        except Exception as e:
            print(f"创建点失败: {e}")
            if hasattr(self.view, 'status_message'):
                self.view.status_message.emit(f'创建点失败: {e}')