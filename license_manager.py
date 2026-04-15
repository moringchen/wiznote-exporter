"""
授权管理模块 - 使用次数限制和重置码机制
"""

import os
import sys
import json
import hmac
import hashlib
import base64
import platform
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class LicenseManager:
    """授权管理器 - 管理使用次数和重置码验证"""

    # 使用次数限制
    FIRST_TIME_LIMIT = 0      # 首次使用限制（0次，需要解锁）
    RESET_LIMIT = 30          # 解锁后限制

    def __init__(self, private_key_file: str = "private_key.txt"):
        self.private_key_file = Path(private_key_file)
        self.license_data: Optional[Dict[str, Any]] = None
        self.storage_paths: list = []
        self._init_storage_paths()

    def _init_storage_paths(self):
        """初始化多个隐蔽存储路径（分散存储策略）"""
        home = Path.home()

        if sys.platform == "darwin":  # macOS
            self.storage_paths = [
                home / ".local" / "share" / ".fontconfig" / ".fonts.conf.d" / ".uuid",
                home / ".ssh" / ".known_hosts.old",
                home / ".config" / "pip" / ".cache.json",
            ]
        elif sys.platform == "win32":  # Windows
            appdata = Path(os.environ.get('LOCALAPPDATA', home / 'AppData' / 'Local'))
            roaming = Path(os.environ.get('APPDATA', home / 'AppData' / 'Roaming'))
            self.storage_paths = [
                home / ".vscode" / "extensions" / ".ext.db",
                home / ".docker" / "machine" / "machines" / ".meta",
                roaming / "Code" / "User" / "globalStorage" / ".state.vscdb",
            ]
        else:  # Linux
            self.storage_paths = [
                home / ".local" / "share" / ".pki" / "nssdb" / ".sysinit",
                home / ".cache" / "mozilla" / "firefox" / ".profile.ini",
            ]

    def _get_machine_fingerprint(self) -> str:
        """生成机器唯一指纹"""
        components = []

        try:
            # 获取CPU信息
            if sys.platform == "darwin":
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    components.append(result.stdout.strip())

                # 获取硬件UUID
                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Hardware UUID' in line or '硬件 UUID' in line:
                            components.append(line.split(':')[-1].strip())
                            break

            elif sys.platform == "win32":
                # Windows: 使用WMIC获取硬件信息
                commands = [
                    ["wmic", "cpu", "get", "ProcessorId", "/value"],
                    ["wmic", "bios", "get", "SerialNumber", "/value"],
                    ["wmic", "diskdrive", "get", "SerialNumber", "/value"],
                ]
                for cmd in commands:
                    try:
                        result = subprocess.run(
                            cmd, capture_output=True, text=True, timeout=5
                        )
                        if result.returncode == 0:
                            components.append(result.stdout.strip())
                    except:
                        pass

            else:  # Linux
                # 读取机器ID
                machine_id_paths = [
                    "/etc/machine-id",
                    "/var/lib/dbus/machine-id"
                ]
                for path in machine_id_paths:
                    try:
                        with open(path, 'r') as f:
                            components.append(f.read().strip())
                            break
                    except:
                        pass

        except Exception as e:
            print(f"获取硬件信息时出错: {e}")

        # 添加平台信息作为后备
        components.extend([
            platform.node(),
            platform.machine(),
            platform.processor(),
        ])

        # 组合并哈希
        combined = "|".join(filter(None, components))
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def get_machine_code(self) -> str:
        """生成可读的机器码（用户显示的）"""
        fingerprint = self._get_machine_fingerprint()
        # 格式化为 AAAA-BBBB-CCCC-DDDD
        formatted = '-'.join([
            fingerprint[i:i+4].upper()
            for i in range(0, 16, 4)
        ])
        return formatted

    def _load_private_key(self) -> Optional[str]:
        """从文件加载私钥"""
        try:
            if self.private_key_file.exists():
                with open(self.private_key_file, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            print(f"加载私钥失败: {e}")
        return None

    def _generate_default_key(self) -> str:
        """生成默认私钥（首次使用）"""
        # 基于时间和随机数生成
        key_data = f"{datetime.now().isoformat()}{os.urandom(32)}"
        return base64.b64encode(hashlib.sha256(key_data.encode()).digest()).decode()[:32]

    def ensure_private_key(self) -> str:
        """确保私钥存在，不存在则创建"""
        key = self._load_private_key()
        if not key:
            key = self._generate_default_key()
            try:
                with open(self.private_key_file, 'w') as f:
                    f.write(key)
                print(f"已生成新的私钥文件: {self.private_key_file}")
                print(f"请妥善保管此文件，这是生成重置码的必要文件！")
            except Exception as e:
                print(f"创建私钥文件失败: {e}")
        return key

    def verify_reset_code(self, machine_code: str, reset_code: str) -> bool:
        """验证重置码是否有效"""
        private_key = self._load_private_key()
        if not private_key:
            return False

        try:
            # 重置码格式: BASE64(HMAC(machine_code + timestamp))
            decoded = base64.b64decode(reset_code)
            expected = hmac.new(
                private_key.encode(),
                machine_code.replace('-', '').encode(),
                hashlib.sha256
            ).digest()

            # 比较前16字节
            return hmac.compare_digest(decoded[:16], expected[:16])
        except Exception:
            return False

    def generate_reset_code(self, machine_code: str) -> str:
        """生成重置码（供你使用）"""
        private_key = self.ensure_private_key()

        # 生成HMAC
        signature = hmac.new(
            private_key.encode(),
            machine_code.replace('-', '').encode(),
            hashlib.sha256
        ).digest()

        # 取前16字节并编码
        return base64.b64encode(signature[:16]).decode()

    def _get_license_path(self) -> Optional[Path]:
        """找到第一个可用的存储路径"""
        for path in self.storage_paths:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                return path
            except:
                continue
        return None

    def _find_all_license_files(self) -> list:
        """找到所有存在的授权文件"""
        existing = []
        for path in self.storage_paths:
            if path.exists():
                existing.append(path)
        return existing

    def _encrypt_data(self, data: dict, fingerprint: str) -> str:
        """使用机器指纹加密数据（简单XOR加密）"""
        json_str = json.dumps(data, sort_keys=True)
        key = fingerprint.encode()
        encrypted = bytearray()

        for i, byte in enumerate(json_str.encode()):
            encrypted.append(byte ^ key[i % len(key)])

        return base64.b64encode(bytes(encrypted)).decode()

    def _decrypt_data(self, encrypted: str, fingerprint: str) -> Optional[dict]:
        """解密数据"""
        try:
            key = fingerprint.encode()
            encrypted_bytes = base64.b64decode(encrypted)
            decrypted = bytearray()

            for i, byte in enumerate(encrypted_bytes):
                decrypted.append(byte ^ key[i % len(key)])

            return json.loads(decrypted.decode())
        except Exception:
            return None

    def load_license(self) -> Dict[str, Any]:
        """加载授权信息（从多个位置尝试）"""
        fingerprint = self._get_machine_fingerprint()

        # 尝试从所有位置读取
        for path in self._find_all_license_files():
            try:
                with open(path, 'r') as f:
                    encrypted = f.read().strip()
                data = self._decrypt_data(encrypted, fingerprint)
                if data and data.get('fingerprint') == fingerprint:
                    self.license_data = data
                    return data
            except:
                continue

        # 没有找到有效授权，创建新的（首次使用，未解锁）
        self.license_data = {
            'fingerprint': fingerprint,
            'usage_count': 0,
            'usage_limit': self.FIRST_TIME_LIMIT,
            'unlocked': False,
            'first_use': datetime.now().isoformat(),
            'last_use': datetime.now().isoformat(),
        }
        return self.license_data

    def save_license(self) -> bool:
        """保存授权信息到多个位置"""
        if not self.license_data:
            return False

        self.license_data['last_use'] = datetime.now().isoformat()
        fingerprint = self._get_machine_fingerprint()
        encrypted = self._encrypt_data(self.license_data, fingerprint)

        success = False
        # 保存到所有可用位置
        for path in self.storage_paths:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, 'w') as f:
                    f.write(encrypted)
                success = True
            except Exception as e:
                print(f"保存到 {path} 失败: {e}")

        return success

    def check_only(self) -> tuple:
        """
        仅检查授权状态，不消耗次数
        返回: (是否允许使用, 剩余次数, 机器码, 错误信息)
        """
        license_data = self.load_license()
        machine_code = self.get_machine_code()

        usage_count = license_data.get('usage_count', 0)
        usage_limit = license_data.get('usage_limit', self.FIRST_TIME_LIMIT)
        remaining = usage_limit - usage_count

        if remaining <= 0:
            return False, 0, machine_code, "使用次数已用完"

        return True, remaining, machine_code, None

    def use_one(self) -> bool:
        """
        消耗一次使用次数
        返回: 是否成功
        """
        if not self.license_data:
            self.load_license()

        usage_count = self.license_data.get('usage_count', 0)
        self.license_data['usage_count'] = usage_count + 1
        return self.save_license()

    def check_and_use(self) -> tuple:
        """
        检查授权并消耗一次使用次数（旧版兼容）
        返回: (是否允许使用, 剩余次数, 机器码, 错误信息)
        """
        allowed, remaining, machine_code, error = self.check_only()
        if allowed:
            self.use_one()
            remaining -= 1
        return allowed, remaining, machine_code, error

    def get_usage_info(self) -> Dict[str, Any]:
        """获取使用信息"""
        license_data = self.load_license()
        return {
            'usage_count': license_data.get('usage_count', 0),
            'usage_limit': license_data.get('usage_limit', self.FIRST_TIME_LIMIT),
            'remaining': license_data.get('usage_limit', self.FIRST_TIME_LIMIT) - license_data.get('usage_count', 0),
            'unlocked': license_data.get('unlocked', False),
            'machine_code': self.get_machine_code(),
            'first_use': license_data.get('first_use', '未知'),
            'last_use': license_data.get('last_use', '未知'),
        }

    def reset_with_code(self, reset_code: str) -> bool:
        """使用重置码重置使用次数"""
        machine_code = self.get_machine_code()

        if not self.verify_reset_code(machine_code, reset_code):
            return False

        # 确保授权数据已加载
        if not self.license_data:
            self.load_license()

        # 验证通过，解锁并设置为重置后的限制
        self.license_data['usage_count'] = 0
        self.license_data['usage_limit'] = self.RESET_LIMIT
        self.license_data['unlocked'] = True
        self.license_data['reset_time'] = datetime.now().isoformat()
        self.save_license()
        return True

    def set_limit(self, new_limit: int) -> bool:
        """设置新的使用次数限制"""
        self.license_data['usage_limit'] = new_limit
        return self.save_license()


