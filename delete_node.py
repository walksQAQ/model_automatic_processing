import os
import re


def remove_shape_tag(directory):
    pattern = re.compile(r'(?P<prefix>\w+)Shape(?=</node>)')  # 动态匹配前缀+Shape

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.visual'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r+', encoding='utf-8') as f:
                        content = f.read()
                        new_content = pattern.sub(r'\g<prefix>', content)  # 保留前缀
                        # 回写文件
                        f.seek(0)
                        f.write(new_content)
                        f.truncate()
                    print(f"已处理: {file_path}")
                except Exception as e:
                    print(f"处理失败: {file_path}, 错误: {e}")

if __name__ == "__main__":
    target_dir = "./Camoulages"  # 替换为目标目录

    remove_shape_tag(target_dir)