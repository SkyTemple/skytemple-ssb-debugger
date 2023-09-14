__version__ = '1.6.0a3'
from setuptools import setup, find_packages

# README read-in
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()
# END README read-in

setup(
    name='skytemple-ssb-debugger',
    version=__version__,
    packages=find_packages(),
    description='Script Engine Debugger for Pokémon Mystery Dungeon Explorers of Sky (EU/US)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/SkyTemple/skytemple-ssb-debugger',
    install_requires=[
        'ndspy >= 3.0.0',
        'skytemple-files >= 1.6.0a3',
        'pmdsky-debug-py',  #  Whatever version skytemple-files requires.
        'skytemple-icons >= 0.1.0',
        'range-typed-integers >= 1.0.0',
        'pygobject >= 3.26.0',
        'pycairo >= 1.16.0',
        'skytemple-ssb-emulator >= 1.6.0a1',
        'explorerscript >= 0.1.3',
        'nest-asyncio >= 1.4.1',
        'pygtkspellcheck >= 5.0',
        'importlib_metadata>=4.6; python_version < "3.10"'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Programming Language :: Python',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    package_data={'skytemple_ssb_debugger': ['*.lang', '*.css', '*.glade', '**/*.glade', 'data/*/*/*/*/*', 'py.typed']},
    entry_points='''
        [console_scripts]
        skytemple-ssb-debugger=skytemple_ssb_debugger.main:main
    ''',
)
