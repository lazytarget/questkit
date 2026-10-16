#!/usr/bin/env bash
# Mechanical git steps of /new-quest. Harness-neutral; needs only git.
#   new-quest.sh start <slug> [--remote R]   worktree + branch off R's default branch; prints facts
#   new-quest.sh push                         push the current quest branch (run inside the worktree)
#   new-quest.sh purge <slug>                 remove worktree + local branch (run from anywhere in the repo)
set -euo pipefail

die() { echo "new-quest: $*" >&2; exit 1; }
main_root() { dirname "$(cd "$(git rev-parse --git-common-dir)" && pwd)"; }
cfg() { awk -F': *' -v k="$2" '$1==k {gsub(/[ "'\'']/, "", $2); print $2; exit}' "$1"; }

cmd_start() {
  local slug="${1:-}" remote=""
  [[ $slug =~ ^[a-z0-9][a-z0-9-]*$ ]] || die "slug must be kebab-case"
  shift
  [[ ${1:-} == --remote ]] && remote="${2:?--remote needs a value}"

  local root; root="$(main_root)"
  if [[ -z $remote ]]; then
    local remotes; remotes="$(git -C "$root" remote)"
    [[ -n $remotes ]] || die "no git remote"
    if [[ $(wc -l <<<"$remotes") -eq 1 ]]; then
      remote="$remotes"
    else
      git -C "$root" fetch --all -q
      local best=0 r b t
      for r in $remotes; do
        b="$(git -C "$root" ls-remote --symref "$r" HEAD | awk '/^ref:/ {sub("refs/heads/","",$2); print $2; exit}')"
        t="$(git -C "$root" log -1 --format=%ct "$r/$b" 2>/dev/null || echo 0)"
        (( t > best )) && { best=$t; remote=$r; }
      done
      echo "NOTE=several remotes; picked newest ($remote). Pass --remote to override." >&2
    fi
  fi

  local base
  base="$(git -C "$root" ls-remote --symref "$remote" HEAD | awk '/^ref:/ {sub("refs/heads/","",$2); print $2; exit}')"
  [[ -n $base ]] || die "cannot resolve default branch of $remote"
  git -C "$root" fetch -q "$remote" "$base"

  local wt; wt="$(dirname "$root")/$(basename "$root")-worktrees/$slug"
  git -C "$root" worktree add -q -b "quest/$slug" "$wt" "$remote/$base"

  echo "WORKTREE=$wt"
  echo "REMOTE=$remote"
  echo "BASE=$base"
  echo "BRANCH=quest/$slug"
  local hooks=inactive
  if grep -qs 'quest-' "$wt/.pre-commit-config.yaml" && [[ -x "$(git -C "$wt" rev-parse --git-path hooks/pre-commit)" ]]; then hooks=active; fi
  echo "HOOKS=$hooks"
  # one line per quest log: project (name for --in, empty for a catch-all log), dir, git mode
  local f
  while IFS= read -r f; do
    echo "LOG project=$(cfg "$f" project) dir=$(dirname "$f") git=$(cfg "$f" git)"
  done < <(cd "$wt" && find . -name .questkit.yaml -not -path './.git/*' | sort | sed "s|^\.|$wt|")
}

cmd_push() {
  local branch remote
  branch="$(git rev-parse --abbrev-ref HEAD)"
  [[ $branch == quest/* ]] || die "not on a quest/* branch"
  [[ -z $(git status --porcelain) ]] || die "uncommitted changes; commit first"
  remote="${1:-$(git config --get "branch.$branch.remote" || true)}"
  [[ -n $remote ]] || remote="$(git for-each-ref --format='%(upstream:remotename)' "refs/heads/$branch")"
  [[ -n $remote ]] || remote="$(git remote | head -n1)"
  git push -u "$remote" "$branch"
}

cmd_purge() {
  local slug="${1:?slug}" root; root="$(main_root)"
  cd "$root"
  git worktree remove "$(dirname "$root")/$(basename "$root")-worktrees/$slug"
  git branch -D "quest/$slug"
}

case "${1:-}" in
  start) shift; cmd_start "$@" ;;
  push) shift; cmd_push "$@" ;;
  purge) shift; cmd_purge "$@" ;;
  *) die "usage: start <slug> [--remote R] | push [remote] | purge <slug>" ;;
esac
