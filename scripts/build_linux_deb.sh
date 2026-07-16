#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Erro: o pacote Linux deve ser construído em Linux." >&2
    exit 1
fi
case "$(uname -m)" in
    x86_64|amd64) ;;
    *) echo "Erro: esta receita produz somente amd64." >&2; exit 1 ;;
esac

BUILD_ROOT="$ROOT_DIR/build/linux"
PYI_WORK="$BUILD_ROOT/pyinstaller"
STAGE="$BUILD_ROOT/debian-root"
EXTRACTED="$BUILD_ROOT/extracted"
DIST_DIR="$ROOT_DIR/dist"
RELEASE_DIR="$ROOT_DIR/release"
BUILD_VENV="$BUILD_ROOT/venv"
SOURCE_PYTHON="${PYTHON_BIN:-python3}"

if [[ -n "${SMARTFILE_BUILD_PYTHON:-}" ]]; then
    BUILD_PYTHON="$SMARTFILE_BUILD_PYTHON"
else
    "$SOURCE_PYTHON" -m venv "$BUILD_VENV"
    BUILD_PYTHON="$BUILD_VENV/bin/python"
fi

if [[ "${SMARTFILE_SKIP_INSTALL:-0}" != "1" ]]; then
    "$BUILD_PYTHON" -m pip install --upgrade pip
    "$BUILD_PYTHON" -m pip install -r requirements.txt -r requirements-build.txt
fi

VERSION="$("$BUILD_PYTHON" -c 'from app.version import __version__; print(__version__)')"
DEBIAN_VERSION="$("$BUILD_PYTHON" -c 'from app.version import debian_version; print(debian_version())')"
ARTIFACT="smartfile_${DEBIAN_VERSION}_amd64.deb"
MAINTAINER="${SMARTFILE_MAINTAINER:-SmartFile contributors <boente66@users.noreply.github.com>}"

echo "==> SmartFile $VERSION (Debian $DEBIAN_VERSION)"
if [[ "${SMARTFILE_SKIP_TESTS:-0}" != "1" ]]; then
    echo "==> Testes e verificações estáticas"
    QT_QPA_PLATFORM=offscreen "$BUILD_PYTHON" -m pytest -q
    "$BUILD_PYTHON" -m compileall -q app run.py scripts/render_linux_icons.py
    "$BUILD_PYTHON" -m pip check
    git diff --check
fi

echo "==> Limpando somente saídas conhecidas"
rm -rf "$STAGE" "$EXTRACTED"
if [[ "${SMARTFILE_REUSE_BUNDLE:-0}" != "1" ]]; then
    rm -rf "$PYI_WORK" "$DIST_DIR/SmartFile"
fi
mkdir -p "$PYI_WORK" "$STAGE" "$EXTRACTED" "$RELEASE_DIR"

if [[ "${SMARTFILE_REUSE_BUNDLE:-0}" != "1" ]]; then
    echo "==> Gerando bundle PyInstaller onedir"
    "$BUILD_PYTHON" -m PyInstaller \
        --noconfirm --clean \
        --distpath "$DIST_DIR" \
        --workpath "$PYI_WORK" \
        packaging/pyinstaller/smartfile.spec
else
    echo "==> Reutilizando bundle existente para validação iterativa"
fi

test -x "$DIST_DIR/SmartFile/smartfile"
test -f "$DIST_DIR/SmartFile/_internal/assets/style.qss"
test -f "$DIST_DIR/SmartFile/_internal/assets/icons/app.svg"
test -f "$DIST_DIR/SmartFile/_internal/app/database/schema.sql"

echo "==> Verificando bibliotecas compartilhadas do bundle"
MISSING_LIBS="$BUILD_ROOT/missing-libraries.txt"
: > "$MISSING_LIBS"
while IFS= read -r elf_file; do
    missing="$(ldd "$elf_file" 2>/dev/null | grep 'not found' || true)"
    if [[ -n "$missing" ]]; then
        printf '%s\n%s\n' "$elf_file" "$missing" >> "$MISSING_LIBS"
    fi
done < <(find "$DIST_DIR/SmartFile" -type f -print0 | xargs -0 file | awk -F: '/ELF/{print $1}')
if [[ -s "$MISSING_LIBS" ]]; then
    echo "Erro: há bibliotecas compartilhadas não resolvidas no bundle." >&2
    cat "$MISSING_LIBS" >&2
    exit 1
fi

smoke_test() {
    local executable="$1"
    local sandbox="$2"
    local log_file="$3"
    mkdir -p "$sandbox/data" "$sandbox/config" "$sandbox/cache" "$sandbox/runtime"
    chmod 700 "$sandbox/runtime"
    set +e
    timeout 8 env \
        QT_QPA_PLATFORM=offscreen \
        XDG_DATA_HOME="$sandbox/data" \
        XDG_CONFIG_HOME="$sandbox/config" \
        XDG_CACHE_HOME="$sandbox/cache" \
        XDG_RUNTIME_DIR="$sandbox/runtime" \
        "$executable" >"$log_file" 2>&1
    local status=$?
    set -e
    if [[ $status -ne 124 ]]; then
        echo "Erro: smoke test encerrou inesperadamente ($status)." >&2
        cat "$log_file" >&2
        return 1
    fi
    if grep -Eq 'Traceback|ModuleNotFoundError|ImportError' "$log_file"; then
        cat "$log_file" >&2
        return 1
    fi
}

