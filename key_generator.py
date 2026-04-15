#!/usr/bin/env python3
"""
重置码生成器 - 供你使用（不要分发给用户）

使用方法:
    python key_generator.py <机器码>

示例:
    python key_generator.py A3F9-K2M8-PQ7D-RL4N
"""

import sys
from license_manager import LicenseManager


def main():
    if len(sys.argv) < 2:
        print("使用方法: python key_generator.py <机器码>")
        print("示例: python key_generator.py A3F9-K2M8-PQ7D-RL4N")
        print()
        print("注意: 需要 private_key.txt 文件存在")
        sys.exit(1)

    machine_code = sys.argv[1].strip().upper()

    # 验证格式
    if len(machine_code.replace('-', '')) != 16:
        print("错误: 机器码格式不正确，应为16位字符（如 A3F9-K2M8-PQ7D-RL4N）")
        sys.exit(1)

    manager = LicenseManager()

    # 确保私钥存在
    manager.ensure_private_key()

    # 生成重置码
    reset_code = manager.generate_reset_code(machine_code)

    print()
    print("=" * 60)
    print("           重置码生成成功")
    print("=" * 60)
    print()
    print(f"机器码: {machine_code}")
    print(f"重置码: {reset_code}")
    print()
    print("=" * 60)
    print("请将此重置码发送给用户")
    print("用户需要在程序提示时输入此重置码")
    print("=" * 60)


if __name__ == "__main__":
    main()
