import subprocess
import os
import shutil
import sys
import time
import psutil
import re
import chardet
import xml.etree.ElementTree as ET  # 新增导入语句
from pathlib import Path
from threading import Thread
from queue import Queue, Empty

# 配置基准路径
BASE_DIR = Path(__file__).parent.resolve()
SOURCE_DIR = BASE_DIR / "Camoulages"
TEMP_DIR = BASE_DIR / "Camoulages_GEO"
OUTPUT_DIR = BASE_DIR / "Camoulages_Upgrade"

# 可执行文件路径
GEOMETRYPACK_V1 = BASE_DIR / "old_pri-to-geo/geometrypack.exe"
GEOMETRYPACK_V2 = BASE_DIR / "new_pri-to-geo/geometrypack.exe"

# 执行参数
MAX_TIMEOUT = 300
CPU_THRESHOLD = 90
MEM_THRESHOLD = 80

# ========== 新增预处理函数 ==========
def cleanup_temp_models():
    """清理所有.temp_model文件"""
    temp_files = list(SOURCE_DIR.rglob('*.temp_model'))
    for file_path in temp_files:
        try:
            file_path.unlink(missing_ok=True)
            print(f"已删除临时文件: {file_path.relative_to(SOURCE_DIR)}")
        except Exception as e:
            print(f"删除失败 {file_path}: {str(e)}")


def execute_node_deletion():
    """执行XML节点删除脚本[4](@ref)"""
    delete_script = BASE_DIR / "delete_node.py"

    if not delete_script.exists():
        print(f"节点删除脚本不存在：{delete_script}")
        sys.exit(1)

    try:
        print("\n=== 开始执行XML节点删除 ===")
        # 修改1：禁用自动解码，获取原始字节流
        result = subprocess.run(
            [sys.executable, str(delete_script), "--input", str(SOURCE_DIR)],
            check=True,
            capture_output=True,
            text=False  # 保持二进制输出
        )

        # 修改2：动态检测编码
        raw_output = result.stdout
        if raw_output:
            detected_encoding = chardet.detect(raw_output)['encoding']
            decoded_output = raw_output.decode(detected_encoding or 'utf-8', errors='replace')
            print(decoded_output)

        print("XML节点删除完成")
    except subprocess.CalledProcessError as e:
        # 修改3：处理字节流错误
        error_msg = e.stderr.decode(chardet.detect(e.stderr)['encoding'], errors='replace')
        print(f"节点删除失败：{error_msg}")
        sys.exit(1)

def delete_lods_folder():
    """删除lods目录"""
    lods_path = SOURCE_DIR / "lods"
    if lods_path.exists():
        try:
            shutil.rmtree(lods_path, ignore_errors=True)
            print(f"已删除lods目录: {lods_path.relative_to(SOURCE_DIR)}")
        except Exception as e:
            print(f"删除失败 {lods_path}: {str(e)}")
            sys.exit(1)

def execute_visual_rename():
    """执行visual文件重命名"""
    rename_script = BASE_DIR / "visual-rename.py"

    if not rename_script.exists():
        print(f"重命名脚本不存在：{rename_script}")
        sys.exit(1)

    try:
        print("\n===开始重命名visual文件 ===")
        result = subprocess.run(
            [sys.executable, str(rename_script), "--input", str(SOURCE_DIR)],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        print("visual文件重命名完成")
    except subprocess.CalledProcessError as e:
        print(f"重命名失败：{e.stderr}")
        sys.exit(1)
# ========== 预处理结束 ==========

def validate_environment():
    """环境验证函数"""
    required_dirs = {
        "源目录": SOURCE_DIR,
        "临时目录": TEMP_DIR,
        "输出目录": OUTPUT_DIR
    }
    required_files = {
        "旧版工具": GEOMETRYPACK_V1,
        "新版工具": GEOMETRYPACK_V2
    }

    # 验证目录
    for name, path in required_dirs.items():
        if not path.exists():
            print(f"{name}不存在：{path}")
            sys.exit(1)
        if not path.is_dir():
            print(f"{name}应为目录：{path}")
            sys.exit(1)

    # 验证文件
    for name, path in required_files.items():
        if not path.exists():
            print(f"{name}不存在：{path}")
            sys.exit(1)
        if not path.is_file():
            print(f"{name}应为文件：{path}")
            sys.exit(1)


def safe_clear_directory(rel_path):
    """安全清空目录"""
    abs_path = rel_path.resolve()
    try:
        if abs_path.exists():
            # 记录目录状态
            dir_size = sum(f.stat().st_size for f in abs_path.glob('**/*') if f.is_file())
            print(f"正在清理目录（原大小：{dir_size / 1024:.2f}KB）: {rel_path}")

            # 执行删除
            shutil.rmtree(abs_path, ignore_errors=True)

            # 验证删除结果
            if abs_path.exists():
                print(f"警告：目录未完全清除，请手动检查 {rel_path}")
            else:
                print(f"成功清空目录: {rel_path}")

        rel_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"严重错误: {str(e)}")
        sys.exit(1)

