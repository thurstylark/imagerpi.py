# imagerpi.py

Capture and deploy images of RaspberryPi SD Cards

By default, capture mode will shrink the last partition on the source drive to the minimum as reported by `resize2fs(1)`, plus the value defined by `--free` (default: '500M'). This can be disabled by passing `--no-shrink`.

Filesystem and partition shrinking is only supported for ext4 filesystems for the time being. If an unsupported filesystem is encountered, and `--no-shrink` was not specified, the resizing step will be skipped.

Deploy mode will simply write the specified source to the specified destination, no questions asked. Be sure you know what you're overwriting before going through with this.

## Dependencies

- [pyparted](https://github.com/rhinstaller/pyparted)
- [tqdm](https://github.com/tqdm/tqdm)

## Usage

```
usage: imagerpi.py [-h] [-b SIZE] [-v] {capture,deploy} ...

Capture or Deploy images to sdcards

positional arguments:
  {capture,deploy}      sub-command help
    capture             capture help
    deploy              deploy help

optional arguments:
  -h, --help            show this help message and exit
  -b SIZE, --buffer-size SIZE
                        Use a transfer buffer of size SIZE. Accepts suffixes
                        of B, K, M, or G.
  -v, --verbose         Enable verbose logging
```

### Capturing an image:

```
usage: imagerpi.py capture [-h] [--no-copy] [--no-shrink] [-f SIZE] src dest

positional arguments:
  src                   Source disk
  dest                  Destination file

optional arguments:
  -h, --help            show this help message and exit
  --no-copy             Don't copy to dest.
  --no-shrink           Skip the filesystem shrinking step.
  -f SIZE, --free SIZE  Shrink last partition filesystem to include a minimum
                        of SIZE free space. Accepts suffixes of B, K, M, or G.
```

Example:

```
imagerpi.py capture /dev/mmcblk0 rpi.img
```

### Deploying an image:

```
usage: imagerpi.py deploy [-h] src dest

positional arguments:
  src         Source file
  dest        Destination disk

optional arguments:
  -h, --help  show this help message and exit
```

Example:

```
imagerpi.py deploy rpi.img /dev/mmcblk0
```

## TODO

- Make tqdm an optional dependency
- Make pyparted an optional dependency
- Support compression (gz, xz, bzip2, et al.)
- Re-tool partition resizing operation to operate on the resulting image file instead of on the source device
- Add support for more filesystems 
- Add more useful verbose messages
