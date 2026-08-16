#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${1:-dist/SmartFile}"
MAX_GLIBC="${2:-2.35}"
MAX_GLIBCXX="${3:-3.4.29}"

fail() {
    echo "Erro: $*" >&2
    exit 1
}

version_gt() {
    local candidate="$1"
    local baseline="$2"
    [[ "$candidate" != "$baseline" ]] \
        && [[ "$(printf '%s\n%s\n' "$candidate" "$baseline" | sort -V | tail -n 1)" == "$candidate" ]]
}

[[ -d "$BUNDLE_DIR" ]] || fail "bundle ausente: $BUNDLE_DIR"
command -v file >/dev/null || fail "comando file indisponível"
command -v readelf >/dev/null || fail "comando readelf indisponível"

highest_glibc="0"
highest_glibc_file=""
highest_glibcxx="0"
highest_glibcxx_file=""
elf_count=0

while IFS= read -r elf_file; do
    elf_count=$((elf_count + 1))
    undefined_symbols="$(
        readelf --dyn-syms --wide "$elf_file" 2>/dev/null \
            | awk '$7 == "UND" {print $8}' \
            || true
    )"

    required_glibc="$(
        printf '%s\n' "$undefined_symbols" \
            | grep -Eo 'GLIBC_[0-9]+([.][0-9]+)*' \
            | sort -Vu \
            | tail -n 1 \
            || true
    )"
    required_glibc="${required_glibc#GLIBC_}"
    if [[ -n "$required_glibc" ]] \
        && version_gt "$required_glibc" "$highest_glibc"; then
        highest_glibc="$required_glibc"
        highest_glibc_file="$elf_file"
    fi

    required_glibcxx="$(
        printf '%s\n' "$undefined_symbols" \
            | grep -Eo 'GLIBCXX_[0-9]+([.][0-9]+)*' \
            | sort -Vu \
            | tail -n 1 \
            || true
    )"
    required_glibcxx="${required_glibcxx#GLIBCXX_}"
    if [[ -n "$required_glibcxx" ]] \
        && version_gt "$required_glibcxx" "$highest_glibcxx"; then
        highest_glibcxx="$required_glibcxx"
        highest_glibcxx_file="$elf_file"
    fi
done < <(
    find "$BUNDLE_DIR" -type f -print0 \
        | xargs -0 file \
        | awk -F: '/ELF/{print $1}'
)

[[ $elf_count -gt 0 ]] || fail "nenhum ELF encontrado em $BUNDLE_DIR"

build_glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null || ldd --version | head -n 1)"
printf 'BUILD_GLIBC=%s\n' "$build_glibc"
printf 'BASELINE_GLIBC=%s\n' "$MAX_GLIBC"
printf 'BASELINE_GLIBCXX=%s\n' "$MAX_GLIBCXX"
printf 'ELF_COUNT=%s\n' "$elf_count"
printf 'MAX_REQUIRED_GLIBC=%s\n' "$highest_glibc"
printf 'MAX_REQUIRED_GLIBC_FILE=%s\n' "$highest_glibc_file"
printf 'MAX_REQUIRED_GLIBCXX=%s\n' "$highest_glibcxx"
printf 'MAX_REQUIRED_GLIBCXX_FILE=%s\n' "$highest_glibcxx_file"

if version_gt "$highest_glibc" "$MAX_GLIBC"; then
    fail "bundle exige GLIBC_$highest_glibc, acima da baseline GLIBC_$MAX_GLIBC"
fi
if version_gt "$highest_glibcxx" "$MAX_GLIBCXX"; then
    fail "bundle exige GLIBCXX_$highest_glibcxx, acima da baseline GLIBCXX_$MAX_GLIBCXX"
fi

echo "ABI Linux compatível com a baseline configurada."
