"""
VTK格式导出器
"""
import numpy as np
import meshio
from typing import Dict, Optional


class VTKExporter:
    """VTK格式导出器"""
    
    @staticmethod
    def export_unstructured_grid(nodes: np.ndarray, 
                                elements: np.ndarray,
                                cell_data: Optional[Dict[str, np.ndarray]] = None,
                                point_data: Optional[Dict[str, np.ndarray]] = None,
                                filename: str = "output.vtu"):
        """
        导出非结构化网格到VTK格式
        
        Parameters:
        -----------
        nodes : np.ndarray
            节点坐标 (Nx3)
        elements : np.ndarray
            单元节点索引 (Mx4 for tetra, Mx8 for hexa)
        cell_data : dict, optional
            单元数据，格式: {'property_name': np.ndarray}
        point_data : dict, optional
            节点数据，格式: {'property_name': np.ndarray}
        filename : str
            输出文件名
        """
        # 判断单元类型
        if elements.shape[1] == 4:
            cell_type = "tetra"
        elif elements.shape[1] == 8:
            cell_type = "hexahedron"
        else:
            raise ValueError(f"Unsupported element type with {elements.shape[1]} nodes")
        
        cells = [(cell_type, elements)]
        
        # 转换cell_data格式：meshio需要列表的列表
        formatted_cell_data = {}
        if cell_data:
            for key, value in cell_data.items():
                if isinstance(value, np.ndarray):
                    formatted_cell_data[key] = [value]
                else:
                    formatted_cell_data[key] = value
        
        mesh = meshio.Mesh(
            points=nodes,
            cells=cells,
            cell_data=formatted_cell_data if formatted_cell_data else None,
            point_data=point_data
        )
        
        mesh.write(filename)
        print(f"Mesh exported to {filename}")
        
    @staticmethod
    def export_structured_grid(x: np.ndarray, y: np.ndarray, z: np.ndarray,
                              field_data: Optional[np.ndarray] = None,
                              filename: str = "output.vts"):
        """
        导出结构化网格到VTK格式
        
        Parameters:
        -----------
        x, y, z : np.ndarray
            各方向的坐标数组
        field_data : np.ndarray, optional
            场数据 (nx, ny, nz)
        filename : str
            输出文件名
        """
        # 创建结构化网格
        # 使用meshio创建结构化网格
        nx, ny, nz = len(x), len(y), len(z)
        
        # 创建点坐标
        points = []
        for k in range(nz):
            for j in range(ny):
                for i in range(nx):
                    points.append([x[i], y[j], z[k]])
        
        nodes = np.array(points)
        
        # 创建六面体单元
        elements = []
        for k in range(nz - 1):
            for j in range(ny - 1):
                for i in range(nx - 1):
                    n0 = k * ny * nx + j * nx + i
                    n1 = n0 + 1
                    n2 = n0 + nx
                    n3 = n2 + 1
                    n4 = n0 + ny * nx
                    n5 = n1 + ny * nx
                    n6 = n2 + ny * nx
                    n7 = n3 + ny * nx
                    elements.append([n0, n1, n3, n2, n4, n5, n7, n6])
        
        elements = np.array(elements)
        
        cell_data = {}
        if field_data is not None:
            # 将场数据映射到单元
            cell_data['field'] = [field_data.flatten()]
        
        VTKExporter.export_unstructured_grid(
            nodes, elements, cell_data=cell_data, filename=filename
        )
        
    @staticmethod
    def export_points(nodes: np.ndarray,
                     point_data: Optional[Dict[str, np.ndarray]] = None,
                     filename: str = "output.vtp"):
        """
        导出点云数据
        
        Parameters:
        -----------
        nodes : np.ndarray
            点坐标 (Nx3)
        point_data : dict, optional
            点数据
        filename : str
            输出文件名
        """
        mesh = meshio.Mesh(
            points=nodes,
            cells=[],
            point_data=point_data
        )
        mesh.write(filename)
        print(f"Points exported to {filename}")

