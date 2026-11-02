#!/bin/sh
# first-person preview: fp.sh name eye_x eye_y eye_z target_x target_y target_z [radius]
cd "$(dirname "$0")"
TARGET="$5,$6,$7" FOV=${FOV:-75} python3 preview_scene.py ../out/addon/maps/mg_trenchwarfare.vmap ../preview/$1.png $2 $3 ${8:-420} $2 $3 $4 | tail -1
