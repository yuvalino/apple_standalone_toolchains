#!/usr/bin/env python3

import os
import shutil
import tarfile
import argparse
import plistlib
import subprocess

ARCHS = [
    'x86',
    'x86_64',
    'arm',
    'arm64',
]

MIN_VERSION = dict(
    iphoneos = '4.0',
    macosx   = '10.5',
)

CLANG_WRAPPER = '''
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int set_compiler_path(char * envar, int maxlen, char ** out_path)
{{
    char exe[1024] = {{0}};
    char * sep = NULL;
    if (-1 == readlink("/proc/self/exe", exe, 1023))
        return 1;
    sep = strrchr(exe, '/');
    if (NULL != sep)
        *sep = 0;
    snprintf(envar, maxlen - 1, "COMPILER_PATH=%s", exe);
    *out_path = envar + strlen("COMPILER_PATH=");
    return 0;
}}

void fromenv(char * out_val, const char * name, char * default_val)
{{
    char * enval = getenv(name);
    strcpy(out_val, ((NULL != enval) ? enval : default_val));
}}

int main(int argc, char * argv[])
{{
    int i = 0;
    int j = 0;
    char ** v = 0;
    char env_compiler[1024] = {{0}};
    char default_sdk_path[1024] = {{0}};
    char sdk_path[1024] = {{0}};
    char arch[128] = {{0}};
    char min_os_version[128] = {{0}};

    char * compiler_path = NULL;

    char * default_args[] = {{
        "{compiler}",
        "-target", "{target_triple}",
        "-isysroot", sdk_path,
        "-arch", "{arch}",
        
        min_os_version,
        "-mlinker-version=450.3"
    }};
    
    char ** args = (char **) calloc(1, (sizeof(char *) * argc) + sizeof(default_args));
    if (NULL == args)
    {{
        fprintf(stderr, "failed to alloc args\\n");
        return 1;
    }}
    
    
    if (0 != set_compiler_path(env_compiler, 1024, &compiler_path))
    {{
        fprintf(stderr, "failed to set compiler path\\n");
        return 1;
    }}

    snprintf(default_sdk_path, 1023, "%s/../sdk", compiler_path);
    fromenv(sdk_path, "{platform_high}_SDK_SYSROOT", default_sdk_path);

    strcpy(min_os_version, "-m{platform_low}-version-min=");
    fromenv(min_os_version + strlen(min_os_version), "{platform_high}_DEPLOYMENT_TARGET", "{default_min_version}");
     
    setenv("CODESIGN_ALLOCATE", "{target_triple}-codesign_allocate", 1);
    setenv("IOS_FAKE_CODE_SIGN", "1", 1);
    setenv("COMPILER_PATH", compiler_path, 1);
    
    for (i = 0; i < sizeof(default_args)/sizeof(default_args[0]); i++)
    {{
        args[i] = default_args[i];
    }}
    for (j = 1; j < argc; j++)
    {{
        args[i + j - 1] = argv[j];
    }}
    execvp("{compiler}", args);
    fprintf(stderr, "error: compiler invoaction failed (%d - %s)\\n", errno, strerror(errno));
}}
'''

