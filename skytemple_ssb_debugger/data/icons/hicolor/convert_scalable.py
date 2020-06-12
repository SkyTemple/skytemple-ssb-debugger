#!/usr/bin/env python3
# Converts the scalable icons into PNGs up to 512x512px.
from glob import glob
from os import system

for in_path in glob('scalable/apps/*.svg'):
    for dim in [16, 32, 64, 128, 256, 512]:
        out_path = in_path[:-4].replace('scalable/', f'{dim}x{dim}/') + '.png'
        system(f'inkscape -w {dim} -h {dim} {in_path} --export-filename {out_path}')
