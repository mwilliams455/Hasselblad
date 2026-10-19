#!/usr/bin/env python3
"""Import only the reviewed Native1A app; never build or run imported code.

Normal use reads sync/native1a-import.json and installs HasselbladPhoton/.
--archive accepts the retained local tarball; --verify-only reconstructs and
checks without installing. --verify-index checks the actual staged Git blobs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request


EXPECTED = {
    "schema_version": 1,
    "checkpoint": "Native1A",
    "upstream_commit": "b2eff821a858033515eb2700e7292befecc95225",
    "archive_url": "https://codeload.github.com/eszdman/PhotonCamera/tar.gz/b2eff821a858033515eb2700e7292befecc95225",
    "archive_sha256": "26396340dca501c5161bb843331c50eddab5810e6891bf40b5e5565d8fae5cf8",
    "archive_bytes": 78893630,
    "archive_root": "PhotonCamera-b2eff821a858033515eb2700e7292befecc95225",
    "patch_path": "build_evidence/Native1A_full_source.patch",
    "patch_sha256": "7b4d049a016a95c5b67e3ceb5fa6e0b0e87f59f6e8c9c38a96a76b78a5976f8e",
    "inventory_path": "build_evidence/native1a_source_changes.json",
    "inventory_sha256": "275273792cafd06bcc4b00a8752e10e2b33b5e2927857642d38d872e0b22e5ae",
    "destination": "HasselbladPhoton",
    "expected_source_files": 1092,
}
OMITTED_UPSTREAM_FILES = {
    ".idea/AndroidProjectSystem.xml",
    ".idea/deploymentTargetSelector.xml",
    ".idea/kotlinc.xml",
    ".idea/migrations.xml",
    ".idea/misc.xml",
    ".idea/runConfigurations.xml",
}
EXECUTABLE_FILES = {"gradlew"}
CHUNK = 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def relative_path(value):
    require(isinstance(value, str) and value, "Expected a nonempty relative path")
    require("\\" not in value and not any(ord(c) < 32 for c in value),
            "Unsupported path characters")
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(p not in ("", ".", "..") for p in value.split("/")),
            "Noncanonical or unsafe relative path: " + value)
    return path


def repository_file(root, name):
    path = root
    for part in relative_path(name).parts:
        path = path / part
        require(not path.is_symlink(), "Repository input contains a symlink: " + name)
    require(path.is_file(), "Missing repository input: " + name)
    return path


def digest(path):
    require(stat.S_ISREG(path.lstat().st_mode), "Expected a regular file: " + str(path))
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inputs(root, manifest_name):
    manifest = json.loads(repository_file(root, manifest_name).read_text())
    require(manifest == EXPECTED, "Import manifest differs from the reviewed Native1A pins")
    patch = repository_file(root, EXPECTED["patch_path"])
    inventory_path = repository_file(root, EXPECTED["inventory_path"])
    require(digest(patch) == EXPECTED["patch_sha256"], "Full source patch SHA-256 mismatch")
    require(digest(inventory_path) == EXPECTED["inventory_sha256"], "Source inventory SHA-256 mismatch")
    inventory = json.loads(inventory_path.read_text())
    require(inventory["checkpoint"] == "Native1A"
            and inventory["upstream_commit"] == EXPECTED["upstream_commit"]
            and inventory["source_file_count"] == EXPECTED["expected_source_files"],
            "Unexpected source inventory identity")
    expected_files = inventory["all_source_sha256"]
    require(isinstance(expected_files, dict) and len(expected_files) == 1092,
            "Expected exactly 1,092 source files")
    for name, checksum in expected_files.items():
        relative_path(name)
        require(re.fullmatch(r"[0-9a-f]{64}", checksum) is not None,
                "Invalid inventory checksum for " + name)
    return patch, expected_files


def verify_tree(root, expected_files):
    require(root.is_dir() and not root.is_symlink(), "Source root must be a real directory")
    found = set()
    expected_dirs = set()
    for name in expected_files:
        expected_dirs.update(str(p) for p in PurePosixPath(name).parents if str(p) != ".")
    for directory, subdirs, names in os.walk(root, followlinks=False):
        for entry in subdirs:
            path = Path(directory) / entry
            relative = path.relative_to(root).as_posix()
            require(stat.S_ISDIR(path.lstat().st_mode) and relative in expected_dirs,
                    "Unexpected source directory or link: " + relative)
        for entry in names:
            path = Path(directory) / entry
            relative = path.relative_to(root).as_posix()
            mode = path.lstat().st_mode
            require(stat.S_ISREG(mode) and not mode & 0o7000,
                    "Nonregular source file or special mode: " + relative)
            require(relative in expected_files, "Unexpected source file: " + relative)
            require(bool(mode & 0o111) == (relative in EXECUTABLE_FILES),
                    "Unexpected source executable mode: " + relative)
            require(digest(path) == expected_files[relative], "Source SHA-256 mismatch: " + relative)
            found.add(relative)
    require(found == set(expected_files),
            "Missing source files: " + ", ".join(sorted(set(expected_files) - found)))


def download_archive(destination):
    request = urllib.request.Request(EXPECTED["archive_url"],
                                     headers={"User-Agent": "Hasselblad-Native1A-import"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("xb") as output:
        require(response.geturl().startswith("https://codeload.github.com/"),
                "Unexpected archive download redirect")
        total = 0
        while chunk := response.read(CHUNK):
            total += len(chunk)
            require(total <= EXPECTED["archive_bytes"], "Archive exceeds pinned byte count")
            output.write(chunk)


def extract_archive(archive, source):
    require(archive.stat().st_size == EXPECTED["archive_bytes"], "Archive byte-count mismatch")
    require(digest(archive) == EXPECTED["archive_sha256"], "Archive SHA-256 mismatch")
    source.mkdir()
    seen = set()
    file_count = 0
    total_bytes = 0
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = member.name[:-1] if member.isdir() and member.name.endswith("/") else member.name
            path = relative_path(name)
            require(path.parts[0] == EXPECTED["archive_root"], "Unexpected archive root")
            require(name not in seen, "Duplicate archive path: " + name)
            seen.add(name)
            require(len(seen) <= 4096, "Too many archive entries")
            require(member.isdir() or member.isfile(),
                    "Archive links and special entries are not allowed: " + name)
            require(not member.issparse() and not member.mode & 0o7000,
                    "Sparse files or special file modes are not allowed")
            if len(path.parts) == 1:
                require(member.isdir(), "Archive root is not a directory")
                continue
            target = source.joinpath(*path.parts[1:])
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            require(0 <= member.size <= 128 * 1024 * 1024, "Invalid archive file size")
            file_count += 1
            total_bytes += member.size
            require(total_bytes <= 512 * 1024 * 1024, "Archive expands beyond the import bound")
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = tar.extractfile(member)
            require(stream is not None, "Missing regular-file contents")
            with stream, target.open("xb") as output:
                shutil.copyfileobj(stream, output, CHUNK)
            require(target.stat().st_size == member.size, "Truncated archive file")
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    require(file_count == 1073 and total_bytes == 239056450, "Pinned archive layout mismatch")
    # These six IDE files were omitted from the reviewed source bundle. Do not
    # broadly ignore directories: every remaining source path must match.
    for name in sorted(OMITTED_UPSTREAM_FILES):
        (source / name).unlink()
    (source / ".idea").rmdir()


def verify_index(root, expected_files):
    prefix = EXPECTED["destination"] + "/"
    entries = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z", "--", prefix], cwd=root).split(b"\0")
    indexed = {}
    for entry in entries:
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        name = raw_name.decode("utf-8")
        require(name.startswith(prefix), "Unexpected staged path")
        relative = name[len(prefix):]
        require(relative in expected_files and relative not in indexed and stage == "0",
                "Unexpected, duplicate or unmerged staged source: " + relative)
        require(mode == ("100755" if relative in EXECUTABLE_FILES else "100644"),
                "Staged source mode mismatch: " + relative)
        indexed[relative] = object_id
    require(set(indexed) == set(expected_files), "Staged source file set differs from inventory")
    process = subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for name in sorted(indexed):
            object_id = indexed[name]
            process.stdin.write((object_id + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split()
            require(len(header) == 3 and header[:2] == [object_id, "blob"],
                    "Cannot read staged source blob: " + name)
            remaining = int(header[2])
            require(0 <= remaining <= 128 * 1024 * 1024, "Unexpected staged blob size")
            checksum = hashlib.sha256()
            while remaining:
                chunk = process.stdout.read(min(remaining, CHUNK))
                require(bool(chunk), "Truncated staged blob")
                checksum.update(chunk)
                remaining -= len(chunk)
            require(process.stdout.read(1) == b"\n", "Invalid Git batch response")
            require(checksum.hexdigest() == expected_files[name],
                    "Staged blob differs from reviewed source: " + name)
        process.stdin.close()
        require(process.wait() == 0, "Git staged-blob reader failed")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="sync/native1a-import.json")
    parser.add_argument("--archive", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true")
    mode.add_argument("--verify-index", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    patch, expected_files = inputs(root, args.manifest)
    if args.verify_index:
        require(args.archive is None, "--archive does not apply to staged-index verification")
        verify_index(root, expected_files)
        print(json.dumps({"result": "pass", "mode": "staged-index", "files": len(expected_files)}))
        return
    destination = root / EXPECTED["destination"]
    existed = os.path.lexists(destination)
    if existed:
        verify_tree(destination, expected_files)
    with tempfile.TemporaryDirectory(prefix="hasselblad-native1a-import-") as temp_name:
        temp = Path(temp_name)
        archive = args.archive.resolve() if args.archive else temp / "upstream.tar.gz"
        if args.archive is None:
            download_archive(archive)
        source = temp / "source"
        extract_archive(archive, source)
        # Stay outside the checkout even if a caller places TMPDIR within it.
        apply_env = os.environ.copy()
        for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            apply_env.pop(key, None)
        apply_env.update(GIT_CEILING_DIRECTORIES=str(temp),
                         GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        subprocess.run(["git", "apply", "--check", "--", str(patch)],
                       cwd=source, env=apply_env, check=True)
        subprocess.run(["git", "apply", "--whitespace=nowarn", "--", str(patch)],
                       cwd=source, env=apply_env, check=True)
        verify_tree(source, expected_files)
        status = "already-identical" if existed else "verified-without-install"
        if not args.verify_only:
            if os.path.lexists(destination):
                verify_tree(destination, expected_files)
                status = "already-identical"
            else:
                # copytree creates the destination exclusively; it refuses an
                # existing directory instead of replacing any user's tree.
                shutil.copytree(source, destination)
                verify_tree(destination, expected_files)
                status = "installed"
    print(json.dumps({"result": "pass", "mode": "verify-only" if args.verify_only else "import",
                      "destination": EXPECTED["destination"], "status": status,
                      "files": len(expected_files), "archive_sha256": EXPECTED["archive_sha256"],
                      "patch_sha256": EXPECTED["patch_sha256"]}))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.CalledProcessError) as error:
        print("Native1A import refused: " + str(error), file=sys.stderr)
        raise SystemExit(1)
