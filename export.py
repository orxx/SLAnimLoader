import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ZIPPER = r"C:\Program Files\7-Zip\7z.exe"


def get_dest_path(entry):
    if entry.startswith("."):
        return None
    if re.match(r"SLAnimLoader-.*\.7z", entry):
        return None

    DEST_LOCATIONS = {
        'export.py': None,
        'meta.ini': None,
        'Interface': 'Interface',
        'Scripts': 'Scripts',
        'SLAnimLoader.esp': 'SLAnimLoader.esp',
        'SLAnims': 'SLAnims',
        'README.md': 'Readme - SLAnimLoader.txt',
    }
    return DEST_LOCATIONS[entry]


def export_dir(src_path, dest_path):
    os.mkdir(dest_path)
    for entry in os.listdir(src_path):
        if entry.startswith("."):
            continue
        entry_src = os.path.join(src_path, entry)
        entry_dest = os.path.join(dest_path, entry)
        if os.path.isdir(entry_src):
            export_dir(entry_src, entry_dest)
        else:
            shutil.copy2(entry_src, entry_dest)


def export(args):
    if not os.access(ZIPPER, os.X_OK):
        raise Exception("cannot find {}".format(ZIPPER))

    src_dir = args.source_dir
    version = args.version

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_dir = os.path.join(tmpdir, "SLAnimLoader-{}".format(version))
        os.mkdir(dest_dir)
        dest_entries = []
        for entry in os.listdir(src_dir):
            dest = get_dest_path(entry)
            if dest is None:
                continue

            src_path = os.path.join(src_dir, entry)
            dest_path = os.path.join(dest_dir, dest)
            dest_entries.append(dest)
            if os.path.isdir(src_path):
                export_dir(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)

        archive_name = "SLAnimLoader-{}.7z".format(version)
        zip_cmd = [ZIPPER, "a", os.path.join("..", archive_name)]
        zip_cmd.extend(dest_entries)

        p = subprocess.Popen(zip_cmd, cwd=dest_dir)
        p.wait()
        if p.returncode != 0:
            raise Exception("error creating archive")

        tmp_archive = os.path.join(tmpdir, archive_name)
        archive_path = os.path.join(args.output_dir, archive_name)
        shutil.move(tmp_archive, archive_path)

    return archive_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-s', '--source-dir',
                    help='The directory containing the mod sources')
    ap.add_argument('-o', '--output-dir',
                    help='The output directory')
    ap.add_argument('-V', '--version',
                    required=True,
                    help='The version number to release')
    args = ap.parse_args()

    if args.source_dir is None:
        args.source_dir = os.path.dirname(sys.argv[0])
    if args.output_dir is None:
        args.output_dir = args.source_dir

    print("Generating release archive for version {}".format(args.version))
    archive_path = export(args)
    print("Successfully generated {}".format(archive_path))


if __name__ == '__main__':
    main()
