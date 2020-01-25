# Apple Standalone Toolchains
## Background
This tool is supposed provide an API similiar to Android NDK's standalone toolchain creation script.
It is based on [cctools-port](https://github.com/tpoechtrager/cctools-port).
Currently, the script is **highly linux-oriented**.

## Overview
Final output of this tool is a directory (set with `--install-dir`) that contains isolated set of tools that can be used to build binaries for MacOSX / iOS. For example, `clang` is going to be at `<install_dir>/bin/<arch>-apple-darwin11-clang`.

## Dependencies
- Python 3.7+ (with fstrings support)

## Making the toolchain
```bash
$ git clone git@github.com:yuvalino/apple_standalone_toolchains.git
$ cd apple_standalone_toolchains
$ git submodule update --init
$ ./make_standalone_toolchains.py
    --sdk *path to sdk archive or dir*
    --arch *{x86,x86_64,arm,arm64}*
    --install-dir *tools installation dir*

    [--min-version *minimum target macosx/ios version, default 10.6 for macosx and 4.0 for ios*]
    [--clang *clang executable to wrap, default 'clang'*]
    [--clangxx *clang++ executable to wrap, default '(--clang)++'*]

    [-v, -f]

```

Building usually takes 5-10 minutes.
If you want to see some output (else the building process is very non-informative) pass `-v`.

## Known Issues
Due to Apple's current strict limitations:
- `libc++` or any other basic library cannot be statically linked.

## Future Plans
- Especially compiled `libc++` with the latest C++ library features (tuple, optional, etc).
- Perhaps use `llvm-lld` instead of `cctools-port` when TAPI (`.tbd` files) are supported with `llvm`.

