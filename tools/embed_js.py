"""
Script to embed JavaScript dependencies in mpl.js.
"""

from collections import namedtuple
from pathlib import Path
import re
import shutil
import subprocess
import sys


Package = namedtuple('Package', [
    # The package to embed, in some form that `npm install` can use.
    'name',
    # The path to the source file within the package to embed.
    'source',
    # The path to the license file within the package to embed.
    'license'])
# The list of packages to embed, in some form that `npm install` can use.
JAVASCRIPT_PACKAGES = [
    # Polyfill/ponyfill for ResizeObserver.
    Package('@jsxtools/resize-observer', 'index.js', 'LICENSE.md'),
]
# This is the magic line that must exist in mpl.js, after which the embedded
# JavaScript will be appended.
MPLJS_MAGIC_HEADER = (
    "///////////////// REMAINING CONTENT GENERATED BY embed_js.py "
    "/////////////////\n")


def safe_name(name):
    """
    Make *name* safe to use as a JavaScript variable name.
    """
    return '_'.join(re.split(r'[@/-]', name)).upper()


def prep_package(web_backend_path, pkg):
    source = web_backend_path / 'node_modules' / pkg.name / pkg.source
    license = web_backend_path / 'node_modules' / pkg.name / pkg.license
    if not source.exists():
        # Exact version should already be saved in package.json, so we use
        # --no-save here.
        try:
            subprocess.run(['npm', 'install', '--no-save', pkg.name],
                           cwd=web_backend_path)
        except FileNotFoundError as err:
            raise ValueError(
                f'npm must be installed to fetch {pkg.name}') from err
    if not source.exists():
        raise ValueError(
            f'{pkg.name} package is missing source in {pkg.source}')
    elif not license.exists():
        raise ValueError(
            f'{pkg.name} package is missing license in {pkg.license}')

    return source, license


def gen_embedded_lines(pkg, source):
    name = safe_name(pkg.name)
    print('Embedding', source, 'as', name)
    yield '// prettier-ignore\n'
    for line in source.read_text().splitlines():
        yield (line.replace('module.exports=function', f'var {name}=function')
               + ' // eslint-disable-line\n')


def build_mpljs(web_backend_path, license_path):
    mpljs_path = web_backend_path / "js/mpl.js"
    mpljs_orig = mpljs_path.read_text().splitlines(keepends=True)
    try:
        mpljs_orig = mpljs_orig[:mpljs_orig.index(MPLJS_MAGIC_HEADER) + 1]
    except IndexError as err:
        raise ValueError(
            f'The mpl.js file *must* have the exact line: {MPLJS_MAGIC_HEADER}'
        ) from err

    with mpljs_path.open('w') as mpljs:
        mpljs.writelines(mpljs_orig)

        for pkg in JAVASCRIPT_PACKAGES:
            source, license = prep_package(web_backend_path, pkg)
            mpljs.writelines(gen_embedded_lines(pkg, source))

            shutil.copy(license,
                        license_path / f'LICENSE{safe_name(pkg.name)}')


if __name__ == '__main__':
    # Write the mpl.js file.
    web_backend_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (Path(__file__).parent.parent / "lib/matplotlib/backends/web_backend")
    license_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent.parent / "LICENSE"
    build_mpljs(web_backend_path, license_path)
