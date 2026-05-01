#!/usr/bin/env python3
import sys
from license_manager import LicenseManager


def main():
    if len(sys.argv) < 2:
        print("使用方法: python key_generator_v1_1.py <1.1机器码>")
        sys.exit(1)

    machine_code = sys.argv[1].strip().upper()
    if not machine_code.startswith('V11-') or len(machine_code.split('-')) != 5:
        print("错误: 1.1 机器码格式不正确，应为 V11-XXXX-XXXX-XXXX-XXXX")
        sys.exit(1)

    manager = LicenseManager()
    manager.ensure_private_key()
    reset_code = manager.generate_reset_code_v1_1(machine_code)

    print()
    print("=" * 60)
    print("        1.1 解锁码生成成功")
    print("=" * 60)
    print()
    print(f"机器码: {machine_code}")
    print(f"解锁码: {reset_code}")
    print()
    print("=" * 60)
    print("请将此解锁码发送给 1.1 用户")
    print("=" * 60)


if __name__ == "__main__":
    main()