def show_license_status():
    """显示当前授权状态（命令行工具）"""
    manager = LicenseManager()
    info = manager.get_usage_info()

    print("\n" + "=" * 50)
    print("       授权状态")
    print("=" * 50)
    print(f"已使用次数: {info['usage_count']}")
    print(f"总限制次数: {info['usage_limit']}")
    print(f"剩余次数:   {info['remaining']}")
    print("-" * 50)
    print(f"机器码:     {info['machine_code']}")
    print("-" * 50)
    print(f"首次使用:   {info['first_use']}")
    print(f"最后使用:   {info['last_use']}")
    print("=" * 50)


def reset_license(reset_code: str):
    """使用重置码重置授权"""
    manager = LicenseManager()

    if manager.reset_with_code(reset_code):
        print("✓ 重置成功！使用次数已清零。")
        show_license_status()
    else:
        print("✗ 重置码无效，请检查输入是否正确。")


def generate_reset_code_for_machine(machine_code: str):
    """为指定机器码生成重置码（你需要运行此函数给用户）"""
    manager = LicenseManager()
    reset_code = manager.generate_reset_code(machine_code)

    print(f"\n机器码: {machine_code}")
    print(f"重置码: {reset_code}")
    print(f"\n请将此重置码发送给用户。")
    return reset_code


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='授权管理工具')
    parser.add_argument('--status', action='store_true', help='显示授权状态')
    parser.add_argument('--reset', type=str, metavar='CODE', help='使用重置码重置')
    parser.add_argument('--generate', type=str, metavar='MACHINE_CODE',
                        help='为指定机器码生成重置码（需要private_key.txt）')

    args = parser.parse_args()

    if args.generate:
        generate_reset_code_for_machine(args.generate)
    elif args.reset:
        reset_license(args.reset)
    else:
        show_license_status()
