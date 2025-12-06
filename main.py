"""
道路地下三维建模与网格划分软件 - 主程序入口
启动GUI界面进行建模开发
"""
import sys
from PyQt5.QtWidgets import QApplication
from gui.main_window import MainWindow


def main():
    """主函数 - 启动GUI界面"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    # 设置应用信息
    app.setApplicationName("道路地下三维建模与网格划分软件")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("3D Modeling")
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

