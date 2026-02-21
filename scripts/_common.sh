#!/usr/bin/env sh
# 公共环境变量和工具函数，供 xgate/xtest 等脚本 source 使用

export UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-.uv-tools}"

# 检查参数中是否包含 -h 或 --help，若包含则打印帮助信息并退出
# 用法: check_help "$@"  (需在调用前定义 show_help 函数)
check_help() {
    for arg in "$@"; do
        case "$arg" in
            -h|--help)
                show_help
                exit 0
                ;;
        esac
    done
}

# 执行命令，若因参数错误失败则追加打印帮助信息
# 用法: run_or_help <错误退出码> <命令...>
#   错误退出码: 匹配该退出码时追加帮助 (argparse=2, pytest=4)
# 需在调用前定义 show_help 函数
run_or_help() {
    error_code="$1"
    shift

    set +e
    "$@"
    rc=$?
    set -e

    if [ "$rc" = "$error_code" ]; then
        echo "" >&2
        echo "========================================" >&2
        show_help >&2
        exit "$rc"
    fi

    exit "$rc"
}
