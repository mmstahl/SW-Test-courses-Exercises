#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/repo}"
OUT_DIR="${OUT_DIR:-/out}"
PY_VERSION="${PY_VERSION:-3.9.13}"
PY_MINOR="${PY_VERSION%.*}"
BUILD_TARGET="${BUILD_TARGET:-all}"

mkdir -p "$OUT_DIR"
if [[ -z "${OUT_DIR}" || "${OUT_DIR}" == "/" ]]; then
    echo "Refusing to clear OUT_DIR='${OUT_DIR}'" >&2
    exit 2
fi
find "$OUT_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

export WINEDEBUG=-all
export WINEPREFIX=/root/.wine

wineboot --init >/dev/null 2>&1
mkdir -p /root/.wine/drive_c/py
cd /root/.wine/drive_c/py

curl -L --fail "https://www.python.org/ftp/python/${PY_VERSION}/python-${PY_VERSION}-embed-amd64.zip" -o /tmp/python-embed-amd64.zip
unzip -q -o /tmp/python-embed-amd64.zip

pth_file="$(find . -maxdepth 1 -name 'python3*._pth' -print -quit)"
if [[ -z "$pth_file" ]]; then
    echo "Could not locate python embed ._pth file under $(pwd)" >&2
    exit 1
fi
sed -i 's/^#import site/import site/' "$pth_file"
grep -Fq 'Lib\\site-packages' "$pth_file" || printf 'Lib\\site-packages\n' >> "$pth_file"

curl -L --fail "https://bootstrap.pypa.io/pip/${PY_MINOR}/get-pip.py" -o /tmp/get-pip.py
wine 'C:\py\python.exe' /tmp/get-pip.py >/dev/null
wine 'C:\py\python.exe' -m pip install --quiet pyinstaller

build_exe() {
    local source_path="$1"
    local exe_name="$2"
    local output_dir="$3"
    local source_dir="$(dirname "$source_path")"
    local source_file="$(basename "$source_path")"

    echo "Building ${exe_name}.exe"
    mkdir -p "$OUT_DIR/$output_dir"
    cd "$REPO_DIR/$source_dir"
    wine 'C:\py\python.exe' -m PyInstaller --onefile --console \
        --name "$exe_name" \
        --distpath /tmp/pyi-dist \
        --workpath /tmp/pyi-build \
        --specpath /tmp/pyi-spec \
        "$source_file"
    cp "/tmp/pyi-dist/${exe_name}.exe" "$OUT_DIR/$output_dir/${exe_name}.exe"
    rm -rf /tmp/pyi-dist /tmp/pyi-build /tmp/pyi-spec
}

build_target() {
    case "$1" in
        transform_obj)
            build_exe "03 EP class activity/dev/transform_obj.py" "transform_obj" "03 EP class activity"
            ;;
        check_age.v99)
            build_exe "04 BV class activity/dev/check_age.v99.py" "check_age.v99" "04 BV class activity"
            ;;
        check_age.v100)
            build_exe "04 BV class activity/dev/check_age.v100.py" "check_age.v100" "04 BV class activity"
            ;;
        triage_rules)
            build_exe "05.1 Decision tables activity/dev/triage_rules.py" "triage_rules" "05.1 Decision tables activity"
            ;;
        trace_it)
            build_exe "06.1 State machine activity/dev/trace_it.py" "trace_it" "06.1 State machine activity"
            ;;
        get_a_room)
            build_exe "09 Metamorphic testing/dev/get_a_room.py" "get_a_room" "09 Metamorphic testing"
            ;;
        *)
            echo "Unknown BUILD_TARGET: $1" >&2
            echo "Valid targets: all transform_obj check_age.v99 check_age.v100 triage_rules trace_it get_a_room" >&2
            exit 2
            ;;
    esac
}

if [[ "$BUILD_TARGET" == "all" ]]; then
    mkdir -p "$OUT_DIR/03 EP class activity"
    cp "$REPO_DIR/03 EP class activity/present.obj" "$OUT_DIR/03 EP class activity/present.obj"
    build_target transform_obj
    build_target check_age.v99
    build_target check_age.v100
    build_target triage_rules
    build_target trace_it
    build_target get_a_room
else
    build_target "$BUILD_TARGET"
fi

echo "Student workspace created at ${OUT_DIR}"
find "$OUT_DIR" -maxdepth 2 -type f -printf '%P\n' | sort
