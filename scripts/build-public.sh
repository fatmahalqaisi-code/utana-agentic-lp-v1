#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repository_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
manifest="$repository_root/public-files.txt"
output="$repository_root/public"
staging=$(mktemp -d "$repository_root/.public.XXXXXX")

cleanup() {
  if [ -n "${staging:-}" ] && [ -d "$staging" ]; then
    rm -rf "$staging"
  fi
}

trap cleanup EXIT
trap 'exit 1' HUP INT TERM

file_count=0
while IFS= read -r relative_path || [ -n "$relative_path" ]; do
  case "$relative_path" in
    ''|'#'*) continue ;;
    /*|.|..|../*|*/..|*/../*|*//* )
      printf 'Unsafe path in %s: %s\n' "$manifest" "$relative_path" >&2
      exit 1
      ;;
  esac

  case "$relative_path" in
    *.html) source_file="$repository_root/src/pages/$relative_path" ;;
    *.css) source_file="$repository_root/src/styles/$relative_path" ;;
    *.js) source_file="$repository_root/src/js/$relative_path" ;;
    *) source_file="$repository_root/static/$relative_path" ;;
  esac
  destination="$staging/$relative_path"

  if [ ! -f "$source_file" ]; then
    printf 'Allowlisted source file does not exist: %s\n' "$relative_path" >&2
    exit 1
  fi

  mkdir -p "$(dirname "$destination")"
  cp "$source_file" "$destination"
  chmod 0644 "$destination"
  file_count=$((file_count + 1))
done < "$manifest"

if [ "$file_count" -eq 0 ]; then
  printf 'No files were listed in %s\n' "$manifest" >&2
  exit 1
fi

find "$staging" -type d -exec chmod 0755 {} +

python3 "$script_dir/verify-public.py" "$staging" "$manifest"
python3 "$script_dir/verify-seo.py" "$staging" "$manifest"

rm -rf "$output"
mv "$staging" "$output"
staging=

printf 'Built %s with %s allowlisted files.\n' "$output" "$file_count"
