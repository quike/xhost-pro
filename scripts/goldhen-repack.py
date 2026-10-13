"""Swap the GoldHEN payload in the released filesystem images.

Builds, per board, a filesystem OTA (flash from xhost setup) and a full
flash image (flash with esptool) from the committed 0.9.7 release files.

usage: python scripts/goldhen-repack.py <goldhen.bin> <label>
requires: pip install littlefs-python
"""
import gzip, hashlib, os, re, sys
import littlefs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OTA_HEADER_SIZE = 17
BUNDLED_LABEL = 'GoldHEN 2.2.4'

# fs_offset/fs_size: LittleFS partition inside the 4MB webusb image
BOARDS = {
    'esp32-s2': dict(block_size=4096, full='0.9.7-esp32s2.bin', fs_offset=0x1b0000, fs_size=0x250000),
    'esp8266': dict(block_size=8192, full='0.9.7-esp8266.bin', fs_offset=0x100000, fs_size=0x2fa000),
}


def lfs_options(block_size, size):
    # disk_version 2.0 keeps images mountable by the 0.9.7 firmware
    return dict(block_size=block_size, block_count=size // block_size, read_size=64, prog_size=64,
                name_max=32, attr_max=0x3fe, disk_version=0x00020000)


def read_files(image, block_size):
    fs = littlefs.LittleFS(mount=False, **lfs_options(block_size, len(image)))
    fs.context.buffer = bytearray(image)
    fs.mount()
    files = {}
    for root, _, names in fs.walk('/'):
        for name in names:
            path = root.rstrip('/') + '/' + name
            with fs.open(path, 'rb') as handle:
                files[path] = handle.read()
    return files


def write_files(files, block_size, size):
    fs = littlefs.LittleFS(**lfs_options(block_size, size))
    for path in sorted(files):
        directory = os.path.dirname(path)
        if directory != '/':
            fs.makedirs(directory, exist_ok=True)
        with fs.open(path, 'wb') as handle:
            handle.write(files[path])
    return bytes(fs.context.buffer)


def gz(data):
    return gzip.compress(data, 9, mtime=0)


def swap_goldhen(files, goldhen, label):
    files['/pl/ghen@latest.900.bin.gz'] = gz(goldhen)
    menu = gzip.decompress(files['/menu.json.gz']).decode().replace(BUNDLED_LABEL, 'GoldHEN ' + label)
    files['/menu.json.gz'] = gz(menu.encode())
    # new manifest hash forces the PS4 appcache to refetch
    manifest = gzip.decompress(files['/cache.manifest.gz']).decode()
    digest = hashlib.md5(goldhen + menu.encode()).hexdigest()
    files['/cache.manifest.gz'] = gz(re.sub(r'#[0-9a-f]{32}', '#' + digest, manifest).encode())


def main(goldhen_path, label):
    goldhen = open(goldhen_path, 'rb').read()
    tag = 'gh' + label
    for board, cfg in BOARDS.items():
        ota = open(os.path.join(ROOT, 'ota', f'{board}-base.fs.ota'), 'rb').read()
        header, image = ota[:OTA_HEADER_SIZE], ota[OTA_HEADER_SIZE:]
        assert len(image) == cfg['fs_size'], board

        files = read_files(image, cfg['block_size'])
        swap_goldhen(files, goldhen, label)
        fs_image = write_files(files, cfg['block_size'], cfg['fs_size'])
        assert read_files(fs_image, cfg['block_size']) == files, board

        ota_path = os.path.join(ROOT, 'ota', f'{board}-{tag}.fs.ota')
        open(ota_path, 'wb').write(header + fs_image)

        full = open(os.path.join(ROOT, 'webusb', cfg['full']), 'rb').read()
        start, end = cfg['fs_offset'], cfg['fs_offset'] + cfg['fs_size']
        full_path = os.path.join(ROOT, 'webusb', cfg['full'].replace('.bin', f'-{tag}.bin'))
        open(full_path, 'wb').write(full[:start] + fs_image + full[end:])

        print(f'{board}: {os.path.relpath(ota_path, ROOT)}, {os.path.relpath(full_path, ROOT)}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
