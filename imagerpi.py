#!/usr/bin/python3

import parted, os, stat, argparse, logging, subprocess
from tqdm import *


def human2bytes(s):
    """
    Accepts a size value with a suffix of B, K, M, or G, and returns an int in bytes.
    >>> human2bytes('1M')
    1048576
    >>> human2bytes('1G')
    1073741824
    """
    symbols = ('B', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    letter = s[-1:].strip().upper()
    num = s[:-1]
    assert num.isdigit() and letter in symbols, s
    num = float(num)
    prefix = {symbols[0]: 1}
    for i, s in enumerate(symbols[1:]):
        prefix[s] = 1 << (i + 1) * 10
    return int(num * prefix[letter])


def is_blockdev(path):
    """Checks if path is a block device. An argparse extension."""
    try:
        stat.S_ISBLK(os.stat(path).st_mode)
    except:
        raise argparse.ArgumentTypeError(path + " is not a block device")
        return False
    return path


def capture(args):
    """Captures an image of args.src to args.dest, and shrinks the filesystem on the last partition"""
    # Get device info
    device = parted.getDevice(args.src)
    lastpart = parted.newDisk(device).partitions[-1]
    lastsector = lastpart.geometry.end + 1
    sectorsize = device.sectorSize
    lastbyte = lastsector * sectorsize

    logging.debug("Total Size: %s", str(lastbyte))

    if os.path.isfile(args.dest):
        if not yes_or_no("File: '%s' already exists. Overwrite?", args.dest):
            print("Operation aborted.")
            raise SystemExit

    if not args.no_shrink: lastbyte = shrinkfs(lastpart, args.free)

    if not args.no_copy: docopy(args.src, args.dest, lastbyte, args.buffer_size)


def deploy(args):
    """Deploys the disk image at args.src to the block device args.dest"""
    lastbyte = os.path.getsize(args.src)

    logging.debug("Total Size: %s", str(lastbyte))

    docopy(args.src, args.dest, lastbyte, args.buffer_size)


def shrinkfs(part, minfree):
    """Shrink the filesystem and partition of part, then return the new last byte of the partition"""
    try:
        fs = part.fileSystem.type
    except AttributeError:
        raise TypeError("must be type 'parted.partition.Partition'")

    supported_filesystems = ['ext4']
    assert part.fileSystem.type in supported_filesystems, "Filesystem type '%s' not supported for resize operation" % part.fileSystem.type

    minfree = human2bytes(minfree)

    if (part.fileSystem.type == 'ext4'):
        print("Determining if filesystem needs to shrink...")
        
        # Parse the output of resize2fs and dumpe2fs to get info about the unmounted filesystem
        resize_output = subprocess.run(['resize2fs', '-P', part.path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='utf8').stdout
        dump_output = subprocess.run(['dumpe2fs', '-h', part.path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, encoding='utf8').stdout

        fs_blocksize = int(dump_output.splitlines()[17].split()[-1])
        fs_cursize = int(dump_output.splitlines()[12].split()[-1]) * fs_blocksize
        fs_minsize = int(resize_output.split()[-1]) * fs_blocksize
        shrink_to = fs_minsize + minfree
        
        if fs_cursize <= shrink_to:
            print('%s does not need resize. Current size is less than or equal to target size.')
            return (part.geometry.end + 1) * part.disk.device.sectorSize

        print("Partition needs resize. Resizing to %s bytes...", str(shrink_to))
        
        print('Running `e2fsck -f %s`...', part.path)
        fsck_run = subprocess.Popen(['e2fsck', '-f', part.path], encoding='utf8', stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        logging.debug(fsck_run.stdout)
        logging.debug(fsck_run.stderr)
        
        print('Shrinking %s to %s blocks...', part.path, str(chrink_to / fs_blocksize))
        resize_run = subprocess.Popen(['resize2fs', part.path, str(shrink_to / fs_blocksize)], encoding='utf8', stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        logging.debug(resize_run.stdout)
        logging.debug(resize_run.stderr)

        return shrinkpart(part, shrink_to)
    

def shrinkpart(part, size):
    dsk = part.disk
    dev = dsk.device
    print('Resizing partition...')
    # Create a new geometry
    newgeo = parted.Geometry(
            start=part.geometry.start,
            length=parted.sizeToSectors(shrink_to, 'B', dev.sectorSize),
            device=dev)
    logging.DEBUG(newgeo.__str__())
    # Create a new partition with our new geometry
    newpart = parted.Partition(
            disk=dsk, 
            type=parted.PARTITION_NORMAL,
            geometry=newgeo)
    # Create a constraint that aligns our new geometry with the optimal alignment of the disk
    constraint = parted.Constraint( maxGeom=newgeo).intersect(dev.optimalAlignedConstraint)
    dsk.deletePartition(part)
    dsk.addPartition(partition=newpart, constraint=constraint)
    try:
        dsk.commit()
    except:
        pass

    return (newgeo.end + 1) * dev.sectorSize


def docopy(src, dest, lastbyte, buffer_size):
    """Copy src to dest from beginning to lastbyte in chunks of buffer_size bytes"""
    logging.debug("opening %s", dest)
    with open(dest, 'wb') as destfile:
        logging.debug("opening %s", src)
        with open(src, 'rb') as srcfile:
            for startbyte in trange(0, lastbyte, buffer_size):
                endbyte = min(lastbyte, startbyte + buffer_size)
                srcfile.seek(startbyte)
                destfile.write(srcfile.read(buffer_size))
            logging.debug("closing %s", src)
        logging.debug("closing %s", dest)


def yes_or_no(question, *args):
    """Ask the user a yes or no question, return boolean. Default True if no input"""
    question = question % args
    reply = input(question+' (Y/n): ')
    if not reply:
        return True
    response = str(reply.lower().strip())
    if response in ['y', 'yes']:
        return True
    if response in ['n', 'no']:
        return False
    else:
        print("Unknown input: '%s'.", reply)
        return yes_or_no(question)

# Set up argument parsing
parser = argparse.ArgumentParser(description='Capture or Deploy images to sdcards')
parser.add_argument('-b', '--buffer-size', metavar='SIZE', type=human2bytes, default='512K', 
                    help="Use a transfer buffer of size SIZE. Accepts suffixes of B, K, M, or G.")
parser.add_argument('-v', '--verbose', action="store_true",
                    help="Enable verbose logging")
subparsers = parser.add_subparsers(help='sub-command help')

# Capture mode args
parser_cap = subparsers.add_parser('capture', help='capture help')
parser_cap.add_argument('src', help="Source disk", type=is_blockdev)
parser_cap.add_argument('dest', help="Destination file")
parser_cap.add_argument('--no-copy', action="store_true", default=False, 
                    help="Don't copy to dest.")
parser_cap.add_argument('--no-shrink', action="store_true", default=False, 
                    help="Skip the filesystem shrinking step.")
parser_cap.add_argument('-f', '--free', metavar='SIZE', default='500M', 
                    help="Shrink last partition filesystem to include a minimum of SIZE free space. Accepts suffixes of B, K, M, or G.")
parser_cap.set_defaults(func=capture)

# Deploy mode args
parser_dep = subparsers.add_parser('deploy', help='deploy help')
parser_dep.add_argument('src', help="Source file")
parser_dep.add_argument('dest', help="Destination disk", type=is_blockdev)
parser_dep.set_defaults(func=deploy)

args = parser.parse_args()
if args.verbose:
    logging.basicConfig(level=logging.DEBUG)


logging.debug("Source: %s", args.src)
logging.debug("Destination: %s", args.dest)
logging.debug("Buffer Size: %s", str(args.buffer_size))

args.func(args)

print("Operation completed. Syncing filesystems...")
os.sync()
print("Done.")
