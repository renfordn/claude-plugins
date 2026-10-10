#!/bin/sh
# monday-sync git probe: read-only branch state for one repo + branch, printed as one JSON object.
#
#   sh git_probe.sh <repo> <branch> [pushed_head]
#
# {"branch","on_origin","ahead","head","merged","merge_subject","origin_url"}
#   on_origin      refs/remotes/origin/<branch> exists (as fresh as the user's last fetch)
#   ahead          commits on the branch tip not on origin/main
#   head           origin/<branch> tip, else local <branch> tip, else ""
#   merged         pushed_head is an ancestor of origin/main (and not on its first-parent line), or
#                  a merge commit on origin/main whose subject names the branch merged this tip
#                  (tip reachable from the merge's 2nd parent, not its 1st). Never true for a branch
#                  with 0 commits of its own. Squash/rebase merges are not detected.
#   merge_subject  subject of the merge commit that brought the branch in, else ""
# Any git failure (no repo, no origin/main) prints "unknown" values. Never fetches, never writes.
# POSIX sh; send it to a device shell verbatim (the skill inlines it in a heredoc).

export GIT_OPTIONAL_LOCKS=0
repo=$1
branch=$2
pushed_head=${3:-}
case $repo in "~/"*) repo="$HOME/${repo#"~/"}" ;; "~") repo=$HOME ;; esac

esc() { printf '%s' "$1" | LC_ALL=C tr -d '\000-\037' | LC_ALL=C sed 's/\\/\\\\/g; s/"/\\"/g'; }

unknown() {
  printf '{"branch":"%s","on_origin":"unknown","ahead":"unknown","head":"unknown","merged":"unknown","merge_subject":"unknown","origin_url":"unknown"}\n' "$(esc "$branch")"
  exit 0
}

g() { git -C "$repo" "$@" 2>/dev/null; }

[ -n "$repo" ] && [ -n "$branch" ] || unknown
g rev-parse --git-dir >/dev/null || unknown
main=$(g rev-parse --verify -q refs/remotes/origin/main) || unknown
origin_url=$(g config --get remote.origin.url) || origin_url=""

on_origin=false
head=""
if tip=$(g rev-parse --verify -q "refs/remotes/origin/$branch"); then
  on_origin=true
  head=$tip
elif tip=$(g rev-parse --verify -q "refs/heads/$branch"); then
  head=$tip
fi
ahead=0
if [ -n "$head" ]; then
  ahead=$(g rev-list --count "$main..$head") || unknown
fi

merged=false
merge_subject=""

# (a) recorded pushed_head reached origin/main through a merge (works after branch deletion)
if [ -n "$pushed_head" ] && g cat-file -e "$pushed_head^{commit}" \
   && g merge-base --is-ancestor "$pushed_head" "$main" \
   && ! g rev-list --first-parent "$main" | grep -qx "$(g rev-parse "$pushed_head")"; then
  merged=true
  merge_subject=$(g log --merges --ancestry-path --reverse --format=%s "$pushed_head..$main" | head -n 1)
fi

# (b) a merge commit on origin/main naming the branch merged the current tip
if [ "$merged" = false ] && [ -n "$head" ]; then
  tab=$(printf '\t')
  merges=$(g log --merges --format="%H$tab%s" "$main") || unknown
  found=$(printf '%s\n' "$merges" | while IFS="$tab" read -r sha subject; do
    [ -n "$sha" ] || continue
    case $subject in
      (*"/$branch"|*"/$branch "*|*"'$branch'"*|*" $branch"|*" $branch "*) ;;
      (*) continue ;;
    esac
    if g merge-base --is-ancestor "$head" "$sha^2" && ! g merge-base --is-ancestor "$head" "$sha^1"; then
      printf '%s\n' "$subject"
      break
    fi
  done)
  if [ -n "$found" ]; then
    merged=true
    merge_subject=$found
  fi
fi

printf '{"branch":"%s","on_origin":%s,"ahead":%s,"head":"%s","merged":%s,"merge_subject":"%s","origin_url":"%s"}\n' \
  "$(esc "$branch")" "$on_origin" "$ahead" "$head" "$merged" "$(esc "$merge_subject")" "$(esc "$origin_url")"