def compile_c(c_code):
    wrapper_compiler = subprocess.Popen(
        ['/usr/bin/env', 'cc', '-o', '/dev/stdout', '-x', 'c', '-'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = wrapper_compiler.communicate(c_code.encode())
    if wrapper_compiler.returncode != 0:
        raise ValueError('failed to compiler wrapper:\n{}'.format(stderr.decode('utf-8')))
    return stdout

def mkdir(path, mode=0o777, exist_ok=False, recursive=False):
    if os.path.isdir(path) and exist_ok:
        return
    if recursive:
        os.makedirs(path, mode)
        return
    os.mkdir(path, mode)
    return

def extract(input_path, output_path):
    if os.path.isdir(input_path):
        shutil.copytree(input_path, output_path)
        return
    if tarfile.is_tarfile(input_path):
        with tarfile.open(input_path, 'r:xz') as tar:
            tar.extractall(output_path)
        return
    raise ValueError(f'could not extract "{input_path}"')

def expand_sdk(sdk):
    if 'SDKSettings.plist' in os.listdir(sdk):
        return
    sdk_items = [os.path.join(sdk, x) for x in os.listdir(sdk)]
    sdk_items = [x for x in sdk_items if os.path.isdir(x) and 'SDKSettings.plist' in os.listdir(x)]
    if len(sdk_items) == 0:
        raise ValueError(f'An apple SDK was not found in "{sdk}"')
    if len(sdk_items) > 1:
        raise ValueError(f'Multiple apple SDK candidates found in "{sdk}"')
    sub_sdk = sdk_items[0]
    for item in os.listdir(sub_sdk):
        shutil.move(os.path.join(sub_sdk, item), os.path.join(sdk, item))
    os.rmdir(sub_sdk)

def get_sdk_info(sdk):
    with open(os.path.join(sdk, 'SDKSettings.plist'), 'rb') as reader:
        sdk_settings = plistlib.load(reader)
    return dict(
        name = sdk_settings['CanonicalName'],
        version = sdk_settings['Version'],
        platform = sdk_settings['DefaultProperties']['PLATFORM_NAME'],
    )

def create_apple_toolchain(
    arch,
    input_sdk,
    install_dir,
    
    min_version,
    clang,
    clangxx,
    force,
):
    # Create installation directory, take -f/--force into account
    if os.path.isdir(install_dir):
        if not force:
            raise ValueError(f'installation dir "{install_dir}" already exists (use -f to force)')
        shutil.rmtree(install_dir)
    mkdir(install_dir)

    print(f'creating apple standalone toolchain for arch {arch}')

    # Extract SDK and gather some SDK info
    sdk_dir = os.path.join(install_dir, 'sdk')
    bin_dir = os.path.join(install_dir, 'bin')

    extract(input_sdk, sdk_dir)
    expand_sdk(sdk_dir)
    sdk_info = get_sdk_info(sdk_dir)
    print(f'detected apple SDK for "{sdk_info["name"]}"')
    if not min_version:
        min_version = MIN_VERSION[sdk_info['platform']]
        print(f'defaulting to minimum version {sdk_info["platform"]}{min_version}')

    mkdir(bin_dir)

    target_triple = f'{arch}-darwin-apple'
    wrapper = compile_c(
        CLANG_WRAPPER.format(
            compiler=clang,
            platform_high=sdk_info['platform'].upper(),
            platform_low=sdk_info['platform'].lower(),
            target_triple=target_triple,
            arch=arch,
            default_min_version=min_version,
        )
    )
    wrapper_path = os.path.join(bin_dir, f'{target_triple}-{os.path.basename(clang)}')
    with open(wrapper_path, 'wb') as writer:
        writer.write(wrapper)
        os.chmod(wrapper_path, 0o755)
    

def main():

    arg_parser = argparse.ArgumentParser()

    # Required
    arg_parser.add_argument('--sdk', required=True)
    arg_parser.add_argument('--arch', choices=ARCHS, required=True)
    arg_parser.add_argument('--install-dir', required=True)
    # Optional
    arg_parser.add_argument('--min-version')
    arg_parser.add_argument('--clang', default='clang')
    arg_parser.add_argument('--clangxx', help='takes --clang and adds ++ by default')
    arg_parser.add_argument('-f', '--force', action='store_true')
    
    args = arg_parser.parse_args()

    if not args.clangxx:
        args.clangxx = f'{args.clang}++'

    create_apple_toolchain(
        arch        = args.arch,
        input_sdk   = args.sdk,
        install_dir = args.install_dir,
        min_version = args.min_version,
        clang       = args.clang,
        clangxx     = args.clangxx,
        force       = args.force,
    )

if __name__=='__main__':
    main()
