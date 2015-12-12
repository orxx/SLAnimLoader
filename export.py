import os
import re
import shutil
import subprocess
import sys
import tempfile

VERSION = 1.0

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


def export():
    if not os.access(ZIPPER, os.X_OK):
        raise Exception("cannot find {}".format(ZIPPER))

    src_dir = os.path.dirname(sys.argv[0])
    with tempfile.TemporaryDirectory() as tmpdir:
        dest_dir = os.path.join(tmpdir, "SLAnimLoader-{}".format(VERSION))
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

        archive_name = "SLAnimLoader-{}.7z".format(VERSION)
        zip_cmd = [ZIPPER, "a", os.path.join("..", archive_name)]
        zip_cmd.extend(dest_entries)
        print(zip_cmd)

        p = subprocess.Popen(zip_cmd, cwd=dest_dir)
        p.wait()
        if p.returncode != 0:
            raise Exception("error creating archive")

        tmp_archive = os.path.join(tmpdir, archive_name)
        archive_path = os.path.join(src_dir, archive_name)
        shutil.move(tmp_archive, archive_path)

    print("Successfully generated {}".format(archive_path))

export()
