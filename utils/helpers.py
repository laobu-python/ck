# szj
# 2025/12/6
'''
辅助函数,辅助工具
'''
import csv
import json


def write_csv(file_path, rows, headers=None, encoding='utf-8-sig'):
    """将二维数据写入 CSV 文件。

    参数:
        file_path (str): 保存路径
        rows (list): 数据行列表，每行是 list/tuple
        headers (list): 表头（可选）
        encoding (str): 默认 utf-8-sig，Excel 直接打开中文不乱码

    返回:
        int: 写入的数据行数
    """
    rows = [list(r) for r in rows]
    with open(file_path, 'w', newline='', encoding=encoding) as f:
        writer = csv.writer(f)
        if headers:
            writer.writerow(list(headers))
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_json(file_path, data, encoding='utf-8', ensure_ascii=False, indent=2):
    """将 Python 对象（dict / list）写入 JSON 文件。

    参数:
        file_path (str): 保存路径
        data: 要保存的数据（dict / list）
        encoding (str): 编码，默认 utf-8
        ensure_ascii (bool): False 时中文直接可读（默认）
        indent (int): 缩进空格数，默认 2

    返回:
        bool: 是否写入成功
    """
    with open(file_path, 'w', encoding=encoding) as f:
        json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
    return True
