#!/usr/bin/env python3
# Converts the scalable icons into PNGs up to 512x512px.
import os
from glob import glob
from os import system

for in_path in glob('scalable/apps/*.svg'):
    for dim in [16, 32, 64, 128, 256, 512]:
        out_path = os.path.dirname(in_path).replace('scalable/', f'{dim}x{dim}/')
        system(f'gtk-encode-symbolic-svg {in_path} {dim}x{dim} -o {out_path}')