echo "==> Smoke test fora do venv"
smoke_test "$DIST_DIR/SmartFile/smartfile" "$BUILD_ROOT/smoke-dist" "$BUILD_ROOT/smoke-dist.log"

echo "==> Montando árvore Debian"
install -d "$STAGE/DEBIAN" "$STAGE/opt/smartfile" \
    "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
    "$STAGE/usr/share/icons/hicolor" "$STAGE/usr/share/doc/smartfile"
cp -a "$DIST_DIR/SmartFile/." "$STAGE/opt/smartfile/"
install -m 0755 packaging/debian/usr/bin/smartfile "$STAGE/usr/bin/smartfile"
install -m 0644 packaging/debian/usr/share/applications/smartfile.desktop \
    "$STAGE/usr/share/applications/smartfile.desktop"
install -m 0755 packaging/debian/DEBIAN/postinst packaging/debian/DEBIAN/prerm \
    packaging/debian/DEBIAN/postrm "$STAGE/DEBIAN/"
install -m 0644 LICENSE README.md docs/Manual_Usuario.md docs/Manual_Usuario.pdf \
    docs/BETA_LINUX.md \
    docs/RELEASE_NOTES_0.9.0-beta.1.md "$STAGE/usr/share/doc/smartfile/"
install -m 0644 CHANGELOG.md "$STAGE/usr/share/doc/smartfile/changelog"
gzip -9n "$STAGE/usr/share/doc/smartfile/changelog"
"$BUILD_PYTHON" scripts/render_linux_icons.py assets/icons/app.svg \
    "$STAGE/usr/share/icons/hicolor"

INSTALLED_SIZE="$(du -sk "$STAGE" | cut -f1)"
sed \
    -e "s|@VERSION@|$DEBIAN_VERSION|g" \
    -e "s|@MAINTAINER@|$MAINTAINER|g" \
    -e "s|@INSTALLED_SIZE@|$INSTALLED_SIZE|g" \
    packaging/debian/DEBIAN/control.in > "$STAGE/DEBIAN/control"
chmod 0644 "$STAGE/DEBIAN/control"
find "$STAGE/opt/smartfile" -type d -exec chmod 0755 {} +
find "$STAGE/opt/smartfile" -type f -exec chmod go-w {} +
chmod 0755 "$STAGE/opt/smartfile/smartfile"

echo "==> Auditoria de conteúdo sensível"
sensitive_found=0
while IFS= read -r candidate; do
    case "$candidate" in
        */_internal/certifi/cacert.pem)
            # Bundle público de CAs necessário para conexões TLS.
            ;;
        *)
            echo "$candidate" >&2
            sensitive_found=1
            ;;
    esac
done < <(find "$STAGE" -type f \( \
    -iname '*.db' -o -iname '*.sqlite*' -o -iname '*.p12' -o -iname '*.pfx' \
    -o -iname '*.pem' -o -iname '*token*' -o -iname '*oauth*.json' \
    -o -iname '*.log' \) -print)
if [[ $sensitive_found -ne 0 ]]; then
    echo "Erro: arquivo potencialmente sensível encontrado no pacote." >&2
    exit 1
fi

desktop-file-validate "$STAGE/usr/share/applications/smartfile.desktop"
rm -f "$RELEASE_DIR/$ARTIFACT" "$RELEASE_DIR/$ARTIFACT.sha256"
dpkg-deb --root-owner-group -Zgzip -z6 --build "$STAGE" "$RELEASE_DIR/$ARTIFACT"
dpkg-deb --info "$RELEASE_DIR/$ARTIFACT"
dpkg-deb --contents "$RELEASE_DIR/$ARTIFACT" > "$BUILD_ROOT/package-contents.txt"

if command -v lintian >/dev/null 2>&1; then
    lintian "$RELEASE_DIR/$ARTIFACT" | tee "$BUILD_ROOT/lintian.log"
else
    echo "Aviso: lintian não está instalado; validação Lintian não executada."
fi

dpkg-deb -x "$RELEASE_DIR/$ARTIFACT" "$EXTRACTED"
smoke_test "$EXTRACTED/opt/smartfile/smartfile" \
    "$BUILD_ROOT/smoke-package" "$BUILD_ROOT/smoke-package.log"

(cd "$RELEASE_DIR" && sha256sum "$ARTIFACT" > "$ARTIFACT.sha256")

echo
echo "Build concluído:"
echo "  pacote: $RELEASE_DIR/$ARTIFACT"
echo "  checksum: $RELEASE_DIR/$ARTIFACT.sha256"
echo "  Installed-Size: $INSTALLED_SIZE KiB"
echo "  observação: smoke tests locais não substituem teste de instalação em SO limpo."
