import subprocess
import json
import logging
import os
import urllib.parse
import zipfile
import tarfile
import shutil
import platform
import argparse
import multiprocessing
import re
from typing import Callable, Optional, List, Union, Dict
if platform.system() == 'Windows':
    import winreg


logging.basicConfig(level=logging.DEBUG)


class ChangeDirectory(object):
    def __init__(self, cwd):
        self._cwd = cwd

    def __enter__(self):
        self._old_cwd = os.getcwd()
        logging.debug(f'pushd {self._cwd}')
        os.chdir(self._cwd)

    def __exit__(self, exctype, excvalue, trace):
        logging.debug(f'popd {self._old_cwd}')
        os.chdir(self._old_cwd)
        return False


def cd(cwd):
    return ChangeDirectory(cwd)


def cmd(args, **kwargs):
    logging.debug(f'+{args} {kwargs}')
    if 'check' not in kwargs:
        kwargs['check'] = True
    if 'resolve' in kwargs:
        resolve = kwargs['resolve']
        del kwargs['resolve']
    else:
        resolve = True
    if resolve:
        args = [shutil.which(args[0]), *args[1:]]
    return subprocess.run(args, **kwargs)


def rm_rf(path: str):
    if not os.path.exists(path):
        return
    if os.path.isfile(path) or os.path.islink(path):
        os.remove(path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def mkdir_p(path: str):
    os.makedirs(path, exist_ok=True)


if platform.system() == 'Windows':
    PATH_SEPARATOR = ';'
else:
    PATH_SEPARATOR = ':'


def add_path(path: str, is_after=False):
    if 'PATH' not in os.environ:
        os.environ['PATH'] = path
        return

    if is_after:
        os.environ['PATH'] = os.environ['PATH'] + PATH_SEPARATOR + path
    else:
        os.environ['PATH'] = path + PATH_SEPARATOR + os.environ['PATH']


def download(url: str, output_dir: Optional[str] = None, filename: Optional[str] = None) -> str:
    if filename is None:
        output_path = urllib.parse.urlparse(url).path.split('/')[-1]
    else:
        output_path = filename

    if output_dir is not None:
        output_path = os.path.join(output_dir, output_path)

    if os.path.exists(output_path):
        return output_path

    try:
        if shutil.which('curl') is not None:
            cmd(["curl", "-fLo", output_path, url])
        else:
            cmd(["wget", "-cO", output_path, url])
    except Exception:
        # ゴミを残さないようにする
        if os.path.exists(output_path):
            os.remove(output_path)
        raise

    return output_path


def read_version_file(path: str) -> Dict[str, str]:
    versions = {}

    lines = open(path).readlines()
    for line in lines:
        line = line.strip()

        # コメント行
        if line[:1] == '#':
            continue

        # 空行
        if len(line) == 0:
            continue

        [a, b] = map(lambda x: x.strip(), line.split('=', 2))
        versions[a] = b.strip('"')

    return versions


# dir 以下にある全てのファイルパスを、dir2 からの相対パスで返す
def enum_all_files(dir, dir2):
    for root, _, files in os.walk(dir):
        for file in files:
            yield os.path.relpath(os.path.join(root, file), dir2)


def get_depot_tools(source_dir, enable_fetch=False):
    dir = os.path.join(source_dir, 'depot_tools')
    if os.path.exists(dir):
        if enable_fetch:
            cmd(['git', 'fetch'])
            cmd(['git', 'checkout', '-f', 'origin/HEAD'])
    else:
        cmd(['git', 'clone', 'https://chromium.googlesource.com/chromium/tools/depot_tools.git', dir])
    return dir


PATCH_INFO = {
    'libjpeg_turbo_mangle_jpeg_names.patch': (1, ['third_party', 'libjpeg_turbo']),
    '4k.patch': (2, []),
    'macos_h264_encoder.patch': (2, []),
}

PATCHES = {
    'windows': [
        '4k.patch',
        'windows_add_deps.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'macos_x86_64': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'macos_arm64': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ios': [
        'add_dep_zlib.patch',
        '4k.patch',
        'macos_h264_encoder.patch',
        'macos_screen_capture.patch',
        'macos_simulcast.patch',
        'ios_simulcast.patch',
        'ssl_verify_callback_with_native_handle.patch',
    ],
    'android': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'android_webrtc_version.patch',
        'android_fixsegv.patch',
        'android_simulcast.patch',
    ],
    'raspberry-pi-os_armv6': [
        'nacl_armv6_2.patch',
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'raspberry-pi-os_armv7': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'raspberry-pi-os_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-18.04_armv8': [
        'add_dep_zlib.patch',
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-18.04_x86_64': [
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ],
    'ubuntu-20.04_x86_64': [
        '4k.patch',
        'ssl_verify_callback_with_native_handle.patch',
        'libjpeg_turbo_mangle_jpeg_names.patch',
    ]
}

def apply_patch(patch, dir, depth):
    opts = [f'-p{depth}']
    if platform.system() == 'Windows':
        opts += ['--ignore-space-change', '--ignore-whitespace', '--whitespace=nowarn']
    with cd(dir):
        cmd(['git', 'apply'] + opts + [patch])


def get_webrtc(source_dir, patch_dir, version, target, force_fetch=False, enable_fetch=False):
    webrtc_dir = os.path.join(source_dir, 'webrtc')
    if force_fetch:
        rm_rf(webrtc_dir)

    mkdir_p(webrtc_dir)
    if not os.path.exists(os.path.join(webrtc_dir, 'src')):
        with cd(webrtc_dir):
            if target == 'android':
                with open('.gclient', 'w') as f:
                    f.write("target_os = [ 'android' ]\n")
            if target == 'ios':
                with open('.gclient', 'w') as f:
                    f.write("target_os = [ 'ios' ]\n")
            cmd(['gclient'])
            cmd(['fetch', 'webrtc'])
            enable_fetch = True

    src_dir = os.path.join(webrtc_dir, 'src')
    if enable_fetch:
        with cd(src_dir):
            cmd(['git', 'checkout', '-f', version])
            cmd(['gclient', 'sync', '-D', '--force', '--reset', '--with_branch_heads'])
            for patch in PATCHES[target]:
                depth, dirs = PATCH_INFO.get(patch, (1, ['.']))
                dir = os.path.join(src_dir, *dirs)
                apply_patch(os.path.join(patch_dir, patch), dir, depth)


def git_get_url_and_revision(dir):
    with cd(dir):
        rev = cmd(['git', 'rev-parse', 'HEAD'], capture_output=True, encoding='utf-8').stdout.strip()
        url = cmd(['git', 'remote', 'get-url', 'origin'], capture_output=True, encoding='utf-8').stdout.strip()
        return url, rev


def build_webrtc_ios(source_dir, build_dir, debug=False, gen=False, no_build=False):
    pass


def build_webrtc_android(source_dir, build_dir, debug=False, gen=False, no_build=False):
    pass


def build_webrtc(source_dir, build_dir, target: str, version_info, debug=False, gen=False, no_build=False):
    # ビルド
    if not os.path.exists(os.path.join(build_dir, 'args.gn')) or gen:
        gn_args = [
            f"is_debug={'true' if debug else 'false'}",
            "rtc_include_tests=false",
            "rtc_use_h264=false",
            "is_component_build=false",
            "use_rtti=true",
        ]
        if target == 'windows':
            gn_args += [
                "use_custom_libcxx=false",
            ]
        elif target.startswith('macos'):
            gn_args += [
                'target_os="mac"',
                f'target_cpu="{"x64" if target == "macos_x86_64" else "arm64"}"',
                'mac_deployment_target="10.11"',
                'enable_stripping=true',
                'enable_dsyms=true',
                'rtc_build_examples=false',
                'rtc_libvpx_build_vp9=true',
                'rtc_enable_symbol_export=true',
                'rtc_enable_objc_symbol_export=false',
                'libcxx_abi_unstable=false',
            ]
        elif target == 'ubuntu-20.04_x86_64':
            gn_args += [
                'target_os="linux"',
                'rtc_use_pipewire=false',
            ]

        with cd(os.path.join(source_dir, 'webrtc', 'src')):
            cmd(['gn', 'gen', build_dir, '--args=' + ' '.join(gn_args)])

    if no_build:
        return

    cmd(['ninja', '-C', build_dir])
    if target == 'windows':
        pass
    elif target.startswith('macos'):
        cmd(['ninja', '-C', build_dir,
            'builtin_audio_decoder_factory',
            'default_task_queue_factory',
            'native_api',
            'default_codec_factory_objc',
            'peerconnection',
            'videocapture_objc',
            'mac_framework_objc',
        ])
        ar = '/usr/bin/ar'
    else:
        ar = os.path.join(source_dir, 'webrtc/src/third_party/llvm-build/Release+Asserts/bin/llvm-ar')

    # ar で libwebrtc.a を生成する
    if target != 'windows':
        r = cmd(['find', '.', '-name', '*.o'], capture_output=True, encoding='utf-8')
        files = r.stdout.splitlines()
        cmd([ar, '-rc', os.path.join(build_dir, 'libwebrtc.a'), *files])

    # macOS の場合は WebRTC.framework に追加情報を入れる
    if target.startswith('macos'):
        info = {}
        info['branch'] = 'M' + version_info['WEBRTC_VERSION'].split('.')[0]
        info['commit'] = version_info['WEBRTC_VERSION'].split('.')[2]
        info['revision'] = version_info['WEBRTC_COMIT']
        info['maint'] = version_info['WEBRTC_BUILD_VERSION'].split('.')[3]
        with open(os.path.join(build_dir, 'WebRTC.framework', 'Resources', 'build_info.json'), 'w') as f:
            f.write(json.dumps(info, indent=4))

        # Info.plistの編集(tools_wertc/ios/build_ios_libs.py内の処理を踏襲)
        info_plist_path = os.path.join(build_dir, 'WebRTC.framework', 'Resources', 'Info.plist')
        ver = cmd(['/usr/libexec/PlistBuddy', '-c', 'Print :CFBundleShortVersionString', info_plist_path], resolve=False, capture_output=True, encoding='utf-8').stdout.strip()
        cmd(['/usr/libexec/PlistBuddy', '-c', f'Set :CFBundleVersion {ver}.0', info_plist_path], resolve=False, encoding='utf-8')
        cmd(['plutil', '-convert', 'binary1', info_plist_path])

        # xcframeworkの作成
        rm_rf(os.path.join(build_dir, 'WebRTC.xcframework'))
        cmd(['xcodebuild', '-create-xcframework',
            '-framework', os.path.join(build_dir, 'WebRTC.framework'),
            '-debug-symbols', os.path.join(build_dir, 'WebRTC.dSYM'),
            '-output', os.path.join(build_dir, 'WebRTC.xcframework')])



BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def main():
    """
    メモ

    ビルド方針:
        - 引数無しで実行した場合、ビルドのみ行う
            - もし必要とするファイルが存在しなければ取得や生成を行うが、新しい更新があるかどうかは確認しない。
        - 各種引数を渡すと、更新や生成を行う。
            - --fetch-depot-tools - depot_tools を更新する
            - --fetch - WebRTC のソースを更新する
                - 既存の変更は全て破棄され、パッチのみが当たった状態になる
            - --fetch-force - 既存の WebRTC のソースを捨てて新しく取得し直す
                - どうしてもうまくいかなくなった時に使う。基本的には不要なはず
            - --gen - gn gen をやり直す
            - --no-build - ビルドを行わない
    """
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers()
    bp = sp.add_parser('build')
    bp.set_defaults(op='build')
    bp.add_argument("target", choices=['windows', 'macos_x86_64', 'macos_arm64', 'ubuntu-20.04_x86_64'])
    bp.add_argument("--debug", action='store_true')
    bp.add_argument('--fetch-depot-tools', action='store_true')
    bp.add_argument("--fetch", action='store_true')
    bp.add_argument("--fetch-force", action='store_true')
    bp.add_argument("--gen", action='store_true')
    bp.add_argument("--no-build", action='store_true')
    pp = sp.add_parser('package')
    pp.set_defaults(op='package')
    pp.add_argument("target", choices=['windows', 'macos_x86_64', 'macos_arm64', 'ubuntu-20.04_x86_64'])
    args = parser.parse_args()

    if not hasattr(args, 'op'):
        parser.error('Required subcommand')

    if args.target == 'windows':
        # $SOURCE_DIR の下に置きたいが、webrtc のパスが長すぎると動かない問題と、
        # GitHub Actions の D:\ の容量が少なくてビルド出来ない問題があるので
        # このパスにソースを配置する
        source_dir = 'C:\\webrtc'
        # また、WebRTC のビルドしたファイルは同じドライブに無いといけないっぽいので、
        # BUILD_DIR とは別で用意する
        base_build_dir = f'C:\\webrtc-build'
    else:
        source_dir = os.path.join(BASE_DIR, '_source', args.target)
        base_build_dir = os.path.join(BASE_DIR, '_build', args.target)
    package_dir = os.path.join(BASE_DIR, '_package', args.target)

    mkdir_p(source_dir)
    mkdir_p(package_dir)
    patch_dir = os.path.join(BASE_DIR, 'patches')

    if args.target == 'windows':
        # Windows の WebRTC ビルドに必要な環境変数の設定
        download("https://github.com/microsoft/vswhere/releases/download/2.8.4/vswhere.exe", base_build_dir)
        r = cmd([os.path.join(base_build_dir, 'vswhere.exe'), '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], capture_output=True, encoding='utf-8')
        path = r.stdout.strip()
        if len(path) == 0:
            raise Exception('Visual Studio not installed')
        path = os.path.join(path, 'Common7', 'Tools', 'VsDevCmd.bat')
        r = cmd(['cmd', '/c', f'{path}', '&&', 'set'], capture_output=True, encoding='utf-8')
        for m in re.finditer(r'(\w+)=(.*)', r.stdout):
            os.environ[m.group(1)] = m.group(2)

        os.environ['GYP_MSVS_VERSION'] = "2019"
        os.environ['DEPOT_TOOLS_WIN_TOOLCHAIN'] = "0"
        os.environ['PYTHONIOENCODING'] = "utf-8"

    version_file = read_version_file('VERSION')

    if args.op == 'build':
        configuration = 'debug' if args.debug else 'release'
        build_dir = os.path.join(base_build_dir, configuration)
        mkdir_p(build_dir)

        with cd(BASE_DIR):
            dir = get_depot_tools(source_dir, enable_fetch=args.fetch_depot_tools)
            add_path(dir)

            # ソース取得
            get_webrtc(source_dir, patch_dir, version_file['WEBRTC_COMMIT'], args.target, enable_fetch=args.fetch, force_fetch=args.fetch_force)

            # ビルド
            build_webrtc_args = {
                'source_dir': source_dir,
                'build_dir': build_dir,
                'debug': args.debug,
                'gen': args.gen,
                'no_build': args.no_build,
            }
            # 特殊すぎるので別枠行き
            if args.target == 'ios':
                build_webrtc_ios(**build_webrtc_args)
            elif args.target == 'android':
                build_webrtc_android(**build_webrtc_args)
            else:
                build_webrtc(target=args.target, version_info=version_file, **build_webrtc_args)

    if args.op == 'package':
        with cd(BASE_DIR):
            source_webrtc_dir = os.path.join(source_dir, 'webrtc', 'src')
            package_webrtc_dir = os.path.join(package_dir, 'webrtc')
            rm_rf(package_webrtc_dir)
            mkdir_p(package_webrtc_dir)

            # ライセンス生成
            CONFIGURATIONS = ['debug', 'release']
            dirs = map(lambda x: os.path.join(base_build_dir, x), CONFIGURATIONS)
            cmd(['python3', os.path.join(source_webrtc_dir, 'tools_webrtc', 'libs', 'generate_licenses.py'),
                '--target', ':webrtc', package_webrtc_dir, *dirs])
            os.rename(os.path.join(package_webrtc_dir, 'LICENSE.md'), os.path.join(package_webrtc_dir, 'NOTICE'))

            # ヘッダーファイルをコピー
            if platform.system() == 'Windows':
                # robocopy の戻り値は特殊なので、check=False にしてうまくエラーハンドリングする
                # https://docs.microsoft.com/ja-jp/troubleshoot/windows-server/backup-and-storage/return-codes-used-robocopy-utility
                r = cmd(['robocopy', source_webrtc_dir, os.path.join(package_webrtc_dir, 'include'), '*.h', '*.hpp', '/S', '/NP', '/NFL', '/NDL'], check=False)
                if r.returncode >= 4:
                    raise Exception('robocopy failed')
            else:
                mkdir_p(os.path.join(package_webrtc_dir, 'include'))
                cmd(['rsync', '-amv', '--include=*/', '--include=*.h', '--include=*.hpp', '--exclude=*', os.path.join(source_webrtc_dir, '.'), os.path.join(package_webrtc_dir, 'include', '.')])

            # バージョン情報
            lines = []
            GIT_INFOS = [
                (['.'], ''),
                (['build'], 'BUILD'),
                (['buildtools'], 'BUILDTOOLS'),
                (['buildtools', 'third_party', 'libc++', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBCXX_TRUNK'),
                (['buildtools', 'third_party', 'libc++abi', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBCXXABI_TRUNK'),
                (['buildtools', 'third_party', 'libunwind', 'trunk'], 'BUILDTOOLS_THIRD_PARTY_LIBUNWIND_TRUNK'),
                (['third_party'], 'THIRD_PARTY'),
                (['tools'], 'TOOLS'),
            ]
            for dirs, name in GIT_INFOS:
                url, rev = git_get_url_and_revision(os.path.join(source_webrtc_dir, *dirs))
                prefix = 'WEBRTC_SRC_' + (f'{name}_' if len(name) != 0 else '')
                lines += [
                    f'{prefix}URL={url}',
                    f'{prefix}COMMIT={rev}',
                ]
            shutil.copyfile('VERSION', os.path.join(package_webrtc_dir, 'VERSIONS'))
            with open(os.path.join(package_webrtc_dir, 'VERSIONS'), 'ab') as f:
                f.writelines(map(lambda x: (x + '\n').encode('utf-8'), lines))

            # ライブラリ
            for configuration in CONFIGURATIONS:
                mkdir_p(os.path.join(package_webrtc_dir, configuration))
                if args.target == 'windows':
                    files = [
                        (['obj', 'webrtc.lib'], ['webrtc.lib']),
                    ]
                elif args.target.startswith('macos'):
                    files = [
                        (['obj', 'libwebrtc.a'], ['libwebrtc.a']),
                        (['WebRTC.xcframework'], ['WebRTC.xcframework']),
                    ]
                else:
                    files = [
                        (['obj', 'libwebrtc.a'], ['libwebrtc.a']),
                    ]
                for src, dst in files:
                    shutil.copy2(os.path.join(base_build_dir, configuration, *src), os.path.join(package_webrtc_dir, configuration, *dst))

            # 圧縮
            with cd(package_dir):
                if args.target == 'windows':
                    with zipfile.ZipFile('webrtc.zip', 'w') as f:
                        for file in enum_all_files('webrtc', '.'):
                            f.write(filename=file, arcname=file)
                else:
                    with tarfile.open('webrtc.tar.gz', 'w:gz') as f:
                        for file in enum_all_files('webrtc', '.'):
                            f.add(name=file, arcname=file)


if __name__ == '__main__':
    main()