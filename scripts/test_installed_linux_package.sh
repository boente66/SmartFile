#!/usr/bin/env bash
set -euo pipefail

PACKAGE_NAME="${1:-smartfile}"
DESKTOP_FILE="/usr/share/applications/smartfile.desktop"
METainfo_FILE="/usr/share/metainfo/io.github.boente66.SmartFile.metainfo.xml"
WRAPPER="/usr/bin/smartfile"
BINARY="/opt/smartfile/smartfile"
FAILURE_PATTERN='Traceback|ModuleNotFoundError|ImportError|cannot open shared object file|Could not load the Qt platform plugin|No such file or directory.*(assets|schema\.sql)'

fail() {
    echo "Erro: $*" >&2
    exit 1
}

assert_root_owned() {
    local path="$1"
    [[ "$(stat -c '%U:%G' "$path")" == "root:root" ]] \
        || fail "$path não pertence a root:root"
}

run_diagnostic_smoke() {
    local command_path="$1"
    local label="$2"
    local sandbox
    sandbox="$(mktemp -d "/tmp/smartfile-${label}.XXXXXX")"
    mkdir -p "$sandbox/data" "$sandbox/config" "$sandbox/cache" "$sandbox/runtime"
    chmod 700 "$sandbox/runtime"

    set +e
    (
        cd /tmp
        env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV \
            PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
            QT_QPA_PLATFORM=offscreen \
            XDG_DATA_HOME="$sandbox/data" \
            XDG_CONFIG_HOME="$sandbox/config" \
            XDG_CACHE_HOME="$sandbox/cache" \
            XDG_RUNTIME_DIR="$sandbox/runtime" \
            timeout 60 "$command_path" --smoke-test
    ) >"$sandbox/diagnostic.log" 2>&1
    local status=$?
    set -e

    if [[ $status -ne 0 ]]; then
        cat "$sandbox/diagnostic.log" >&2
        fail "$label --smoke-test encerrou com status $status"
    fi
    if grep -Eiq "$FAILURE_PATTERN" "$sandbox/diagnostic.log"; then
        cat "$sandbox/diagnostic.log" >&2
        fail "$label registrou erro de inicialização"
    fi
    rm -rf "$sandbox"
}

run_persistent_startup_smoke() {
    local command_path="$1"
    local sandbox
    sandbox="$(mktemp -d /tmp/smartfile-startup.XXXXXX)"
    mkdir -p "$sandbox/data" "$sandbox/config" "$sandbox/cache" "$sandbox/runtime"
    chmod 700 "$sandbox/runtime"

    set +e
    (
        cd /tmp
        timeout 8 env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV \
            PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
            QT_QPA_PLATFORM=offscreen \
            XDG_DATA_HOME="$sandbox/data" \
            XDG_CONFIG_HOME="$sandbox/config" \
            XDG_CACHE_HOME="$sandbox/cache" \
            XDG_RUNTIME_DIR="$sandbox/runtime" \
            "$command_path"
    ) >"$sandbox/startup.log" 2>&1
    local status=$?
    set -e

    if [[ $status -ne 124 ]]; then
        cat "$sandbox/startup.log" >&2
        fail "o aplicativo instalado encerrou inesperadamente com status $status"
    fi
    if grep -Eiq "$FAILURE_PATTERN" "$sandbox/startup.log"; then
        cat "$sandbox/startup.log" >&2
        fail "o aplicativo instalado registrou erro no startup"
    fi
    rm -rf "$sandbox"
}

[[ "$(dpkg-query -W -f='${db:Status-Status}' "$PACKAGE_NAME")" == "installed" ]] \
    || fail "o dpkg não registra $PACKAGE_NAME como instalado"
[[ "$(env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    sh -c 'command -v smartfile')" == "$WRAPPER" ]] \
    || fail "smartfile não foi encontrado em $WRAPPER"
[[ -x "$WRAPPER" ]] || fail "$WRAPPER não é executável"
[[ -x "$BINARY" ]] || fail "$BINARY não é executável"
[[ -f "$DESKTOP_FILE" ]] || fail "launcher desktop ausente"
[[ -f "$METainfo_FILE" ]] || fail "metadados AppStream ausentes"

assert_root_owned "$WRAPPER"
assert_root_owned "$BINARY"
assert_root_owned "$DESKTOP_FILE"
assert_root_owned "$METainfo_FILE"

desktop-file-validate "$DESKTOP_FILE"
appstreamcli validate --no-net --strict "$METainfo_FILE"

desktop_exec="$(sed -n 's/^Exec=//p' "$DESKTOP_FILE")"
[[ "$desktop_exec" == "smartfile" ]] \
    || fail "Exec inesperado no launcher: $desktop_exec"
[[ "$(sed -n 's/^Icon=//p' "$DESKTOP_FILE")" == "smartfile" ]] \
    || fail "Icon do launcher não corresponde ao tema hicolor"

for size in 16 24 32 48 64 128 256; do
    icon="/usr/share/icons/hicolor/${size}x${size}/apps/smartfile.png"
    [[ -r "$icon" ]] || fail "ícone ausente: $icon"
    assert_root_owned "$icon"
done
[[ -r /usr/share/icons/hicolor/scalable/apps/smartfile.svg ]] \
    || fail "ícone SVG escalável ausente"

run_diagnostic_smoke "$BINARY" "binary"
run_diagnostic_smoke "$WRAPPER" "wrapper"
run_diagnostic_smoke "$desktop_exec" "desktop"
run_persistent_startup_smoke "$WRAPPER"

echo "Pacote SmartFile instalado e validado com sucesso."
