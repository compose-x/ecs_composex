#!/usr/bin/env bash
set -ex
for file in "$@"; do
    sed -i -E 's/([0-9]{12})/000000000000/g' $file
    sed -i -E 's/(Z[A-Z0-9]+)/ZONEREDACTED123/g' $file
    git add -u $file
done
