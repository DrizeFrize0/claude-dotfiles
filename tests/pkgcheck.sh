#!/usr/bin/env bash
# usage: pkgcheck.sh pkg...  -> prints repo/version or AUR/version or MISSING
for p in "$@"; do
  r=$(curl -sS "https://archlinux.org/packages/search/json/?name=$p" | jq -r '.results[0] | select(.!=null) | "\(.repo) \(.pkgver)-\(.pkgrel)"')
  if [ -n "$r" ]; then echo "$p: $r"; continue; fi
  a=$(curl -sS "https://aur.archlinux.org/rpc/v5/info?arg[]=$p" | jq -r '.results[0] | select(.!=null) | "AUR \(.Version) votes=\(.NumVotes) outofdate=\(.OutOfDate)"')
  if [ -n "$a" ]; then echo "$p: $a"; else echo "$p: MISSING"; fi
done
