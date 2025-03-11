import re
import shutil
from pathlib import Path

def generate_lod_versions_for_all(src_dir="Camoulages", copies=3):
    """
    单次处理指定目录下的.visual文件（仅生成LOD副本）
    参数：
        src_dir: 源目录路径（默认同目录/Camoulages）
        copies: 生成副本数量（默认3）
    """
    src_path = Path(src_dir).resolve()
    processed_count = 0

    # 验证源目录有效性
    if not src_path.exists():
        raise FileNotFoundError(f"源目录不存在: {src_path}")
    if not src_path.is_dir():
        raise NotADirectoryError(f"路径不是目录: {src_path}")

    # 统一输出目录（避免嵌套）
    dest_root = src_path.parent / "Camoulages/lods"
    dest_root.mkdir(exist_ok=True)

    # 遍历源目录文件（排除lods目录）
    for src_file in src_path.rglob('*.visual'):
        if "lods" in src_file.parts:
            continue

        # 创建目标子目录（保持相对路径）
        relative_path = src_file.relative_to(src_path)
        dest_dir = dest_root / relative_path.parent
        dest_dir.mkdir(parents=True, exist_ok=True)

        base_name = src_file.stem
        extension = src_file.suffix

        # 直接读取源文件内容（不修改内容）
        with open(src_file, 'r', encoding='utf-8') as f:
            original_content = f.read()

        # 生成指定数量的副本
        for i in range(1, copies + 1):
            try:
                # 生成唯一文件名
                new_name = f"{base_name}_lod{i}{extension}"
                dest_path = dest_dir / new_name

                # 防止重复处理
                if dest_path.exists():
                    continue

                # 仅执行文件名替换逻辑
                final_content = re.sub(
                    rf'(?<!\w){re.escape(base_name)}(?!\w)',  # 精确匹配原始文件名
                    f'{base_name}_lod{i}',
                    original_content
                )

                # 写入新文件
                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(final_content)

                processed_count += 1
                print(f"生成: {dest_path.relative_to(dest_root)}")

            except Exception as e:
                print(f"失败 {src_file.name} → LOD{i}: {str(e)}")

    return processed_count

if __name__ == "__main__":
    try:
        total = generate_lod_versions_for_all()
        print(f"\n共生成 {total} 个LOD文件（存放于Camoulages/lods目录）")
    except Exception as e:
        print(f"\n运行错误: {str(e)}")