class ProcessMonitor(Thread):
    """进程资源监控"""

    def __init__(self, process, version_tag):
        super().__init__()
        self.process = process
        self.tag = version_tag
        self.output = Queue()
        self._stop_event = False

    def run(self):
        while not self._stop_event:
            try:
                line = self.process.stdout.readline()
                if line:
                    self.output.put(line.strip())
                    print(f"[{self.tag}] {line.strip()}")
            except UnicodeDecodeError:
                pass

            try:
                p = psutil.Process(self.process.pid)
                cpu = p.cpu_percent(interval=1)
                mem = p.memory_percent()
                if cpu > CPU_THRESHOLD or mem > MEM_THRESHOLD:
                    print(f"[{self.tag}] 资源告警 CPU:{cpu}% MEM:{mem}%")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    def stop(self):
        self._stop_event = True

def execute_geometrypack(exe_path, input_dir, output_dir, options=None):
    """执行打包程序"""
    cmd = [
        str(exe_path.resolve()),
        "--verbose",
        "--tree",
        str(input_dir.resolve()),
        str(output_dir.resolve())
    ]

    if options:
        cmd[2:2] = options

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1
        )

        version_tag = "OLD" if "old_pri" in str(exe_path) else "NEW"
        monitor = ProcessMonitor(proc, version_tag)
        monitor.start()

        start_time = time.time()
        while proc.poll() is None:
            if time.time() - start_time > MAX_TIMEOUT:
                print(f"[{version_tag}] 执行超时，强制终止...")
                proc.kill()
                raise TimeoutError(f"执行超过 {MAX_TIMEOUT} 秒未完成")
            time.sleep(0.5)

        while not monitor.output.empty():
            print(monitor.output.get_nowait())

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd)

    except Exception as e:
        print(f"执行失败：{str(e)}")
        sys.exit(1)
    finally:
        monitor.stop()

def handle_geometry_files(output_dir):
    """处理Geometry文件"""
    output_path = Path(output_dir)
    geometry_files = []

    # 递归收集文件
    for root, _, files in os.walk(output_path):
        current_dir = Path(root)
        if current_dir == output_path:
            continue
        for file in files:
            if file.lower().endswith('.geometry'):
                geometry_files.append((current_dir, file))

    # 移动文件并处理重名
    for current_dir, file in geometry_files:
        src = current_dir / file
        dest = output_path / file

        # 自动重命名策略
        counter = 1
        while dest.exists():
            stem = dest.stem.rstrip(f' ({counter - 1})')
            new_name = f"{stem} ({counter}){dest.suffix}"
            dest = output_path / new_name
            counter += 1

        shutil.move(str(src), str(dest))
        print(f"已移动 {src.relative_to(output_path)} → {dest.name}")

    # 删除空目录
    for root, dirs, _ in os.walk(output_path, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            if dir_path != output_path:
                try:
                    shutil.rmtree(dir_path)
                    print(f"已删除子目录 {dir_path.relative_to(output_path)}")
                except Exception as e:
                    print(f"删除失败 {dir_path}: {str(e)}")


def copy_processed_visuals(source_roots, target_root):
    """复制所有处理后visual文件并保留原始结构"""
    copied_files = 0
    processed_files = set()
    target_root = Path(target_root).resolve()

    for source_root in map(Path, source_roots):
        if not source_root.exists():
            print(f"警告：跳过不存在的源目录 {source_root}")
            continue

        # 关键修改：统一基准路径
        base_path = source_root.parent if "lods" in str(source_root) else source_root

        for visual_file in source_root.rglob('*.visual'):
            # 计算相对于原Camoulages目录的路径
            relative_path = visual_file.relative_to(base_path)

            # 构建目标路径（自动排除lods层级）
            dest_path = target_root / relative_path

            # 防止覆盖
            if dest_path in processed_files:
                continue
            processed_files.add(dest_path)

            # 创建目录并复制
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(visual_file, dest_path)
            copied_files += 1
            print(f"已复制 {relative_path}")

    print(f"\n共复制 {copied_files} 个处理后的.visual文件")

if __name__ == "__main__":
    try:
        validate_environment()

        # === 预处理步骤 ===
        print("\n=== 预处理开始 ===")
        safe_clear_directory(TEMP_DIR)
        safe_clear_directory(OUTPUT_DIR)
        cleanup_temp_models()
        delete_lods_folder()
        execute_node_deletion()
        execute_visual_rename()  # 此时处理后的文件生成到 SOURCE_DIR/lods

        # === 旧版打包 ===
        print("\n=== 旧版打包开始 ===")
        execute_geometrypack(GEOMETRYPACK_V1, SOURCE_DIR, TEMP_DIR)

        # === 新版增量更新 ===
        print("\n=== 新版增量更新 ===")
        execute_geometrypack(GEOMETRYPACK_V2, TEMP_DIR, OUTPUT_DIR, ["--update-content"])

        # === Geometry文件处理 ===
        print("\n=== Geometry文件处理 ===")
        handle_geometry_files(OUTPUT_DIR)

        # === 复制处理后的Visual文件 ===
        print("\n=== 复制处理后的Visual文件 ===")
        # 同时处理原目录和lods目录
        copy_processed_visuals(
            source_roots=[SOURCE_DIR, SOURCE_DIR / "lods"],  # 双源目录
            target_root=OUTPUT_DIR
        )

        print(f"\n操作成功完成！最终输出目录：{OUTPUT_DIR.resolve()}")

    except (KeyboardInterrupt, SystemExit):
        print("\n用户中断操作")
        sys.exit(0)