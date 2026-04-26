#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
harness_dir="$script_dir"
codex_home="${CODEX_HOME:-$HOME/.codex}"
bin_dir="${HOME}/.local/bin"
rules_file="$codex_home/rules/default.rules"
launcher_src="$harness_dir/bin/codex-polymagix"
launcher_dest="$bin_dir/codex-polymagix"
rules_src="$harness_dir/rules/productivity.rules"

mkdir -p "$bin_dir" "$codex_home/rules"
install -m 0755 "$launcher_src" "$launcher_dest"

tmp_file="$(mktemp)"
if [[ -f "$rules_file" ]]; then
  awk '
    $0 == "# BEGIN codex-productivity-harness" { skip = 1; next }
    $0 == "# END codex-productivity-harness" { skip = 0; next }
    skip != 1 { print }
  ' "$rules_file" > "$tmp_file"
else
  : > "$tmp_file"
fi

{
  cat "$tmp_file"
  printf '
# BEGIN codex-productivity-harness
'
  cat "$rules_src"
  printf '# END codex-productivity-harness
'
} > "$rules_file"
rm -f "$tmp_file"

cat <<MSG
Installed productivity Codex harness.

Launcher:
  $launcher_dest

Rules updated:
  $rules_file

Start trusted Polymagix sessions with:
  codex-polymagix -C /home/peter/Work/polymagix/codex-skills

Optional extra writable roots:
  CODEX_EXTRA_ADD_DIRS=/path/one:/path/two codex-polymagix
MSG
